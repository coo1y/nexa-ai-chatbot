"""Date/time answers that models cannot know on their own (current time, date math)."""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.services.tools.base import Tool, ToolContext, ToolInputError, ToolResult

_OPERATIONS = ("now", "convert_timezone", "difference", "add", "weekday")


def _zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ToolInputError(f"unknown timezone '{name}' (use IANA names such as 'Asia/Bangkok')") from exc


def _parse(value: Any, field: str, tz: ZoneInfo | None = None) -> datetime:
    if not value:
        raise ToolInputError(f"'{field}' is required for this operation")
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ToolInputError(f"'{field}' must be an ISO-8601 date or datetime") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz or UTC)
    return parsed


def run(args: dict[str, Any], now: datetime | None = None) -> str:
    operation = args.get("operation", "now")
    now = now or datetime.now(UTC)
    if operation == "now":
        tz = _zone(args.get("timezone"))
        local = now.astimezone(tz)
        return f"Current time in {tz.key}: {local.strftime('%A, %d %B %Y %H:%M:%S %Z')} (ISO {local.isoformat(timespec='seconds')})"
    if operation == "convert_timezone":
        src = _zone(args.get("timezone"))
        dst = _zone(args.get("target_timezone"))
        moment = _parse(args.get("datetime"), "datetime", src)
        converted = moment.astimezone(dst)
        return f"{moment.isoformat(timespec='minutes')} ({src.key}) = {converted.strftime('%A, %d %B %Y %H:%M %Z')} ({dst.key})"
    if operation == "difference":
        start = _parse(args.get("datetime"), "datetime")
        end = _parse(args.get("end_datetime"), "end_datetime")
        delta = end - start
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes = remainder // 60
        weeks = abs(days) / 7
        return f"Difference: {days} days, {hours} hours, {minutes} minutes (≈ {weeks:.2f} weeks, {delta.total_seconds() / 3600:.2f} hours total)"
    if operation == "add":
        start = _parse(args.get("datetime"), "datetime")
        try:
            delta = timedelta(
                days=float(args.get("days", 0) or 0),
                hours=float(args.get("hours", 0) or 0),
                minutes=float(args.get("minutes", 0) or 0),
                weeks=float(args.get("weeks", 0) or 0),
            )
            result = start + delta
        except (TypeError, ValueError, OverflowError) as exc:
            raise ToolInputError("invalid offset") from exc
        return f"{start.isoformat(timespec='minutes')} + offset = {result.strftime('%A, %d %B %Y %H:%M %Z')}"
    if operation == "weekday":
        target = args.get("datetime")
        try:
            day = date.fromisoformat(str(target)[:10])
        except ValueError as exc:
            raise ToolInputError("'datetime' must be an ISO date") from exc
        return f"{day.isoformat()} is a {day.strftime('%A')} (ISO week {day.isocalendar().week})"
    raise ToolInputError(f"unknown operation '{operation}'")


async def _handle(args: dict[str, Any], _ctx: ToolContext) -> ToolResult:
    text = run(args)
    return ToolResult(content=text, summary=text)


datetime_tool = Tool(
    name="datetime",
    label="Date & time",
    description=(
        "Get the current date/time in a timezone, convert between timezones, compute the difference "
        "between two dates, add an offset to a date, or find the weekday of a date. Always use this "
        "instead of guessing the current date."
    ),
    parameters={
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": list(_OPERATIONS)},
            "timezone": {"type": "string", "description": "IANA timezone, default UTC"},
            "target_timezone": {"type": "string"},
            "datetime": {"type": "string", "description": "ISO-8601 date or datetime"},
            "end_datetime": {"type": "string"},
            "days": {"type": "number"},
            "hours": {"type": "number"},
            "minutes": {"type": "number"},
            "weeks": {"type": "number"},
        },
        "required": ["operation"],
    },
    handler=_handle,
    timeout_seconds=2.0,
)
