import importlib.util
import uuid
from pathlib import Path


def load_run_eval_module():
    path = Path(__file__).with_name("run_eval.py")
    spec = importlib.util.spec_from_file_location("run_eval", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_api_eval_generates_required_metrics_and_reports():
    run_eval = load_run_eval_module()
    reports_dir = Path(__file__).resolve().parents[2] / ".pytest_tmp" / "real_api_eval" / uuid.uuid4().hex
    reports_dir.mkdir(parents=True, exist_ok=True)

    report = run_eval.run_eval(
        cases_path=Path(__file__).with_name("eval_cases.json"),
        reports_dir=reports_dir,
        max_cases=2,
    )

    metric_names = {
        "route_accuracy",
        "tool_accuracy",
        "skill_hit_rate",
        "resource_hit_rate",
        "memory_hit_rate",
        "task_created_rate",
        "trace_completeness",
    }
    assert metric_names.issubset(report["metrics"])
    assert report["case_count"] == 2
    assert report["real_api"] is True
    assert report["fallback_count"] == 0
    assert all(case["reply"] for case in report["cases"])
    assert (reports_dir / "eval_report.json").exists()
    assert (reports_dir / "eval_report.md").exists()
