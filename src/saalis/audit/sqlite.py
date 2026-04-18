from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from saalis.audit.base import AuditStore
from saalis.models import AuditEvent, AuditEventType, DeferredDecision


class _Base(DeclarativeBase):
    pass


class _AuditRow(_Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class _DeferredRow(_Base):
    __tablename__ = "deferred_decisions"

    decision_id: Mapped[str] = mapped_column(String, primary_key=True)
    audit_event_id: Mapped[str] = mapped_column(String, nullable=False)
    deferred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    resolution_outcome: Mapped[str | None] = mapped_column(String, nullable=True)


def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


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

    # ── AuditEvent ────────────────────────────────────────────────────────

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
                    timestamp=_to_utc(row.timestamp),  # type: ignore[arg-type]
                )
                for row in rows
            ]

    async def get_event(self, event_id: str) -> AuditEvent | None:
        await self._ensure_schema()
        async with self._session_factory() as session:
            row = await session.get(_AuditRow, event_id)
            if row is None:
                return None
            return AuditEvent(
                id=row.id,
                event_type=AuditEventType(row.event_type),
                payload=json.loads(row.payload),
                timestamp=_to_utc(row.timestamp),  # type: ignore[arg-type]
            )

    # ── DeferredDecision ──────────────────────────────────────────────────

    async def get_deferred_event_id(self, decision_id: str) -> str | None:
        """Return the audit event id for the human_deferred event of a decision."""
        await self._ensure_schema()
        async with self._session_factory() as session:
            stmt = select(_AuditRow).where(
                _AuditRow.event_type == AuditEventType.human_deferred.value
            )
            rows = (await session.execute(stmt)).scalars().all()
            for row in rows:
                try:
                    payload = json.loads(row.payload)
                except (json.JSONDecodeError, ValueError):
                    continue
                if payload.get("decision_id") == decision_id:
                    return row.id
        return None

    async def defer(self, decision_id: str, audit_event_id: str) -> None:
        await self._ensure_schema()
        async with self._session_factory() as session:
            row = _DeferredRow(
                decision_id=decision_id,
                audit_event_id=audit_event_id,
                deferred_at=datetime.now(UTC),
            )
            session.add(row)
            await session.commit()

    async def get_deferred(self, decision_id: str) -> DeferredDecision | None:
        await self._ensure_schema()
        async with self._session_factory() as session:
            row = await session.get(_DeferredRow, decision_id)
            if row is None:
                return None
            return DeferredDecision(
                decision_id=row.decision_id,
                audit_event_id=row.audit_event_id,
                deferred_at=_to_utc(row.deferred_at),  # type: ignore[arg-type]
                resolved_at=_to_utc(row.resolved_at),
                resolved_by=row.resolved_by,
                resolution_outcome=row.resolution_outcome,
            )

    async def resolve_deferred(
        self, decision_id: str, outcome: str, resolved_by: str
    ) -> None:
        await self._ensure_schema()
        async with self._session_factory() as session:
            row = await session.get(_DeferredRow, decision_id)
            if row is None:
                raise KeyError(f"No deferred decision found for decision_id={decision_id!r}")
            row.resolved_at = datetime.now(UTC)
            row.resolved_by = resolved_by
            row.resolution_outcome = outcome
            await session.commit()

    async def close(self) -> None:
        await self._engine.dispose()
