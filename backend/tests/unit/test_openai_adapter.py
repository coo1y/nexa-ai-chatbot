"""The OpenAI-compatible adapter: stream assembly and error translation (no network)."""

from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest

from app.services.llm.base import CompletionRequest, Finish, LLMError, TextDelta, ToolCallsReady
from app.services.llm.openai_compatible import OpenAICompatibleProvider


def chunk(
    content: str | None = None, tool_calls: list | None = None, finish: str | None = None, usage: Any = None
) -> Any:
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=finish)], usage=usage)


def tc(index: int, id: str | None = None, name: str | None = None, args: str | None = None) -> Any:
    return SimpleNamespace(index=index, id=id, function=SimpleNamespace(name=name, arguments=args))


class FakeStream:
    def __init__(self, chunks: list[Any]) -> None:
        self.chunks = chunks

    def __aiter__(self):  # type: ignore[no-untyped-def]
        async def gen():  # type: ignore[no-untyped-def]
            for c in self.chunks:
                yield c

        return gen()


def provider_with(create: Any) -> OpenAICompatibleProvider:
    provider = OpenAICompatibleProvider(base_url="http://llm.invalid/v1", api_key="k", timeout=5)
    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))  # type: ignore[assignment]
    return provider


REQ = CompletionRequest(model="m", messages=[{"role": "user", "content": "hi"}], tools=[{"type": "function"}])


async def test_streams_text_and_usage() -> None:
    captured: dict[str, Any] = {}

    async def create(**kwargs: Any) -> FakeStream:
        captured.update(kwargs)
        return FakeStream(
            [
                chunk("Hel"),
                chunk("lo", finish="stop"),
                SimpleNamespace(choices=[], usage=SimpleNamespace(prompt_tokens=5, completion_tokens=2)),
            ]
        )

    events = [e async for e in provider_with(create).stream(REQ)]
    assert events[:2] == [TextDelta("Hel"), TextDelta("lo")]
    assert events[-1] == Finish(reason="stop", prompt_tokens=5, completion_tokens=2)
    assert captured["stream"] is True and captured["tool_choice"] == "auto"


async def test_assembles_streamed_tool_calls() -> None:
    async def create(**_: Any) -> FakeStream:
        return FakeStream(
            [
                chunk(tool_calls=[tc(0, id="call_a", name="calculator", args='{"expr')]),
                chunk(tool_calls=[tc(0, args='ession": "1+1"}')]),
                chunk(tool_calls=[tc(1, id="call_b", name="datetime", args="{}")], finish="tool_calls"),
            ]
        )

    events = [e async for e in provider_with(create).stream(REQ)]
    ready = next(e for e in events if isinstance(e, ToolCallsReady))
    assert [(c.id, c.name, c.arguments) for c in ready.calls] == [
        ("call_a", "calculator", '{"expression": "1+1"}'),
        ("call_b", "datetime", "{}"),
    ]
    assert events[-1].reason == "tool_calls"  # type: ignore[union-attr]


def _status_error(cls: type[openai.APIStatusError], status: int) -> openai.APIStatusError:
    request = httpx.Request("POST", "http://llm.invalid")
    return cls("err", response=httpx.Response(status, request=request), body=None)


@pytest.mark.parametrize(
    ("exc", "retryable", "code"),
    [
        (openai.APITimeoutError(request=httpx.Request("POST", "http://x")), True, "upstream_unavailable"),
        (_status_error(openai.RateLimitError, 429), True, "upstream_rate_limited"),
        (_status_error(openai.InternalServerError, 500), True, "upstream_unavailable"),
        (_status_error(openai.AuthenticationError, 401), False, "upstream_misconfigured"),
        (_status_error(openai.BadRequestError, 400), False, "upstream_bad_request"),
    ],
)
async def test_error_translation(exc: Exception, retryable: bool, code: str) -> None:
    async def create(**_: Any) -> Any:
        raise exc

    with pytest.raises(LLMError) as info:
        [e async for e in provider_with(create).stream(REQ)]
    assert (info.value.retryable, info.value.code) == (retryable, code)
