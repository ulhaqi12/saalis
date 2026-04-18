from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from saalis.audit.base import AuditStore
from saalis.models import AuditEvent, AuditEventType


class JSONLAuditStore(AuditStore):
    """Append-only JSONL file audit store."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = asyncio.Lock()

    async def append(self, event: AuditEvent) -> None:
        line = event.model_dump_json() + "\n"
        loop = asyncio.get_event_loop()
        async with self._lock:
            await loop.run_in_executor(None, self._write_line, line)

    def _write_line(self, line: str) -> None:
        with self._path.open("a", encoding="utf-8") as f:
            f.write(line)

    async def query(
        self,
        event_type: AuditEventType | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        if not self._path.exists():
            return []

        results: list[AuditEvent] = []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                event = AuditEvent.model_validate_json(line)
                if event_type and event.event_type != event_type:
                    continue
                if since and event.timestamp < since:
                    continue
                if until and event.timestamp > until:
                    continue
                results.append(event)
                if len(results) >= limit:
                    break

        return results
