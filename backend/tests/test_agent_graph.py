import uuid
from pathlib import Path

from agent.self_evolution import SelfEvolutionCore
from agent.skill_registry import SkillRegistry
from agent_graph.graph import GraphCore
from agent_graph import uploads
from tool_system import installer, registry_store
from tool_system.installer import approve_install, install_tool
from tools import skill_installer_tool


def local_tmp_path():
    path = Path(__file__).resolve().parents[2] / ".pytest_tmp" / "agent_graph_contract" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def isolate_tool_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(registry_store, "DEFAULT_REGISTRY_PATH", tmp_path / "installed_tools.json")
    monkeypatch.setattr(installer, "APPROVALS_PATH", tmp_path / "approvals.json")
    monkeypatch.setattr(installer, "INSTALLED_TOOLS_DIR", tmp_path / "installed_tool_packages")


def write_imported_skill(root, trigger="graph skill", resource_text="graph resource answer"):
    skill_dir = root / "skills" / "imported" / "graph_demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"""---
skill_id: graph_demo_skill
name: Graph Demo Skill
description: Skill used by GraphCore tests.
enabled: true
triggers:
  - {trigger}
---

# Graph Demo Skill

## Instructions
- Use the resource note when relevant.
""",
        encoding="utf-8",
    )
    (skill_dir / "notes.md").write_text(resource_text, encoding="utf-8")
    return skill_dir


class FakeResponse:
    text = "<html><title>Example</title><body>Hello graph execution.</body></html>"

    def raise_for_status(self):
        return None


def test_graph_chat_returns_compatible_fields_and_uses_langgraph():
    core = GraphCore()
    result = core.chat("hello", "test")

    for key in ["reply", "emotion", "tool_used", "tool_trace", "sources", "agent_flow", "active_skills"]:
        assert key in result
    assert result["agent_flow"][0]["agent_name"] == "Supervisor Agent"
    assert hasattr(core.graph, "invoke")
    assert core.graph.__class__.__name__ == "CompiledStateGraph"


def test_install_request_routes_to_tool_search_and_security(monkeypatch):
    tmp_path = local_tmp_path()
    isolate_tool_storage(monkeypatch, tmp_path)

    result = GraphCore().chat("install a tool that can read web pages", "test")

    assert result["approval_required"] is True
    assert result["approval_id"].startswith("approval_")
    assert any(step["agent_name"] == "Tool Search Agent" for step in result["agent_flow"])
    assert any(step["agent_name"] == "Security Review Agent" for step in result["agent_flow"])


def test_installed_tool_execution_adds_tool_trace(monkeypatch):
    tmp_path = local_tmp_path()
    isolate_tool_storage(monkeypatch, tmp_path)
    pending = install_tool("web_reader", "market")
    approve_install(pending["approval_id"], True)
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: FakeResponse())

    result = GraphCore().chat("use web_reader to summarize this page: https://example.com", "test")

    assert result["tool_used"] == "web_reader.fetch_page"
    assert result["tool_trace"][0]["tool_call"]["name"] == "web_reader.fetch_page"
    assert result["sources"][0]["url"] == "https://example.com"


def test_image_attachment_goes_through_multimodal_node(monkeypatch):
    tmp_path = local_tmp_path()
    image_path = tmp_path / "shot.png"
    image_path.write_bytes(b"fake image")
    monkeypatch.setattr(uploads, "DEFAULT_UPLOADS_INDEX_PATH", tmp_path / "uploads_index.json")
    uploads.register_upload(
        {
            "file_id": "img_1",
            "filename": "shot.png",
            "content_type": "image/png",
            "size": image_path.stat().st_size,
            "path": str(image_path),
            "type": "image",
        }
    )

    result = GraphCore().chat(
        "analyze this uploaded image",
        "test",
        attachments=[{"type": "image", "file_id": "img_1", "filename": "shot.png"}],
    )

    assert any(step["agent_name"] == "Multimodal Agent" for step in result["agent_flow"])
    assert "shot.png" in result["reply"]


def test_graph_chat_returns_skill_agent_fields(monkeypatch):
    fake_skill = {
        "skill_id": "fake_skill",
        "name": "Fake Skill",
        "description": "Fake skill from registry",
        "enabled": True,
        "triggers": ["fake trigger"],
        "path": "fake.md",
    }
    evolved_skill = {
        "skill_id": "evolved_skill",
        "name": "Evolved Skill",
        "strategy_summary": "Use evolved evidence.",
        "description": "Evolved from repeated use.",
        "enabled": True,
        "evidence_count": 3,
    }
    monkeypatch.setattr(SkillRegistry, "match", lambda self, message: [fake_skill])
    monkeypatch.setattr(SkillRegistry, "build_context", lambda self, skills: "registry context")
    monkeypatch.setattr(SelfEvolutionCore, "load_active_skills", lambda self, message: [evolved_skill])
    evolution_context_calls = []

    def fake_evolution_context(self, skills):
        evolution_context_calls.append(skills)
        return "evolved context"

    monkeypatch.setattr(SelfEvolutionCore, "build_skill_context", fake_evolution_context)

    result = GraphCore().chat("please use fake trigger", "skill-agent-test")

    assert any(step["agent_name"] == "Skill Agent" for step in result["agent_flow"])
    assert result["active_skills"]
    assert result["skills_used"]
    assert result["skill_trace"]
    assert evolution_context_calls and evolution_context_calls[0][0]["skill_id"] == "evolved_skill"


def test_graph_chat_loads_skill_resource_results(monkeypatch):
    tmp_path = local_tmp_path()
    write_imported_skill(tmp_path, trigger="resource trigger", resource_text="resource trigger evidence")
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_STATIC_SKILLS_DIR", tmp_path / "skills")
    monkeypatch.setattr(skill_installer_tool, "DEFAULT_GENERATED_SKILLS_DIR", tmp_path / "generated_skills")
    monkeypatch.setattr(SelfEvolutionCore, "load_active_skills", lambda self, message: [])

    result = GraphCore().chat("resource trigger evidence", "skill-resource-test")

    assert any(step["agent_name"] == "Skill Resource Agent" for step in result["agent_flow"])
    assert result["skill_resource_results"]
    assert result["skill_resource_results"][0]["resource_path"] == "notes.md"
