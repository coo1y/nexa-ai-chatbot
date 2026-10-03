import json

import pytest

from app.services.tools.base import ToolInputError
from app.services.tools.data_process import describe, parse_table, run

CSV = "region,product,sales\nnorth,a,100\nsouth,a,250\nnorth,b,50\nsouth,b,\n"


def test_parse_csv_coerces_numbers() -> None:
    rows = parse_table(CSV)
    assert rows[0] == {"region": "north", "product": "a", "sales": 100}
    assert rows[3]["sales"] is None


def test_parse_json_numbers_list() -> None:
    assert parse_table("[1, 2, 3]") == [{"value": 1}, {"value": 2}, {"value": 3}]


def test_describe() -> None:
    stats = describe(parse_table(json.dumps([1, 2, 3, 4])))
    assert stats["value"]["mean"] == 2.5
    assert stats["value"]["median"] == 2.5
    assert stats["value"]["sum"] == 10


def test_sort_filter_aggregate() -> None:
    sorted_out, _ = run({"operation": "sort", "data": CSV, "column": "sales", "order": "desc"})
    assert sorted_out.splitlines()[1].startswith("south,a,250")

    filtered, summary = run({"operation": "filter", "data": CSV, "column": "sales", "operator": ">", "value": "75"})
    assert summary == "Filtered to 2 of 4 rows"
    assert "north,b" not in filtered

    aggregated, _ = run(
        {"operation": "aggregate", "data": CSV, "column": "sales", "group_by": "region", "aggregation": "sum"}
    )
    assert "north,150" in aggregated and "south,250" in aggregated


def test_convert_to_json() -> None:
    out, _ = run({"operation": "to_json", "data": CSV})
    assert json.loads(out)[1]["sales"] == 250


@pytest.mark.parametrize(
    "args",
    [
        {"operation": "describe", "data": ""},
        {"operation": "describe", "data": "{not json"},
        {"operation": "sort", "data": CSV},
        {"operation": "sort", "data": CSV, "column": "missing"},
        {"operation": "unknown", "data": CSV},
        {"operation": "describe", "data": "a,b\nx,y\n"},
    ],
)
def test_invalid(args: dict) -> None:
    with pytest.raises(ToolInputError):
        run(args)


def test_size_limit() -> None:
    with pytest.raises(ToolInputError, match="too large"):
        parse_table("[" + "1," * 150_000 + "1]")
