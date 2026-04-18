from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import RESOLVE_BODY


async def test_audit_by_decision_id(client: AsyncClient):
    r = await client.post("/v1/decisions/resolve", json=RESOLVE_BODY)
    decision_id = r.json()["decision_id"]

    r2 = await client.get(f"/v1/decisions/{decision_id}/audit")
    assert r2.status_code == 200
    events = r2.json()
    assert len(events) > 0
    assert all(e["payload"].get("decision_id") == decision_id for e in events)


async def test_audit_unknown_decision_returns_empty(client: AsyncClient):
    r = await client.get("/v1/decisions/nonexistent-id/audit")
    assert r.status_code == 200
    assert r.json() == []


async def test_get_event_by_id(client: AsyncClient):
    r = await client.post("/v1/decisions/resolve", json=RESOLVE_BODY)
    decision_id = r.json()["decision_id"]

    events_r = await client.get(f"/v1/decisions/{decision_id}/audit")
    event_id = events_r.json()[0]["id"]

    r2 = await client.get(f"/v1/audit/events/{event_id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == event_id


async def test_get_event_not_found(client: AsyncClient):
    r = await client.get("/v1/audit/events/no-such-event")
    assert r.status_code == 404
