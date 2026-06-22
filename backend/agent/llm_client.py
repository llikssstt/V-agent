import json
import os
import re

import requests


class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY", "").strip()
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    @property
    def mock_mode(self):
        return not self.api_key

    def complete_json(self, prompt, stage, context):
        if self.mock_mode:
            if stage == "planner":
                return self._mock_planner(context)
            return self._mock_responder(context)
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.6,
                    "response_format": {"type": "json_object"},
                },
                timeout=30,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception:
            if stage == "planner":
                return self._mock_planner(context)
            return self._mock_responder(context)

    def _mock_planner(self, context):
        message = context.get("message", "")
        lower = message.lower()
        planner = {
            "intent": "日常聊天",
            "emotion": "neutral",
            "skills_used": ["persona_skill", "chat_skill"],
            "memory_action": "none",
            "memory_query": "",
            "memory_to_write": {"content": "", "category": "user_profile", "importance": 1},
            "memory_delete_query": "",
            "tool_call": {"name": "none", "arguments": {}},
        }

        if any(text in message for text in ["不想动", "难受", "累", "废了", "焦虑", "开摆"]):
            planner.update({"intent": "情绪陪伴", "emotion": "sad", "skills_used": ["persona_skill", "comfort_skill"]})
        elif any(text in message for text in ["你好", "你是谁", "介绍"]):
            planner.update({"intent": "自我介绍", "emotion": "happy"})

        if "记住" in message:
            content = message.split("记住", 1)[-1].strip(" ：:。")
            planner["memory_action"] = "write"
            planner["memory_to_write"] = {"content": content or message, "category": "project", "importance": 4}
        elif any(text in message for text in ["还记得", "记得我", "我最近"]):
            planner["memory_action"] = "read"
            planner["memory_query"] = message
        elif any(text in message for text in ["删除记忆", "忘掉"]):
            planner["memory_action"] = "delete"
            planner["memory_delete_query"] = message

        if any(text in message for text in ["几点", "时间", "日期"]):
            planner["tool_call"] = {"name": "time", "arguments": {}}
            planner["intent"] = "查询时间"
            planner["emotion"] = "thinking"
        elif self._extract_expression(message):
            planner["tool_call"] = {"name": "calculator", "arguments": {"expression": self._extract_expression(message)}}
            planner["intent"] = "计算"
            planner["emotion"] = "thinking"
        elif any(text in message for text in ["待办", "todo", "任务清单"]):
            action = "add" if any(text in message for text in ["添加", "加一个", "记到待办"]) else "list"
            planner["tool_call"] = {"name": "todo", "arguments": {"action": action, "content": message}}
            planner["intent"] = "待办管理"
        elif any(text in message for text in ["安排", "计划", "两小时", "2小时", "学习"]):
            planner["tool_call"] = {"name": "study_plan", "arguments": {"goal": message, "duration": "2小时" if "两" in message or "2" in message else "今晚"}}
            planner["intent"] = "生成计划"
            planner["emotion"] = "thinking"

        return json.dumps(planner, ensure_ascii=False)

    def _mock_responder(self, context):
        message = context.get("message", "")
        planner = context.get("planner", {})
        memory_result = context.get("memory_result", {})
        tool_result = context.get("tool_result", {})
        emotion = planner.get("emotion", "neutral")
        tool_name = (planner.get("tool_call") or {}).get("name", "none")
        memory_action = planner.get("memory_action", "none")

        if tool_name == "study_plan" and tool_result.get("result", {}).get("ok"):
            result = tool_result["result"]
            reply = "收到，今晚走“别整虚的，直接推进”路线：\n" + "\n".join(f"{i + 1}. {step}" for i, step in enumerate(result.get("steps", [])))
        elif tool_name == "calculator":
            result = tool_result.get("result", {})
            reply = f"算出来了：{result.get('expression')} = {result.get('result')}" if result.get("ok") else f"这个式子我没法安全计算：{result.get('error')}"
        elif tool_name == "time":
            reply = f"现在是 {tool_result.get('result', {}).get('text')}，电子小熙看了一眼屏幕角落。"
        elif tool_name == "todo":
            result = tool_result.get("result", {})
            if result.get("item"):
                reply = f"记到待办里了：{result['item']['content']}。这波先别慌，任务已经落地。"
            else:
                items = result.get("items", [])
                reply = "当前待办：" + ("、".join(item["content"] for item in items) if items else "暂时是空的。")
        elif memory_action == "write":
            reply = "记住了，这条我先收进长期记忆。之后你问起来，我会把它捞出来。"
        elif memory_action == "read":
            memories = memory_result.get("items", [])
            if memories:
                reply = "我记得，你最近在做：" + "；".join(item["content"] for item in memories[:3])
            else:
                reply = "我这边暂时没捞到相关记忆。你可以再告诉我一次，我这次认真存档。"
        elif "你是谁" in message or "你好" in message:
            reply = "我是小熙，屏幕里的常驻嘉宾。主要业务是陪你聊天、接住碎碎念，顺手把生活里的小麻烦拆成能处理的几块。"
            emotion = "happy"
        elif emotion == "sad":
            reply = "懂了，今日状态：灵魂在线，行动离线。先别给自己下狠判决，我们只做一个最小动作，比如把要做的东西打开，先不要求立刻起飞。"
        else:
            reply = "收到。小熙在线接住这条消息了。你可以继续说，我会尽量把它拆成能处理的小块。"

        return json.dumps(
            {
                "reply": reply,
                "emotion": emotion,
                "tool_used": tool_name,
                "skills_used": planner.get("skills_used", ["persona_skill", "chat_skill"]),
                "memory_action": memory_action,
            },
            ensure_ascii=False,
        )

    def _extract_expression(self, message):
        matches = re.findall(r"[0-9][0-9\.\s\+\-\*\/\(\)]{2,}[0-9\)]", message)
        return matches[0].strip() if matches else ""
