"""Data-access layer. Route handlers and services never build SQL themselves."""

import statistics
import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.db.base import utcnow
from app.db.models import ChatRequestLog, Feedback, UploadedFile


class FileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, file: UploadedFile) -> UploadedFile:
        self.session.add(file)
        await self.session.commit()
        return file

    async def get_for_client(self, file_id: str, client_id: str, *, with_data: bool = False) -> UploadedFile | None:
        stmt = select(UploadedFile).where(
            UploadedFile.id == file_id,
            UploadedFile.client_id == client_id,
            UploadedFile.expires_at > utcnow(),
        )
        if with_data:
            stmt = stmt.options(undefer(UploadedFile.data))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_many_for_client(self, file_ids: list[str], client_id: str) -> dict[str, UploadedFile]:
        if not file_ids:
            return {}
        stmt = (
            select(UploadedFile)
            .where(
                UploadedFile.id.in_(file_ids),
                UploadedFile.client_id == client_id,
                UploadedFile.expires_at > utcnow(),
            )
            .options(undefer(UploadedFile.data))
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return {row.id: row for row in rows}

    async def delete_for_client(self, file_id: str, client_id: str) -> bool:
        result = await self.session.execute(
            delete(UploadedFile).where(UploadedFile.id == file_id, UploadedFile.client_id == client_id)
        )
        await self.session.commit()
        return (result.rowcount or 0) > 0  # type: ignore[attr-defined]

    async def purge_expired(self, now: datetime | None = None) -> int:
        result = await self.session.execute(delete(UploadedFile).where(UploadedFile.expires_at <= (now or utcnow())))
        await self.session.commit()
        return result.rowcount or 0  # type: ignore[attr-defined]


class FeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        *,
        client_id: str,
        conversation_id: str,
        message_id: str,
        rating: str,
        comment: str | None,
        capability: str | None,
        model: str | None,
    ) -> tuple[Feedback, bool]:
        """Insert or update the rating a client gave a message. Returns (row, created)."""
        existing = (
            await self.session.execute(
                select(Feedback).where(Feedback.client_id == client_id, Feedback.message_id == message_id)
            )
        ).scalar_one_or_none()
        if existing:
            existing.rating = rating
            existing.comment = comment
            existing.updated_at = utcnow()
            await self.session.commit()
            return existing, False
        row = Feedback(
            id=str(uuid.uuid4()),
            client_id=client_id,
            conversation_id=conversation_id,
            message_id=message_id,
            rating=rating,
            comment=comment,
            capability=capability,
            model=model,
        )
        self.session.add(row)
        await self.session.commit()
        return row, True

    async def counts_since(self, since: datetime) -> dict[str, int]:
        rows = (
            await self.session.execute(
                select(Feedback.rating, func.count()).where(Feedback.updated_at >= since).group_by(Feedback.rating)
            )
        ).all()
        counts = {"up": 0, "down": 0}
        for rating, count in rows:
            counts[rating] = count
        return counts


class RequestLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, log: ChatRequestLog) -> None:
        self.session.add(log)
        await self.session.commit()

    async def summary(self, window: timedelta) -> dict:
        since = utcnow() - window
        rows = (
            (await self.session.execute(select(ChatRequestLog).where(ChatRequestLog.created_at >= since)))
            .scalars()
            .all()
        )
        by_status: dict[str, int] = {}
        by_capability: dict[str, int] = {}
        by_error: dict[str, int] = {}
        tool_usage: dict[str, int] = {}
        ttfts: list[int] = []
        durations: list[int] = []
        retries = 0
        for row in rows:
            by_status[row.status] = by_status.get(row.status, 0) + 1
            by_capability[row.capability] = by_capability.get(row.capability, 0) + 1
            if row.error_code:
                by_error[row.error_code] = by_error.get(row.error_code, 0) + 1
            for tool in row.tools_used or []:
                tool_usage[tool] = tool_usage.get(tool, 0) + 1
            if row.ttft_ms is not None:
                ttfts.append(row.ttft_ms)
            durations.append(row.duration_ms)
            retries += row.retries
        total = len(rows)
        return {
            "since": since,
            "total_requests": total,
            "by_status": by_status,
            "by_capability": by_capability,
            "errors_by_code": by_error,
            "tool_usage": tool_usage,
            "error_rate": round(by_status.get("error", 0) / total, 4) if total else 0.0,
            "total_retries": retries,
            "ttft_ms": _percentiles(ttfts),
            "duration_ms": _percentiles(durations),
        }


def _percentiles(values: list[int]) -> dict[str, float | None]:
    if not values:
        return {"p50": None, "p95": None, "max": None}
    ordered = sorted(values)
    if len(ordered) == 1:
        return {"p50": float(ordered[0]), "p95": float(ordered[0]), "max": float(ordered[0])}
    quantiles = statistics.quantiles(ordered, n=100, method="inclusive")
    return {"p50": round(quantiles[49], 1), "p95": round(quantiles[94], 1), "max": float(ordered[-1])}
