from dataclasses import dataclass
from typing import Callable, Dict

from tools.calculator_tool import calculate
from tools.study_plan_tool import generate_study_plan
from tools.time_tool import get_current_time
from tools.todo_tool import run_todo
from tools.web_tools import web_fetch, web_search


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    arguments: dict
    handler: Callable[[dict], dict]

    def public_schema(self):
        return {"name": self.name, "description": self.description, "arguments": self.arguments}


def _time_handler(args):
    return get_current_time()


def _calculator_handler(args):
    return calculate(args.get("expression", ""))


def _todo_handler(args):
    return run_todo(args.get("action", "list"), args.get("content", ""))


def _study_plan_handler(args):
    return generate_study_plan(args.get("goal", ""), args.get("duration", ""))


def _web_search_handler(args):
    return web_search(args.get("query", ""), max_results=args.get("max_results", 5))


def _web_fetch_handler(args):
    return web_fetch(args.get("url", ""), max_chars=args.get("max_chars", 8000))


TOOL_REGISTRY: Dict[str, ToolSpec] = {
    "time": ToolSpec("time", "获取当前时间", {}, _time_handler),
    "calculator": ToolSpec("calculator", "计算简单四则运算表达式", {"expression": "表达式"}, _calculator_handler),
    "todo": ToolSpec("todo", "添加或查看待办事项", {"action": "add | list", "content": "待办内容"}, _todo_handler),
    "study_plan": ToolSpec("study_plan", "根据目标和时间生成简单计划", {"goal": "目标", "duration": "可用时间"}, _study_plan_handler),
    "web_search": ToolSpec("web_search", "搜索最新网页信息", {"query": "搜索关键词", "max_results": 5}, _web_search_handler),
    "web_fetch": ToolSpec("web_fetch", "读取指定网页正文", {"url": "网页 URL", "max_chars": 8000}, _web_fetch_handler),
}

AVAILABLE_TOOLS = [tool.public_schema() for tool in TOOL_REGISTRY.values()]


def get_tool_names():
    return list(TOOL_REGISTRY.keys())


def structured_error(tool, code, message, details=None):
    return {"ok": False, "tool": tool, "error": {"code": code, "message": message, "details": details or {}}}


def execute_tool(tool_call):
    name = (tool_call or {}).get("name", "none")
    args = (tool_call or {}).get("arguments") or {}
    if name == "none":
        return {"ok": True, "tool": "none", "result": None}
    tool = TOOL_REGISTRY.get(name)
    if not tool:
        return structured_error(name, "unknown_tool", f"未知工具: {name}")
    try:
        result = tool.handler(args)
    except Exception as exc:
        return structured_error(name, "tool_exception", str(exc))
    if isinstance(result, dict) and result.get("ok") is False and "tool" in result and "error" in result:
        return result
    return {"ok": True, "tool": name, "result": result}
