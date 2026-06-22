from tools.calculator_tool import calculate
from tools.study_plan_tool import generate_study_plan
from tools.time_tool import get_current_time
from tools.todo_tool import run_todo


AVAILABLE_TOOLS = [
    {"name": "time", "description": "获取当前时间", "arguments": {}},
    {"name": "calculator", "description": "计算简单四则运算表达式", "arguments": {"expression": "表达式"}},
    {"name": "todo", "description": "添加或查看待办事项", "arguments": {"action": "add | list", "content": "待办内容"}},
    {"name": "study_plan", "description": "根据目标和时间生成简单计划", "arguments": {"goal": "目标", "duration": "可用时间"}},
]


def execute_tool(tool_call):
    name = (tool_call or {}).get("name", "none")
    args = (tool_call or {}).get("arguments") or {}
    if name == "none":
        return {"ok": True, "tool": "none", "result": None}
    if name == "time":
        return {"ok": True, "tool": name, "result": get_current_time()}
    if name == "calculator":
        return {"ok": True, "tool": name, "result": calculate(args.get("expression", ""))}
    if name == "todo":
        return {"ok": True, "tool": name, "result": run_todo(args.get("action", "list"), args.get("content", ""))}
    if name == "study_plan":
        return {"ok": True, "tool": name, "result": generate_study_plan(args.get("goal", ""), args.get("duration", ""))}
    return {"ok": False, "tool": name, "error": f"未知工具: {name}"}

