from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import make_client, make_settings


@pytest.fixture
async def defer_client(tmp_path):
    settings = make_settings(strategy="defer_to_human", audit_path=str(tmp_path / "test.db"))
    app, c = await make_client(settings)
    async with c:
        yield c
    await app.state.app_state.audit_store.close()


RESOLVE_BODY = {
    "question": "Approve the refactor?",
    "agents": [{"name": "Claude", "id": "a1", "weight": 1.0}],
    "proposals": [
        {"agent_id": "a1", "id": "p1", "content": "Approve", "confidence": 0.9},
        {"agent_id": "a1", "id": "p2", "content": "Reject", "confidence": 0.5},
    ],
}

HUMAN_BODY = {
    "winner_proposal_id": "p1",
    "rationale": "Reviewed carefully, looks good",
    "operator_id": "ops@example.com",
}


async def test_human_response_resolves_decision(defer_client: AsyncClient):
    r = await defer_client.post("/v1/decisions/resolve", json=RESOLVE_BODY)
    assert r.json()["status"] == "pending_human"
    decision_id = r.json()["decision_id"]

    r2 = await defer_client.post(
        f"/v1/decisions/{decision_id}/human_response", json=HUMAN_BODY
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "resolved"
    assert body["winner_proposal_id"] == "p1"
    assert "ops@example.com" in body["explanation"]["summary"]


async def test_human_response_emits_audit_event(defer_client: AsyncClient):
    r = await defer_client.post("/v1/decisions/resolve", json=RESOLVE_BODY)
    decision_id = r.json()["decision_id"]

    await defer_client.post(
        f"/v1/decisions/{decision_id}/human_response", json=HUMAN_BODY
    )

    events_r = await defer_client.get(f"/v1/decisions/{decision_id}/audit")
    event_types = [e["event_type"] for e in events_r.json()]
    assert "human_responded" in event_types


async def test_human_response_unknown_decision_404(defer_client: AsyncClient):
    r = await defer_client.post(
        "/v1/decisions/no-such-id/human_response", json=HUMAN_BODY
    )
    assert r.status_code == 404


async def test_human_response_already_resolved_409(defer_client: AsyncClient):
    r = await defer_client.post("/v1/decisions/resolve", json=RESOLVE_BODY)
    decision_id = r.json()["decision_id"]

    await defer_client.post(
        f"/v1/decisions/{decision_id}/human_response", json=HUMAN_BODY
    )
    # Second call on same decision
    r2 = await defer_client.post(
        f"/v1/decisions/{decision_id}/human_response", json=HUMAN_BODY
    )
    assert r2.status_code == 409
