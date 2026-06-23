def infer_category(content, explicit_category=None):
    if explicit_category:
        return explicit_category
    text = str(content or "")
    if any(token in text for token in ["偏好", "喜欢", "回答", "风格", "直接", "简洁"]):
        return "interaction_style"
    if any(token in text for token in ["项目", "Agent", "报告", "大作业", "课程"]):
        return "project"
    if any(token in text for token in ["目标", "学习", "准备"]):
        return "learning_goal"
    if any(token in text for token in ["待办", "完成"]):
        return "todo"
    return "user_profile"


def strip_memory_command(message):
    text = str(message or "").strip()
    for prefix in ["记住", "帮我记一下", "以后记得", "你要记得", "保存一下"]:
        if prefix in text:
            return text.split(prefix, 1)[-1].strip(" ：。")
    return text


class MemoryWriter:
    def __init__(self, core):
        self.core = core

    def write_from_user_message(self, message, category=None, importance=0.8):
        content = strip_memory_command(message)
        return self.core.write_memory(
            content=content,
            category=infer_category(content, category),
            importance=importance,
            source="user_explicit",
        )

    def update_by_query(self, query, content):
        retrieved = self.core.retriever.retrieve(query, top_k=1)
        if not retrieved["memories"]:
            return None
        return self.core.update_memory(retrieved["memories"][0]["memory_id"], content=content)

    def delete_by_query(self, query):
        retrieved = self.core.retriever.retrieve(query, top_k=3)
        deleted = []
        for memory in retrieved["memories"]:
            deleted.append(self.core.delete_memory(memory["memory_id"]))
        return deleted
