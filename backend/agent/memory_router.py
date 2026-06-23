def route_memory_intent(message):
    text = str(message or "")
    lower = text.lower()
    write_hints = ["记住", "帮我记一下", "以后记得", "你要记得", "保存一下"]
    read_hints = ["你还记得", "我之前说过", "上次我说", "我最近在做什么", "你知道我的偏好吗"]
    delete_hints = ["忘记", "删除记忆", "别记了", "不要再记", "清除"]
    update_hints = ["改成", "更新一下", "不是", "而是", "我现在不做", "我现在改成"]

    if any(hint in text for hint in delete_hints):
        return {
            "need_retrieve": True,
            "need_write": False,
            "need_update": False,
            "need_delete": True,
            "memory_intent": "delete",
            "reason": "用户要求删除或遗忘记忆",
        }
    if any(hint in text for hint in update_hints):
        return {
            "need_retrieve": True,
            "need_write": False,
            "need_update": True,
            "need_delete": False,
            "memory_intent": "update",
            "reason": "用户表达了对已有记忆的更新",
        }
    if any(hint in text for hint in write_hints):
        return {
            "need_retrieve": False,
            "need_write": True,
            "need_update": False,
            "need_delete": False,
            "memory_intent": "write",
            "reason": "用户明确要求记住信息",
        }
    if any(hint in text for hint in read_hints):
        return {
            "need_retrieve": True,
            "need_write": False,
            "need_update": False,
            "need_delete": False,
            "memory_intent": "retrieve",
            "reason": "用户询问历史记忆",
        }

    soft_retrieve_hints = ["项目", "报告", "大作业", "nlp", "学习", "压力", "偏好", "喜欢", "习惯", "目标"]
    need_retrieve = any(hint in lower for hint in soft_retrieve_hints)
    return {
        "need_retrieve": need_retrieve,
        "need_write": False,
        "need_update": False,
        "need_delete": False,
        "memory_intent": "retrieve" if need_retrieve else "none",
        "reason": "普通对话触发少量相关记忆检索" if need_retrieve else "未发现记忆操作意图",
    }
