import argparse
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


METRIC_NAMES = [
    "route_accuracy",
    "tool_accuracy",
    "skill_hit_rate",
    "resource_hit_rate",
    "memory_hit_rate",
    "task_created_rate",
    "trace_completeness",
]


def run_eval(cases_path=None, reports_dir=None, max_cases=None):
    cases_path = Path(cases_path or Path(__file__).with_name("eval_cases.json"))
    reports_dir = Path(reports_dir or Path(__file__).with_name("reports"))
    reports_dir.mkdir(parents=True, exist_ok=True)

    previous_env = _push_real_api_env()
    try:
        cases = json.loads(cases_path.read_text(encoding="utf-8"))
        if max_cases:
            cases = cases[: int(max_cases)]
        report = _run_cases(cases, reports_dir)
        _write_reports(report, reports_dir)
        return report
    finally:
        _restore_env(previous_env)


def _run_cases(cases, reports_dir):
    from agent import llm_client
    from agent.memory_core import MemoryCore
    from agent_graph.graph import GraphCore
    from agent_graph import task_runtime
    from agent_graph import task_scheduler
    from agent_graph.nodes import memory_node as memory_node_module

    llm_client.CALL_SOURCES.clear()
    tmp_path = reports_dir / f"runtime_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    task_runtime.TASK_STORE_PATH = tmp_path / "tasks.json"
    task_scheduler.TASK_STORE_PATH = tmp_path / "tasks.json"
    task_scheduler.SCHEDULER_STATE_PATH = tmp_path / "task_scheduler.json"
    memory_core = MemoryCore(tmp_path / "memory")
    original_memory_core = memory_node_module.MemoryCore
    memory_node_module.MemoryCore = lambda: memory_core
    try:
        results = []
        for case in cases:
            _seed_memories(memory_core, case.get("setup_memories", []))
            response = GraphCore().chat(case["message"], session_id=f"eval-{case['id']}")
            results.append(_case_result(case, response))
    finally:
        memory_node_module.MemoryCore = original_memory_core
        shutil.rmtree(tmp_path, ignore_errors=True)

    metrics = _metrics(results)
    fallback_sources = [item for item in llm_client.CALL_SOURCES if item.get("source") != "real_api"]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(results),
        "real_api": bool(llm_client.CALL_SOURCES) and not fallback_sources,
        "fallback_count": len(fallback_sources),
        "llm_call_sources": llm_client.CALL_SOURCES,
        "metrics": metrics,
        "cases": results,
    }


def _push_real_api_env():
    keys = ["DISABLE_DOTENV_LOAD", "LLM_DISABLE_FALLBACK", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"]
    previous = {key: os.environ.get(key) for key in keys}
    os.environ["DISABLE_DOTENV_LOAD"] = "0"
    _load_backend_env()
    os.environ["LLM_DISABLE_FALLBACK"] = "1"
    if not os.getenv("LLM_API_KEY", "").strip():
        raise RuntimeError("LLM_API_KEY is required for real API eval")
    return previous


def _restore_env(previous):
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _load_backend_env():
    env_path = BACKEND_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def _seed_memories(memory_core, memories):
    for memory in memories or []:
        content = memory.get("content", "")
        if not content:
            continue
        existing = [item for item in memory_core.list_memories() if item.get("content") == content]
        if existing:
            continue
        memory_core.write_memory(
            content,
            memory.get("category", "preference"),
            memory.get("importance", 0.8),
            source="eval_setup",
        )


def _case_result(case, response):
    actual_route = (response.get("planner_result") or {}).get("route", "response")
    actual_tool = response.get("tool_used") or "none"
    active_skills = response.get("active_skills") or []
    resources = response.get("skill_resource_results") or []
    memories = response.get("retrieved_memories") or []
    task = response.get("task") or {}
    trace_complete = all(key in response and isinstance(response.get(key), list) for key in ["agent_flow", "tool_trace", "skill_trace"])
    return {
        "id": case.get("id"),
        "question": case.get("message"),
        "reply": response.get("reply", ""),
        "expected": {
            "route": case.get("expected_route"),
            "tool": case.get("expected_tool", "none"),
            "skill": bool(case.get("expect_skill")),
            "resource": bool(case.get("expect_resource")),
            "memory": bool(case.get("expect_memory")),
            "task": bool(case.get("expect_task", True)),
            "trace": bool(case.get("expect_trace", True)),
        },
        "actual": {
            "route": actual_route,
            "tool": actual_tool,
            "skill": bool(active_skills),
            "resource": bool(resources),
            "memory": bool(memories),
            "task": bool(task.get("task_id")),
            "trace": trace_complete,
        },
        "planner_result": response.get("planner_result", {}),
        "tool_trace": response.get("tool_trace", []),
        "agent_flow": response.get("agent_flow", []),
        "skill_trace": response.get("skill_trace", []),
        "active_skills": active_skills,
        "skill_resource_results": resources,
        "retrieved_memories": memories,
    }


def _metrics(results):
    return {
        "route_accuracy": _rate(results, lambda item: item["actual"]["route"] == item["expected"]["route"]),
        "tool_accuracy": _rate(results, lambda item: item["actual"]["tool"] == item["expected"]["tool"]),
        "skill_hit_rate": _expected_rate(results, "skill"),
        "resource_hit_rate": _expected_rate(results, "resource"),
        "memory_hit_rate": _expected_rate(results, "memory"),
        "task_created_rate": _expected_rate(results, "task"),
        "trace_completeness": _expected_rate(results, "trace"),
    }


def _rate(items, predicate):
    if not items:
        return 0.0
    return round(sum(1 for item in items if predicate(item)) / len(items), 4)


def _expected_rate(items, key):
    expected = [item for item in items if item["expected"][key]]
    if not expected:
        return 1.0
    return _rate(expected, lambda item: item["actual"][key])


def _write_reports(report, reports_dir):
    (reports_dir / "eval_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# V-Agent Real API Eval Report",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Cases: `{report['case_count']}`",
        f"- Real API only: `{report['real_api']}`",
        f"- Fallback count: `{report['fallback_count']}`",
        "",
        "## Metrics",
        "",
    ]
    for name in METRIC_NAMES:
        lines.append(f"- `{name}`: `{report['metrics'].get(name)}`")
    lines.extend(["", "## Cases", ""])
    for case in report["cases"]:
        lines.extend(
            [
                f"### {case['id']}",
                "",
                f"- Question: {case['question']}",
                f"- Reply: {case['reply']}",
                f"- Expected route/tool: `{case['expected']['route']}` / `{case['expected']['tool']}`",
                f"- Actual route/tool: `{case['actual']['route']}` / `{case['actual']['tool']}`",
                f"- Skill/resource/memory/task/trace: `{case['actual']['skill']}` / `{case['actual']['resource']}` / `{case['actual']['memory']}` / `{case['actual']['task']}` / `{case['actual']['trace']}`",
                "",
            ]
        )
    (reports_dir / "eval_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Run V-Agent real API eval cases.")
    parser.add_argument("--cases", default=str(Path(__file__).with_name("eval_cases.json")))
    parser.add_argument("--reports-dir", default=str(Path(__file__).with_name("reports")))
    parser.add_argument("--max-cases", type=int, default=None)
    args = parser.parse_args()
    report = run_eval(args.cases, args.reports_dir, args.max_cases)
    print(json.dumps({"metrics": report["metrics"], "fallback_count": report["fallback_count"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
