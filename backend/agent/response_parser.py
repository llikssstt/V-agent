import json

from agent.emotion import normalize_emotion, normalize_memory_action, normalize_tool


FALLBACK_RESPONSE = {
    "reply": "我这边刚才有点卡壳了，但我还在。你可以再说一遍，我继续接住。",
    "emotion": "thinking",
    "tool_used": "none",
    "skills_used": ["persona_skill"],
    "memory_action": "none",
}


DEFAULT_PLANNER = {
    "intent": "日常聊天",
    "emotion": "neutral",
    "skills_used": ["persona_skill", "chat_skill"],
    "memory_action": "none",
    "memory_query": "",
    "memory_to_write": {"content": "", "category": "user_profile", "importance": 1},
    "memory_delete_query": "",
    "tool_call": {"name": "none", "arguments": {}},
}


def _loads_json(value):
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        raise ValueError("LLM output is not JSON text")
    text = value.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def parse_planner(value):
    try:
        data = {**DEFAULT_PLANNER, **_loads_json(value)}
    except Exception:
        return DEFAULT_PLANNER.copy()
    data["emotion"] = normalize_emotion(data.get("emotion"))
    data["memory_action"] = normalize_memory_action(data.get("memory_action"))
    tool_call = data.get("tool_call") if isinstance(data.get("tool_call"), dict) else {"name": "none", "arguments": {}}
    tool_call["name"] = normalize_tool(tool_call.get("name"))
    tool_call["arguments"] = tool_call.get("arguments") if isinstance(tool_call.get("arguments"), dict) else {}
    data["tool_call"] = tool_call
    if not isinstance(data.get("skills_used"), list):
        data["skills_used"] = ["persona_skill"]
    if not isinstance(data.get("memory_to_write"), dict):
        data["memory_to_write"] = DEFAULT_PLANNER["memory_to_write"]
    return data


def parse_responder(value):
    try:
        data = {**FALLBACK_RESPONSE, **_loads_json(value)}
    except Exception:
        return FALLBACK_RESPONSE.copy()
    data["reply"] = str(data.get("reply") or FALLBACK_RESPONSE["reply"]).strip()
    data["emotion"] = normalize_emotion(data.get("emotion"))
    data["tool_used"] = normalize_tool(data.get("tool_used"))
    data["memory_action"] = normalize_memory_action(data.get("memory_action"))
    if not isinstance(data.get("skills_used"), list):
        data["skills_used"] = ["persona_skill"]
    return {
        "reply": data["reply"],
        "emotion": data["emotion"],
        "tool_used": data["tool_used"],
        "skills_used": data["skills_used"],
        "memory_action": data["memory_action"],
    }

