from typing import Any

import httpx
from pydantic import SecretStr

from tests.conftest import chat, user_message


async def test_health(client: httpx.AsyncClient, contract: Any) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    contract("HealthResponse", response.json())
    assert response.json()["database"] == "ok"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-request-id"]


async def test_capabilities(client: httpx.AsyncClient, contract: Any) -> None:
    body = (await client.get("/capabilities")).json()
    contract("CapabilitiesResponse", body)
    assert [c["id"] for c in body["capabilities"]] == ["fast", "reasoning", "vision"]
    assert {t["name"] for t in body["tools"]} == {
        "calculator",
        "unit_convert",
        "datetime",
        "data_process",
        "web_search",
    }
    assert ".pdf" in body["uploads"]["document_extensions"]


async def test_feedback_create_and_update(client: httpx.AsyncClient, contract: Any) -> None:
    events = await chat(client, [user_message("hello")])
    message_id = events[0][1]["message_id"]
    payload = {"conversation_id": "conv_test", "message_id": message_id, "rating": "up", "capability": "fast"}
    created = await client.post("/feedback", json=payload)
    assert created.status_code == 201
    contract("FeedbackResponse", created.json())

    updated = await client.post("/feedback", json={**payload, "rating": "down", "comment": "too short"})
    assert updated.status_code == 200
    assert updated.json()["id"] == created.json()["id"] and updated.json()["rating"] == "down"

    metrics = (await client.get("/metrics")).json()
    assert metrics["feedback"] == {"up": 0, "down": 1}


async def test_feedback_validation(client: httpx.AsyncClient) -> None:
    response = await client.post("/feedback", json={"conversation_id": "c", "message_id": "m", "rating": "meh"})
    assert response.status_code == 422


async def test_metrics_reflect_traffic(client: httpx.AsyncClient, contract: Any) -> None:
    await chat(client, [user_message("hello")])
    await chat(client, [user_message("calculate 2 * 21")])
    await chat(client, [user_message("boom [[mock:fail]]")])
    metrics = (await client.get("/metrics", params={"window_minutes": 5})).json()
    contract("MetricsResponse", metrics)
    assert metrics["total_requests"] == 3
    assert metrics["by_status"] == {"completed": 2, "error": 1}
    assert metrics["errors_by_code"] == {"upstream_unavailable": 1}
    assert metrics["tool_usage"] == {"calculator": 1}
    assert metrics["total_retries"] == 3
    assert metrics["ttft_ms"]["p50"] is not None


async def test_metrics_token(client: httpx.AsyncClient, container: Any) -> None:
    container.settings.ops_token = SecretStr("s3cret")
    assert (await client.get("/metrics")).status_code == 401
    assert (await client.get("/metrics", headers={"Authorization": "Bearer wrong"})).status_code == 401
    assert (await client.get("/metrics", headers={"Authorization": "Bearer s3cret"})).status_code == 200


async def test_unknown_route_uses_error_envelope(client: httpx.AsyncClient, contract: Any) -> None:
    response = await client.get("/nope")
    assert response.status_code == 404
    contract("ErrorResponse", response.json())


async def test_metrics_disabled_in_production_without_token(client: httpx.AsyncClient, container: Any) -> None:
    container.settings.app_env = "production"
    response = await client.get("/metrics")
    assert response.status_code == 401
    assert "OPS_TOKEN" in response.json()["error"]["message"]


async def test_oversized_bodies_are_rejected_before_parsing(client: httpx.AsyncClient, container: Any) -> None:
    container.settings.max_request_bytes = 1000
    big = {"conversation_id": "c", "messages": [user_message("x" * 2000)]}
    response = await client.post("/chat/stream", json=big)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
    assert response.headers["x-request-id"]

    container.settings.upload_max_bytes = 100
    upload = await client.post("/files", files={"file": ("a.txt", b"a" * 200_000)})
    assert upload.status_code == 413


async def test_database_outage_degrades_gracefully(client: httpx.AsyncClient, container: Any) -> None:
    """With the database down: health reports degraded, DB-backed endpoints return a handled 503,
    and chat still streams (telemetry is best-effort)."""
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.db.session import Database

    broken = Database.__new__(Database)
    broken.engine = create_async_engine("postgresql+asyncpg://nexa:x@db-host.invalid:5432/nexa")
    from sqlalchemy.ext.asyncio import async_sessionmaker

    broken.session_factory = async_sessionmaker(broken.engine, expire_on_commit=False)
    container.db = broken
    container.chat.db = broken

    health = await client.get("/health")
    assert health.status_code == 503 and health.json()["database"] == "unavailable"

    metrics = await client.get("/metrics")
    assert metrics.status_code == 503
    assert metrics.json()["error"]["code"] == "service_unavailable"
    assert "invalid" not in metrics.text  # no infrastructure details leak

    events = await chat(client, [user_message("still there?")])
    assert events[-1][1]["finish_reason"] == "stop"
