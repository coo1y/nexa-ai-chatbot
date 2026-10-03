import pytest

from app.services.tools.base import ToolContext, ToolInputError
from app.services.tools.units import convert, normalise_unit, unit_convert_tool


@pytest.mark.parametrize(
    ("value", "src", "dst", "expected"),
    [
        (1, "km", "m", 1000),
        (10, "miles", "km", 16.09344),
        (100, "°C", "°F", 212),
        (32, "fahrenheit", "celsius", 0),
        (0, "c", "k", 273.15),
        (1, "lb", "kg", 0.45359237),
        (1, "gallon", "liters", 3.785411784),
        (60, "mph", "km/h", 96.56064),
        (1, "GiB", "MB", 1073.741824),
        (1, "kWh", "J", 3.6e6),
        (1, "hour", "minutes", 60),
    ],
)
def test_conversions(value: float, src: str, dst: str, expected: float) -> None:
    assert convert(value, src, dst) == pytest.approx(expected, rel=1e-9)


def test_aliases() -> None:
    assert normalise_unit("Kilometres") == "km"
    assert normalise_unit("feet") == "ft"


def test_incompatible_units() -> None:
    with pytest.raises(ToolInputError, match="cannot convert"):
        convert(1, "kg", "m")


def test_unknown_unit() -> None:
    with pytest.raises(ToolInputError, match="unknown unit"):
        convert(1, "florps", "m")


async def test_handler_rejects_non_numeric() -> None:
    with pytest.raises(ToolInputError):
        await unit_convert_tool.handler({"value": "abc", "from_unit": "m", "to_unit": "km"}, ToolContext())
