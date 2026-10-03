import math

import pytest

from app.services.tools.base import ToolContext, ToolInputError
from app.services.tools.calculator import calculator_tool, evaluate, format_number


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2 + 3 * 4", 14),
        ("(2 + 3) * 4", 20),
        ("2 ^ 10", 1024),
        ("10 / 4", 2.5),
        ("7 // 2", 3),
        ("-5 + 2", -3),
        ("sqrt(16) + abs(-2)", 6),
        ("log(1000)", 3),
        ("log(8, 2)", 3),
        ("factorial(5)", 120),
        ("max(1, 9, 3)", 9),
        ("3 × 4 ÷ 2", 6),
    ],
)
def test_evaluates_arithmetic(expression: str, expected: float) -> None:
    assert evaluate(expression) == pytest.approx(expected)


def test_constants() -> None:
    assert evaluate("2 * pi") == pytest.approx(2 * math.pi)


@pytest.mark.parametrize(
    ("expression", "message"),
    [
        ("__import__('os').system('ls')", "unsupported"),
        ("open('x')", "unsupported"),
        ("1 / 0", "division by zero"),
        ("2 ** 100000", "exponent too large"),
        ("factorial(10000)", "factorial"),
        ("", "empty"),
        ("1 +", "syntax"),
        ("x + 1", "unsupported"),
        ("1" * 600, "too long"),
    ],
)
def test_rejects_unsafe_or_invalid(expression: str, message: str) -> None:
    with pytest.raises(ToolInputError, match=message):
        evaluate(expression)


def test_format_number() -> None:
    assert format_number(4.0) == "4"
    assert format_number(1 / 3) == "0.333333333333"
    assert format_number(10**80).endswith("e+80")


async def test_tool_handler_formats_result() -> None:
    result = await calculator_tool.handler({"expression": "12 * 12"}, ToolContext())
    assert result.content == "12 * 12 = 144"
