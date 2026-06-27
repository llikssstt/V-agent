import json
import uuid
from pathlib import Path

from agent.agent_core import AgentCore
from agent.llm_client import LLMClient
from agent.memory import MemoryStore
from agent.skill_registry import SkillRegistry


def local_tmp_path():
    path = Path(__file__).resolve().parents[2] / ".pytest_tmp" / "agent_loop_v2" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


class FakeRetriever:
    def retrieve(self, message):
        return {"memories": [], "profile": {}, "conversation_hits": []}


class FakeMemoryCore:
    def __init__(self):
        self.retriever = FakeRetriever()

    def save_conversation_turn(self, session_id, role, content):
        return {"session_id": session_id, "role": role, "content": content}

    def read_user_profile(self):
        return {}


class FakeEvolutionCore:
    def load_active_skills(self, message):
        return []

    def build_skill_context(self, skills):
        return ""

    def reflect_after_turn(self, user_message, assistant_reply, retrieved_memories, active_skills):
        return {"evolution_events": [], "evolution_summary": "", "active_skills": active_skills or []}


class FakeLLM(LLMClient):
    def __init__(self, planners):
        self.planners = list(planners)
        self.contexts = []

    def complete_json(self, prompt, stage, context):
        self.contexts.append({"stage": stage, "prompt": prompt, "context": context})
        if stage == "planner":
            if self.planners:
                return json.dumps(self.planners.pop(0), ensure_ascii=False)
            return json.dumps(planner_response(tool_name="none", final_ready=True), ensure_ascii=False)
        if stage == "responder":
            return json.dumps(
                {
                    "reply": "final answer",
                    "emotion": "thinking",
                    "tool_used": "none",
                    "skills_used": ["persona_skill"],
                    "memory_action": "none",
                },
                ensure_ascii=False,
            )
        return json.dumps({"events": [], "confidence": 0.0}, ensure_ascii=False)

    def responder_context(self):
        for item in reversed(self.contexts):
            if item["stage"] == "responder":
                return item["context"]
        return {}


def planner_response(tool_name="none", arguments=None, final_ready=False, reason="test"):
    return {
        "intent": "test",
        "emotion": "thinking",
        "skills_used": ["persona_skill"],
        "memory_action": "none",
        "memory_query": "",
        "memory_to_write": {"content": "", "category": "user_profile", "importance": 1},
        "memory_delete_query": "",
        "tool_call": {"name": tool_name, "arguments": arguments or {}},
        "final_ready": final_ready,
        "reason": reason,
    }


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


def test_plain_chat_records_none_tool_trace(monkeypatch):
    tmp_path = local_tmp_path()
    llm = FakeLLM([planner_response(tool_name="none", final_ready=True)])
    agent = make_agent(tmp_path, llm)

    response = agent.chat("hello", session_id="plain")

    assert response["tool_used"] == "none"
    assert len(response["tool_trace"]) == 1
    assert response["tool_trace"][0]["tool_call"]["name"] == "none"


def test_single_step_tool_call_records_tool_result(monkeypatch):
    tmp_path = local_tmp_path()
    llm = FakeLLM([planner_response(tool_name="calculator", arguments={"expression": "1 + 2"}, final_ready=True)])
    monkeypatch.setattr(
        "agent.agent_core.execute_tool",
        lambda tool_call: {"ok": True, "tool": tool_call["name"], "result": {"value": 3}},
    )
    agent = make_agent(tmp_path, llm)

    response = agent.chat("calculate", session_id="single")

    assert response["tool_used"] == "calculator"
    assert response["tool_trace"][0]["tool_result"]["result"]["value"] == 3


def test_multi_step_tool_call_passes_previous_trace_to_planner(monkeypatch):
    tmp_path = local_tmp_path()
    llm = FakeLLM(
        [
            planner_response(tool_name="web_search", arguments={"query": "vite latest"}, reason="search first"),
            planner_response(tool_name="web_fetch", arguments={"url": "https://example.test"}, final_ready=True, reason="fetch detail"),
        ]
    )

    def fake_execute(tool_call):
        if tool_call["name"] == "web_search":
            return {
                "ok": True,
                "tool": "web_search",
                "result": {"results": [{"title": "Vite", "url": "https://example.test", "snippet": "release", "source": "tavily"}]},
            }
        return {"ok": True, "tool": "web_fetch", "result": {"title": "Vite Release", "url": "https://example.test", "content": "details"}}

    monkeypatch.setattr("agent.agent_core.execute_tool", fake_execute)
    agent = make_agent(tmp_path, llm)

    response = agent.chat("latest vite", session_id="multi")

    assert [entry["tool_call"]["name"] for entry in response["tool_trace"]] == ["web_search", "web_fetch"]
    planner_contexts = [item["context"] for item in llm.contexts if item["stage"] == "planner"]
    assert planner_contexts[0]["tool_trace"] == []
    assert planner_contexts[1]["tool_trace"][0]["tool_call"]["name"] == "web_search"


def test_max_steps_limits_tool_loop(monkeypatch):
    tmp_path = local_tmp_path()
    llm = FakeLLM([planner_response(tool_name="calculator", arguments={"expression": "1 + 1"}) for _ in range(10)])
    monkeypatch.setattr("agent.agent_core.execute_tool", lambda tool_call: {"ok": True, "tool": tool_call["name"], "result": {"value": 2}})
    agent = make_agent(tmp_path, llm, max_steps=2)

    response = agent.chat("loop", session_id="max")

    assert len(response["tool_trace"]) == 2


def test_tool_failure_still_reaches_responder(monkeypatch):
    tmp_path = local_tmp_path()
    llm = FakeLLM([planner_response(tool_name="web_search", arguments={"query": "news"})])
    monkeypatch.setattr(
        "agent.agent_core.execute_tool",
        lambda tool_call: {"ok": False, "tool": "web_search", "error": {"code": "request_failed", "message": "boom"}},
    )
    agent = make_agent(tmp_path, llm)

    response = agent.chat("news", session_id="failure")

    assert response["tool_trace"][0]["tool_result"]["ok"] is False
    assert llm.responder_context()["tool_trace"][0]["tool_result"]["error"]["code"] == "request_failed"


def test_responder_receives_complete_tool_trace(monkeypatch):
    tmp_path = local_tmp_path()
    llm = FakeLLM(
        [
            planner_response(tool_name="calculator", arguments={"expression": "1 + 2"}),
            planner_response(tool_name="none", final_ready=True),
        ]
    )
    monkeypatch.setattr("agent.agent_core.execute_tool", lambda tool_call: {"ok": True, "tool": tool_call["name"], "result": {"value": 3}})
    agent = make_agent(tmp_path, llm)

    response = agent.chat("calculate", session_id="trace")

    assert llm.responder_context()["tool_trace"] == response["tool_trace"]
    assert "tool_result" not in llm.responder_context()


def test_sources_are_extracted_from_web_tool_trace(monkeypatch):
    tmp_path = local_tmp_path()
    llm = FakeLLM(
        [
            planner_response(tool_name="web_search", arguments={"query": "vite latest"}),
            planner_response(tool_name="web_fetch", arguments={"url": "https://example.test/vite"}, final_ready=True),
        ]
    )

    def fake_execute(tool_call):
        if tool_call["name"] == "web_search":
            return {
                "ok": True,
                "tool": "web_search",
                "result": {
                    "results": [
                        {"title": "Vite Releases", "url": "https://example.test/vite", "snippet": "Latest release", "source": "tavily"}
                    ]
                },
            }
        return {
            "ok": True,
            "tool": "web_fetch",
            "result": {"title": "Vite Releases", "url": "https://example.test/vite", "content": "Latest release details"},
        }

    monkeypatch.setattr("agent.agent_core.execute_tool", fake_execute)
    agent = make_agent(tmp_path, llm)

    response = agent.chat("latest vite", session_id="sources")

    assert response["sources"] == [
        {"title": "Vite Releases", "url": "https://example.test/vite", "snippet": "Latest release", "source": "tavily"}
    ]


def test_skill_context_includes_description_triggers_and_instructions():
    tmp_path = local_tmp_path()
    skills_dir = tmp_path / "skills"
    generated_dir = tmp_path / "generated"
    skills_dir.mkdir()
    generated_dir.mkdir()
    (skills_dir / "web_research.md").write_text(
        """---
name: web_research
description: Research current web information.
triggers:
  - latest
---

# Web Research

## Instructions
- Search first.
- Cite URLs.
""",
        encoding="utf-8",
    )
    registry = SkillRegistry(static_dir=skills_dir, generated_dir=generated_dir)

    context = registry.build_context(registry.match("latest vite release"))

    assert "Research current web information." in context
    assert "latest" in context
    assert "Search first." in context
    assert "Cite URLs." in context
