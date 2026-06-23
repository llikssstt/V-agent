import argparse
import json
import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from agent.agent_core import AgentCore
from agent.llm_client import LLMClient
from agent.memory import MemoryStore


def run_checks(use_real_api=False):
    if not use_real_api:
        os.environ["DISABLE_DOTENV_LOAD"] = "1"
        os.environ.pop("LLM_API_KEY", None)

    run_dir = ROOT / ".integration_tmp"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)

    client = LLMClient()
    agent = AgentCore(
        llm_client=client,
        memory_store=MemoryStore(run_dir / "memory.json"),
        conversations_path=run_dir / "conversations.json",
    )

    cases = [
        ("task_planning", "帮我安排今晚两小时完成课程报告。"),
        ("calculator_tool", "帮我计算 2 * (3 + 4)。"),
        ("todo_tool", "帮我添加一个待办：完成 NLP 报告。"),
        ("memory_write", "记住我最近在做 NLP 课程陪伴 Agent。"),
        ("memory_read", "你还记得我最近在做什么吗？"),
    ]

    results = []
    for name, message in cases:
        before = len(client.call_sources)
        response = agent.chat(message, session_id="module-check")
        results.append(
            {
                "case": name,
                "message": message,
                "reply_preview": response["reply"][:120],
                "emotion": response["emotion"],
                "tool_used": response["tool_used"],
                "memory_action": response["memory_action"],
                "skills_used": response["skills_used"],
                "call_sources": client.call_sources[before:],
            }
        )

    return {
        "mode": "real_api" if use_real_api else "mock",
        "api_key_present": bool(client.api_key),
        "base_url": client.base_url,
        "model": client.model,
        "results": results,
        "memory_count": len(agent.memory.list_memories()),
        "memory_items": agent.memory.list_memories(),
    }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-api", action="store_true", help="Use backend/.env or process env to call the configured external LLM API.")
    args = parser.parse_args()
    print(json.dumps(run_checks(use_real_api=args.real_api), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
