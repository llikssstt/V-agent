import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_MEMORY_PATH = Path(__file__).resolve().parents[1] / "storage" / "memory.json"


class MemoryStore:
    def __init__(self, path=DEFAULT_MEMORY_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def _read(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write(self, memories):
        self.path.write_text(json.dumps(memories, ensure_ascii=False, indent=2), encoding="utf-8")

    def write_memory(self, content, category, importance=1, source="user"):
        now = datetime.now(timezone.utc).isoformat()
        memory = {
            "memory_id": str(uuid.uuid4()),
            "content": str(content).strip(),
            "category": category if category in {"user_profile", "preference", "project", "todo", "learning_goal"} else "user_profile",
            "importance": int(importance or 1),
            "created_at": now,
            "updated_at": now,
            "source": source or "user",
        }
        memories = self._read()
        memories.append(memory)
        self._write(memories)
        return memory

    def retrieve_memory(self, query, top_k=5):
        query_text = str(query or "").lower()
        terms = [part for part in query_text.replace("，", " ").replace(",", " ").split() if part]
        query_chars = {char for char in query_text if "\u4e00" <= char <= "\u9fff"}
        broad_memory_question = any(hint in query_text for hint in ["记得", "最近", "做什么", "什么吗"])
        scored = []
        for memory in self._read():
            content = memory.get("content", "").lower()
            content_chars = {char for char in content if "\u4e00" <= char <= "\u9fff"}
            score = 0
            if query_text and query_text in content:
                score += 3
            score += sum(1 for term in terms if term in content)
            score += min(len(query_chars & content_chars), 5)
            if broad_memory_question and memory.get("importance", 1) >= 3:
                score += 2
            if score or not query_text:
                scored.append((score, memory))
        scored.sort(key=lambda item: (item[0], item[1].get("importance", 1)), reverse=True)
        return [memory for _, memory in scored[:top_k]]

    def delete_memory(self, memory_id):
        memories = self._read()
        remaining = [item for item in memories if item.get("memory_id") != memory_id]
        self._write(remaining)
        return len(remaining) != len(memories)

    def delete_memory_by_query(self, query):
        matches = self.retrieve_memory(query, top_k=20)
        ids = {item["memory_id"] for item in matches}
        memories = [item for item in self._read() if item.get("memory_id") not in ids]
        self._write(memories)
        return len(ids)

    def list_memories(self):
        return self._read()
