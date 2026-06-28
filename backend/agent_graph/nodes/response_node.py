import json

from agent.llm_client import LLMClient
from agent.response_parser import parse_responder
from agent_graph.nodes.common import flow_step
from agent_graph.prompt_loader import load_prompt


def response_node(state, llm_client=None):
    llm = llm_client or LLMClient()
    if llm.mock_mode:
        response = _mock_response(state)
    else:
        response = parse_responder(
            llm.complete_json(
                _response_prompt(state),
                "responder",
                _response_context(state),
            )
        )
    state["final_reply"] = response.get("reply", "")
    state["emotion"] = response.get("emotion", "thinking")
    state["response"] = response
    state.setdefault("agent_flow", []).append(flow_step("Response Agent", "final_reply", reason="compose graph response"))
    return state


def _mock_response(state):
    if state.get("approval_required"):
        selected = state.get("selected_tool") or {}
        review = state.get("security_review") or {}
        reply = (
            f"Found tool {selected.get('name') or selected.get('tool_id')}. Permission review is required before installation.\n"
            f"Risk level: {review.get('risk_level')}.\nReason: {review.get('reason')}."
        )
    elif state.get("execution_result"):
        result = state["execution_result"]
        if result.get("ok") and isinstance(result.get("result"), dict):
            payload = result["result"]
            reply = f"web_reader fetched: {payload.get('title') or payload.get('url')}\n\n{payload.get('content', '')[:1000]}"
        else:
            error = result.get("error") or {}
            reply = f"Tool execution failed: {error.get('message') or error.get('code') or 'unknown error'}"
    elif state.get("vision_result"):
        images = state["vision_result"].get("images", [])
        reply = "Image analysis complete.\n" + "\n".join(f"- {item.get('filename')}: {item.get('visual_summary')}" for item in images)
    elif state.get("skill_resource_results"):
        first = state["skill_resource_results"][0]
        reply = (
            f"Using skill resource {first.get('resource_path')} from {first.get('skill_name') or first.get('skill_id')}, "
            f"I found: {first.get('content', '')[:600]}"
        )
    else:
        parts = ["I am V-Agent. I can use memory, skills, approved tools, and uploaded images to help with general tasks."]
        if state.get("memory_context"):
            parts.append("Relevant memory was loaded.")
        if state.get("active_skills"):
            parts.append("Relevant skills were loaded.")
        reply = " ".join(parts)
    return {
        "reply": reply,
        "emotion": "thinking",
        "tool_used": _last_tool_used(state.get("tool_trace", [])),
        "skills_used": [skill.get("skill_id") or skill.get("name") for skill in state.get("active_skills", [])],
        "memory_action": (state.get("memory_result") or {}).get("memory_action", "none"),
    }


def _response_prompt(state):
    return load_prompt("graph_response.md") + "\n\nContext:\n" + json.dumps(_response_context(state), ensure_ascii=False)


def _response_context(state):
    return {
        "message": state.get("user_message", ""),
        "memory_context": state.get("memory_context", ""),
        "active_skills": state.get("active_skills", []),
        "skill_context": state.get("skill_context", ""),
        "skill_resource_results": state.get("skill_resource_results", []),
        "tool_trace": state.get("tool_trace", []),
        "sources": state.get("sources", []),
        "agent_flow": state.get("agent_flow", []),
    }


def _last_tool_used(tool_trace):
    for entry in reversed(tool_trace or []):
        name = ((entry.get("tool_call") or {}).get("name") or "none")
        if name != "none":
            return name
    return "none"
