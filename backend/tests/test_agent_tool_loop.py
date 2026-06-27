import json
import uuid
from pathlib import Path

from agent.agent_core import AgentCore
from agent.llm_client import LLMClient
from agent.memory import MemoryStore
from agent.response_parser import parse_planner


def local_tmp_path():
    path = Path(__file__).resolve().parents[2] / ".pytest_tmp" / "agent_loop" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


class FakeRetriever:
    def retrieve(self, message):
        return {"memories": [], "profile": {}, "conversation_hits": []}


class FakeMemoryCore:
    def __init__(self):
        self.retriever = FakeRetriever()
        self.saved_turns = []

    def save_conversation_turn(self, session_id, role, content):
        self.saved_turns.append({"session_id": session_id, "role": role, "content": content})
        return self.saved_turns[-1]

    def read_user_profile(self):
        return {}


class FakeEvolutionCore:
    def load_active_skills(self, message):
        return []

    def build_skill_context(self, skills):
        return ""

    def reflect_after_turn(self, user_message, assistant_reply, retrieved_memories, active_skills):
        return {"evolution_events": [], "evolution_summary": "", "active_skills": active_skills or []}


class ScriptedLLM(LLMClient):
    def __init__(self, planners):
        self.planners = list(planners)
        self.contexts = []
        self.prompts = []
        self.responder_context = None

    def complete_json(self, prompt, stage, context):
        self.prompts.append({"stage": stage, "prompt": prompt})
        self.contexts.append({"stage": stage, "context": context})
        if stage == "planner":
            if self.planners:
                return json.dumps(self.planners.pop(0), ensure_ascii=False)
            return json.dumps(
                {
                    "intent": "done",
                    "emotion": "thinking",
                    "skills_used": ["persona_skill"],
                    "memory_action": "none",
                    "tool_call": {"name": "none", "arguments": {}},
                    "final_ready": True,
                    "reason": "no more steps",
                },
                ensure_ascii=False,
            )
        if stage == "responder":
            self.responder_context = context
            return json.dumps(
                {
                    "reply": "done",
                    "emotion": "thinking",
                    "tool_used": "none",
                    "skills_used": ["persona_skill"],
                    "memory_action": "none",
                },
                ensure_ascii=False,
            )
        return json.dumps({"events": [], "confidence": 0.0}, ensure_ascii=False)


def make_agent(tmp_path, llm, max_steps=4):
    return AgentCore(
        llm_client=llm,
        memory_store=MemoryStore(tmp_path / "memory.json"),
        memory_core=FakeMemoryCore(),
        evolution_core=FakeEvolutionCore(),
        conversations_path=tmp_path / "conversations.json",
        skills_dir=tmp_path / "skills",
        generated_skills_dir=tmp_path / "generated_skills",
        max_steps=max_steps,
    )


def test_parse_planner_defaults_missing_loop_fields():
    planner = parse_planner(
        json.dumps(
            {
                "intent": "legacy planner",
                "emotion": "neutral",
                "skills_used": ["persona_skill"],
                "memory_action": "none",
                "tool_call": {"name": "none", "arguments": {}},
            },
            ensure_ascii=False,
        )
    )

    assert planner["final_ready"] is False
    assert planner["reason"] == ""


def test_plain_chat_stops_without_tool_and_returns_tool_trace():
    tmp_path = local_tmp_path()
    llm = ScriptedLLM(
        [
            {
                "intent": "chat",
                "emotion": "neutral",
                "skills_used": ["persona_skill"],
                "memory_action": "none",
                "tool_call": {"name": "none", "arguments": {}},
                "final_ready": True,
                "reason": "plain chat",
            }
        ]
    )
    agent = make_agent(tmp_path, llm)

    response = agent.chat("hello", session_id="loop-plain")

    assert response["tool_used"] == "none"
    assert len(response["tool_trace"]) == 1
    assert response["tool_trace"][0]["tool_call"]["name"] == "none"
    assert response["tool_trace"][0]["planner"]["final_ready"] is True


def test_web_search_step_enters_tool_trace():
    tmp_path = local_tmp_path()
    llm = ScriptedLLM(
        [
            {
                "intent": "fresh info",
                "emotion": "thinking",
                "skills_used": ["persona_skill"],
                "memory_action": "none",
                "tool_call": {"name": "web_search", "arguments": {"query": "latest Python release"}},
                "final_ready": False,
                "reason": "need search",
            }
        ]
    )
    agent = make_agent(tmp_path, llm)

    response = agent.chat("latest Python release", session_id="loop-search")

    assert response["tool_used"] == "web_search"
    assert response["tool_trace"][0]["tool_call"]["name"] == "web_search"
    assert response["tool_trace"][0]["tool_result"]["tool"] == "web_search"
    assert "tool_trace" in llm.responder_context


def test_tool_loop_does_not_exceed_max_steps():
    tmp_path = local_tmp_path()
    planners = [
        {
            "intent": "calculate",
            "emotion": "thinking",
            "skills_used": ["persona_skill"],
            "memory_action": "none",
            "tool_call": {"name": "calculator", "arguments": {"expression": "1 + 1"}},
            "final_ready": False,
            "reason": "keep calculating",
        }
        for _ in range(10)
    ]
    llm = ScriptedLLM(planners)
    agent = make_agent(tmp_path, llm, max_steps=3)

    response = agent.chat("calculate repeatedly", session_id="loop-max")

    assert len(response["tool_trace"]) == 3
    assert all(item["tool_call"]["name"] == "calculator" for item in response["tool_trace"])


def test_responder_receives_complete_tool_trace():
    tmp_path = local_tmp_path()
    llm = ScriptedLLM(
        [
            {
                "intent": "first step",
                "emotion": "thinking",
                "skills_used": ["persona_skill"],
                "memory_action": "none",
                "tool_call": {"name": "calculator", "arguments": {"expression": "1 + 2"}},
                "final_ready": False,
                "reason": "need calculation",
            },
            {
                "intent": "done",
                "emotion": "thinking",
                "skills_used": ["persona_skill"],
                "memory_action": "none",
                "tool_call": {"name": "none", "arguments": {}},
                "final_ready": True,
                "reason": "calculation is enough",
            },
        ]
    )
    agent = make_agent(tmp_path, llm)

    response = agent.chat("calculate once", session_id="loop-responder")

    assert len(response["tool_trace"]) == 2
    assert llm.responder_context["tool_trace"] == response["tool_trace"]
    assert "tool_result" not in llm.responder_context
