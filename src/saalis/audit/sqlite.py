from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from saalis.audit.base import AuditStore
from saalis.models import AuditEvent, AuditEventType


class _Base(DeclarativeBase):
    pass


class _AuditRow(_Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class SQLiteAuditStore(AuditStore):
    """SQLite-backed audit store using sqlalchemy async."""

    def __init__(self, db_url: str = "sqlite+aiosqlite:///./saalis_audit.db") -> None:
        self._engine = create_async_engine(db_url, echo=False)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)
        self._initialized = False

    async def _ensure_schema(self) -> None:
        if self._initialized:
            return
        async with self._engine.begin() as conn:
            await conn.run_sync(_Base.metadata.create_all)
        self._initialized = True

    async def append(self, event: AuditEvent) -> None:
        await self._ensure_schema()
        async with self._session_factory() as session:
            row = _AuditRow(
                id=event.id,
                event_type=event.event_type.value,
                payload=json.dumps(event.payload),
                timestamp=event.timestamp,
            )
            session.add(row)
            await session.commit()

    async def query(
        self,
        event_type: AuditEventType | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        await self._ensure_schema()
        async with self._session_factory() as session:
            stmt = select(_AuditRow).order_by(_AuditRow.timestamp)
            if event_type:
                stmt = stmt.where(_AuditRow.event_type == event_type.value)
            if since:
                stmt = stmt.where(_AuditRow.timestamp >= since)
            if until:
                stmt = stmt.where(_AuditRow.timestamp <= until)
            stmt = stmt.limit(limit)

            rows = (await session.execute(stmt)).scalars().all()
            return [
                AuditEvent(
                    id=row.id,
                    event_type=AuditEventType(row.event_type),
                    payload=json.loads(row.payload),
                    timestamp=row.timestamp.replace(tzinfo=UTC)
                    if row.timestamp.tzinfo is None
                    else row.timestamp,
                )
                for row in rows
            ]

    async def close(self) -> None:
        await self._engine.dispose()
