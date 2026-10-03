import json

import pytest

import nexa_mcp


def test_operations_listed_from_contract() -> None:
    ops = nexa_mcp.list_operations(nexa_mcp.load_contract())
    assert {(o["method"], o["path"], o["operationId"]) for o in ops} >= {
        ("POST", "/chat/stream", "streamChat"),
        ("POST", "/files", "uploadFile"),
        ("GET", "/health", "getHealth"),
    }
    assert len(ops) == 8


def test_base_url_allow_list() -> None:
    assert nexa_mcp.resolve_base_url("http://localhost:8080/") == "http://localhost:8080"
    for bad in ["http://169.254.169.254", "file:///etc/passwd", "https://evil.example.com", "localhost"]:
        with pytest.raises(nexa_mcp.GuardrailError):
            nexa_mcp.resolve_base_url(bad)


def test_compare_contract_detects_drift() -> None:
    contract = {
        "paths": {"/health": {"get": {}}, "/feedback": {"post": {}}},
        "components": {"schemas": {"X": {"properties": {"a": {}, "b": {}}}}},
    }
    implemented = {
        "paths": {"/api/v1/health": {"get": {}}, "/api/v1/extra": {"get": {}}},
        "components": {"schemas": {"X": {"properties": {"a": {}, "c": {}}}}},
    }
    diff = nexa_mcp.compare_contract(contract, implemented)
    assert diff["in_sync"] is False
    assert diff["missing_in_backend"] == ["POST /feedback"]
    assert diff["undocumented_in_contract"] == ["GET /extra"]
    assert diff["schema_property_mismatches"] == {"X": {"only_in_contract": ["b"], "only_in_backend": ["c"]}}


def test_summarize_stream() -> None:
    def ev(name: str, data: dict) -> str:
        return f"event: {name}\ndata: {json.dumps(data)}\n\n"

    body = (
        ev("start", {"routing": {"capability": "fast"}})
        + ev(
            "tool_result",
            {"name": "calculator", "status": "success", "summary": "2+2 = 4", "id": "x", "duration_ms": 1},
        )
        + ev("delta", {"text": "It is "})
        + ev("delta", {"text": "4"})
        + ev("done", {"finish_reason": "stop"})
    )
    summary = nexa_mcp.summarize_stream(body)
    assert summary["routing"] == {"capability": "fast"}
    assert summary["text"] == "It is 4"
    assert summary["tools"] == [{"name": "calculator", "status": "success", "summary": "2+2 = 4"}]
    assert summary["done"] == {"finish_reason": "stop"}


async def test_tools_registered_with_read_only_hints() -> None:
    tools = {t.name: t for t in await nexa_mcp.mcp.list_tools()}
    assert set(tools) == {
        "contract_operations",
        "contract_schema",
        "contract_drift",
        "service_health",
        "service_metrics",
        "chat_probe",
    }
    assert tools["service_health"].annotations.read_only_hint is True
    assert tools["chat_probe"].annotations.read_only_hint is False


async def test_contract_schema_tool() -> None:
    result = await nexa_mcp.mcp.call_tool("contract_schema", {"name": "DeltaEvent"})
    assert "text" in json.dumps(result, default=str)
