import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agent.memory_logger import MemoryLogger
from agent.memory_retriever import LocalEmbeddingModel, MemoryRetriever


DEFAULT_STORAGE_DIR = Path(__file__).resolve().parents[1] / "storage"
VALID_CATEGORIES = {
    "user_profile",
    "preference",
    "project",
    "learning_goal",
    "todo",
    "emotional_pattern",
    "interaction_style",
    "agent_note",
}
SENSITIVE_HINTS = [
    "身份证",
    "护照",
    "银行卡",
    "信用卡",
    "密码",
    "验证码",
    "token",
    "api key",
    "apikey",
    "secret",
    "私钥",
]


class MemoryCore:
    def __init__(self, storage_dir=DEFAULT_STORAGE_DIR, embedder=None):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.memory_path = self.storage_dir / "memory.json"
        self.profile_path = self.storage_dir / "user_profile.json"
        self.db_path = self.storage_dir / "conversations.db"
        self.logger = MemoryLogger(self.storage_dir / "memory_logs.jsonl")
        self.embedder = embedder or LocalEmbeddingModel()
        self._init_files()
        self._init_db()
        self.retriever = MemoryRetriever(self)

    def _init_files(self):
        if not self.memory_path.exists():
            self.memory_path.write_text("[]\n", encoding="utf-8")
        if not self.profile_path.exists():
            self.profile_path.write_text(
                json.dumps(
                    {
                        "name": "",
                        "preferred_language": "中文",
                        "preferred_style": "自然、直接、清晰",
                        "current_projects": [],
                        "learning_goals": [],
                        "interaction_preferences": [],
                        "updated_at": "",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    created_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts
                USING fts5(content, role, session_id, created_at)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_vectors (
                    memory_id TEXT PRIMARY KEY,
                    embedding TEXT NOT NULL
                )
                """
            )

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _read_memories(self):
        try:
            return json.loads(self.memory_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write_memories(self, memories):
        self.memory_path.write_text(json.dumps(memories, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def read_user_profile(self):
        try:
            return json.loads(self.profile_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def update_user_profile(self, **updates):
        profile = self.read_user_profile()
        profile.update(updates)
        profile["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return profile

    def list_memories(self, include_inactive=False):
        memories = self._read_memories()
        if include_inactive:
            return memories
        return [memory for memory in memories if memory.get("status", "active") == "active"]

    def is_sensitive(self, content):
        text = str(content or "").lower()
        return any(hint in text for hint in SENSITIVE_HINTS)

    def write_memory(self, content, category, importance=0.7, source="user_explicit"):
        if self.is_sensitive(content):
            self.logger.log("write", query="[filtered]", memory_ids=[], result="skipped", reason="sensitive content")
            raise ValueError("sensitive memory content is not allowed")
        now = datetime.now(timezone.utc).isoformat()
        memory = {
            "memory_id": f"mem_{uuid.uuid4().hex[:12]}",
            "content": str(content).strip(),
            "category": category if category in VALID_CATEGORIES else "user_profile",
            "importance": max(0.1, min(float(importance or 0.7), 1.0)),
            "created_at": now,
            "updated_at": now,
            "source": source or "user_explicit",
            "status": "active",
        }
        memories = self._read_memories()
        memories.append(memory)
        self._write_memories(memories)
        self.upsert_memory_vector(memory["memory_id"], memory["content"])
        self.logger.log("write", query=memory["content"], memory_ids=[memory["memory_id"]], result="success", reason=memory["source"])
        return memory

    def update_memory(self, memory_id, content=None, category=None, importance=None, status=None):
        if content is not None and self.is_sensitive(content):
            self.logger.log("update", query="[filtered]", memory_ids=[memory_id], result="skipped", reason="sensitive content")
            raise ValueError("sensitive memory content is not allowed")
        memories = self._read_memories()
        updated = None
        for memory in memories:
            if memory["memory_id"] == memory_id:
                if content is not None:
                    memory["content"] = str(content).strip()
                if category is not None:
                    memory["category"] = category if category in VALID_CATEGORIES else memory["category"]
                if importance is not None:
                    memory["importance"] = max(0.1, min(float(importance), 1.0))
                if status is not None:
                    memory["status"] = status
                memory["updated_at"] = datetime.now(timezone.utc).isoformat()
                updated = memory
                break
        if updated is None:
            raise KeyError(memory_id)
        self._write_memories(memories)
        self.upsert_memory_vector(updated["memory_id"], updated["content"])
        self.logger.log("update", query=updated["content"], memory_ids=[updated["memory_id"]], result="success")
        return updated

    def delete_memory(self, memory_id):
        deleted = self.update_memory(memory_id, status="inactive")
        self.logger.log("delete", query=deleted["content"], memory_ids=[memory_id], result="success", reason="soft delete")
        return deleted

    def upsert_memory_vector(self, memory_id, content):
        vector = self.embedder.encode([content])[0]
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO memory_vectors(memory_id, embedding) VALUES (?, ?)",
                (memory_id, json.dumps(vector)),
            )

    def get_memory_vector(self, memory_id):
        with self._connect() as conn:
            row = conn.execute("SELECT embedding FROM memory_vectors WHERE memory_id = ?", (memory_id,)).fetchone()
        if not row:
            return []
        return json.loads(row[0])

    def save_conversation_turn(self, session_id, role, content):
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO conversations(session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, content, created_at),
            )
            conn.execute(
                "INSERT INTO conversations_fts(content, role, session_id, created_at) VALUES (?, ?, ?, ?)",
                (content, role, session_id, created_at),
            )
        return {"session_id": session_id, "role": role, "content": content, "created_at": created_at}

    def search_conversations(self, query, top_k=3):
        terms = [term for term in str(query or "").replace("，", " ").replace("？", " ").replace(",", " ").split() if term]
        if not terms:
            return []
        like_terms = [f"%{term}%" for term in terms[:5]]
        where = " OR ".join(["content LIKE ?" for _ in like_terms])
        sql = f"SELECT role, content, created_at FROM conversations WHERE {where} ORDER BY id DESC LIMIT ?"
        with self._connect() as conn:
            rows = conn.execute(sql, (*like_terms, top_k)).fetchall()
        return [
            {"role": role, "content": content, "created_at": created_at, "score": 0.5}
            for role, content, created_at in rows
        ]

    def list_logs(self, limit=100):
        return self.logger.list_logs(limit=limit)
