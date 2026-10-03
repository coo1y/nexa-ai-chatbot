"""Adapter for any OpenAI-compatible chat-completions endpoint."""

from collections.abc import AsyncIterator
from typing import Any

import openai
from openai import AsyncOpenAI

from app.services.llm.base import (
    CompletionRequest,
    Finish,
    LLMError,
    LLMEvent,
    TextDelta,
    ToolCall,
    ToolCallsReady,
)


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, *, base_url: str, api_key: str, timeout: float) -> None:
        # Retries are handled by the orchestrator so that they are configurable and visible.
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=0)

    async def stream(self, request: CompletionRequest) -> AsyncIterator[LLMEvent]:
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if request.tools:
            kwargs["tools"] = request.tools
            kwargs["tool_choice"] = "auto"
        try:
            stream = await self._client.chat.completions.create(**kwargs)
            pending: dict[int, dict[str, str]] = {}
            finish_reason = "stop"
            usage: Any = None
            async for chunk in stream:
                if getattr(chunk, "usage", None):
                    usage = chunk.usage
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta
                if delta and delta.content:
                    yield TextDelta(delta.content)
                if delta and delta.tool_calls:
                    for tc in delta.tool_calls:
                        slot = pending.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                        if tc.id:
                            slot["id"] = tc.id
                        if tc.function and tc.function.name:
                            slot["name"] = tc.function.name
                        if tc.function and tc.function.arguments:
                            slot["arguments"] += tc.function.arguments
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
            if pending:
                calls = [
                    ToolCall(id=slot["id"] or f"call_{index}", name=slot["name"], arguments=slot["arguments"] or "{}")
                    for index, slot in sorted(pending.items())
                ]
                yield ToolCallsReady(calls)
                finish_reason = "tool_calls"
            yield Finish(
                reason=finish_reason,
                prompt_tokens=getattr(usage, "prompt_tokens", None),
                completion_tokens=getattr(usage, "completion_tokens", None),
            )
        except openai.APIError as exc:
            raise _translate(exc) from exc

    async def complete(self, request: CompletionRequest) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=request.model,
                messages=request.messages,  # type: ignore[arg-type]
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            )
        except openai.APIError as exc:
            raise _translate(exc) from exc
        return response.choices[0].message.content or ""


def _translate(exc: openai.APIError) -> LLMError:
    if isinstance(exc, (openai.APITimeoutError, openai.APIConnectionError)):
        return LLMError("model endpoint unreachable", retryable=True, code="upstream_unavailable")
    if isinstance(exc, openai.RateLimitError):
        return LLMError("model rate limited", retryable=True, code="upstream_rate_limited")
    if isinstance(exc, openai.InternalServerError):
        return LLMError("model server error", retryable=True, code="upstream_unavailable")
    if isinstance(exc, (openai.AuthenticationError, openai.PermissionDeniedError)):
        return LLMError("model credentials rejected", retryable=False, code="upstream_misconfigured")
    if isinstance(exc, openai.BadRequestError):
        # e.g. context too long or unsupported content for the selected model.
        return LLMError("model rejected the request", retryable=False, code="upstream_bad_request")
    return LLMError("model request failed", retryable=True, code="upstream_error")
