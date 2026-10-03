from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.chat import ID_PATTERN
from app.schemas.common import ApiModel, Capability


class FeedbackRequest(ApiModel):
    conversation_id: str = Field(pattern=ID_PATTERN)
    message_id: str = Field(pattern=ID_PATTERN)
    rating: Literal["up", "down"]
    comment: str | None = Field(default=None, max_length=1000)
    capability: Capability | None = None
    model: str | None = Field(default=None, max_length=128)


class FeedbackResponse(ApiModel):
    id: str
    message_id: str
    rating: Literal["up", "down"]
    created_at: datetime
    updated_at: datetime
