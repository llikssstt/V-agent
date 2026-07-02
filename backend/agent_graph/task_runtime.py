import json
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


TASK_STORE_PATH = Path(__file__).resolve().parents[1] / "storage" / "tasks.json"
RUNNABLE_STATUSES = {"created", "running"}
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
_store_lock = threading.RLock()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class TaskRuntime:
    def __init__(self, path=None):
        self.path = Path(path or TASK_STORE_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"tasks": {}})

    def create_task(self, title, session_id="default"):
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        task = {
            "task_id": task_id,
            "session_id": session_id,
            "title": str(title or "Untitled task")[:240],
            "status": "created",
            "steps": [],
            "artifacts": [],
            "logs": [],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        task["logs"].append({"timestamp": now_iso(), "event": "created", "message": task["title"]})
        with _store_lock:
            data = self._read()
            data.setdefault("tasks", {})[task_id] = task
            self._write(data)
        return task

    def list_tasks(self):
        with _store_lock:
            tasks = list(self._read().get("tasks", {}).values())
        return sorted(tasks, key=lambda item: item.get("updated_at", ""), reverse=True)

    def get_task(self, task_id):
        with _store_lock:
            task = self._read().get("tasks", {}).get(task_id)
        if not task:
            raise KeyError(task_id)
        return task

    def set_plan(self, task_id, steps, tool_intent=None):
        return self._mutate(
            task_id,
            lambda task: (
                task.update(
                    {
                        "status": "running",
                        "steps": [_normalize_step(index, step) for index, step in enumerate(steps or [], 1)],
                        "tool_intent": tool_intent or {"name": "none", "arguments": {}},
                    }
                ),
                task["logs"].append({"timestamp": now_iso(), "event": "plan", "message": f"{len(steps or [])} step(s) planned"}),
            ),
        )

    def append_step(self, task_id, title, status, detail=""):
        return self._mutate(
            task_id,
            lambda task: task["steps"].append(
                {
                    "step_id": f"step_{len(task.get('steps', [])) + 1}",
                    "title": title,
                    "status": status,
                    "detail": detail,
                    "updated_at": now_iso(),
                }
            ),
        )

    def next_pending_step(self, task_id):
        task = self.get_task(task_id)
        for step in task.get("steps", []):
            if step.get("status") == "pending":
                return step
        return None

    def update_step_status(self, task_id, step_id, status, detail=""):
        def mutate(task):
            for step in task.get("steps", []):
                if step.get("step_id") == step_id:
                    step["status"] = status
                    step["detail"] = detail
                    step["updated_at"] = now_iso()
                    if status == "in_progress":
                        step["attempts"] = int(step.get("attempts") or 0) + 1
                        step["last_error"] = ""
                    if status == "failed":
                        step["last_error"] = detail
                    task["logs"].append(
                        {"timestamp": now_iso(), "event": "step_status", "message": f"{step_id}:{status}", "detail": detail}
                    )
                    break
            else:
                raise KeyError(step_id)

        return self._mutate(task_id, mutate)

    def retry_step(self, task_id, step_id):
        def mutate(task):
            for step in task.get("steps", []):
                if step.get("step_id") == step_id:
                    if step.get("status") != "failed":
                        raise TaskStepNotRetryable(step.get("status") or "unknown")
                    step["status"] = "pending"
                    step["detail"] = "queued for retry"
                    step["updated_at"] = now_iso()
                    task["status"] = "running"
                    task["logs"].append(
                        {"timestamp": now_iso(), "event": "step_retry", "message": step_id, "attempts": step.get("attempts", 0)}
                    )
                    break
            else:
                raise KeyError(step_id)

        return self._mutate(task_id, mutate)

    def add_artifact(self, task_id, artifact_type, payload):
        return self._mutate(
            task_id,
            lambda task: task.setdefault("artifacts", []).append(
                {"artifact_id": f"artifact_{uuid.uuid4().hex[:10]}", "type": artifact_type, "payload": payload, "created_at": now_iso()}
            ),
        )

    def finish_task(self, task_id, status="completed"):
        return self._mutate(
            task_id,
            lambda task: (
                task.update({"status": status}),
                task["logs"].append({"timestamp": now_iso(), "event": "status", "message": status}),
            ),
        )

    def pause_task(self, task_id):
        return self._set_status(task_id, "paused", allowed={"created", "running"})

    def resume_task(self, task_id):
        return self._set_status(task_id, "running", allowed={"paused"})

    def cancel_task(self, task_id):
        return self._set_status(task_id, "cancelled", disallowed=TERMINAL_STATUSES)

    def ensure_runnable(self, task):
        status = task.get("status") or "created"
        if status not in RUNNABLE_STATUSES:
            raise TaskNotRunnable(status)

    def _set_status(self, task_id, status, allowed=None, disallowed=None):
        def mutate(task):
            current = task.get("status") or "created"
            if allowed is not None and current not in allowed:
                raise TaskNotRunnable(current)
            if disallowed is not None and current in disallowed:
                raise TaskNotRunnable(current)
            task["status"] = status
            task["logs"].append({"timestamp": now_iso(), "event": "status", "message": status, "previous": current})

        return self._mutate(task_id, mutate)

    def _mutate(self, task_id, mutator):
        with _store_lock:
            data = self._read()
            task = data.setdefault("tasks", {}).get(task_id)
            if not task:
                raise KeyError(task_id)
            mutator(task)
            task["updated_at"] = now_iso()
            self._write(data)
            return task

    def _read(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {"tasks": {}}

    def _write(self, data):
        tmp_path = self.path.with_name(f"{self.path.name}.{uuid.uuid4().hex}.tmp")
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        last_error = None
        for _ in range(5):
            try:
                tmp_path.replace(self.path)
                return
            except PermissionError as exc:
                last_error = exc
                time.sleep(0.02)
        raise last_error


def _normalize_step(index, step):
    if isinstance(step, str):
        step = {"title": step}
    step = dict(step or {})
    tool_intent = step.get("tool_intent") if isinstance(step.get("tool_intent"), dict) else {}
    return {
        "step_id": step.get("step_id") or f"step_{index}",
        "title": step.get("title") or f"Step {index}",
        "status": step.get("status") or "pending",
        "detail": step.get("detail", ""),
        "tool_intent": {
            "name": str(tool_intent.get("name") or "none"),
            "arguments": tool_intent.get("arguments") if isinstance(tool_intent.get("arguments"), dict) else {},
        },
        "attempts": int(step.get("attempts") or 0),
        "last_error": step.get("last_error", ""),
        "updated_at": step.get("updated_at") or now_iso(),
    }


class TaskNotRunnable(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__(f"task is {status}")


class TaskStepNotRetryable(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__(f"step is {status}")
