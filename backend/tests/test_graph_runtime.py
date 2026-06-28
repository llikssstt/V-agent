import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from agent.self_evolution import SelfEvolutionCore
from agent_graph.graph import GraphCore
from agent_graph.nodes.response_node import _response_prompt, response_node
from agent_graph.nodes.skill_node import skill_node
from agent_graph.nodes.skill_resource_node import skill_resource_node
from agent_graph.nodes.supervisor_node import supervisor_node
from main import app
from tools import skill_installer_tool


def local_tmp_path():
    path = Path(__file__).resolve().parents[2] / ".pytest_tmp" / "graph_runtime" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_skill_with_resources(root, resource_count=5):
    skill_dir = root / "skills" / "imported" / "runtime_demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
skill_id: runtime_demo_skill
name: Runtime Demo Skill
description: Runtime skill for GraphCore integration tests.
enabled: true
triggers:
  - runtime trigger
---

# Runtime Demo Skill

## Instructions
- Read relevant resource files only.
""",
        encoding="utf-8",
    )
    for index in range(resource_count):
        (skill_dir / f"resource_{index}.md").write_text(
            f"runtime trigger evidence resource {index}\n" + ("x" * 4500),
            encoding="utf-8",
        )
    (skill_dir / "binary.bin").write_bytes(b"\x00\x01\x02")
    return skill_dir


def patch_skill_dirs(monkeypatch, tmp_path):
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_STATIC_SKILLS_DIR", tmp_path / "skills")
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_GENERATED_SKILLS_DIR", tmp_path / "generated_skills")


def test_response_prompt_loads_template_rules():
    prompt = _response_prompt({"user_message": "hello", "skill_resource_results": []})

    assert "strict JSON" in prompt
    assert "Do not expose root_dir" in prompt
    assert "Do not claim that Skill scripts were executed" in prompt
    assert "skill_resource_results" in prompt


def test_graph_chat_returns_agent_flow_and_skill_fields(monkeypatch):
    tmp_path = local_tmp_path()
    write_skill_with_resources(tmp_path, resource_count=1)
    patch_skill_dirs(monkeypatch, tmp_path)
    monkeypatch.setattr(SelfEvolutionCore, "load_active_skills", lambda self, message: [])

    result = GraphCore().chat("runtime trigger evidence", "runtime-test")

    assert result["agent_flow"]
    assert any(step["agent_name"] == "Skill Agent" for step in result["agent_flow"])
    assert result["active_skills"]
    assert result["skill_trace"]
    assert result["skill_resource_results"]
    assert [entry["tool_call"]["name"] for entry in result["tool_trace"]] == [
        "search_skill_resources",
        "read_skill_resource",
    ]


def test_chat_api_returns_skill_runtime_fields(monkeypatch):
    tmp_path = local_tmp_path()
    write_skill_with_resources(tmp_path, resource_count=1)
    patch_skill_dirs(monkeypatch, tmp_path)
    monkeypatch.setattr(SelfEvolutionCore, "load_active_skills", lambda self, message: [])

    response = TestClient(app).post("/chat", json={"message": "runtime trigger evidence", "session_id": "runtime-api"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_skills"]
    assert payload["skill_trace"]
    assert payload["skill_resource_results"]


def test_response_node_mock_mentions_skill_resource_file():
    class FakeLLM:
        mock_mode = True

    state = response_node(
        {
            "agent_flow": [],
            "skill_resource_results": [
                {"resource_path": "guide.md", "skill_name": "Runtime Demo Skill", "content": "resource backed answer"}
            ],
        },
        llm_client=FakeLLM(),
    )

    assert "guide.md" in state["final_reply"]
    assert "resource backed answer" in state["final_reply"]


def test_skill_resource_node_limits_reads_and_records_trace(monkeypatch):
    tmp_path = local_tmp_path()
    write_skill_with_resources(tmp_path, resource_count=5)
    patch_skill_dirs(monkeypatch, tmp_path)
    monkeypatch.setattr(SelfEvolutionCore, "load_active_skills", lambda self, message: [])
    state = skill_node({"user_message": "runtime trigger evidence", "agent_flow": [], "tool_trace": []})

    state = skill_resource_node(state)

    read_calls = [entry for entry in state["tool_trace"] if entry["tool_call"]["name"] == "read_skill_resource"]
    assert len(state["skill_resource_results"]) == 2
    assert len(read_calls) == len(state["skill_resource_results"])
    assert sum(len(item["content"]) for item in state["skill_resource_results"]) <= 12000
    assert all(not item["resource_path"].endswith(".bin") for item in state["skill_resource_results"])


def test_supervisor_does_not_route_plain_tool_word_to_tool_search():
    state = supervisor_node({"user_message": "Explain what a tool is in software design.", "agent_flow": []})

    assert state["route"] == "response"


def test_supervisor_routes_explicit_tool_discovery_and_url_and_image():
    assert supervisor_node({"user_message": "install a tool that reads web pages", "agent_flow": []})["route"] == "tool_search"
    assert supervisor_node({"user_message": "summarize https://example.com", "agent_flow": []})["route"] == "execute_tool"
    assert (
        supervisor_node({"user_message": "analyze this", "attachments": [{"type": "image"}], "agent_flow": []})["route"]
        == "multimodal"
    )
