import json

from agent.persona import PERSONA_PROMPT
from tools.tool_executor import AVAILABLE_TOOLS


def build_planner_prompt(message, history, memories):
    return f"""
{PERSONA_PROMPT}

你是 Planner LLM。请只返回 JSON，不要输出解释。

用户输入：
{message}

短期上下文：
{json.dumps(history[-8:], ensure_ascii=False)}

长期记忆摘要：
{json.dumps(memories[:8], ensure_ascii=False)}

可用工具：
{json.dumps(AVAILABLE_TOOLS, ensure_ascii=False)}

返回格式：
{{
  "intent": "用户意图简述",
  "emotion": "neutral | happy | sad | thinking | surprised | serious",
  "skills_used": ["persona_skill", "chat_skill"],
  "memory_action": "none | read | write | delete",
  "memory_query": "",
  "memory_to_write": {{"content": "", "category": "user_profile | preference | project | todo | learning_goal", "importance": 1}},
  "memory_delete_query": "",
  "tool_call": {{"name": "none | time | calculator | todo | study_plan", "arguments": {{}}}}
}}
"""


def build_responder_prompt(message, history, planner, memory_result, tool_result):
    return f"""
{PERSONA_PROMPT}

你是 Responder LLM。请结合上下文、Planner 决策、工具结果和记忆结果，返回最终 JSON。

用户输入：
{message}

短期上下文：
{json.dumps(history[-8:], ensure_ascii=False)}

Planner:
{json.dumps(planner, ensure_ascii=False)}

记忆结果：
{json.dumps(memory_result, ensure_ascii=False)}

工具结果：
{json.dumps(tool_result, ensure_ascii=False)}

返回格式：
{{
  "reply": "给用户看的自然语言回复",
  "emotion": "neutral | happy | sad | thinking | surprised | serious",
  "tool_used": "none | time | calculator | todo | study_plan",
  "skills_used": ["persona_skill", "chat_skill"],
  "memory_action": "none | read | write | delete"
}}
"""

