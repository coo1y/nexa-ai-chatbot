"""The FastAPI implementation must match the hand-written OpenAPI contract."""

from typing import Any

import pytest

from app.main import create_app

REQUEST_SCHEMAS = ["ChatRequest", "ChatMessage", "AttachmentRef", "FeedbackRequest"]


@pytest.fixture(scope="module")
def generated() -> dict[str, Any]:
    return create_app().openapi()


def _operations(spec: dict[str, Any], prefix: str = "") -> dict[tuple[str, str], str]:
    ops = {}
    for path, item in spec["paths"].items():
        for method, op in item.items():
            if method in {"get", "post", "put", "patch", "delete"}:
                ops[(path.removeprefix(prefix), method)] = op["operationId"]
    return ops


def test_same_operations(openapi_spec: dict[str, Any], generated: dict[str, Any]) -> None:
    assert _operations(generated, "/api/v1") == _operations(openapi_spec)


def test_success_status_codes_match(openapi_spec: dict[str, Any], generated: dict[str, Any]) -> None:
    for path, item in openapi_spec["paths"].items():
        for method, op in item.items():
            if method == "parameters":
                continue
            implemented = generated["paths"][f"/api/v1{path}"][method]["responses"]
            contract_success = {c for c in op["responses"] if c.startswith("2")}
            implemented_success = {c for c in implemented if c.startswith("2")}
            assert contract_success <= implemented_success | {"200"}, (path, method)


def test_schema_properties_match(openapi_spec: dict[str, Any], generated: dict[str, Any]) -> None:
    contract = openapi_spec["components"]["schemas"]
    implemented = generated["components"]["schemas"]
    shared = [name for name in contract if name in implemented]
    assert len(shared) >= 15
    for name in shared:
        if "properties" not in contract[name]:
            continue
        assert set(contract[name]["properties"]) == set(implemented[name]["properties"]), name


@pytest.mark.parametrize("name", REQUEST_SCHEMAS)
def test_request_schemas_have_same_required_fields(
    openapi_spec: dict[str, Any], generated: dict[str, Any], name: str
) -> None:
    contract = openapi_spec["components"]["schemas"][name]
    implemented = generated["components"]["schemas"][name]
    assert set(contract.get("required", [])) == set(implemented.get("required", []))


def test_stream_events_documented(stream_event_schemas: dict[str, str]) -> None:
    from app.schemas.chat import StreamEventName

    assert set(stream_event_schemas) == set(StreamEventName.__args__)  # type: ignore[attr-defined]
