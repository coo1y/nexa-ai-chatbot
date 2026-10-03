"""Deterministic, network-free provider.

Used for automated tests, CI end-to-end runs and offline demos. It mimics the behaviour
the orchestrator relies on: streamed text, tool calls (for calculator / unit conversion /
date-time / search follow-ups) and failures that can be triggered from a message.
"""

import asyncio
import json
import re
from collections.abc import AsyncIterator
from typing import Any

from app.services.llm.base import CompletionRequest, Finish, LLMError, LLMEvent, TextDelta, ToolCall, ToolCallsReady

FAIL_MARKER = "[[mock:fail]]"
SLOW_MARKER = "[[mock:slow]]"
_ARITHMETIC = re.compile(r"(?<![\w.])(\(*\s*-?\d[\d.,]*\s*\)*\s*(?:[-+*/^%]|\*\*)\s*[-+*/^%().\d\s,*]*[\d)])")
_CONVERSION = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*([a-zA-Z°/]+(?:\s[a-zA-Z]+)?)\s+(?:to|in|into)\s+([a-zA-Z°/]+(?:\s[a-zA-Z]+)?)", re.I
)


class MockProvider:
    name = "mock"

    def __init__(self, *, token_delay: float = 0.0, fail_times: int = 0) -> None:
        self.token_delay = token_delay
        # Number of upcoming calls that fail with a retryable error (tests use this).
        self.fail_times = fail_times
        self.calls: list[CompletionRequest] = []

    async def stream(self, request: CompletionRequest) -> AsyncIterator[LLMEvent]:
        self.calls.append(request)
        last_user = _last_user_text(request.messages)
        if self.fail_times > 0:
            self.fail_times -= 1
            raise LLMError("mock transient failure", retryable=True, code="upstream_unavailable")
        if FAIL_MARKER in last_user:
            raise LLMError("mock forced failure", retryable=True, code="upstream_unavailable")
        delay = 0.15 if SLOW_MARKER in last_user else self.token_delay

        last = request.messages[-1]
        if last.get("role") != "tool" and request.tools:
            call = _plan_tool_call(last_user, {t["function"]["name"] for t in request.tools})
            if call:
                yield ToolCallsReady([call])
                yield Finish(reason="tool_calls", prompt_tokens=_count(request), completion_tokens=8)
                return

        text = _compose_answer(request.messages, last_user)
        for token in re.findall(r"\S+\s*|\n", text):
            if delay:
                await asyncio.sleep(delay)
            yield TextDelta(token)
        yield Finish(reason="stop", prompt_tokens=_count(request), completion_tokens=len(text.split()))

    async def complete(self, request: CompletionRequest) -> str:
        self.calls.append(request)
        return "safe"


def _plan_tool_call(text: str, available: set[str]) -> ToolCall | None:
    lowered = text.lower()
    if "unit_convert" in available and (match := _CONVERSION.search(text)) and "convert" in lowered:
        value, src, dst = match.groups()
        args = {"value": float(value), "from_unit": src.strip(), "to_unit": dst.strip()}
        return ToolCall(id="call_convert", name="unit_convert", arguments=json.dumps(args))
    if (
        "calculator" in available
        and (match := _ARITHMETIC.search(text))
        and any(w in lowered for w in ("calculate", "compute", "what is", "what's", "evaluate", "="))
    ):
        expression = match.group(1).replace(",", "").replace("^", "**").strip()
        return ToolCall(id="call_calc", name="calculator", arguments=json.dumps({"expression": expression}))
    if "datetime" in available and any(w in lowered for w in ("what time", "today's date", "what day", "current date")):
        return ToolCall(id="call_time", name="datetime", arguments=json.dumps({"operation": "now", "timezone": "UTC"}))
    if "data_process" in available and "statistics" in lowered and (data := _extract_numbers(text)):
        args = {"operation": "describe", "data": json.dumps(data)}
        return ToolCall(id="call_data", name="data_process", arguments=json.dumps(args))
    return None


def _compose_answer(messages: list[dict[str, Any]], last_user: str) -> str:
    last = messages[-1]
    if last.get("role") == "tool":
        content = str(last.get("content", ""))
        if "<search_results query=" in content:
            summary = _first_line(content)
            return (
                "Here is what I found on the web [1]. The results were summarised from the listed sources [2].\n\n"
                + summary
            )
        return f"The tool returned: {content[:500]}"

    has_image = any(
        isinstance(m.get("content"), list) and any(p.get("type") == "image_url" for p in m["content"]) for m in messages
    )
    if any("<search_results query=" in str(m.get("content")) for m in messages):
        return "According to recent sources, here is a summary of the latest information [1]. Additional context is available [2]."
    if has_image:
        return "Mock vision analysis: the image shows the uploaded picture. I can describe colours, objects and layout."
    joined = " ".join(str(m.get("content")) for m in messages if isinstance(m.get("content"), str))
    if "<document name=" in joined:
        if "summar" in last_user.lower():
            return "**Summary:** The document discusses its main topic. Key points:\n\n- Point one\n- Point two"
        return "Based on the document, the answer to your question is found in the provided text."
    if "```" in last_user or "code" in last_user.lower() or "function" in last_user.lower():
        return "Here is an example:\n\n```python\ndef add(a: int, b: int) -> int:\n    return a + b\n```\n\nThis function adds two numbers."
    return f"Mock response to: {last_user[:200]}".strip()


_EMBEDDED_RX = re.compile(
    r"<(document|search_results)\b.*?</\1>(\n.*?\[1\]\.)?|\[(An attachment|Image attached)[^\]]*\]", re.S
)


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    """The user's own words in the latest turn (embedded documents/search results removed)."""
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, list):
                content = " ".join(p.get("text", "") for p in content if p.get("type") == "text")
            return _EMBEDDED_RX.sub("", str(content or "")).strip()
    return ""


def _first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip() and not line.strip().startswith("<"):
            return line.strip()[:300]
    return text[:300]


def _extract_numbers(text: str) -> list[float]:
    return [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", text)]


def _count(request: CompletionRequest) -> int:
    return sum(len(str(m.get("content", ""))) for m in request.messages) // 4
