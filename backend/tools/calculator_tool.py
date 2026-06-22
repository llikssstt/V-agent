import ast
import operator
import re


ALLOWED_PATTERN = re.compile(r"^[0-9\.\s\+\-\*\/\(\)]+$")
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
        return OPERATORS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
        return OPERATORS[type(node.op)](_eval_node(node.operand))
    raise ValueError("只支持数字、括号和 + - * / 四则运算")


def calculate(expression):
    text = str(expression or "").strip()
    if not text or not ALLOWED_PATTERN.fullmatch(text):
        return {"ok": False, "error": "表达式包含不允许的字符"}
    try:
        tree = ast.parse(text, mode="eval")
        result = _eval_node(tree)
        return {"ok": True, "expression": text, "result": result}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

