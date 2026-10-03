"""Shared fixtures.

Unit and integration tests both run against the real FastAPI app with the deterministic
mock LLM and mock search providers. Integration tests additionally use the database named
by TEST_DATABASE_URL (Postgres in CI), falling back to a temporary SQLite file.
"""

import json
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml
from sqlalchemy import text

from app.container import Container, build_container
from app.core.config import Settings
from app.db.base import Base
from app.db.session import Database
from app.main import create_app
from app.services.llm.mock import MockProvider
from app.services.tools.web_search import MockSearchProvider

ROOT = Path(__file__).resolve().parents[2]
OPENAPI_PATH = ROOT / "openapi.yaml"
CLIENT_ID = "test-client-0001"


def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "test",
        "database_url": os.environ.get("TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{tmp_path}/test.db",
        "llm_provider": "mock",
        "search_provider": "mock",
        "llm_retry_base_delay_seconds": 0.0,
        "rate_limit_chat_per_minute": 1000,
        "rate_limit_upload_per_minute": 1000,
        "log_level": "WARNING",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def mock_llm() -> MockProvider:
    return MockProvider()


@pytest.fixture
def mock_search() -> MockSearchProvider:
    return MockSearchProvider()


@pytest.fixture
async def container(
    settings: Settings, mock_llm: MockProvider, mock_search: MockSearchProvider
) -> AsyncIterator[Container]:
    db = Database(settings)
    await db.create_all()
    async with db.engine.begin() as conn:  # clean slate when sharing a Postgres database
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f"DELETE FROM {table.name}"))
    built = build_container(settings, llm=mock_llm, search=mock_search, db=db)
    yield built
    await db.dispose()


@pytest.fixture
async def client(container: Container) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(container=container)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver/api/v1", headers={"X-Client-Id": CLIENT_ID}
    ) as http:
        yield http


def parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for block in body.strip().split("\n\n"):
        name, data = None, None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if name and data is not None:
            events.append((name, data))
    return events


def user_message(content: str, attachments: list[str] | None = None, msg_id: str | None = None) -> dict[str, Any]:
    return {
        "id": msg_id or f"u{uuid.uuid4().hex[:10]}",
        "role": "user",
        "content": content,
        "attachments": [{"file_id": f} for f in attachments or []],
    }


def assistant_message(content: str) -> dict[str, Any]:
    return {"id": f"a{uuid.uuid4().hex[:10]}", "role": "assistant", "content": content, "attachments": []}


async def chat(
    client: httpx.AsyncClient, messages: list[dict[str, Any]], **extra: Any
) -> list[tuple[str, dict[str, Any]]]:
    payload = {"conversation_id": "conv_test", "messages": messages, **extra}
    response = await client.post("/chat/stream", json=payload)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    return parse_sse(response.text)


def text_of(events: list[tuple[str, dict[str, Any]]]) -> str:
    return "".join(data["text"] for name, data in events if name == "delta")


@pytest.fixture(scope="session")
def openapi_spec() -> dict[str, Any]:
    return yaml.safe_load(OPENAPI_PATH.read_text())
