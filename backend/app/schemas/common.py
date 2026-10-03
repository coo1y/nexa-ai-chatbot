from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

Capability = Literal["fast", "reasoning", "vision"]
CapabilityChoice = Literal["auto", "fast", "reasoning", "vision"]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
