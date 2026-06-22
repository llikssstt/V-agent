from fastapi.testclient import TestClient
from pathlib import Path
import uuid

from agent.memory import MemoryStore
from main import app
from tools.calculator_tool import calculate
from tools.study_plan_tool import generate_study_plan
from tools.todo_tool import TodoStore
from agent.llm_client import LLMClient


def local_tmp_path():
    path = Path(__file__).resolve().parents[2] / ".pytest_tmp" / str(uuid.uuid4())
    path.mkdir(parents=True, exist_ok=True)
    return path


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
    assert set(data) == {"reply", "emotion", "tool_used", "skills_used", "memory_action"}
    assert data["reply"]
    assert data["emotion"] in {"neutral", "happy", "sad", "thinking", "surprised", "serious"}
    assert data["tool_used"] in {"none", "time", "calculator", "todo", "study_plan"}
    assert data["memory_action"] in {"none", "read", "write", "delete"}
    assert isinstance(data["skills_used"], list)


def test_llm_client_falls_back_to_mock_when_real_api_fails(monkeypatch):
    def fail_post(*args, **kwargs):
        raise RuntimeError("network unavailable")

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr("agent.llm_client.requests.post", fail_post)
    client = LLMClient()

    output = client.complete_json("", "planner", {"message": "你好呀，你是谁？"})

    assert "自我介绍" in output


def test_memory_store_write_retrieve_delete():
    tmp_path = local_tmp_path()
    store = MemoryStore(tmp_path / "memory.json")

    memory = store.write_memory("用户最近在做 Live2D 虚拟陪伴 Agent", "project", 4, "user")
    matches = store.retrieve_memory("Live2D Agent")

    assert matches[0]["memory_id"] == memory["memory_id"]
    assert store.delete_memory(memory["memory_id"]) is True
    assert store.list_memories() == []


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
