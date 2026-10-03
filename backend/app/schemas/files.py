from datetime import datetime
from typing import Literal

from app.schemas.common import ApiModel


class FileMeta(ApiModel):
    id: str
    filename: str
    kind: Literal["document", "image"]
    content_type: str
    size_bytes: int
    char_count: int
    page_count: int | None = None
    truncated: bool = False
    width: int | None = None
    height: int | None = None
    created_at: datetime
    expires_at: datetime
