import re

from agent_graph.nodes.common import flow_step


def supervisor_node(state):
    message = state.get("user_message", "")
    lower = message.lower()
    route = "response"
    reason = "general response"
    if any(item.get("type") == "image" for item in state.get("attachments", [])):
        route = "multimodal"
        reason = "image attachment detected"
    elif "web_reader" in lower or re.search(r"https?://", message):
        route = "execute_tool"
        reason = "installed tool execution requested"
    elif _is_tool_discovery_request(lower):
        route = "tool_search"
        reason = "tool discovery or install requested"
    state["route"] = route
    state.setdefault("agent_flow", []).append(flow_step("Supervisor Agent", f"route:{route}", reason=reason))
    return state


def _is_tool_discovery_request(lower):
    explicit_phrases = [
        "install tool",
        "install a tool",
        "install an agent tool",
        "find a tool",
        "find tool",
        "tool that can",
        "need a tool",
        "need something that can",
        "add a tool",
        "安装工具",
        "安装一个工具",
        "找工具",
        "需要一个工具",
        "需要一个能",
    ]
    return any(phrase in lower for phrase in explicit_phrases)
