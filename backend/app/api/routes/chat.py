from collections.abc import AsyncIterator
from contextlib import aclosing

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.deps import ClientIdDep, ContainerDep, enforce_rate_limit
from app.schemas.chat import ChatRequest
from app.schemas.common import ErrorResponse

router = APIRouter(tags=["chat"])


@router.post(
    "/chat/stream",
    operation_id="streamChat",
    summary="Generate an assistant response as a Server-Sent Events stream",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"text/event-stream": {}}, "description": "Stream of chat events"},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
async def stream_chat(
    payload: ChatRequest, request: Request, container: ContainerDep, client_id: ClientIdDep
) -> StreamingResponse:
    enforce_rate_limit(container, request, client_id, "chat", container.settings.rate_limit_chat_per_minute)

    async def event_source() -> AsyncIterator[str]:
        async with aclosing(container.chat.stream(payload, client_id)) as events:
            async for name, data in events:
                yield f"event: {name}\ndata: {data.model_dump_json()}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
