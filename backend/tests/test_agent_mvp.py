import os
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from agent.env_loader import load_env_file
from agent.llm_client import LLMClient
from agent.memory import MemoryStore
from main import app
from tools.calculator_tool import calculate
from tools.registry import get_tool_names
from tools.study_plan_tool import generate_study_plan
from tools.todo_tool import TodoStore


def local_tmp_path():
    path = Path(__file__).resolve().parents[2] / ".pytest_tmp" / str(uuid.uuid4())
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_load_env_file_sets_missing_values(monkeypatch):
    tmp_path = local_tmp_path()
    monkeypatch.delenv("DISABLE_DOTENV_LOAD", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    backend_dir = tmp_path / "backend"
    agent_file = backend_dir / "agent" / "llm_client.py"
    agent_file.parent.mkdir(parents=True)
    agent_file.write_text("", encoding="utf-8")
    env_path = backend_dir / ".env"
    env_path.write_text("LLM_API_KEY=test-from-env\nLLM_MODEL=test-model\n", encoding="utf-8")

    loaded = load_env_file(agent_file)

    assert "LLM_API_KEY" in loaded
    assert os.environ["LLM_API_KEY"] == "test-from-env"


def test_health_returns_ok():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_mock_returns_required_fields():
    client = TestClient(app)

    response = client.post("/chat", json={"message": "你好呀，你是谁？", "session_id": "test"})

    assert response.status_code == 200
    data = response.json()
    assert {"reply", "emotion", "tool_used", "skills_used", "memory_action", "retrieved_memories", "evolution_events", "active_skills", "evolution_summary"}.issubset(data)
    assert data["reply"]
    assert data["emotion"] in {"neutral", "happy", "sad", "thinking", "surprised", "serious"}
    assert data["tool_used"] in {"none", *get_tool_names()}
    assert data["memory_action"] in {"none", "read", "write", "delete"}
    assert isinstance(data["skills_used"], list)
    assert isinstance(data["retrieved_memories"], list)
    assert isinstance(data["evolution_events"], list)
    assert isinstance(data["active_skills"], list)


def test_llm_client_falls_back_to_mock_when_real_api_fails(monkeypatch):
    def fail_post(*args, **kwargs):
        raise RuntimeError("network unavailable")

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr("agent.llm_client.requests.post", fail_post)
    client = LLMClient()

    output = client.complete_json("", "planner", {"message": "你好呀，你是谁？"})

    assert "自我介绍" in output
    assert client.call_sources[-1] == {"stage": "planner", "source": "fallback_mock"}


def test_memory_store_write_retrieve_delete():
    tmp_path = local_tmp_path()
    store = MemoryStore(tmp_path / "memory.json")

    memory = store.write_memory("用户最近在做 NLP 课程陪伴 Agent", "project", 4, "user")
    matches = store.retrieve_memory("NLP Agent")

    assert matches[0]["memory_id"] == memory["memory_id"]
    assert store.delete_memory(memory["memory_id"]) is True
    assert store.list_memories() == []


def test_memory_store_retrieves_project_from_natural_chinese_question():
    tmp_path = local_tmp_path()
    store = MemoryStore(tmp_path / "memory.json")

    memory = store.write_memory("我最近在做 NLP 课程陪伴 Agent", "project", 4, "user")
    matches = store.retrieve_memory("你还记得我最近在做什么吗？")

    assert matches[0]["memory_id"] == memory["memory_id"]


def test_calculator_allows_arithmetic_and_rejects_code():
    assert calculate("2 * (3 + 4)")["result"] == 14

    blocked = calculate("__import__('os').system('echo bad')")

    assert blocked["ok"] is False


def test_todo_store_adds_and_lists_items():
    tmp_path = local_tmp_path()
    store = TodoStore(tmp_path / "todos.json")

    added = store.add("完成 NLP 课程报告")
    items = store.list()

    assert added["content"] == "完成 NLP 课程报告"
    assert items[0]["todo_id"] == added["todo_id"]


def test_study_plan_generates_steps():
    plan = generate_study_plan("完成课程报告", "2小时")

    assert plan["ok"] is True
    assert "完成课程报告" in plan["plan"]
    assert len(plan["steps"]) >= 3
