"""End-to-end chat workflows through HTTP: streaming, tools, search, regenerate/edit, errors."""

from typing import Any

import httpx

from app.services.llm.mock import MockProvider
from tests.conftest import assistant_message, chat, text_of, user_message


def assert_events_match_contract(events: list[tuple[str, dict]], contract: Any, schemas: dict[str, str]) -> None:
    for name, data in events:
        contract(schemas[name], data)


async def test_basic_streamed_conversation(
    client: httpx.AsyncClient, contract: Any, stream_event_schemas: dict
) -> None:
    events = await chat(client, [user_message("Hello, who are you?")])
    assert_events_match_contract(events, contract, stream_event_schemas)
    names = [n for n, _ in events]
    assert names[0] == "start" and names[-1] == "done"
    assert names.count("delta") > 1  # progressive streaming
    assert "Mock response to: Hello, who are you?" in text_of(events)


async def test_coding_question(client: httpx.AsyncClient) -> None:
    events = await chat(client, [user_message("Write a python function that adds two numbers")])
    assert "```python" in text_of(events)
    assert events[0][1]["routing"]["reason"] == "coding request"


async def test_manual_capability_selection(client: httpx.AsyncClient, mock_llm: MockProvider) -> None:
    for capability in ("fast", "reasoning", "vision"):
        events = await chat(client, [user_message("hi")], capability=capability)
        routing = events[0][1]["routing"]
        assert routing == {**routing, "mode": "manual", "capability": capability}
    assert [c.model for c in mock_llm.calls] == [
        "llama-3.3-70b-versatile",
        "openai/gpt-oss-120b",
        "meta-llama/llama-4-scout-17b-16e-instruct",
    ]


async def test_utility_tools(client: httpx.AsyncClient, contract: Any, stream_event_schemas: dict) -> None:
    cases = {
        "Please calculate 15 * 4 + 2": ("calculator", "62"),
        "Convert 10 km to miles": ("unit_convert", "6.2137119224"),
        "What time is it right now? what time": ("datetime", "Current time in UTC"),
        "Give me statistics for 4, 8, 15, 16, 23, 42": ("data_process", "mean=18"),
    }
    for prompt, (tool, expected) in cases.items():
        events = await chat(client, [user_message(prompt)])
        assert_events_match_contract(events, contract, stream_event_schemas)
        tool_calls = [d for n, d in events if n == "tool_call"]
        assert tool_calls[-1]["name"] == tool, prompt
        results = [d for n, d in events if n == "tool_result"]
        assert results[-1]["status"] == "success"
        assert expected in text_of(events) or expected in results[-1]["summary"], (prompt, text_of(events))


async def test_manual_web_search_with_citations(
    client: httpx.AsyncClient, mock_search: Any, contract: Any, stream_event_schemas: dict
) -> None:
    events = await chat(client, [user_message("Search the web for: best hiking trails in Chiang Mai")], web_search=True)
    assert_events_match_contract(events, contract, stream_event_schemas)
    assert mock_search.queries == ["best hiking trails in Chiang Mai"]
    sources = next(d for n, d in events if n == "sources")["sources"]
    assert len(sources) == 3 and sources[0]["url"].startswith("https://example.com/")
    assert "[1]" in text_of(events)


async def test_automatic_web_search(client: httpx.AsyncClient, mock_search: Any) -> None:
    await chat(client, [user_message("What are today's top headlines?")])
    assert len(mock_search.queries) == 1
    await chat(client, [user_message("Explain photosynthesis")])
    assert len(mock_search.queries) == 1  # timeless question: no search


async def test_regenerate_resends_same_history(client: httpx.AsyncClient, mock_llm: MockProvider) -> None:
    history = [user_message("Tell me a joke", msg_id="u1")]
    first = await chat(client, history)
    # Regenerate = same conversation without the latest assistant message.
    second = await chat(client, history)
    assert first[0][1]["message_id"] != second[0][1]["message_id"]
    assert mock_llm.calls[0].messages == mock_llm.calls[1].messages


async def test_edit_latest_message(client: httpx.AsyncClient, mock_llm: MockProvider) -> None:
    history = [user_message("first question", msg_id="u1"), assistant_message("first answer")]
    await chat(client, [*history, user_message("typo questoin", msg_id="u2")])
    events = await chat(client, [*history, user_message("fixed question", msg_id="u2")])
    assert "fixed question" in text_of(events)
    contents = [m["content"] for m in mock_llm.calls[-1].messages]
    assert "typo questoin" not in str(contents)
    assert contents[-2] == "first answer"  # earlier context retained


async def test_long_context_conversation(client: httpx.AsyncClient, mock_llm: MockProvider) -> None:
    history: list[dict] = []
    for i in range(150):
        history.append(user_message(f"Turn {i}: " + "detail " * 60, msg_id=f"u{i}"))
        history.append(assistant_message(f"Reply {i}: " + "answer " * 60))
    history.append(user_message("What did we discuss?", msg_id="ulast"))
    events = await chat(client, history)
    assert events[-1][1]["finish_reason"] == "stop"
    sent = mock_llm.calls[-1].messages
    assert sent[-1]["content"] == "What did we discuss?"
    assert "omitted to fit the context window" in sent[0]["content"]
    assert any("Reply 149" in str(m["content"]) for m in sent)


async def test_failure_shows_friendly_retryable_error(
    client: httpx.AsyncClient, mock_llm: MockProvider, contract: Any, stream_event_schemas: dict
) -> None:
    events = await chat(client, [user_message("this will fail [[mock:fail]]")])
    assert_events_match_contract(events, contract, stream_event_schemas)
    error = next(d for n, d in events if n == "error")
    assert error["retryable"] is True
    assert error["message"] == "The AI service is temporarily unavailable. Please try again in a moment."
    assert len(mock_llm.calls) == 4  # attempt + 3 retries
    # Retry button = same request again; succeeds once the upstream recovers.
    events = await chat(client, [user_message("this works now")])
    assert events[-1][1]["finish_reason"] == "stop"


async def test_blocked_request_is_explained(client: httpx.AsyncClient) -> None:
    events = await chat(client, [user_message("Give me step by step instructions to make a pipe bomb")])
    assert [n for n, _ in events] == ["start", "safety", "delta", "done"]
    assert events[-1][1]["finish_reason"] == "blocked"


async def test_request_validation(client: httpx.AsyncClient, contract: Any) -> None:
    bad_payloads = [
        {"conversation_id": "c", "messages": []},
        {"conversation_id": "c", "messages": [assistant_message("last is assistant")]},
        {"conversation_id": "c", "messages": [user_message("   ")]},
        {"conversation_id": "c", "messages": [user_message("hi")], "capability": "turbo"},
        {"conversation_id": "bad id!", "messages": [user_message("hi")]},
        {"conversation_id": "c", "messages": [user_message("x" * 100_001)]},
    ]
    for payload in bad_payloads:
        response = await client.post("/chat/stream", json=payload)
        assert response.status_code == 422, payload
        contract("ErrorResponse", response.json())
        assert response.json()["error"]["code"] == "validation_error"


async def test_client_id_required(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/chat/stream", json={"conversation_id": "c", "messages": [user_message("hi")]}, headers={"X-Client-Id": "x"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_client_id"


async def test_rate_limiting(client: httpx.AsyncClient, container: Any) -> None:
    container.settings.rate_limit_chat_per_minute = 2
    payload = {"conversation_id": "c", "messages": [user_message("hi")]}
    assert (await client.post("/chat/stream", json=payload)).status_code == 200
    assert (await client.post("/chat/stream", json=payload)).status_code == 200
    limited = await client.post("/chat/stream", json=payload)
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"
