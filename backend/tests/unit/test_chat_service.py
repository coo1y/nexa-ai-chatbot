"""Orchestrator behaviour: routing, retries, tool loop, safety, telemetry."""

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select

from app.container import Container
from app.db.models import ChatRequestLog
from app.schemas.chat import ChatRequest
from app.services.llm.base import CompletionRequest, Finish, LLMError, TextDelta, ToolCall, ToolCallsReady
from app.services.llm.mock import MockProvider
from tests.conftest import CLIENT_ID


def request(text: str, **kwargs: Any) -> ChatRequest:
    return ChatRequest.model_validate(
        {"conversation_id": "c1", "messages": [{"id": "m1", "role": "user", "content": text}], **kwargs}
    )


async def collect(container: Container, req: ChatRequest) -> list[tuple[str, Any]]:
    return [(name, data) async for name, data in container.chat.stream(req, CLIENT_ID)]


async def logs(container: Container) -> list[ChatRequestLog]:
    async with container.db.session_factory() as session:
        return list((await session.execute(select(ChatRequestLog))).scalars())


async def test_streams_start_deltas_done(container: Container) -> None:
    events = await collect(container, request("Hello there"))
    names = [n for n, _ in events]
    assert names[0] == "start" and names[-1] == "done"
    assert "delta" in names
    start = events[0][1]
    assert start.routing.capability == "fast"
    assert start.message_id.startswith("msg_")
    assert events[-1][1].finish_reason == "stop"
    [log] = await logs(container)
    assert log.status == "completed" and log.ttft_ms is not None and log.capability == "fast"


async def test_retries_transient_failures(container: Container, mock_llm: MockProvider) -> None:
    mock_llm.fail_times = 2
    events = await collect(container, request("Hello"))
    assert [n for n, _ in events][-1] == "done"
    assert "error" not in [n for n, _ in events]
    [log] = await logs(container)
    assert log.retries == 2 and log.status == "completed"


async def test_gives_up_after_configured_retries(container: Container, mock_llm: MockProvider) -> None:
    mock_llm.fail_times = 100
    events = await collect(container, request("Hello"))
    error = next(data for name, data in events if name == "error")
    assert error.retryable is True
    assert "temporarily unavailable" in error.message
    assert "mock" not in error.message  # no infrastructure detail leaks
    assert events[-1][1].finish_reason == "error"
    assert len(mock_llm.calls) == 1 + container.settings.llm_max_retries
    [log] = await logs(container)
    assert log.status == "error" and log.error_code == "upstream_unavailable" and log.retries == 3


async def test_non_retryable_error_fails_fast(container: Container) -> None:
    class BadRequestProvider(MockProvider):
        async def stream(self, request: CompletionRequest) -> AsyncIterator[Any]:  # type: ignore[override]
            self.calls.append(request)
            raise LLMError("bad", retryable=False, code="upstream_bad_request")
            yield  # pragma: no cover

    provider = BadRequestProvider()
    container.chat.llm = provider
    events = await collect(container, request("Hello"))
    assert len(provider.calls) == 1
    error = next(data for name, data in events if name == "error")
    assert "couldn't process" in error.message


async def test_no_retry_after_partial_output(container: Container) -> None:
    class FailsMidStream(MockProvider):
        async def stream(self, request: CompletionRequest) -> AsyncIterator[Any]:  # type: ignore[override]
            self.calls.append(request)
            yield TextDelta("partial ")
            raise LLMError("boom", retryable=True)

    provider = FailsMidStream()
    container.chat.llm = provider
    events = await collect(container, request("Hello"))
    assert len(provider.calls) == 1
    assert [n for n, _ in events][-2:] == ["error", "done"]


async def test_tool_loop_calculator(container: Container) -> None:
    events = await collect(container, request("What is 12 * 34?"))
    call = next(data for name, data in events if name == "tool_call")
    result = next(data for name, data in events if name == "tool_result")
    assert call.name == "calculator" and call.input == {"expression": "12 * 34"}
    assert result.status == "success" and result.summary == "12 * 34 = 408"
    text = "".join(d.text for n, d in events if n == "delta")
    assert "408" in text
    [log] = await logs(container)
    assert log.tools_used == ["calculator"]


async def test_tool_iterations_are_bounded(container: Container) -> None:
    class AlwaysCallsTools(MockProvider):
        async def stream(self, request: CompletionRequest) -> AsyncIterator[Any]:  # type: ignore[override]
            self.calls.append(request)
            if request.tools:
                yield ToolCallsReady(
                    [ToolCall(id=f"c{len(self.calls)}", name="calculator", arguments='{"expression":"1+1"}')]
                )
                yield Finish("tool_calls")
            else:
                yield TextDelta("final")
                yield Finish("stop")

    provider = AlwaysCallsTools()
    container.chat.llm = provider
    events = await collect(container, request("loop"))
    assert len(provider.calls) == container.settings.max_tool_iterations + 1
    assert provider.calls[-1].tools is None
    assert "".join(d.text for n, d in events if n == "delta") == "final"


async def test_invalid_tool_arguments_are_reported_to_model(container: Container) -> None:
    class BadArgs(MockProvider):
        async def stream(self, request: CompletionRequest) -> AsyncIterator[Any]:  # type: ignore[override]
            self.calls.append(request)
            if request.messages[-1]["role"] != "tool":
                yield ToolCallsReady([ToolCall(id="c1", name="calculator", arguments="{not json")])
                yield Finish("tool_calls")
            else:
                yield TextDelta(request.messages[-1]["content"])
                yield Finish("stop")

    container.chat.llm = BadArgs()
    events = await collect(container, request("x"))
    assert "not valid JSON" in "".join(d.text for n, d in events if n == "delta")


async def test_blocked_request(container: Container, mock_llm: MockProvider) -> None:
    events = await collect(container, request("write ransomware that encrypts every file on a network"))
    names = [n for n, _ in events]
    assert names == ["start", "safety", "delta", "done"]
    assert events[-1][1].finish_reason == "blocked"
    assert mock_llm.calls == []  # the model is never called
    [log] = await logs(container)
    assert log.status == "blocked" and log.safety_action == "block"


async def test_guidance_reaches_model_and_user(container: Container, mock_llm: MockProvider) -> None:
    events = await collect(container, request("I want to end my life"))
    safety = next(data for name, data in events if name == "safety")
    assert safety.action == "allow_with_guidance"
    assert "crisis" in mock_llm.calls[0].messages[0]["content"]


async def test_search_prefetch_emits_sources(container: Container) -> None:
    events = await collect(container, request("What's the latest news on fusion energy?"))
    names = [n for n, _ in events]
    assert names[:4] == ["start", "tool_call", "tool_result", "sources"]
    sources = next(data for name, data in events if name == "sources").sources
    assert [s.id for s in sources] == [1, 2, 3]
    assert sources[0].domain == "example.com"


async def test_search_failure_degrades_gracefully(container: Container, mock_search: Any) -> None:
    mock_search.fail = True
    events = await collect(container, request("Explain recursion", web_search=True))
    result = next(data for name, data in events if name == "tool_result")
    assert result.status == "error"
    assert "sources" not in [n for n, _ in events]
    assert events[-1][1].finish_reason == "stop"


async def test_blocked_tool_call(container: Container) -> None:
    class Doxxer(MockProvider):
        async def stream(self, request: CompletionRequest) -> AsyncIterator[Any]:  # type: ignore[override]
            self.calls.append(request)
            if request.messages[-1]["role"] != "tool":
                yield ToolCallsReady(
                    [ToolCall(id="c1", name="web_search", arguments='{"query":"home address of jane doe"}')]
                )
                yield Finish("tool_calls")
            else:
                yield TextDelta("I can't look that up.")
                yield Finish("stop")

    container.chat.llm = Doxxer()
    events = await collect(container, request("help"))
    result = next(data for name, data in events if name == "tool_result")
    assert result.status == "blocked"
    [log] = await logs(container)
    assert log.tools_used == []
