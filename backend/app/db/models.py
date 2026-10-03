"""Persistent data model.

Conversations themselves live in the user's browser (product requirement). The server
database stores only what the server needs:

* ``uploaded_files``  – extracted document text / normalised images, kept for a limited
  retention window so follow-up questions can reference an upload by id.
* ``feedback``        – 👍/👎 ratings on assistant responses.
* ``chat_requests``   – content-free request telemetry (routing, latency, tools, status)
  used for operational diagnosis and latency benchmarking.

``client_id`` is an anonymous, browser-generated identifier. It is the extension point
for optional user accounts: a future ``users`` table can own client ids.
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Index, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime, utcnow


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(16))  # "document" | "image"
    size_bytes: Mapped[int] = mapped_column(Integer)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False)
    data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (UniqueConstraint("client_id", "message_id", name="uq_feedback_client_message"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    conversation_id: Mapped[str] = mapped_column(String(64))
    message_id: Mapped[str] = mapped_column(String(64))
    rating: Mapped[str] = mapped_column(String(8))  # "up" | "down"
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    capability: Mapped[str | None] = mapped_column(String(16), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class ChatRequestLog(Base):
    __tablename__ = "chat_requests"
    __table_args__ = (Index("ix_chat_requests_created_status", "created_at", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    conversation_id: Mapped[str] = mapped_column(String(64))
    routing_mode: Mapped[str] = mapped_column(String(8))  # "auto" | "manual"
    capability: Mapped[str] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(128))
    route_reason: Mapped[str] = mapped_column(String(255), default="")
    tools_used: Mapped[list[str]] = mapped_column(JSON, default=list)
    search_used: Mapped[bool] = mapped_column(Boolean, default=False)
    safety_action: Mapped[str] = mapped_column(String(24), default="allow")
    status: Mapped[str] = mapped_column(String(16))  # completed | stopped | error | blocked
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ttft_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
