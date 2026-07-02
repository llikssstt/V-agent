import uuid
import time
import json
from pathlib import Path

from fastapi.testclient import TestClient

from agent_graph.graph import GraphCore
from main import app
from tools import registry as tool_registry


def local_tmp_path():
    path = Path(__file__).resolve().parents[2] / ".pytest_tmp" / "task_runtime" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def patch_task_store(monkeypatch, tmp_path):
    from agent_graph import task_runtime
    from agent_graph import task_scheduler

    monkeypatch.setattr(task_runtime, "TASK_STORE_PATH", tmp_path / "tasks.json")
    monkeypatch.setattr(task_scheduler, "TASK_STORE_PATH", tmp_path / "tasks.json")
    monkeypatch.setattr(task_scheduler, "SCHEDULER_STATE_PATH", tmp_path / "task_scheduler.json")
    return task_runtime


def test_task_runtime_creates_task_with_steps_and_logs(monkeypatch):
    tmp_path = local_tmp_path()
    task_runtime = patch_task_store(monkeypatch, tmp_path)
    runtime = task_runtime.TaskRuntime()

    task = runtime.create_task("Build a report", session_id="s1")
    runtime.set_plan(task["task_id"], [{"title": "Draft", "status": "pending"}], {"name": "none", "arguments": {}})
    runtime.append_step(task["task_id"], "planner", "completed", "structured plan ready")
    runtime.add_artifact(task["task_id"], "note", {"text": "done"})
    runtime.finish_task(task["task_id"], "completed")

    loaded = runtime.get_task(task["task_id"])
    assert loaded["status"] == "completed"
    assert loaded["steps"][0]["title"] == "Draft"
    assert loaded["logs"][-1]["event"] == "status"
    assert loaded["artifacts"][0]["type"] == "note"


def test_graphcore_returns_task_and_planner_fields(monkeypatch):
    tmp_path = local_tmp_path()
    patch_task_store(monkeypatch, tmp_path)

    result = GraphCore().chat("What is 2 + 3?", "task-graph")

    assert result["task"]["status"] in {"running", "completed"}
    assert result["task"]["steps"]
    assert result["planner_result"]["tool_intent"]["name"] == "calculator"
    assert any(step["agent_name"] == "Planner Agent" for step in result["agent_flow"])


def test_graphcore_uses_llm_planner_json_for_task_and_tool_intent(monkeypatch):
    tmp_path = local_tmp_path()
    patch_task_store(monkeypatch, tmp_path)
    from agent_graph.nodes import planner_node

    calls = []

    class FakeLLM:
        def complete_json(self, prompt, stage, context):
            calls.append({"prompt": prompt, "stage": stage, "context": context})
            return json.dumps(
                {
                    "task_title": "Research current Python release",
                    "route": "execute_tool",
                    "reason": "Need fresh release information",
                    "steps": [
                        {
                            "title": "Search current Python release",
                            "tool_intent": {"name": "web_search", "arguments": {"query": "latest Python release", "max_results": 3}},
                        },
                        {"title": "Summarize result", "tool_intent": {"name": "none", "arguments": {}}},
                    ],
                    "tool_intent": {"name": "none", "arguments": {}},
                }
            )

    def fake_execute(tool_call):
        return {
            "ok": True,
            "tool": tool_call["name"],
            "result": {"results": [{"title": "Python 3.x", "url": "https://python.org", "snippet": "release notes"}]},
        }

    monkeypatch.setattr(planner_node, "LLMClient", lambda: FakeLLM())
    monkeypatch.setattr(tool_registry, "execute_tool", fake_execute)

    result = GraphCore().chat("Find the latest Python release", "llm-planner")

    assert calls
    assert calls[0]["stage"] == "graph_planner"
    assert "strict JSON" in calls[0]["prompt"]
    assert result["planner_result"]["task_title"] == "Research current Python release"
    assert result["planner_result"]["reason"] == "Need fresh release information"
    assert result["planner_result"]["tool_intent"]["name"] == "web_search"
    assert result["task"]["title"] == "Research current Python release"
    assert result["task"]["steps"][0]["title"] == "Search current Python release"
    assert result["task"]["steps"][0]["tool_intent"]["name"] == "web_search"
    assert result["task"]["steps"][1]["tool_intent"]["name"] == "none"
    assert any(entry["tool_call"]["name"] == "web_search" for entry in result["tool_trace"])


def test_task_runtime_persists_step_level_tool_intent(monkeypatch):
    tmp_path = local_tmp_path()
    task_runtime = patch_task_store(monkeypatch, tmp_path)
    runtime = task_runtime.TaskRuntime()
    task = runtime.create_task("Step tools", session_id="step-tools")

    runtime.set_plan(
        task["task_id"],
        [
            {"title": "Search", "tool_intent": {"name": "web_search", "arguments": {"query": "python"}}},
            {"title": "Calculate", "tool_intent": {"name": "calculator", "arguments": {"expression": "1 + 2"}}},
        ],
        {"name": "none", "arguments": {}},
    )

    loaded = runtime.get_task(task["task_id"])
    assert loaded["steps"][0]["tool_intent"] == {"name": "web_search", "arguments": {"query": "python"}}
    assert loaded["steps"][1]["tool_intent"] == {"name": "calculator", "arguments": {"expression": "1 + 2"}}


def test_llm_planner_unknown_tool_routes_to_tool_search(monkeypatch):
    tmp_path = local_tmp_path()
    patch_task_store(monkeypatch, tmp_path)
    from agent_graph.nodes import planner_node

    class FakeLLM:
        def complete_json(self, prompt, stage, context):
            return json.dumps(
                {
                    "task_title": "Use unavailable tool",
                    "route": "execute_tool",
                    "reason": "LLM selected a tool that is not installed",
                    "steps": [{"title": "Try unavailable tool"}],
                    "tool_intent": {"name": "does_not_exist", "arguments": {"query": "x"}},
                }
            )

    monkeypatch.setattr(planner_node, "LLMClient", lambda: FakeLLM())

    result = GraphCore().chat("Use a special unavailable tool", "llm-unknown-tool")

    assert result["planner_result"]["route"] == "tool_search"
    assert result["planner_result"]["tool_intent"]["name"] == "none"
    assert "does_not_exist" in result["planner_result"]["reason"]
    assert not any(entry.get("tool_call", {}).get("name") == "does_not_exist" for entry in result["tool_trace"])


def test_llm_planner_allows_enabled_installed_tool_intent(monkeypatch):
    tmp_path = local_tmp_path()
    patch_task_store(monkeypatch, tmp_path)
    from agent_graph.nodes import planner_node
    from agent_graph import tool_intent_runner

    class FakeLLM:
        def complete_json(self, prompt, stage, context):
            return json.dumps(
                {
                    "task_title": "Read page using installed web reader",
                    "route": "execute_tool",
                    "reason": "Installed web_reader can fetch the page",
                    "steps": [{"title": "Run installed web_reader"}],
                    "tool_intent": {"name": "web_reader.fetch_page", "arguments": {"url": "https://example.com"}},
                }
            )

    class FakeToolManager:
        def list_installed_tools(self):
            return [
                {
                    "tool_id": "web_reader",
                    "enabled": True,
                    "tools": [{"name": "fetch_page"}],
                }
            ]

    def fake_run_tool_intent(tool_call):
        return {"ok": True, "tool": tool_call["name"], "result": {"title": "Example", "url": "https://example.com", "content": "ok"}}

    monkeypatch.setattr(planner_node, "LLMClient", lambda: FakeLLM())
    monkeypatch.setattr(planner_node, "ToolManager", FakeToolManager)
    monkeypatch.setattr(tool_intent_runner, "run_installed_tool", lambda tool_id, tool_name, args: fake_run_tool_intent({"name": f"{tool_id}.{tool_name}", "arguments": args}))

    result = GraphCore().chat("Use web_reader on https://example.com", "llm-installed-tool")

    assert result["planner_result"]["route"] == "execute_tool"
    assert result["planner_result"]["tool_intent"]["name"] == "web_reader.fetch_page"
    assert any(entry["tool_call"]["name"] == "web_reader.fetch_page" for entry in result["tool_trace"])


def test_execution_node_uses_generic_tool_intent(monkeypatch):
    tmp_path = local_tmp_path()
    patch_task_store(monkeypatch, tmp_path)
    calls = []

    def fake_execute(tool_call):
        calls.append(tool_call)
        return {"ok": True, "tool": tool_call["name"], "result": {"value": 5}}

    monkeypatch.setattr(tool_registry, "execute_tool", fake_execute)

    result = GraphCore().chat("What is 2 + 3?", "generic-tool")

    assert calls == [{"name": "calculator", "arguments": {"expression": "2 + 3"}}]
    assert result["tool_trace"][0]["tool_call"]["name"] == "calculator"
    assert result["task"]["artifacts"][0]["type"] == "tool_result"


def test_tasks_api_lists_and_reads_tasks(monkeypatch):
    tmp_path = local_tmp_path()
    patch_task_store(monkeypatch, tmp_path)
    client = TestClient(app)

    chat_response = client.post("/chat", json={"message": "What is 2 + 3?", "session_id": "task-api"})
    assert chat_response.status_code == 200
    task_id = chat_response.json()["task"]["task_id"]

    list_response = client.get("/tasks")
    detail_response = client.get(f"/tasks/{task_id}")

    assert list_response.status_code == 200
    assert any(task["task_id"] == task_id for task in list_response.json()["tasks"])
    assert detail_response.status_code == 200
    assert detail_response.json()["task_id"] == task_id


def test_task_runtime_can_mark_next_pending_step(monkeypatch):
    tmp_path = local_tmp_path()
    task_runtime = patch_task_store(monkeypatch, tmp_path)
    runtime = task_runtime.TaskRuntime()
    task = runtime.create_task("Long task", session_id="s1")
    runtime.set_plan(
        task["task_id"],
        [{"title": "First"}, {"title": "Second"}],
        {"name": "none", "arguments": {}},
    )

    step = runtime.next_pending_step(task["task_id"])
    runtime.update_step_status(task["task_id"], step["step_id"], "completed", "first done")

    loaded = runtime.get_task(task["task_id"])
    assert loaded["steps"][0]["status"] == "completed"
    assert loaded["steps"][0]["detail"] == "first done"
    assert loaded["steps"][1]["status"] == "pending"
    assert loaded["logs"][-1]["event"] == "step_status"


def test_run_next_task_step_api_executes_step_tool_intent_once(monkeypatch):
    tmp_path = local_tmp_path()
    task_runtime = patch_task_store(monkeypatch, tmp_path)
    calls = []

    def fake_execute(tool_call):
        calls.append(tool_call)
        return {"ok": True, "tool": tool_call["name"], "result": {"value": 5}}

    monkeypatch.setattr(tool_registry, "execute_tool", fake_execute)
    runtime = task_runtime.TaskRuntime()
    task = runtime.create_task("Calculate", session_id="task-run-next")
    runtime.set_plan(
        task["task_id"],
        [{"title": "Run calculator", "tool_intent": {"name": "calculator", "arguments": {"expression": "2 + 3"}}}],
        {"name": "web_search", "arguments": {"query": "fallback should not run"}},
    )
    client = TestClient(app)
    run_response = client.post(f"/tasks/{task['task_id']}/run-next")

    assert run_response.status_code == 200
    task = run_response.json()["task"]
    assert calls == [{"name": "calculator", "arguments": {"expression": "2 + 3"}}]
    artifact = task["artifacts"][0]
    assert artifact["type"] == "tool_result"
    assert artifact["payload"]["step_id"] == "step_1"
    assert artifact["payload"]["step_title"] == "Run calculator"
    assert artifact["payload"]["step_tool_intent"] == {"name": "calculator", "arguments": {"expression": "2 + 3"}}
    assert artifact["payload"]["tool_result"]["result"] == {"value": 5}
    assert any(step["status"] == "completed" for step in task["steps"])


def test_run_task_step_falls_back_to_task_tool_intent_for_legacy_steps(monkeypatch):
    tmp_path = local_tmp_path()
    task_runtime = patch_task_store(monkeypatch, tmp_path)
    calls = []

    def fake_execute(tool_call):
        calls.append(tool_call)
        return {"ok": True, "tool": tool_call["name"], "result": {"value": 5}}

    monkeypatch.setattr(tool_registry, "execute_tool", fake_execute)
    runtime = task_runtime.TaskRuntime()
    task = runtime.create_task("Legacy task", session_id="task-legacy")
    runtime.set_plan(
        task["task_id"],
        [{"title": "Legacy step"}],
        {"name": "calculator", "arguments": {"expression": "2 + 3"}},
    )
    task = runtime.get_task(task["task_id"])
    task["steps"][0].pop("tool_intent", None)
    task_runtime.TASK_STORE_PATH.write_text(json.dumps({"tasks": {task["task_id"]: task}}, ensure_ascii=False), encoding="utf-8")

    client = TestClient(app)
    run_response = client.post(f"/tasks/{task['task_id']}/run-next")

    assert run_response.status_code == 200
    assert calls == [{"name": "calculator", "arguments": {"expression": "2 + 3"}}]


def test_run_task_step_does_not_fallback_when_step_tool_intent_is_explicit_none(monkeypatch):
    tmp_path = local_tmp_path()
    task_runtime = patch_task_store(monkeypatch, tmp_path)
    calls = []

    def fake_execute(tool_call):
        calls.append(tool_call)
        return {"ok": True, "tool": tool_call["name"], "result": {}}

    monkeypatch.setattr(tool_registry, "execute_tool", fake_execute)
    runtime = task_runtime.TaskRuntime()
    task = runtime.create_task("Mixed task", session_id="task-explicit-none")
    runtime.set_plan(
        task["task_id"],
        [{"title": "Think first", "tool_intent": {"name": "none", "arguments": {}}}],
        {"name": "calculator", "arguments": {"expression": "2 + 3"}},
    )

    client = TestClient(app)
    run_response = client.post(f"/tasks/{task['task_id']}/run-next")

    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["ok"] is True
    assert calls == []
    assert payload["task"]["steps"][0]["status"] == "completed"
    assert payload["task"]["artifacts"][0]["payload"]["tool_result"]["tool"] == "none"


def test_run_task_until_idle_api_advances_multiple_steps(monkeypatch):
    tmp_path = local_tmp_path()
    task_runtime = patch_task_store(monkeypatch, tmp_path)
    calls = []

    def fake_execute(tool_call):
        calls.append(tool_call)
        return {"ok": True, "tool": tool_call["name"], "result": {"attempt": len(calls)}}

    monkeypatch.setattr(tool_registry, "execute_tool", fake_execute)
    runtime = task_runtime.TaskRuntime()
    task = runtime.create_task("Loop task", session_id="task-run-loop")
    runtime.set_plan(
        task["task_id"],
        [
            {"title": "Step one", "tool_intent": {"name": "calculator", "arguments": {"expression": "1 + 1"}}},
            {"title": "Step two", "tool_intent": {"name": "calculator", "arguments": {"expression": "2 + 2"}}},
            {"title": "Step three", "tool_intent": {"name": "calculator", "arguments": {"expression": "3 + 3"}}},
        ],
        {"name": "none", "arguments": {}},
    )
    client = TestClient(app)

    response = client.post(f"/tasks/{task['task_id']}/run-until-idle", json={"max_steps": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["iterations"] == 2
    assert calls == [
        {"name": "calculator", "arguments": {"expression": "1 + 1"}},
        {"name": "calculator", "arguments": {"expression": "2 + 2"}},
    ]
    assert payload["task"]["steps"][0]["status"] == "completed"
    assert payload["task"]["steps"][1]["status"] == "completed"
    assert payload["task"]["steps"][2]["status"] == "pending"
    assert payload["task"]["status"] == "running"


def test_task_lifecycle_pause_resume_and_cancel_api(monkeypatch):
    tmp_path = local_tmp_path()
    task_runtime = patch_task_store(monkeypatch, tmp_path)
    calls = []

    def fake_execute(tool_call):
        calls.append(tool_call)
        return {"ok": True, "tool": tool_call["name"], "result": {"attempt": len(calls)}}

    monkeypatch.setattr(tool_registry, "execute_tool", fake_execute)
    runtime = task_runtime.TaskRuntime()
    task = runtime.create_task("Lifecycle task", session_id="task-lifecycle")
    runtime.set_plan(
        task["task_id"],
        [
            {"title": "Step one", "tool_intent": {"name": "calculator", "arguments": {"expression": "2 + 3"}}},
            {"title": "Step two", "tool_intent": {"name": "calculator", "arguments": {"expression": "2 + 3"}}},
        ],
        {"name": "calculator", "arguments": {"expression": "2 + 3"}},
    )
    client = TestClient(app)

    pause_response = client.post(f"/tasks/{task['task_id']}/pause")
    blocked_response = client.post(f"/tasks/{task['task_id']}/run-next")
    resume_response = client.post(f"/tasks/{task['task_id']}/resume")
    run_response = client.post(f"/tasks/{task['task_id']}/run-next")
    cancel_response = client.post(f"/tasks/{task['task_id']}/cancel")
    cancelled_run_response = client.post(f"/tasks/{task['task_id']}/run-until-idle", json={"max_steps": 2})

    assert pause_response.status_code == 200
    assert pause_response.json()["task"]["status"] == "paused"
    assert blocked_response.status_code == 409
    assert "paused" in blocked_response.json()["detail"]
    assert resume_response.status_code == 200
    assert resume_response.json()["task"]["status"] == "running"
    assert run_response.status_code == 200
    assert len(calls) == 1
    assert cancel_response.status_code == 200
    cancelled = cancel_response.json()["task"]
    assert cancelled["status"] == "cancelled"
    assert cancelled["logs"][-1]["event"] == "status"
    assert cancelled["logs"][-1]["message"] == "cancelled"
    assert cancelled_run_response.status_code == 409
    assert "cancelled" in cancelled_run_response.json()["detail"]


def test_failed_step_can_be_retried_with_attempt_history(monkeypatch):
    tmp_path = local_tmp_path()
    task_runtime = patch_task_store(monkeypatch, tmp_path)
    calls = []

    def fake_execute(tool_call):
        calls.append(tool_call)
        if len(calls) == 1:
            return {"ok": False, "tool": tool_call["name"], "error": {"message": "temporary failure"}}
        return {"ok": True, "tool": tool_call["name"], "result": {"value": 5}}

    monkeypatch.setattr(tool_registry, "execute_tool", fake_execute)
    runtime = task_runtime.TaskRuntime()
    task = runtime.create_task("Retry task", session_id="task-retry")
    runtime.set_plan(
        task["task_id"],
        [{"title": "Run flaky calculator", "tool_intent": {"name": "calculator", "arguments": {"expression": "2 + 3"}}}],
        {"name": "calculator", "arguments": {"expression": "2 + 3"}},
    )
    client = TestClient(app)

    first_run = client.post(f"/tasks/{task['task_id']}/run-next")
    retry_response = client.post(f"/tasks/{task['task_id']}/steps/step_1/retry")
    second_run = client.post(f"/tasks/{task['task_id']}/run-next")

    assert first_run.status_code == 200
    assert first_run.json()["ok"] is False
    failed_task = first_run.json()["task"]
    assert failed_task["status"] == "failed"
    assert failed_task["steps"][0]["attempts"] == 1
    assert failed_task["steps"][0]["last_error"] == "temporary failure"
    assert retry_response.status_code == 200
    queued_task = retry_response.json()["task"]
    assert queued_task["status"] == "running"
    assert queued_task["steps"][0]["status"] == "pending"
    assert queued_task["steps"][0]["attempts"] == 1
    assert queued_task["logs"][-1]["event"] == "step_retry"
    assert second_run.status_code == 200
    completed_task = second_run.json()["task"]
    assert completed_task["status"] == "completed"
    assert completed_task["steps"][0]["status"] == "completed"
    assert completed_task["steps"][0]["attempts"] == 2
    assert len(calls) == 2


def test_task_scheduler_tick_advances_runnable_tasks_only(monkeypatch):
    tmp_path = local_tmp_path()
    task_runtime = patch_task_store(monkeypatch, tmp_path)
    calls = []

    def fake_execute(tool_call):
        calls.append(tool_call)
        return {"ok": True, "tool": tool_call["name"], "result": {"attempt": len(calls)}}

    monkeypatch.setattr(tool_registry, "execute_tool", fake_execute)
    runtime = task_runtime.TaskRuntime()
    active = runtime.create_task("Active scheduled task", session_id="scheduler")
    runtime.set_plan(
        active["task_id"],
        [
            {"title": "First active", "tool_intent": {"name": "calculator", "arguments": {"expression": "2 + 3"}}},
            {"title": "Second active", "tool_intent": {"name": "calculator", "arguments": {"expression": "2 + 3"}}},
        ],
        {"name": "calculator", "arguments": {"expression": "2 + 3"}},
    )
    paused = runtime.create_task("Paused scheduled task", session_id="scheduler")
    runtime.set_plan(
        paused["task_id"],
        [{"title": "Paused step", "tool_intent": {"name": "calculator", "arguments": {"expression": "4 + 4"}}}],
        {"name": "calculator", "arguments": {"expression": "4 + 4"}},
    )
    runtime.pause_task(paused["task_id"])
    client = TestClient(app)

    start_response = client.post("/tasks/scheduler/start", json={"max_steps_per_tick": 1})
    tick_response = client.post("/tasks/scheduler/tick")
    status_response = client.get("/tasks/scheduler")

    assert start_response.status_code == 200
    assert start_response.json()["scheduler"]["running"] is True
    assert tick_response.status_code == 200
    payload = tick_response.json()
    assert payload["ok"] is True
    assert payload["processed"] == 1
    assert payload["results"][0]["task"]["task_id"] == active["task_id"]
    assert len(calls) == 1
    active_after = client.get(f"/tasks/{active['task_id']}").json()
    paused_after = client.get(f"/tasks/{paused['task_id']}").json()
    assert active_after["steps"][0]["status"] == "completed"
    assert active_after["steps"][1]["status"] == "pending"
    assert paused_after["status"] == "paused"
    assert paused_after["steps"][0]["status"] == "pending"
    assert status_response.status_code == 200
    assert status_response.json()["scheduler"]["running"] is True


def test_task_scheduler_background_worker_advances_tasks_without_manual_tick(monkeypatch):
    tmp_path = local_tmp_path()
    task_runtime = patch_task_store(monkeypatch, tmp_path)
    calls = []

    def fake_execute(tool_call):
        calls.append(tool_call)
        return {"ok": True, "tool": tool_call["name"], "result": {"attempt": len(calls)}}

    monkeypatch.setattr(tool_registry, "execute_tool", fake_execute)
    runtime = task_runtime.TaskRuntime()
    task = runtime.create_task("Background scheduled task", session_id="scheduler-worker")
    runtime.set_plan(
        task["task_id"],
        [
            {"title": "First background step", "tool_intent": {"name": "calculator", "arguments": {"expression": "2 + 3"}}},
            {"title": "Second background step", "tool_intent": {"name": "calculator", "arguments": {"expression": "2 + 3"}}},
        ],
        {"name": "calculator", "arguments": {"expression": "2 + 3"}},
    )
    client = TestClient(app)

    start_response = client.post("/tasks/scheduler/start", json={"max_steps_per_tick": 1, "tick_interval_seconds": 0.01})
    deadline = time.time() + 2
    completed_task = None
    while time.time() < deadline:
        current = client.get(f"/tasks/{task['task_id']}").json()
        if current["status"] == "completed":
            completed_task = current
            break
        time.sleep(0.02)
    stop_response = client.post("/tasks/scheduler/stop")

    assert start_response.status_code == 200
    assert start_response.json()["scheduler"]["worker_running"] is True
    assert completed_task is not None
    assert completed_task["steps"][0]["status"] == "completed"
    assert completed_task["steps"][1]["status"] == "completed"
    assert len(calls) == 2
    assert stop_response.status_code == 200
    assert stop_response.json()["scheduler"]["running"] is False
