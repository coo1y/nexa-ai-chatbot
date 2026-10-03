"""Safe arithmetic evaluator. Parses with ``ast`` and only allows numeric operations."""

import ast
import math
import operator
from collections.abc import Callable
from typing import Any

from app.services.tools.base import Tool, ToolContext, ToolInputError, ToolResult

MAX_EXPRESSION_LENGTH = 500
MAX_EXPONENT = 10_000
MAX_FACTORIAL = 500

_BINARY: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY: dict[type[ast.unaryop], Callable[[Any], Any]] = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _factorial(n: float) -> int:
    if n != int(n) or n < 0 or n > MAX_FACTORIAL:
        raise ToolInputError(f"factorial requires an integer between 0 and {MAX_FACTORIAL}")
    return math.factorial(int(n))


_FUNCTIONS: dict[str, Any] = {
    "sqrt": math.sqrt,
    "cbrt": lambda x: math.copysign(abs(x) ** (1 / 3), x),
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
    "exp": math.exp,
    "ln": math.log,
    "log": lambda x, base=10: math.log(x, base),
    "log2": math.log2,
    "log10": math.log10,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "radians": math.radians,
    "degrees": math.degrees,
    "factorial": _factorial,
    "min": min,
    "max": max,
    "hypot": math.hypot,
}
_CONSTANTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


def evaluate(expression: str) -> float | int:
    expression = expression.strip().replace("^", "**").replace("×", "*").replace("÷", "/")
    if not expression:
        raise ToolInputError("empty expression")
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise ToolInputError("expression too long")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ToolInputError("invalid expression syntax") from exc
    return _eval(tree.body)


def _eval(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise ToolInputError("exponent too large")
        try:
            return _BINARY[type(node.op)](left, right)
        except ZeroDivisionError as exc:
            raise ToolInputError("division by zero") from exc
        except OverflowError as exc:
            raise ToolInputError("result too large") from exc
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONSTANTS:
        return _CONSTANTS[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS:
        if node.keywords:
            raise ToolInputError("keyword arguments are not supported")
        args = [_eval(arg) for arg in node.args]
        try:
            return _FUNCTIONS[node.func.id](*args)
        except (ValueError, TypeError) as exc:
            raise ToolInputError(f"invalid arguments for {node.func.id}") from exc
    raise ToolInputError("unsupported element in expression")


def format_number(value: float | int) -> str:
    if isinstance(value, float):
        if value.is_integer() and abs(value) < 1e16:
            return str(int(value))
        return f"{value:.12g}"
    text = str(value)
    return text if len(text) <= 60 else f"{float(value):.12e}"


async def _handle(args: dict[str, Any], _ctx: ToolContext) -> ToolResult:
    expression = str(args.get("expression", ""))
    result = format_number(evaluate(expression))
    return ToolResult(content=f"{expression} = {result}", summary=f"{expression} = {result}")


calculator_tool = Tool(
    name="calculator",
    label="Calculator",
    description=(
        "Evaluate an arithmetic expression exactly. Supports + - * / // % ** (or ^), parentheses, "
        "sqrt, cbrt, abs, round, floor, ceil, exp, ln, log(x, base), log2, log10, trig functions, "
        "factorial, min, max, hypot and the constants pi, e, tau. Use for any non-trivial arithmetic."
    ),
    parameters={
        "type": "object",
        "properties": {"expression": {"type": "string", "description": "e.g. '(12.5 * 4) / sqrt(2)'"}},
        "required": ["expression"],
    },
    handler=_handle,
    timeout_seconds=2.0,
)
