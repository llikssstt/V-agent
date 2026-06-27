import json
import os
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from agent.agent_core import AgentCore
from agent.emotion import normalize_tool
from agent.llm_client import LLMClient
from agent.skill_registry import SkillRegistry
from main import app
from tools.registry import AVAILABLE_TOOLS, execute_tool, get_tool_names


def local_tmp_path():
    path = Path(__file__).resolve().parents[2] / ".pytest_tmp" / "general_agent" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_tool_registry_lists_all_builtin_tools():
    names = set(get_tool_names())

    assert {"time", "calculator", "todo", "study_plan", "web_search", "web_fetch"}.issubset(names)
    assert {item["name"] for item in AVAILABLE_TOOLS} == names


def test_execute_tool_uses_registry_for_existing_tools():
    result = execute_tool({"name": "calculator", "arguments": {"expression": "2 * (3 + 4)"}})

    assert result["ok"] is True
    assert result["tool"] == "calculator"
    assert result["result"]["result"] == 14


def test_web_search_without_api_key_returns_structured_error(monkeypatch):
    monkeypatch.delenv("SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("SEARCH_PROVIDER", raising=False)
    monkeypatch.setattr("tools.web_tools.load_env_file", lambda: None)

    result = execute_tool({"name": "web_search", "arguments": {"query": "latest Python release"}})

    assert result["ok"] is False
    assert result["tool"] == "web_search"
    assert result["error"]["code"] == "missing_api_key"


def test_web_fetch_rejects_non_http_url():
    result = execute_tool({"name": "web_fetch", "arguments": {"url": "file:///C:/secret.txt"}})

    assert result["ok"] is False
    assert result["tool"] == "web_fetch"
    assert result["error"]["code"] == "invalid_url"


def test_web_fetch_returns_page_text(monkeypatch):
    class FakeResponse:
        text = "<html><head><title>Example Page</title></head><body><script>bad()</script><h1>Hello</h1><p>Readable text.</p></body></html>"

        def raise_for_status(self):
            return None

    def fake_get(url, headers=None, timeout=None):
        return FakeResponse()

    monkeypatch.setattr("tools.web_tools.requests.get", fake_get)

    result = execute_tool({"name": "web_fetch", "arguments": {"url": "https://example.test/page", "max_chars": 500}})

    assert result["ok"] is True
    assert result["tool"] == "web_fetch"
    assert result["result"]["title"] == "Example Page"
    assert "Readable text." in result["result"]["content"]
    assert "bad()" not in result["result"]["content"]


def test_new_tool_names_are_not_filtered_by_parser():
    assert normalize_tool("web_search") == "web_search"
    assert normalize_tool("web_fetch") == "web_fetch"


def test_mock_planner_prefers_web_search_for_fresh_information():
    client = LLMClient()

    planner = json.loads(client.complete_json("", "planner", {"message": "帮我查一下 GitHub 上 Vite 最新版本"}))

    assert planner["tool_call"]["name"] == "web_search"
    assert "GitHub" in planner["tool_call"]["arguments"]["query"]


def test_skill_registry_loads_static_and_generated_skills():
    tmp_path = local_tmp_path()
    static_dir = tmp_path / "skills"
    generated_dir = tmp_path / "generated_skills"
    static_dir.mkdir()
    generated_dir.mkdir()
    (static_dir / "web_skill.md").write_text(
        """---
name: web_research_skill
triggers:
  - GitHub
  - 最新
---

# Web Research Skill

Use web_search before answering fresh information questions.
""",
        encoding="utf-8",
    )
    (generated_dir / "pressure.md").write_text(
        """---
skill_id: skill_pressure
scenario: 学习压力
enabled: true
trigger_examples:
  - 压力好大
---

# Pressure Skill
""",
        encoding="utf-8",
    )
    registry = SkillRegistry(static_dir=static_dir, generated_dir=generated_dir)

    matched = registry.match("GitHub 最新版本是多少？")

    assert [skill["name"] for skill in matched] == ["web_research_skill"]
    assert registry.match("我压力好大")[0]["skill_id"] == "skill_pressure"


def test_skill_registry_loads_nested_skill_md_directories():
    tmp_path = local_tmp_path()
    static_dir = tmp_path / "skills"
    generated_dir = tmp_path / "generated_skills"
    nested = static_dir / "nature_skill"
    nested.mkdir(parents=True)
    generated_dir.mkdir()
    (nested / "SKILL.md").write_text(
        """---
name: nature_skill
triggers:
  - forest
---

# Nature Skill

Use this when the user asks about forest observations.
""",
        encoding="utf-8",
    )
    registry = SkillRegistry(static_dir=static_dir, generated_dir=generated_dir)

    matched = registry.match("please help with forest observations")

    assert matched[0]["name"] == "nature_skill"
    assert matched[0]["path"].endswith("SKILL.md")


def test_chat_mock_still_returns_required_fields_for_general_agent():
    client = TestClient(app)

    response = client.post("/chat", json={"message": "帮我查一下今天的 AI 新闻", "session_id": "general-agent"})

    assert response.status_code == 200
    data = response.json()
    assert {"reply", "tool_used", "skills_used", "retrieved_memories", "evolution_events", "active_skills"}.issubset(data)
    assert data["tool_used"] in {"none", "time", "calculator", "todo", "study_plan", "web_search", "web_fetch"}


def test_agent_injects_matched_skills_into_planner_context():
    tmp_path = local_tmp_path()
    class InspectLLM(LLMClient):
        def __init__(self):
            super().__init__()
            self.prompts = []

        def complete_json(self, prompt, stage, context):
            self.prompts.append({"stage": stage, "prompt": prompt, "context": context})
            if stage == "planner":
                return json.dumps(
                    {
                        "intent": "fresh info",
                        "emotion": "thinking",
                        "skills_used": ["web_research_skill"],
                        "memory_action": "none",
                        "memory_query": "",
                        "memory_to_write": {"content": "", "category": "user_profile", "importance": 1},
                        "memory_delete_query": "",
                        "tool_call": {"name": "web_search", "arguments": {"query": "Vite GitHub latest version"}},
                    },
                    ensure_ascii=False,
                )
            if stage == "responder":
                return json.dumps(
                    {
                        "reply": "搜索工具未配置 API Key，暂时不能查询最新版本。",
                        "emotion": "thinking",
                        "tool_used": "web_search",
                        "skills_used": ["web_research_skill"],
                        "memory_action": "none",
                    },
                    ensure_ascii=False,
                )
            return json.dumps({"events": [], "confidence": 0.0}, ensure_ascii=False)

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "web.md").write_text(
        """---
name: web_research_skill
triggers:
  - GitHub
---

# Web Research Skill
""",
        encoding="utf-8",
    )
    llm = InspectLLM()
    agent = AgentCore(llm_client=llm, conversations_path=tmp_path / "conversations.json", skills_dir=skills_dir, generated_skills_dir=tmp_path / "generated")

    response = agent.chat("GitHub 上 Vite 最新版本是什么？", session_id="skill-inject")

    assert response["active_skills"][0]["name"] == "web_research_skill"
    assert "web_research_skill" in llm.prompts[0]["prompt"]
