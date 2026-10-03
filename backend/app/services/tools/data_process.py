"""Basic transformations and calculations on small user-provided datasets (CSV / JSON)."""

import csv
import io
import json
import statistics
from typing import Any

from app.services.tools.base import Tool, ToolContext, ToolInputError, ToolResult
from app.services.tools.calculator import format_number

MAX_INPUT_CHARS = 200_000
MAX_ROWS = 10_000
MAX_OUTPUT_ROWS = 50

Row = dict[str, Any]


def parse_table(data: str) -> list[Row]:
    """Accept a JSON array (of objects or numbers) or CSV text with a header row."""
    data = data.strip()
    if not data:
        raise ToolInputError("no data provided")
    if len(data) > MAX_INPUT_CHARS:
        raise ToolInputError(f"data too large (max {MAX_INPUT_CHARS} characters)")
    rows: list[Row]
    if data[0] in "[{":
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ToolInputError("invalid JSON data") from exc
        if isinstance(parsed, dict):
            parsed = [parsed]
        if not isinstance(parsed, list):
            raise ToolInputError("JSON data must be an array")
        rows = [item if isinstance(item, dict) else {"value": item} for item in parsed]
    else:
        reader = csv.DictReader(io.StringIO(data))
        if not reader.fieldnames:
            raise ToolInputError("CSV data needs a header row")
        rows = [dict(row) for row in reader]
    if len(rows) > MAX_ROWS:
        raise ToolInputError(f"too many rows (max {MAX_ROWS})")
    return [{k: _coerce(v) for k, v in row.items()} for row in rows]


def _coerce(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        try:
            number = float(stripped.replace(",", "")) if stripped else None
        except ValueError:
            return stripped
        if number is None:
            return None
        return int(number) if number.is_integer() and "." not in stripped else number
    return value


def _numeric_columns(rows: list[Row]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    return [
        c for c in columns if any(isinstance(r.get(c), (int, float)) and not isinstance(r.get(c), bool) for r in rows)
    ]


def _values(rows: list[Row], column: str) -> list[float]:
    return [r[column] for r in rows if isinstance(r.get(column), (int, float)) and not isinstance(r.get(column), bool)]


def describe(rows: list[Row]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for column in _numeric_columns(rows):
        values = _values(rows, column)
        result[column] = {
            "count": len(values),
            "sum": sum(values),
            "mean": statistics.fmean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        }
    if not result:
        raise ToolInputError("no numeric columns found")
    return result


def _compare(left: Any, op: str, right: Any) -> bool:
    if isinstance(right, str):
        right = _coerce(right)
    try:
        return {
            "==": lambda: left == right,
            "!=": lambda: left != right,
            ">": lambda: left > right,
            ">=": lambda: left >= right,
            "<": lambda: left < right,
            "<=": lambda: left <= right,
            "contains": lambda: str(right).lower() in str(left).lower(),
        }[op]()
    except KeyError as exc:
        raise ToolInputError(f"unsupported operator '{op}'") from exc
    except TypeError:
        return False


def run(args: dict[str, Any]) -> tuple[str, str]:
    operation = args.get("operation")
    rows = parse_table(str(args.get("data", "")))
    column = args.get("column")
    if column is not None and rows and all(column not in r for r in rows):
        raise ToolInputError(f"column '{column}' not found")

    if operation == "describe":
        stats = describe(rows)
        lines = [f"{len(rows)} rows."]
        for col, s in stats.items():
            parts = ", ".join(f"{k}={format_number(v) if isinstance(v, (int, float)) else v}" for k, v in s.items())
            lines.append(f"{col}: {parts}")
        return "\n".join(lines), f"Computed statistics for {len(stats)} column(s) over {len(rows)} rows"
    if operation == "sort":
        if not column:
            raise ToolInputError("'column' is required for sort")
        descending = args.get("order", "asc") == "desc"
        present = [r for r in rows if r.get(column) is not None]
        missing = [r for r in rows if r.get(column) is None]
        try:
            ordered = sorted(present, key=lambda r: r[column], reverse=descending) + missing
        except TypeError:  # mixed text/numbers: compare as text
            ordered = sorted(present, key=lambda r: str(r[column]), reverse=descending) + missing
        return _render(ordered), f"Sorted {len(rows)} rows by {column} ({'desc' if descending else 'asc'})"
    if operation == "filter":
        if not column or "operator" not in args:
            raise ToolInputError("'column', 'operator' and 'value' are required for filter")
        kept = [r for r in rows if _compare(r.get(column), str(args["operator"]), args.get("value"))]
        return _render(kept), f"Filtered to {len(kept)} of {len(rows)} rows"
    if operation == "aggregate":
        group_by, agg = args.get("group_by"), args.get("aggregation", "sum")
        if not group_by or not column:
            raise ToolInputError("'group_by' and 'column' are required for aggregate")
        groups: dict[Any, list[float]] = {}
        for row in rows:
            value = row.get(column)
            bucket = groups.setdefault(row.get(group_by), [])
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                bucket.append(value)
        funcs = {
            "sum": sum,
            "mean": lambda v: statistics.fmean(v) if v else 0,
            "count": len,
            "min": lambda v: min(v) if v else None,
            "max": lambda v: max(v) if v else None,
        }
        if agg not in funcs:
            raise ToolInputError(f"unsupported aggregation '{agg}'")
        result = [{group_by: key, f"{agg}_{column}": funcs[agg](values)} for key, values in groups.items()]
        return _render(result), f"Aggregated {column} by {group_by} ({agg}) into {len(result)} groups"
    if operation == "to_json":
        return json.dumps(rows[:MAX_OUTPUT_ROWS], default=str), f"Converted {len(rows)} rows to JSON"
    if operation == "to_csv":
        return _render(rows), f"Converted {len(rows)} rows to CSV"
    raise ToolInputError(f"unknown operation '{operation}'")


def _render(rows: list[Row]) -> str:
    if not rows:
        return "(no rows)"
    columns: list[str] = []
    for row in rows:
        columns.extend(k for k in row if k not in columns)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    for row in rows[:MAX_OUTPUT_ROWS]:
        writer.writerow({k: format_number(v) if isinstance(v, float) else v for k, v in row.items()})
    if len(rows) > MAX_OUTPUT_ROWS:
        buffer.write(f"... ({len(rows) - MAX_OUTPUT_ROWS} more rows)\n")
    return buffer.getvalue()


async def _handle(args: dict[str, Any], _ctx: ToolContext) -> ToolResult:
    content, summary = run(args)
    return ToolResult(content=content, summary=summary)


data_process_tool = Tool(
    name="data_process",
    label="Data processing",
    description=(
        "Run basic data processing on small CSV or JSON datasets supplied by the user: "
        "'describe' (count/sum/mean/median/min/max/stdev per numeric column), 'sort', 'filter', "
        "'aggregate' (group_by + sum/mean/count/min/max), 'to_json', 'to_csv'. "
        "Pass the raw data as a string. A plain list of numbers can be passed as a JSON array."
    ),
    parameters={
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["describe", "sort", "filter", "aggregate", "to_json", "to_csv"]},
            "data": {"type": "string", "description": "CSV text with header row, or a JSON array"},
            "column": {"type": "string"},
            "order": {"type": "string", "enum": ["asc", "desc"]},
            "operator": {"type": "string", "enum": ["==", "!=", ">", ">=", "<", "<=", "contains"]},
            "value": {"type": ["string", "number"]},
            "group_by": {"type": "string"},
            "aggregation": {"type": "string", "enum": ["sum", "mean", "count", "min", "max"]},
        },
        "required": ["operation", "data"],
    },
    handler=_handle,
    timeout_seconds=5.0,
)
