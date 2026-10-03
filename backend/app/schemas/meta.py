from datetime import datetime
from typing import Literal

from app.schemas.common import ApiModel, Capability, CapabilityChoice


class HealthResponse(ApiModel):
    status: Literal["ok", "degraded"]
    version: str
    environment: str
    database: Literal["ok", "unavailable"]
    llm_provider: str
    search_provider: str


class CapabilityInfo(ApiModel):
    id: Capability
    label: str
    description: str
    supports_images: bool


class ToolInfo(ApiModel):
    name: str
    label: str
    description: str


class UploadLimits(ApiModel):
    max_bytes: int
    max_files_per_message: int
    document_extensions: list[str]
    image_extensions: list[str]
    retention_hours: int


class ChatLimits(ApiModel):
    max_message_chars: int
    max_messages: int


class CapabilitiesResponse(ApiModel):
    default: CapabilityChoice
    capabilities: list[CapabilityInfo]
    tools: list[ToolInfo]
    uploads: UploadLimits
    chat: ChatLimits


class Percentiles(ApiModel):
    p50: float | None
    p95: float | None
    max: float | None


class MetricsResponse(ApiModel):
    window_minutes: int
    since: datetime
    total_requests: int
    by_status: dict[str, int]
    by_capability: dict[str, int]
    errors_by_code: dict[str, int]
    tool_usage: dict[str, int]
    error_rate: float
    total_retries: int
    ttft_ms: Percentiles
    duration_ms: Percentiles
    feedback: dict[str, int]
