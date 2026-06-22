import json
from pathlib import Path

from agent.llm_client import LLMClient
from agent.memory import MemoryStore
from agent.prompt_builder import build_planner_prompt, build_responder_prompt
from agent.response_parser import parse_planner, parse_responder
from tools.tool_executor import execute_tool


CONVERSATIONS_PATH = Path(__file__).resolve().parents[1] / "storage" / "conversations.json"


class AgentCore:
    def __init__(self, llm_client=None, memory_store=None, conversations_path=CONVERSATIONS_PATH):
        self.llm = llm_client or LLMClient()
        self.memory = memory_store or MemoryStore()
        self.conversations_path = Path(conversations_path)
        self.conversations_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.conversations_path.exists():
            self.conversations_path.write_text("{}", encoding="utf-8")

    def chat(self, message, session_id="default"):
        clean_message = str(message or "").strip()
        history = self._load_history(session_id)
        history.append({"role": "user", "content": clean_message})
        memories = self.memory.list_memories()

        planner_prompt = build_planner_prompt(clean_message, history, memories)
        planner = parse_planner(self.llm.complete_json(planner_prompt, "planner", {"message": clean_message, "history": history, "memories": memories}))

        memory_result = self._execute_memory(planner)
        tool_result = execute_tool(planner.get("tool_call"))

        responder_prompt = build_responder_prompt(clean_message, history, planner, memory_result, tool_result)
        response = parse_responder(
            self.llm.complete_json(
                responder_prompt,
                "responder",
                {
                    "message": clean_message,
                    "history": history,
                    "planner": planner,
                    "memory_result": memory_result,
                    "tool_result": tool_result,
                },
            )
        )

        history.append({"role": "assistant", "content": response["reply"]})
        self._save_history(session_id, history[-20:])
        return response

    def _execute_memory(self, planner):
        action = planner.get("memory_action", "none")
        if action == "read":
            return {"ok": True, "action": "read", "items": self.memory.retrieve_memory(planner.get("memory_query", ""))}
        if action == "write":
            item = planner.get("memory_to_write") or {}
            content = str(item.get("content", "")).strip()
            if not content:
                return {"ok": False, "action": "write", "error": "memory content is empty"}
            memory = self.memory.write_memory(content, item.get("category", "user_profile"), item.get("importance", 1), "user")
            return {"ok": True, "action": "write", "item": memory}
        if action == "delete":
            count = self.memory.delete_memory_by_query(planner.get("memory_delete_query", ""))
            return {"ok": True, "action": "delete", "deleted": count}
        return {"ok": True, "action": "none"}

    def _read_conversations(self):
        try:
            return json.loads(self.conversations_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _write_conversations(self, data):
        self.conversations_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_history(self, session_id):
        return self._read_conversations().get(session_id, [])

    def _save_history(self, session_id, history):
        data = self._read_conversations()
        data[session_id] = history
        self._write_conversations(data)

