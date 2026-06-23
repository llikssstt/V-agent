def build_memory_context(retrieved, max_memories=5, max_conversations=3):
    if not retrieved:
        return ""

    lines = []
    profile = retrieved.get("profile") or {}
    profile_lines = []
    if profile.get("preferred_language"):
        profile_lines.append(f"* 用户偏好语言：{profile['preferred_language']}")
    if profile.get("preferred_style"):
        profile_lines.append(f"* 用户偏好风格：{profile['preferred_style']}")
    if profile.get("current_projects"):
        profile_lines.append("* 当前项目：" + "，".join(profile["current_projects"][:3]))
    if profile_lines:
        lines.append("【相关用户画像】")
        lines.extend(profile_lines)

    memories = (retrieved.get("memories") or [])[:max_memories]
    if memories:
        lines.append("【相关长期记忆】")
        for memory in memories:
            lines.append(f"* ({memory['category']} / {memory['memory_id']}) {memory['content']}")

    conversations = (retrieved.get("conversation_hits") or [])[:max_conversations]
    if conversations:
        lines.append("【相关历史对话】")
        for hit in conversations:
            lines.append(f"* {hit['role']}: {hit['content']}")

    return "\n".join(lines)
