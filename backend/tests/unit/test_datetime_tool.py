from datetime import UTC, datetime

import pytest

from app.services.tools.base import ToolInputError
from app.services.tools.datetime_tool import run

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


def test_now_in_timezone() -> None:
    assert "Saturday, 03 October 2026 19:00" in run({"operation": "now", "timezone": "Asia/Bangkok"}, now=NOW)


def test_convert_timezone() -> None:
    out = run(
        {
            "operation": "convert_timezone",
            "datetime": "2026-10-03T09:00",
            "timezone": "America/New_York",
            "target_timezone": "Europe/London",
        }
    )
    assert "14:00" in out


def test_difference() -> None:
    out = run({"operation": "difference", "datetime": "2026-01-01", "end_datetime": "2026-12-25"})
    assert out.startswith("Difference: 358 days")


def test_add_and_weekday() -> None:
    assert "Wednesday, 14 October 2026" in run({"operation": "add", "datetime": "2026-10-03", "days": 11})
    assert "Saturday" in run({"operation": "weekday", "datetime": "2026-10-03"})


@pytest.mark.parametrize(
    "args",
    [
        {"operation": "now", "timezone": "Mars/Olympus"},
        {"operation": "difference", "datetime": "not-a-date", "end_datetime": "2026-01-01"},
        {"operation": "explode"},
    ],
)
def test_invalid_input(args: dict) -> None:
    with pytest.raises(ToolInputError):
        run(args)
