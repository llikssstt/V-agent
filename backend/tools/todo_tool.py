import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_TODO_PATH = Path(__file__).resolve().parents[1] / "storage" / "todos.json"


class TodoStore:
    def __init__(self, path=DEFAULT_TODO_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def _read(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write(self, todos):
        self.path.write_text(json.dumps(todos, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, content):
        todo = {
            "todo_id": str(uuid.uuid4()),
            "content": str(content).strip(),
            "done": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        todos = self._read()
        todos.append(todo)
        self._write(todos)
        return todo

    def list(self):
        return self._read()


def run_todo(action="list", content=""):
    store = TodoStore()
    if action == "add":
        if not str(content or "").strip():
            return {"ok": False, "error": "添加待办需要 content"}
        return {"ok": True, "item": store.add(content)}
    if action == "list":
        return {"ok": True, "items": store.list()}
    return {"ok": False, "error": f"不支持的 todo action: {action}"}

