from saalis.audit.jsonl import JSONLAuditStore
from saalis.audit.sqlite import SQLiteAuditStore
from saalis.models import AuditEvent, AuditEventType


def make_event(event_type=AuditEventType.verdict_issued, **payload):
    return AuditEvent(event_type=event_type, payload=payload or {"test": True})


# ── JSONL ──────────────────────────────────────────────────────────────────


async def test_jsonl_append_and_query(tmp_path):
    store = JSONLAuditStore(tmp_path / "audit.jsonl")
    ev = make_event(AuditEventType.verdict_issued, verdict_id="v1")
    await store.append(ev)
    results = await store.query()
    assert len(results) == 1
    assert results[0].id == ev.id


async def test_jsonl_query_by_event_type(tmp_path):
    store = JSONLAuditStore(tmp_path / "audit.jsonl")
    await store.append(make_event(AuditEventType.verdict_issued))
    await store.append(make_event(AuditEventType.arbitration_started))
    results = await store.query(event_type=AuditEventType.verdict_issued)
    assert len(results) == 1
    assert results[0].event_type == AuditEventType.verdict_issued


async def test_jsonl_empty_file_returns_empty(tmp_path):
    store = JSONLAuditStore(tmp_path / "nonexistent.jsonl")
    assert await store.query() == []


async def test_jsonl_limit(tmp_path):
    store = JSONLAuditStore(tmp_path / "audit.jsonl")
    for i in range(10):
        await store.append(make_event(value=i))
    results = await store.query(limit=3)
    assert len(results) == 3


# ── SQLite ─────────────────────────────────────────────────────────────────


async def test_sqlite_append_and_query(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    store = SQLiteAuditStore(db_url)
    ev = make_event(AuditEventType.policy_checked, phase="pre")
    await store.append(ev)
    results = await store.query()
    assert len(results) == 1
    assert results[0].id == ev.id
    assert results[0].payload["phase"] == "pre"
    await store.close()


async def test_sqlite_query_by_event_type(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    store = SQLiteAuditStore(db_url)
    await store.append(make_event(AuditEventType.verdict_issued))
    await store.append(make_event(AuditEventType.human_deferred))
    results = await store.query(event_type=AuditEventType.human_deferred)
    assert len(results) == 1
    assert results[0].event_type == AuditEventType.human_deferred
    await store.close()


async def test_sqlite_multiple_appends(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    store = SQLiteAuditStore(db_url)
    for i in range(5):
        await store.append(make_event(AuditEventType.arbitration_started, i=i))
    results = await store.query(event_type=AuditEventType.arbitration_started)
    assert len(results) == 5
    await store.close()


async def test_sqlite_limit(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    store = SQLiteAuditStore(db_url)
    for i in range(10):
        await store.append(make_event(value=i))
    results = await store.query(limit=4)
    assert len(results) == 4
    await store.close()


async def test_sqlite_get_event(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    store = SQLiteAuditStore(db_url)
    ev = make_event(AuditEventType.verdict_issued, x=1)
    await store.append(ev)
    fetched = await store.get_event(ev.id)
    assert fetched is not None
    assert fetched.id == ev.id
    assert fetched.payload["x"] == 1
    await store.close()


async def test_sqlite_get_event_not_found(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    store = SQLiteAuditStore(db_url)
    assert await store.get_event("nonexistent") is None
    await store.close()


# ── DeferredDecision ────────────────────────────────────────────────────────


async def test_sqlite_defer_and_get(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    store = SQLiteAuditStore(db_url)
    ev = make_event(AuditEventType.human_deferred)
    await store.append(ev)
    await store.defer("decision-1", ev.id)

    deferred = await store.get_deferred("decision-1")
    assert deferred is not None
    assert deferred.decision_id == "decision-1"
    assert deferred.audit_event_id == ev.id
    assert deferred.resolved_at is None
    await store.close()


async def test_sqlite_get_deferred_not_found(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    store = SQLiteAuditStore(db_url)
    assert await store.get_deferred("missing") is None
    await store.close()


async def test_sqlite_resolve_deferred(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    store = SQLiteAuditStore(db_url)
    ev = make_event(AuditEventType.human_deferred)
    await store.append(ev)
    await store.defer("decision-2", ev.id)
    await store.resolve_deferred("decision-2", outcome="p1", resolved_by="ops@example.com")

    deferred = await store.get_deferred("decision-2")
    assert deferred is not None
    assert deferred.resolved_at is not None
    assert deferred.resolved_by == "ops@example.com"
    assert deferred.resolution_outcome == "p1"
    await store.close()


async def test_sqlite_resolve_deferred_not_found(tmp_path):
    import pytest

    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    store = SQLiteAuditStore(db_url)
    with pytest.raises(KeyError):
        await store.resolve_deferred("ghost", "p1", "ops")
    await store.close()
