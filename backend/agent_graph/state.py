from typing import Any, Dict, List, Optional, TypedDict


class VAgentState(TypedDict, total=False):
    session_id: str
    user_message: str
    input_type: str
    attachments: List[Dict[str, Any]]
    route: str
    current_task: str
    vision_result: Dict[str, Any]
    memory_result: Dict[str, Any]
    memory_context: str
    active_skills: List[Dict[str, Any]]
    skills_used: List[str]
    skill_context: str
    skill_trace: List[Dict[str, Any]]
    skill_resource_results: List[Dict[str, Any]]
    candidate_tools: List[Dict[str, Any]]
    selected_tool: Dict[str, Any]
    security_review: Dict[str, Any]
    approval_required: bool
    approval_id: Optional[str]
    approved: bool
    install_result: Dict[str, Any]
    execution_result: Dict[str, Any]
    tool_trace: List[Dict[str, Any]]
    agent_flow: List[Dict[str, Any]]
    final_reply: str
    emotion: str
    sources: List[Dict[str, Any]]
