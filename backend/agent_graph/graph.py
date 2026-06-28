from langgraph.graph import END, StateGraph

from agent_graph.nodes.execution_node import execution_node
from agent_graph.nodes.memory_node import memory_node
from agent_graph.nodes.multimodal_node import multimodal_node
from agent_graph.nodes.response_node import response_node
from agent_graph.nodes.security_review_node import security_review_node
from agent_graph.nodes.skill_node import skill_node
from agent_graph.nodes.skill_resource_node import skill_resource_node
from agent_graph.nodes.supervisor_node import supervisor_node
from agent_graph.nodes.tool_install_node import tool_install_node
from agent_graph.nodes.tool_search_node import tool_search_node
from agent_graph.state import VAgentState


class GraphCore:
    def __init__(self):
        self.graph = self._build_graph()

    def chat(self, message: str, session_id: str = "default", attachments=None) -> dict:
        state = {
            "session_id": session_id,
            "user_message": message,
            "input_type": "multimodal" if attachments else "text",
            "attachments": attachments or [],
            "tool_trace": [],
            "agent_flow": [],
            "sources": [],
        }
        result = self.graph.invoke(state)
        return self._response(result)

    def _build_graph(self):
        graph = StateGraph(VAgentState)
        graph.add_node("supervisor", supervisor_node)
        graph.add_node("memory", memory_node)
        graph.add_node("skill", skill_node)
        graph.add_node("skill_resource", skill_resource_node)
        graph.add_node("multimodal", multimodal_node)
        graph.add_node("tool_search", tool_search_node)
        graph.add_node("security_review", security_review_node)
        graph.add_node("tool_install", tool_install_node)
        graph.add_node("execution", execution_node)
        graph.add_node("response", response_node)

        graph.set_entry_point("supervisor")
        graph.add_edge("supervisor", "memory")
        graph.add_edge("memory", "skill")
        graph.add_edge("skill", "skill_resource")
        graph.add_conditional_edges(
            "skill_resource",
            _route_after_skill_resource,
            {
                "multimodal": "multimodal",
                "tool_search": "tool_search",
                "execute_tool": "execution",
                "response": "response",
            },
        )
        graph.add_conditional_edges(
            "tool_search",
            _route_after_tool_search,
            {
                "security_review": "security_review",
                "execute_tool": "execution",
                "response": "response",
            },
        )
        graph.add_conditional_edges(
            "security_review",
            _route_after_security_review,
            {
                "tool_install": "tool_install",
                "response": "response",
            },
        )
        graph.add_edge("tool_install", "response")
        graph.add_edge("execution", "response")
        graph.add_edge("multimodal", "response")
        graph.add_edge("response", END)
        return graph.compile()

    def _response(self, state):
        execution_tool = "none"
        if state.get("tool_trace"):
            execution_tool = state["tool_trace"][-1].get("tool_call", {}).get("name", "none")
        return {
            "reply": state.get("final_reply", ""),
            "emotion": state.get("emotion", "thinking"),
            "tool_used": execution_tool,
            "skills_used": state.get("skills_used", []),
            "memory_action": (state.get("memory_result") or {}).get("memory_action", "none"),
            "retrieved_memories": (state.get("memory_result") or {}).get("retrieved_memories", []),
            "evolution_events": [],
            "active_skills": state.get("active_skills", []),
            "skill_trace": state.get("skill_trace", []),
            "skill_resource_results": state.get("skill_resource_results", []),
            "evolution_summary": "",
            "tool_trace": state.get("tool_trace", []),
            "sources": state.get("sources", []),
            "agent_flow": state.get("agent_flow", []),
            "approval_required": state.get("approval_required", False),
            "approval_id": state.get("approval_id"),
            "security_review": state.get("security_review", {}),
            "candidate_tools": state.get("candidate_tools", []),
        }


def _route_after_skill_resource(state):
    route = state.get("route")
    if route in {"multimodal", "tool_search", "execute_tool"}:
        return route
    return "response"


def _route_after_tool_search(state):
    route = state.get("route")
    if route in {"security_review", "execute_tool"}:
        return route
    return "response"


def _route_after_security_review(state):
    if state.get("approval_required"):
        return "response"
    return "tool_install"
