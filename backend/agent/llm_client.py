import json
import os
import re

import requests

from agent.env_loader import load_env_file

CALL_SOURCES = []


class LLMClient:
    def __init__(self):
        load_env_file()
        self.api_key = os.getenv("LLM_API_KEY", "").strip()
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.call_sources = []

    @property
    def mock_mode(self):
        return not self.api_key

    def complete_json(self, prompt, stage, context):
        if self.mock_mode:
            self._record_call(stage, "mock")
            return self._mock(stage, context)
        try:
            user_content = prompt
            if context is not None:
                user_content = prompt + "\n\nRuntime context JSON:\n" + json.dumps(context, ensure_ascii=False)
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": user_content}],
                    "temperature": 0.6,
                    "response_format": {"type": "json_object"},
                },
                timeout=30,
            )
            response.raise_for_status()
            self._record_call(stage, "real_api")
            return response.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            if os.getenv("LLM_DISABLE_FALLBACK", "").strip().lower() in {"1", "true", "yes"}:
                self._record_call(stage, "real_api_error", str(exc))
                raise
            self._record_call(stage, "fallback_mock", str(exc))
            return self._mock(stage, context)

    def _record_call(self, stage, source, error=None):
        item = {"stage": stage, "source": source}
        self.call_sources.append(item)
        global_item = dict(item)
        if error:
            global_item["error"] = error[:500]
        CALL_SOURCES.append(global_item)

    def _mock(self, stage, context):
        if stage == "planner":
            return self._mock_planner(context)
        if stage == "evolution_reflection":
            return self._mock_evolution_reflection(context)
        return self._mock_responder(context)

    def _mock_planner(self, context):
        message = context.get("message", "")
        planner = {
            "intent": "日常聊天",
            "emotion": "neutral",
            "skills_used": ["persona_skill", "chat_skill"],
            "memory_action": "none",
            "memory_query": "",
            "memory_to_write": {"content": "", "category": "user_profile", "importance": 1},
            "memory_delete_query": "",
            "tool_call": {"name": "none", "arguments": {}},
            "final_ready": True,
            "reason": "普通聊天不需要工具",
        }
        tool_trace = context.get("tool_trace") or []
        if tool_trace:
            planner["intent"] = "基于工具结果作答"
            planner["emotion"] = "thinking"
            planner["tool_call"] = {"name": "none", "arguments": {}}
            planner["final_ready"] = True
            planner["reason"] = "已有工具结果足够交给 Responder 综合回答"
            return json.dumps(planner, ensure_ascii=False)

        if any(text in message for text in ["不想", "难受", "累", "废了", "焦虑", "摆烂", "压力"]):
            planner.update({"intent": "情绪陪伴", "emotion": "sad", "skills_used": ["persona_skill", "comfort_skill"]})
        elif any(text in message for text in ["你好", "你是谁", "介绍"]):
            planner.update({"intent": "自我介绍", "emotion": "happy"})

        if "记住" in message:
            content = message.split("记住", 1)[-1].strip(" ：。")
            planner["memory_action"] = "write"
            planner["memory_to_write"] = {"content": content or message, "category": "project", "importance": 4}
        elif any(text in message for text in ["还记得", "记得我", "我最近"]):
            planner["memory_action"] = "read"
            planner["memory_query"] = message
        elif any(text in message for text in ["删除记忆", "忘掉", "忘记"]):
            planner["memory_action"] = "delete"
            planner["memory_delete_query"] = message

        if any(text.lower() in message.lower() for text in ["最新", "新闻", "github", "论文", "价格", "版本", "政策", "法规", "标准"]):
            planner["tool_call"] = {"name": "web_search", "arguments": {"query": message, "max_results": 5}}
            planner["intent"] = "联网搜索最新信息"
            planner["emotion"] = "thinking"
            planner["final_ready"] = False
            planner["reason"] = "问题涉及最新信息，需要先搜索"
        elif any(text in message for text in ["几点", "时间", "日期"]):
            planner["tool_call"] = {"name": "time", "arguments": {}}
            planner["intent"] = "查询时间"
            planner["emotion"] = "thinking"
            planner["final_ready"] = False
            planner["reason"] = "需要调用时间工具"
        elif self._extract_expression(message):
            planner["tool_call"] = {"name": "calculator", "arguments": {"expression": self._extract_expression(message)}}
            planner["intent"] = "计算"
            planner["emotion"] = "thinking"
            planner["final_ready"] = False
            planner["reason"] = "需要调用计算器"
        elif any(text in message for text in ["待办", "todo", "任务清单"]):
            action = "add" if any(text in message for text in ["添加", "加一个", "记到待办"]) else "list"
            planner["tool_call"] = {"name": "todo", "arguments": {"action": action, "content": message}}
            planner["intent"] = "待办管理"
            planner["final_ready"] = False
            planner["reason"] = "需要调用待办工具"
        elif any(text in message for text in ["安排", "计划", "两小时", "2小时", "学习"]):
            planner["tool_call"] = {"name": "study_plan", "arguments": {"goal": message, "duration": "2小时" if "两" in message or "2" in message else "今晚"}}
            planner["intent"] = "生成计划"
            planner["emotion"] = "thinking"
            planner["final_ready"] = False
            planner["reason"] = "需要调用学习计划工具"

        return json.dumps(planner, ensure_ascii=False)

    def _mock_responder(self, context):
        message = context.get("message", "")
        planner = context.get("planner", {})
        memory_result = context.get("memory_result", {})
        tool_trace = context.get("tool_trace") or []
        skill_resource_results = context.get("skill_resource_results") or []
        tool_result = self._last_tool_result(tool_trace) or context.get("tool_result", {})
        emotion = planner.get("emotion", "neutral")
        tool_name = (tool_result or {}).get("tool") or (planner.get("tool_call") or {}).get("name", "none")
        memory_action = planner.get("memory_action", "none")

        if skill_resource_results:
            first = skill_resource_results[0]
            reply = f"我参考了 Skill 资源 {first.get('resource_path')}：{first.get('content', '')[:600]}"
        elif tool_name == "study_plan" and tool_result.get("result", {}).get("ok"):
            result = tool_result["result"]
            reply = "收到，今晚走“别整虚的，直接推进”路线：\n" + "\n".join(f"{i + 1}. {step}" for i, step in enumerate(result.get("steps", [])))
        elif tool_name == "calculator":
            result = tool_result.get("result", {})
            reply = f"算出来了：{result.get('expression')} = {result.get('result')}" if result.get("ok") else f"这个式子我没法安全计算：{result.get('error')}"
        elif tool_name == "time":
            reply = f"现在是 {tool_result.get('result', {}).get('text')}，LunaClaw 看了一眼屏幕角落。"
        elif tool_name == "todo":
            result = tool_result.get("result", {})
            if result.get("item"):
                reply = f"记到待办里了：{result['item']['content']}。这波先别慌，任务已经落地。"
            else:
                items = result.get("items", [])
                reply = "当前待办：" + ("、".join(item["content"] for item in items) if items else "暂时是空的。")
        elif tool_name == "web_search":
            result = tool_result.get("result", {})
            if tool_result.get("ok") and result.get("results"):
                first = result["results"][0]
                reply = f"我查到的第一条结果是：{first.get('title')}。链接：{first.get('url')}。摘要：{first.get('snippet')}"
            else:
                error = tool_result.get("error") or {}
                reply = f"我需要联网查询这类最新信息，但当前搜索工具不可用：{error.get('message', '未知错误')}。"
        elif tool_name == "web_fetch":
            result = tool_result.get("result", {})
            if tool_result.get("ok"):
                reply = f"我读取到网页《{result.get('title') or result.get('url')}》的正文摘要：{result.get('content', '')[:300]}"
            else:
                error = tool_result.get("error") or {}
                reply = f"网页读取失败：{error.get('message', '未知错误')}。"
        elif memory_action == "write":
            reply = "记住了，这条我先收进长期记忆。之后你问起时，我会把它拿出来参考。"
        elif memory_action == "read":
            memories = memory_result.get("items", [])
            if memories:
                reply = "我记得，你最近在做：" + "；".join(item["content"] for item in memories[:3])
            else:
                reply = "我这边暂时没找到相关记忆。你可以再告诉我一次，我这次认真存档。"
        elif "你是谁" in message or "你好" in message:
            reply = "我是 LunaClaw，网页里的常驻陪伴 Agent。主要业务是陪你聊天、接住碎碎念，顺手把生活里的小麻烦拆成能处理的几块。"
            emotion = "happy"
        elif emotion == "sad":
            reply = "懂了，今天的状态像是压力顶上来了。先别给自己下判决，我们只做一个最小动作：打开材料，定一个 10 分钟计时器，先推进第一小步。"
        else:
            reply = "收到。LunaClaw 在线接住这条消息了。你可以继续说，我会尽量把它拆成能处理的小块。"

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

    def _last_tool_result(self, tool_trace):
        for entry in reversed(tool_trace or []):
            result = entry.get("tool_result") or {}
            if result.get("tool") and result.get("tool") != "none":
                return result
        return None

    def _mock_evolution_reflection(self, context):
        message = context.get("message", "")
        reply = context.get("assistant_reply", "")
        if any(text in message for text in ["压力", "摆烂", "不想学", "拖延", "焦虑"]):
            return json.dumps(
                {
                    "events": [
                        {
                            "type": "strategy_observed",
                            "summary": "用户在学习压力场景下适合先共情，再拆一个 10 分钟小动作。",
                            "target_type": "skill",
                        }
                    ],
                    "preference_updates": {"planning_style": "先拆 10 分钟小动作"},
                    "memory_updates": [
                        {
                            "content": "用户在学习压力下更适合先共情，再拆一个 10 分钟小动作",
                            "category": "interaction_style",
                            "importance": 0.8,
                        }
                    ],
                    "scenario": "学习压力",
                    "strategy_summary": "先共情，再拆成一个 10 分钟小动作",
                    "skill_candidate": {
                        "name": "study_pressure_micro_step",
                        "description": "用户学习压力较大时，先共情再给一个 10 分钟小动作。",
                        "trigger_examples": ["不想学了", "压力好大", "想摆烂"],
                        "instructions": ["先承认压力", "只给一个可以立刻开始的小动作"],
                    },
                    "confidence": 0.9,
                    "reason": "用户表达学习压力，回复采用了小步推进策略。",
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "events": [],
                "preference_updates": {},
                "memory_updates": [],
                "scenario": "其他",
                "strategy_summary": "",
                "skill_candidate": {},
                "confidence": 0.2,
                "reason": "本轮没有稳定可沉淀的偏好或策略。",
            },
            ensure_ascii=False,
        )

    def _extract_expression(self, message):
        matches = re.findall(r"[0-9][0-9\.\s\+\-\*\/\(\)]{2,}[0-9\)]", message)
        return matches[0].strip() if matches else ""
