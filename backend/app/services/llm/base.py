"""Provider-neutral LLM interface.

The orchestrator only depends on this module, so the concrete open-source model host
(Groq, OpenRouter, Together, self-hosted vLLM...) stays replaceable.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string as produced by the model


@dataclass(slots=True)
class TextDelta:
    text: str


@dataclass(slots=True)
class ToolCallsReady:
    calls: list[ToolCall]


@dataclass(slots=True)
class Finish:
    reason: str  # "stop" | "length" | "tool_calls"
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


LLMEvent = TextDelta | ToolCallsReady | Finish


@dataclass(slots=True)
class CompletionRequest:
    model: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    max_tokens: int = 2048
    temperature: float = 0.4
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMError(Exception):
    """Upstream model failure. ``retryable`` drives the retry policy."""

    def __init__(self, message: str, *, retryable: bool, code: str = "upstream_error") -> None:
        super().__init__(message)
        self.retryable = retryable
        self.code = code


class LLMProvider(Protocol):
    name: str

    def stream(self, request: CompletionRequest) -> AsyncIterator[LLMEvent]:
        """Stream a chat completion. Raises ``LLMError`` on failure."""
        ...

    async def complete(self, request: CompletionRequest) -> str:
        """Non-streaming completion (used for moderation)."""
        ...
