"""Chat request and Server-Sent-Event payload schemas (mirrors openapi.yaml)."""

from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import ApiModel, Capability, CapabilityChoice

MAX_MESSAGE_CHARS = 100_000
MAX_MESSAGES = 400
MAX_ATTACHMENTS_PER_MESSAGE = 10
ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"


class AttachmentRef(ApiModel):
    file_id: str = Field(pattern=r"^[0-9a-f-]{36}$")


class ChatMessage(ApiModel):
    id: str = Field(pattern=ID_PATTERN)
    role: Literal["user", "assistant"]
    content: str = Field(default="", max_length=MAX_MESSAGE_CHARS)
    attachments: list[AttachmentRef] = Field(default_factory=list, max_length=MAX_ATTACHMENTS_PER_MESSAGE)


class ChatRequest(ApiModel):
    conversation_id: str = Field(pattern=ID_PATTERN)
    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_MESSAGES)
    capability: CapabilityChoice = "auto"
    web_search: bool = Field(default=False, description="User explicitly requested a web search.")

    @field_validator("messages")
    @classmethod
    def _last_message_is_user(cls, messages: list[ChatMessage]) -> list[ChatMessage]:
        last = messages[-1]
        if last.role != "user":
            raise ValueError("the last message must be a user message")
        if not last.content.strip() and not last.attachments:
            raise ValueError("the last message must contain text or attachments")
        return messages


# --- Stream events -----------------------------------------------------------------------


class RoutingInfo(ApiModel):
    mode: Literal["auto", "manual"]
    capability: Capability
    model: str
    reason: str


class Source(ApiModel):
    id: int
    title: str
    url: str
    domain: str
    snippet: str = ""


class Usage(ApiModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class StartEvent(ApiModel):
    request_id: str
    message_id: str
    routing: RoutingInfo


class DeltaEvent(ApiModel):
    text: str


class ToolCallEvent(ApiModel):
    id: str
    name: str
    label: str
    input: dict


class ToolResultEvent(ApiModel):
    id: str
    name: str
    status: Literal["success", "error", "blocked"]
    summary: str
    duration_ms: int


class SourcesEvent(ApiModel):
    sources: list[Source]


class SafetyEvent(ApiModel):
    action: Literal["allow_with_guidance", "block"]
    category: str
    message: str


class ErrorEvent(ApiModel):
    code: str
    message: str
    retryable: bool


class DoneEvent(ApiModel):
    finish_reason: Literal["stop", "length", "blocked", "error"]
    usage: Usage
    ttft_ms: int | None
    duration_ms: int


StreamEventName = Literal["start", "delta", "tool_call", "tool_result", "sources", "safety", "error", "done"]
