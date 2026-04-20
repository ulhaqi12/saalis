# Audit Stores

Every arbitration emits a sequence of structured audit events. The audit store persists them so you can replay, query, and prove what happened.

## Audit events

| Event type | When emitted |
|---|---|
| `arbitration_started` | At the start of every `arbitrate()` call |
| `policy_checked` | After pre- and post-policy evaluation |
| `strategy_resolved` | After the strategy picks a winner |
| `verdict_issued` | After the final verdict is ready |
| `human_deferred` | When `DeferToHuman` is used |
| `human_responded` | When a human resolves a deferred decision (sidecar/MCP) |

Each event has an `id`, `event_type`, `timestamp`, and a `payload` dict carrying decision/verdict IDs and relevant metadata.

---

## NullAuditStore

Default. Discards all events. Zero overhead for development or testing.

```python
from saalis.audit.base import NullAuditStore

arb = Arbitrator(strategies=[WeightedVote()])
# NullAuditStore is used automatically when no audit_store is passed
```

---

## JSONLAuditStore

Appends events as newline-delimited JSON to a file. Simple, portable, and readable with any text tool.

```python
from saalis.audit.jsonl import JSONLAuditStore

store = JSONLAuditStore("audit.jsonl")
arb = Arbitrator(strategies=[WeightedVote()], audit_store=store)
await arb.arbitrate(decision)

# Query all events
events = await store.query()

# Query by event type
from saalis.models import AuditEventType
started = await store.query(event_type=AuditEventType.arbitration_started)

# Query by time range
from datetime import datetime, UTC
recent = await store.query(
    since=datetime(2025, 1, 1, tzinfo=UTC),
    limit=50,
)
```

File writes are non-blocking (`run_in_executor`), safe for high-throughput async use.

!!! note
    `JSONLAuditStore` supports `append` and `query` only. It does not support deferred decisions (`DeferToHuman` flow). Use `SQLiteAuditStore` for that.

---

## SQLiteAuditStore

Full-featured store backed by SQLite via SQLAlchemy async. Supports audit events **and** the deferred decision lifecycle.

```python
from saalis.audit.sqlite import SQLiteAuditStore

store = SQLiteAuditStore("sqlite+aiosqlite:///./saalis_audit.db")
arb = Arbitrator(strategies=[WeightedVote()], audit_store=store)
await arb.arbitrate(decision)

# Query events
events = await store.query(limit=100)

# Fetch a single event by ID
event = await store.get_event("some-event-id")

# Close the connection pool when done
await store.close()
```

The schema is created automatically on first use. Two tables:

- `audit_events` — all events
- `deferred_decisions` — records for `DeferToHuman` flow

### Deferred decision methods

These are used internally by the sidecar and MCP server. You can also call them directly:

```python
# Check if a decision is pending human input
deferred = await store.get_deferred(decision_id)
if deferred and deferred.resolved_at is None:
    print("Still waiting for human input")

# List all pending decisions
pending = await store.list_pending_deferred()

# Resolve a deferred decision
await store.resolve_deferred(
    decision_id=decision_id,
    outcome="p2",               # the winning proposal id
    resolved_by="alice",
)
```

---

## Choosing a store

| Requirement | Store |
|---|---|
| Development / testing | `NullAuditStore` |
| Simple persistent log, no HTTP/MCP | `JSONLAuditStore` |
| Full audit trail + `DeferToHuman` | `SQLiteAuditStore` |
| Production scale, multi-process | PostgreSQL (roadmap) |

---

## Writing a custom store

Subclass `AuditStore` and implement `append` and `query`:

```python
from saalis.audit.base import AuditStore
from saalis.models import AuditEvent, AuditEventType
from datetime import datetime

class InMemoryAuditStore(AuditStore):
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    async def append(self, event: AuditEvent) -> None:
        self._events.append(event)

    async def query(
        self,
        event_type: AuditEventType | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        results = self._events
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if since:
            results = [e for e in results if e.timestamp >= since]
        if until:
            results = [e for e in results if e.timestamp <= until]
        return results[:limit]
```
