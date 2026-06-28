from agent_graph.nodes.common import flow_step
from tools.skill_installer_tool import read_skill_resource, search_skill_resources


MIN_RESOURCE_SCORE = 1
MAX_RESOURCES_PER_SKILL = 2
MAX_RESOURCES_TOTAL = 4
MAX_RESOURCE_CONTEXT_CHARS = 12000


def skill_resource_node(state):
    message = state.get("user_message", "")
    results = []
    total_chars = 0
    tool_trace = state.setdefault("tool_trace", [])
    for skill in state.get("active_skills", []) or []:
        if len(results) >= MAX_RESOURCES_TOTAL or total_chars >= MAX_RESOURCE_CONTEXT_CHARS:
            break
        skill_id = skill.get("skill_id")
        if not skill_id or not skill.get("resources"):
            continue
        search_result = search_skill_resources(skill_id, message, top_k=3)
        tool_trace.append(
            {
                "step": len(tool_trace) + 1,
                "agent_name": "Skill Resource Agent",
                "tool_call": {"name": "search_skill_resources", "arguments": {"skill_id": skill_id, "query": message, "top_k": 3}},
                "tool_result": search_result,
            }
        )
        if not search_result.get("ok"):
            continue
        skill_reads = 0
        for hit in search_result.get("results", []):
            if skill_reads >= MAX_RESOURCES_PER_SKILL or len(results) >= MAX_RESOURCES_TOTAL or total_chars >= MAX_RESOURCE_CONTEXT_CHARS:
                break
            if hit.get("score", 0) < MIN_RESOURCE_SCORE:
                continue
            read_result = read_skill_resource(skill_id, hit["resource_path"], max_chars=4000)
            tool_trace.append(
                {
                    "step": len(tool_trace) + 1,
                    "agent_name": "Skill Resource Agent",
                    "tool_call": {"name": "read_skill_resource", "arguments": {"skill_id": skill_id, "resource_path": hit["resource_path"]}},
                    "tool_result": read_result,
                }
            )
            if read_result.get("ok") and read_result.get("content") and not read_result.get("unsupported_binary"):
                remaining = MAX_RESOURCE_CONTEXT_CHARS - total_chars
                content = read_result["content"][:remaining]
                results.append(
                    {
                        "skill_id": skill_id,
                        "skill_name": skill.get("name"),
                        "resource_path": read_result["resource_path"],
                        "content": content,
                        "truncated": read_result["truncated"] or len(read_result["content"]) > len(content),
                        "score": hit.get("score", 0),
                        "metadata": read_result.get("metadata", {}),
                    }
                )
                total_chars += len(content)
                skill_reads += 1

    state["skill_resource_results"] = results
    state.setdefault("agent_flow", []).append(
        flow_step("Skill Resource Agent", "read_relevant_resources", reason=f"{len(results)} resource(s) loaded")
    )
    return state
