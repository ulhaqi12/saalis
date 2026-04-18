from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from saalis.models import AuditEvent, AuditEventType


class AuditStore(ABC):
    @abstractmethod
    async def append(self, event: AuditEvent) -> None: ...

    @abstractmethod
    async def query(
        self,
        event_type: AuditEventType | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]: ...

    async def close(self) -> None:
        """Release any held resources. Default is a no-op."""


class NullAuditStore(AuditStore):
    """No-op store for use when auditing is not needed."""

    async def append(self, event: AuditEvent) -> None:
        pass

    async def query(
        self,
        event_type: AuditEventType | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        return []
