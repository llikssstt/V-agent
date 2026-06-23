from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent.agent_core import AgentCore
from agent.memory_core import MemoryCore
from agent.memory_prompt_builder import build_memory_context
from agent.memory_retriever import MemoryRetriever
from agent.memory_router import route_memory_intent
from main import app


class FakeEmbedder:
    def encode(self, texts):
        vectors = []
        for text in texts:
            lower = text.lower()
            if any(token in lower for token in ["报告", "大作业", "nlp", "project"]):
                vectors.append([1.0, 0.0, 0.0])
            elif any(token in lower for token in ["直接", "简洁", "风格", "style"]):
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return vectors


def tmp_store():
    path = Path(__file__).resolve().parents[2] / ".pytest_tmp" / "memory_rag"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_memory_router_detects_crud_intents():
    assert route_memory_intent("记住我最近在做 NLP 大作业")["memory_intent"] == "write"
    assert route_memory_intent("你还记得我最近在做什么项目吗？")["memory_intent"] == "retrieve"
    assert route_memory_intent("我现在不做问答 Agent 了，改成陪伴 Agent")["memory_intent"] == "update"
    assert route_memory_intent("忘记我最近在做的项目")["memory_intent"] == "delete"


def test_semantic_retriever_matches_related_meaning_without_keyword_overlap(tmp_path):
    core = MemoryCore(tmp_path, embedder=FakeEmbedder())
    project = core.write_memory(
        content="用户正在准备自然语言处理课程报告",
        category="project",
        importance=0.9,
        source="user_explicit",
    )
    core.write_memory(
        content="用户喜欢回答直接一点，不要太啰嗦",
        category="interaction_style",
        importance=0.8,
        source="user_explicit",
    )

    result = MemoryRetriever(core).retrieve("今晚怎么推进 NLP 大作业？", top_k=2)

    assert result["memories"][0]["memory_id"] == project["memory_id"]
    assert result["memories"][0]["score"] > 0


def test_memory_core_updates_soft_deletes_and_logs(tmp_path):
    core = MemoryCore(tmp_path, embedder=FakeEmbedder())
    memory = core.write_memory("用户正在做课程问答 Agent", "project", 0.8, "user_explicit")

    updated = core.update_memory(memory["memory_id"], content="用户正在做 LunaClaw 陪伴 Agent")
    deleted = core.delete_memory(memory["memory_id"])
    active = core.list_memories()
    logs = core.list_logs()

    assert updated["content"] == "用户正在做 LunaClaw 陪伴 Agent"
    assert deleted["status"] == "inactive"
    assert active == []
    assert [entry["operation"] for entry in logs][-2:] == ["update", "delete"]


def test_sensitive_memory_is_filtered_and_logged(tmp_path):
    core = MemoryCore(tmp_path, embedder=FakeEmbedder())

    with pytest.raises(ValueError):
        core.write_memory("我的银行卡密码是 123456", "user_profile", 1.0, "user_explicit")

    assert core.list_memories() == []
    assert core.list_logs()[-1]["result"] == "skipped"


def test_conversation_memory_is_searchable(tmp_path):
    core = MemoryCore(tmp_path, embedder=FakeEmbedder())
    core.save_conversation_turn("s1", "user", "我之前问过 Hermes Agent 的记忆机制")
    core.save_conversation_turn("s1", "assistant", "你问的是 Memory Providers。")

    result = MemoryRetriever(core).retrieve("我之前是不是问过 Hermes 的记忆？", top_k=3)

    assert result["conversation_hits"]
    assert "Hermes" in result["conversation_hits"][0]["content"]


def test_memory_prompt_builder_limits_and_formats_context(tmp_path):
    core = MemoryCore(tmp_path, embedder=FakeEmbedder())
    core.write_memory("用户正在准备 NLP 课程报告", "project", 0.9, "user_explicit")
    retrieved = MemoryRetriever(core).retrieve("报告怎么安排？")

    context = build_memory_context(retrieved)

    assert "相关长期记忆" in context
    assert "NLP 课程报告" in context


def test_memory_api_crud_and_search():
    client = TestClient(app)

    created = client.post(
        "/memory",
        json={"content": "用户正在准备 NLP 课程报告", "category": "project", "importance": 0.9},
    )
    assert created.status_code == 200
    memory_id = created.json()["memory_id"]

    search = client.get("/memory/search", params={"query": "今晚怎么推进课程大作业？"})
    assert search.status_code == 200
    assert "memories" in search.json()

    updated = client.put(f"/memory/{memory_id}", json={"content": "用户正在准备 LunaClaw 课程报告"})
    assert updated.status_code == 200
    assert updated.json()["content"] == "用户正在准备 LunaClaw 课程报告"

    deleted = client.delete(f"/memory/{memory_id}")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "inactive"

    logs = client.get("/memory/logs")
    assert logs.status_code == 200
    assert isinstance(logs.json(), list)


def test_agent_core_returns_retrieved_memories_and_saves_sqlite_history(tmp_path):
    core = MemoryCore(tmp_path, embedder=FakeEmbedder())
    core.write_memory("用户正在准备自然语言处理课程报告", "project", 0.9, "user_explicit")
    agent = AgentCore(memory_core=core)

    response = agent.chat("今晚怎么推进 NLP 大作业？", session_id="rag-chat")
    history_hits = core.search_conversations("NLP 大作业", top_k=5)

    assert "retrieved_memories" in response
    assert response["retrieved_memories"][0]["category"] == "project"
    assert history_hits
