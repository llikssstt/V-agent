import json
import re

from agent.llm_client import LLMClient
from agent_graph.nodes.common import flow_step
from agent_graph.task_runtime import TaskRuntime
from tool_system.manager import ToolManager
from tools.registry import AVAILABLE_TOOLS, get_tool_names


def planner_node(state):
    message = state.get("user_message", "")
    planner_result = _plan(message, state)
    state["planner_result"] = planner_result
    state["tool_intent"] = planner_result.get("tool_intent", {"name": "none", "arguments": {}})
    state["route"] = planner_result.get("route", state.get("route", "response"))
    state["current_task"] = planner_result.get("task_title", message)

    runtime = TaskRuntime()
    task = state.get("task") or runtime.create_task(state["current_task"], state.get("session_id", "default"))
    task = runtime.set_plan(task["task_id"], planner_result.get("steps", []), state["tool_intent"])
    state["task"] = task
    state["task_id"] = task["task_id"]
    state.setdefault("agent_flow", []).append(
        flow_step("Planner Agent", f"plan:{state['route']}", reason=planner_result.get("reason", "structured plan"))
    )
    return state


def _plan(message, state):
    llm_plan = _llm_plan(message, state)
    if llm_plan:
        return llm_plan
    return _rule_plan(message, state)


def _llm_plan(message, state):
    prompt = _planner_prompt()
    context = {
        "message": message,
        "route": state.get("route", "response"),
        "input_type": state.get("input_type", "text"),
        "attachments": state.get("attachments", []),
        "available_tools": AVAILABLE_TOOLS,
        "agent_flow": state.get("agent_flow", []),
    }
    try:
        raw = LLMClient().complete_json(prompt, stage="graph_planner", context=context)
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return None
    return _normalize_llm_plan(parsed)


def _normalize_llm_plan(parsed):
    if not isinstance(parsed, dict):
        return None
    task_title = str(parsed.get("task_title") or "").strip()
    route = str(parsed.get("route") or "").strip()
    steps = parsed.get("steps")
    if not task_title or route not in {"response", "execute_tool", "tool_search", "multimodal"} or not isinstance(steps, list):
        return None
    normalized_steps = []
    for index, step in enumerate(steps[:12], 1):
        if isinstance(step, str):
            title = step
            step_tool_intent = {"name": "none", "arguments": {}}
        elif isinstance(step, dict):
            title = step.get("title") or step.get("description") or f"Step {index}"
            step_tool_intent = _normalize_tool_intent(step.get("tool_intent"))
        else:
            title = f"Step {index}"
            step_tool_intent = {"name": "none", "arguments": {}}
        if route != "execute_tool":
            step_tool_intent = {"name": "none", "arguments": {}}
        elif not _is_allowed_tool_intent(step_tool_intent):
            return _result(
                task_title,
                "tool_search",
                f"Planner selected unavailable tool: {step_tool_intent.get('name')}",
                _strip_step_tools(normalized_steps) or [{"title": str(title)[:240], "tool_intent": {"name": "none", "arguments": {}}}],
                {"name": "none", "arguments": {}},
            )
        normalized_steps.append({"title": str(title)[:240], "tool_intent": step_tool_intent})
    if not normalized_steps:
        return None
    tool_intent = _first_step_tool_intent(normalized_steps) or _normalize_tool_intent(parsed.get("tool_intent"))
    if route != "execute_tool":
        tool_intent = {"name": "none", "arguments": {}}
    elif not _is_allowed_tool_intent(tool_intent):
        return _result(
            task_title,
            "tool_search",
            f"Planner selected unavailable tool: {tool_intent.get('name')}",
            normalized_steps,
            {"name": "none", "arguments": {}},
        )
    return _result(
        task_title,
        route,
        str(parsed.get("reason") or "LLM structured plan")[:500],
        normalized_steps,
        tool_intent,
    )


def _planner_prompt():
    installed_tools = _installed_tool_schemas()
    return (
        "You are LunaClaw's graph planner. Return strict JSON only.\n"
        "Plan the user request as a durable task for an autonomous Agent Runtime.\n"
        "Required JSON schema:\n"
        "{\n"
        '  "task_title": "short task title",\n'
        '  "route": "response | execute_tool | tool_search | multimodal",\n'
        '  "reason": "why this route and plan were chosen",\n'
        '  "steps": [{"title": "durable step title", "tool_intent": {"name": "tool name or none", "arguments": {}}}],\n'
        '  "tool_intent": {"name": "first non-none step tool name or none", "arguments": {}}\n'
        "}\n"
        "Every step must include its own tool_intent. Use name=none for reasoning or response-only steps. "
        "Use route=execute_tool only when a tool should run now. Use route=tool_search only for explicit tool discovery/install needs. "
        "Use route=multimodal for image attachments. Otherwise use response. "
        f"Available built-in tools: {json.dumps(AVAILABLE_TOOLS, ensure_ascii=False)}\n"
        f"Enabled installed tools: {json.dumps(installed_tools, ensure_ascii=False)}"
    )


def _is_allowed_tool_intent(tool_intent):
    name = (tool_intent or {}).get("name", "none")
    if not name or name == "none":
        return True
    if "." not in name:
        return name in set(get_tool_names())
    tool_id, function_name = name.split(".", 1)
    for tool in ToolManager().list_installed_tools():
        if tool.get("tool_id") != tool_id or tool.get("enabled") is False:
            continue
        for spec in tool.get("tools", []):
            if spec.get("name") == function_name:
                return True
    return False


def _normalize_tool_intent(tool_intent):
    if not isinstance(tool_intent, dict):
        return {"name": "none", "arguments": {}}
    return {
        "name": str(tool_intent.get("name") or "none"),
        "arguments": tool_intent.get("arguments") if isinstance(tool_intent.get("arguments"), dict) else {},
    }


def _first_step_tool_intent(steps):
    for step in steps or []:
        tool_intent = _normalize_tool_intent(step.get("tool_intent"))
        if tool_intent.get("name") != "none":
            return tool_intent
    return None


def _strip_step_tools(steps):
    return [
        {"title": step.get("title") or f"Step {index}", "tool_intent": {"name": "none", "arguments": {}}}
        for index, step in enumerate(steps or [], 1)
    ]


def _installed_tool_schemas():
    schemas = []
    try:
        installed = ToolManager().list_installed_tools()
    except Exception:
        return schemas
    for tool in installed:
        if tool.get("enabled") is False:
            continue
        for spec in tool.get("tools", []):
            name = spec.get("name")
            if name:
                schemas.append(
                    {
                        "name": f"{tool.get('tool_id')}.{name}",
                        "description": spec.get("description") or tool.get("description", ""),
                        "arguments": spec.get("input_schema") or spec.get("arguments", {}),
                    }
                )
    return schemas


def _rule_plan(message, state):
    if state.get("route") == "multimodal":
        return _result("Analyze uploaded image", "multimodal", "image attachment detected", [{"title": "Analyze image input"}])
    lower = str(message or "").lower()
    expression = _extract_expression(message)
    if expression:
        tool_intent = {"name": "calculator", "arguments": {"expression": expression}}
        return _result(
            "Calculate expression",
            "execute_tool",
            "calculation request",
            [
                {"title": "Parse expression", "tool_intent": {"name": "none", "arguments": {}}},
                {"title": "Run calculator", "tool_intent": tool_intent},
                {"title": "Explain result", "tool_intent": {"name": "none", "arguments": {}}},
            ],
            tool_intent,
        )
    if "web_reader" in lower:
        url_match = re.search(r"https?://\S+", message)
        tool_intent = {"name": "web_reader.fetch_page", "arguments": {"url": url_match.group(0).rstrip(".,)") if url_match else ""}}
        return _result(
            "Read web page with web_reader",
            "execute_tool",
            "explicit installed web_reader request",
            [
                {"title": "Extract URL", "tool_intent": {"name": "none", "arguments": {}}},
                {"title": "Run web_reader", "tool_intent": tool_intent},
                {"title": "Summarize result", "tool_intent": {"name": "none", "arguments": {}}},
            ],
            tool_intent,
        )
    if re.search(r"https?://", message):
        url_match = re.search(r"https?://\S+", message)
        tool_intent = {"name": "web_fetch", "arguments": {"url": url_match.group(0).rstrip(".,)") if url_match else ""}}
        return _result(
            "Read web page",
            "execute_tool",
            "URL/tool execution request",
            [
                {"title": "Extract URL", "tool_intent": {"name": "none", "arguments": {}}},
                {"title": "Run web fetch tool", "tool_intent": tool_intent},
                {"title": "Summarize result", "tool_intent": {"name": "none", "arguments": {}}},
            ],
            tool_intent,
        )
    if state.get("route") == "tool_search":
        return _result("Find installable tool", "tool_search", "tool discovery request", [{"title": "Search tool market"}, {"title": "Review permissions"}])
    return _result("Answer user request", "response", "no tool required", [{"title": "Review context"}, {"title": "Compose response"}])


def _result(task_title, route, reason, steps, tool_intent=None):
    return {
        "task_title": task_title,
        "route": route,
        "reason": reason,
        "steps": steps,
        "tool_intent": tool_intent or {"name": "none", "arguments": {}},
    }


def _extract_expression(message):
    matches = re.findall(r"[0-9][0-9\.\s\+\-\*\/\(\)]{1,}[0-9\)]", str(message or ""))
    return matches[0].strip() if matches else ""
