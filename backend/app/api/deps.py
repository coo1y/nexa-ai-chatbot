"""FastAPI dependencies shared by the routes."""

import re
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.container import Container
from app.core.errors import ValidationFailed

_CLIENT_ID_RX = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def get_container(request: Request) -> Container:
    return request.app.state.container  # type: ignore[no-any-return]


async def get_session(container: Annotated[Container, Depends(get_container)]) -> AsyncIterator[AsyncSession]:
    async with container.db.session_factory() as session:
        yield session


def get_client_id(
    x_client_id: Annotated[
        str | None,
        Header(description="Anonymous browser-generated client identifier (future: replaced by user accounts)."),
    ] = None,
) -> str:
    if not x_client_id or not _CLIENT_ID_RX.match(x_client_id):
        raise ValidationFailed("Missing or invalid X-Client-Id header.", code="invalid_client_id")
    return x_client_id


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(container: Container, request: Request, client_id: str, scope: str, per_minute: int) -> None:
    container.rate_limiter.check(f"{scope}:client:{client_id}", per_minute)
    # Looser IP-level limit so rotating client ids does not bypass throttling.
    container.rate_limiter.check(f"{scope}:ip:{client_ip(request)}", per_minute * 3)


ContainerDep = Annotated[Container, Depends(get_container)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
ClientIdDep = Annotated[str, Depends(get_client_id)]
