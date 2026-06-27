import json
from pathlib import Path

from agent.llm_client import LLMClient
from agent.memory import MemoryStore
from agent.memory_core import MemoryCore
from agent.memory_prompt_builder import build_memory_context
from agent.memory_router import route_memory_intent
from agent.memory_writer import MemoryWriter
from agent.prompt_builder import build_planner_prompt, build_responder_prompt
from agent.response_parser import parse_planner, parse_responder
from agent.self_evolution import SelfEvolutionCore
from agent.skill_registry import SkillRegistry
from tools.tool_executor import execute_tool


CONVERSATIONS_PATH = Path(__file__).resolve().parents[1] / "storage" / "conversations.json"


class AgentCore:
    def __init__(
        self,
        llm_client=None,
        memory_store=None,
        conversations_path=CONVERSATIONS_PATH,
        memory_core=None,
        evolution_core=None,
        skill_registry=None,
        skills_dir=None,
        generated_skills_dir=None,
        max_steps=4,
    ):
        self.llm = llm_client or LLMClient()
        self.memory = memory_store or MemoryStore()
        self.memory_core = memory_core or MemoryCore()
        self.memory_writer = MemoryWriter(self.memory_core)
        self.evolution_core = evolution_core or SelfEvolutionCore(llm_client=self.llm, memory_core=self.memory_core)
        self.skill_registry = skill_registry or SkillRegistry(static_dir=skills_dir, generated_dir=generated_skills_dir)
        try:
            self.max_steps = max(1, min(int(max_steps or 4), 8))
        except (TypeError, ValueError):
            self.max_steps = 4
        self.conversations_path = Path(conversations_path)
        self.conversations_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.conversations_path.exists():
            self.conversations_path.write_text("{}", encoding="utf-8")

    def chat(self, message, session_id="default"):
        clean_message = str(message or "").strip()
        active_skills = self._dedupe_skills(
            self.skill_registry.match(clean_message) + self.evolution_core.load_active_skills(clean_message)
        )
        skill_context = "\n\n".join(
            part
            for part in [
                self.skill_registry.build_context(active_skills),
                self.evolution_core.build_skill_context([skill for skill in active_skills if skill.get("evidence_count")]),
            ]
            if part
        )

        self.memory_core.save_conversation_turn(session_id, "user", clean_message)
        history = self._load_history(session_id)
        history.append({"role": "user", "content": clean_message})
        memories = self.memory.list_memories()
        memory_route = route_memory_intent(clean_message)
        rag_result = self.memory_core.retriever.retrieve(clean_message) if memory_route["need_retrieve"] else {"memories": [], "profile": self.memory_core.read_user_profile(), "conversation_hits": []}
        memory_context = build_memory_context(rag_result)

        tool_trace = []
        memory_result = {"ok": True, "action": "none"}
        planner = None
        for step in range(1, self.max_steps + 1):
            planner_prompt = build_planner_prompt(clean_message, history, memories, tool_trace)
            if memory_context:
                planner_prompt += "\n\n" + memory_context
            if skill_context:
                planner_prompt += "\n\n" + skill_context
            planner = parse_planner(
                self.llm.complete_json(
                    planner_prompt,
                    "planner",
                    {
                        "message": clean_message,
                        "history": history,
                        "memories": memories,
                        "active_skills": active_skills,
                        "tool_trace": tool_trace,
                    },
                )
            )

            if step == 1:
                memory_result = self._execute_memory(planner, memory_route, clean_message)

            tool_call = planner.get("tool_call") or {"name": "none", "arguments": {}}
            trace_entry = {
                "step": step,
                "planner": planner,
                "tool_call": tool_call,
                "tool_result": {"ok": True, "tool": "none", "result": None},
            }
            if tool_call.get("name") == "none" or planner.get("final_ready"):
                tool_trace.append(trace_entry)
                break

            tool_result = execute_tool(tool_call)
            trace_entry["tool_result"] = tool_result
            tool_trace.append(trace_entry)
            if not tool_result.get("ok", False):
                break

        planner = planner or {}
        responder_prompt = build_responder_prompt(clean_message, history, planner, memory_result, tool_trace)
        if memory_context:
            responder_prompt += "\n\n请优先参考以下已检索记忆，但不要编造未提供的信息：\n" + memory_context
        if skill_context:
            responder_prompt += "\n\n请参考以下已启用的可解释优化 Skill，但不要声称自己有自我意识：\n" + skill_context
        response = parse_responder(
            self.llm.complete_json(
                responder_prompt,
                "responder",
                {
                    "message": clean_message,
                    "history": history,
                    "planner": planner,
                    "memory_result": memory_result,
                    "tool_trace": tool_trace,
                    "active_skills": active_skills,
                },
            )
        )

        history.append({"role": "assistant", "content": response["reply"]})
        self._save_history(session_id, history[-20:])
        self.memory_core.save_conversation_turn(session_id, "assistant", response["reply"])
        response["retrieved_memories"] = rag_result.get("memories", [])
        evolution = self.evolution_core.reflect_after_turn(clean_message, response["reply"], response["retrieved_memories"], active_skills)
        response["evolution_events"] = evolution.get("evolution_events", [])
        response["evolution_summary"] = evolution.get("evolution_summary", "")
        response["active_skills"] = active_skills or evolution.get("active_skills", [])
        response["evolution_count"] = len(response["evolution_events"])
        response["tool_trace"] = tool_trace
        last_tool = self._last_tool_used(tool_trace)
        response["tool_used"] = last_tool or response.get("tool_used", "none")
        return response

    def _execute_memory(self, planner, memory_route=None, message=""):
        route = memory_route or {"memory_intent": "none"}
        action = planner.get("memory_action", "none")
        if route.get("memory_intent") == "write":
            memory = self.memory_writer.write_from_user_message(message)
            return {"ok": True, "action": "write", "item": memory}
        if route.get("memory_intent") == "update":
            updated = self.memory_writer.update_by_query(message, message)
            return {"ok": bool(updated), "action": "update", "item": updated}
        if route.get("memory_intent") == "delete":
            deleted = self.memory_writer.delete_by_query(message)
            return {"ok": True, "action": "delete", "items": deleted}
        if route.get("memory_intent") == "retrieve":
            items = self.memory_core.retriever.retrieve(message).get("memories", [])
            return {"ok": True, "action": "read", "items": items}
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

    def _dedupe_skills(self, skills):
        seen = set()
        result = []
        for skill in skills:
            key = skill.get("skill_id") or skill.get("name") or skill.get("path")
            if key in seen:
                continue
            seen.add(key)
            result.append(skill)
        return result

    def _last_tool_used(self, tool_trace):
        for entry in reversed(tool_trace or []):
            name = ((entry.get("tool_call") or {}).get("name") or "none")
            if name != "none":
                return name
        return "none"
