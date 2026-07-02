from agent_graph.task_runtime import TaskRuntime
from agent_graph.tool_intent_runner import run_tool_intent


def run_task_step(task_id):
    runtime = TaskRuntime()
    task = runtime.get_task(task_id)
    runtime.ensure_runnable(task)
    step = runtime.next_pending_step(task_id)
    if not step:
        task = runtime.finish_task(task_id, "completed")
        return {"ok": True, "task": task, "step": None, "result": None}

    runtime.update_step_status(task_id, step["step_id"], "in_progress", "running")
    tool_intent = _step_tool_intent(step, task)
    result = _execute_step_tool(tool_intent)
    runtime.add_artifact(
        task_id,
        "tool_result",
        {
            "step_id": step["step_id"],
            "step_title": step.get("title", ""),
            "step_tool_intent": tool_intent,
            "tool_result": result,
        },
    )
    task = runtime.update_step_status(
        task_id,
        step["step_id"],
        "completed" if result.get("ok") else "failed",
        "tool_intent executed" if result.get("ok") else ((result.get("error") or {}).get("message") or "tool failed"),
    )
    if not runtime.next_pending_step(task_id):
        task = runtime.finish_task(task_id, "completed" if result.get("ok") else "failed")
    return {"ok": result.get("ok", False), "task": task, "step": step, "result": result}


def run_task_until_idle(task_id, max_steps=5):
    max_steps = max(1, min(int(max_steps or 5), 20))
    runtime = TaskRuntime()
    runtime.ensure_runnable(runtime.get_task(task_id))
    iterations = []
    for _ in range(max_steps):
        result = run_task_step(task_id)
        iterations.append(result)
        if not result.get("ok") or result.get("step") is None:
            break
        task = result.get("task") or {}
        if task.get("status") in {"completed", "failed", "cancelled"}:
            break
    runtime = TaskRuntime()
    return {
        "ok": all(item.get("ok") for item in iterations),
        "iterations": len([item for item in iterations if item.get("step") is not None]),
        "results": iterations,
        "task": runtime.get_task(task_id),
    }


def _step_tool_intent(step, task):
    has_step_intent = isinstance(step, dict) and "tool_intent" in step
    step_intent = step.get("tool_intent") if has_step_intent else None
    if has_step_intent:
        step_intent = step_intent if isinstance(step_intent, dict) else {}
        return {
            "name": str(step_intent.get("name") or "none"),
            "arguments": step_intent.get("arguments") if isinstance(step_intent.get("arguments"), dict) else {},
        }
    task_intent = task.get("tool_intent") if isinstance(task, dict) else None
    if isinstance(task_intent, dict):
        return {
            "name": str(task_intent.get("name") or "none"),
            "arguments": task_intent.get("arguments") if isinstance(task_intent.get("arguments"), dict) else {},
        }
    return {"name": "none", "arguments": {}}


def _execute_step_tool(tool_intent):
    if (tool_intent or {}).get("name") in {None, "", "none"}:
        return {"ok": True, "tool": "none", "result": {"message": "No tool required for this step"}}
    return run_tool_intent(tool_intent)
