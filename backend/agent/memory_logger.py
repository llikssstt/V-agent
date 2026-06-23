import json
from datetime import datetime, timezone
from pathlib import Path


class MemoryLogger:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def log(self, operation, query="", memory_ids=None, result="success", reason=""):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": operation,
            "query": query or "",
            "memory_ids": memory_ids or [],
            "result": result,
            "reason": reason or "",
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def list_logs(self, limit=100):
        if not self.path.exists():
            return []
        lines = [line for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        logs = []
        for line in lines[-limit:]:
            try:
                logs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return logs

