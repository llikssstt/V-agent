import json
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from agent.agent_core import AgentCore
from agent.memory_core import MemoryCore
from agent.self_evolution import SelfEvolutionCore
from main import app


class FakeEmbedder:
    def encode(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]


class ReflectionLLM:
    def __init__(self):
        self.calls = []

    def complete_json(self, prompt, stage, context):
        self.calls.append({"stage": stage, "context": context})
        if stage == "planner":
            return json.dumps(
                {
                    "intent": "学习压力陪伴",
                    "emotion": "thinking",
                    "skills_used": ["persona_skill", "chat_skill"],
                    "memory_action": "none",
                    "memory_query": "",
                    "memory_to_write": {"content": "", "category": "user_profile", "importance": 1},
                    "memory_delete_query": "",
                    "tool_call": {"name": "none", "arguments": {}},
                },
                ensure_ascii=False,
            )
        if stage == "responder":
            return json.dumps(
                {
                    "reply": "先把任务拆成一个 10 分钟小动作，我陪你推进第一步。",
                    "emotion": "thinking",
                    "tool_used": "none",
                    "skills_used": ["persona_skill", "chat_skill"],
                    "memory_action": "none",
                },
                ensure_ascii=False,
            )
        if stage == "evolution_reflection":
            return json.dumps(
                {
                    "events": [
                        {
                            "type": "preference_learned",
                            "summary": "用户在学习压力下更适合先拆一个 10 分钟小动作。",
                            "target_type": "preference",
                        }
                    ],
                    "preference_updates": {"planning_style": "先拆 10 分钟小动作"},
                    "memory_updates": [
                        {
                            "content": "用户在学习压力下更适合先拆一个 10 分钟小动作",
                            "category": "interaction_style",
                            "importance": 0.8,
                        }
                    ],
                    "scenario": "学习压力",
                    "strategy_summary": "先共情，再拆成一个 10 分钟小动作",
                    "skill_candidate": {
                        "name": "study_pressure_micro_step",
                        "description": "用户学习压力较大时，先共情再给一个 10 分钟小动作。",
                        "trigger_examples": ["不想学了", "压力好大", "想摆烂"],
                        "instructions": ["先承认压力", "只给一个可以立刻开始的小动作"],
                    },
                    "confidence": 0.9,
                    "reason": "用户表达学习压力，回复中的小步推进策略有效。",
                },
                ensure_ascii=False,
            )
        raise AssertionError(stage)


def local_tmp_path():
    path = Path(__file__).resolve().parents[2] / ".pytest_tmp" / "self_evolution" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_reflection_updates_state_logs_memory_and_generates_skill_after_threshold():
    tmp_path = local_tmp_path()
    llm = ReflectionLLM()
    memory = MemoryCore(tmp_path / "storage", embedder=FakeEmbedder())
    evolution = SelfEvolutionCore(tmp_path / "storage", tmp_path / "generated_skills", llm, memory)

    for _ in range(3):
        result = evolution.reflect_after_turn(
            user_message="我压力好大，不想学了",
            assistant_reply="先把任务拆成一个 10 分钟小动作。",
            retrieved_memories=[],
            active_skills=[],
        )

    state = evolution.read_state()
    skills = evolution.list_skills()
    logs = evolution.list_logs()

    assert result["evolution_events"]
    assert result["evolution_summary"] == "学习压力：先共情，再拆成一个 10 分钟小动作"
    assert state["preferences"]["planning_style"] == "先拆 10 分钟小动作"
    assert state["scenario_counts"]["学习压力::先共情，再拆成一个 10 分钟小动作"] == 3
    assert skills[0]["enabled"] is True
    assert skills[0]["evidence_count"] == 3
    assert any(entry["target_type"] == "skill" and entry["result"] == "success" for entry in logs)
    assert memory.list_memories()


def test_sensitive_reflection_memory_and_skill_are_skipped():
    tmp_path = local_tmp_path()
    class SensitiveLLM(ReflectionLLM):
        def complete_json(self, prompt, stage, context):
            if stage != "evolution_reflection":
                return super().complete_json(prompt, stage, context)
            return json.dumps(
                {
                    "events": [{"type": "memory_update", "summary": "敏感信息", "target_type": "memory"}],
                    "preference_updates": {},
                    "memory_updates": [{"content": "用户银行卡密码是 123456", "category": "user_profile", "importance": 1}],
                    "scenario": "敏感信息",
                    "strategy_summary": "不要保存敏感信息",
                    "skill_candidate": {"name": "secret_skill", "instructions": ["记住用户密码"]},
                    "confidence": 0.95,
                    "reason": "测试敏感过滤",
                },
                ensure_ascii=False,
            )

    memory = MemoryCore(tmp_path / "storage", embedder=FakeEmbedder())
    evolution = SelfEvolutionCore(tmp_path / "storage", tmp_path / "generated_skills", SensitiveLLM(), memory)

    result = evolution.reflect_after_turn("记住我的银行卡密码", "我不能保存敏感信息。")

    assert result["evolution_events"] == []
    assert memory.list_memories() == []
    assert evolution.list_skills() == []
    assert evolution.list_logs()[-1]["result"] == "skipped"


def test_rollback_restores_state_and_disables_generated_skill():
    tmp_path = local_tmp_path()
    llm = ReflectionLLM()
    memory = MemoryCore(tmp_path / "storage", embedder=FakeEmbedder())
    evolution = SelfEvolutionCore(tmp_path / "storage", tmp_path / "generated_skills", llm, memory)
    for _ in range(3):
        evolution.reflect_after_turn("我压力好大", "先做 10 分钟。")

    skill_operation = next(entry for entry in evolution.list_logs() if entry["target_type"] == "skill")
    rollback = evolution.rollback(skill_operation["operation_id"])

    assert rollback["result"] == "success"
    assert evolution.list_skills()[0]["enabled"] is False
    assert evolution.list_logs()[-1]["operation"] == "rollback"


def test_agent_chat_returns_evolution_fields_and_loads_active_skills():
    tmp_path = local_tmp_path()
    llm = ReflectionLLM()
    memory = MemoryCore(tmp_path / "storage", embedder=FakeEmbedder())
    evolution = SelfEvolutionCore(tmp_path / "storage", tmp_path / "generated_skills", llm, memory)
    for _ in range(3):
        evolution.reflect_after_turn("我压力好大", "先做 10 分钟。")
    agent = AgentCore(llm_client=llm, memory_core=memory, evolution_core=evolution, conversations_path=tmp_path / "conversations.json")

    response = agent.chat("我今天压力好大，想摆烂", session_id="evo-chat")

    assert response["active_skills"]
    assert response["evolution_events"]
    assert response["evolution_summary"]
    assert any(call["stage"] == "evolution_reflection" for call in llm.calls)


def test_evolution_api_lists_logs_skills_and_rolls_back():
    client = TestClient(app)

    chat = client.post("/chat", json={"message": "我压力好大，想摆烂", "session_id": "api-evo"})
    assert chat.status_code == 200
    assert {"evolution_events", "active_skills", "evolution_summary"}.issubset(chat.json())

    logs = client.get("/evolution/logs")
    assert logs.status_code == 200
    assert isinstance(logs.json(), list)

    skills = client.get("/evolution/skills")
    assert skills.status_code == 200
    assert isinstance(skills.json(), list)
