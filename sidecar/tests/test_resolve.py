from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import RESOLVE_BODY


async def test_resolve_returns_verdict(client: AsyncClient):
    r = await client.post("/v1/decisions/resolve", json=RESOLVE_BODY)
    assert r.status_code == 200
    body = r.json()
    assert body["winner_proposal_id"] == "p1"
    assert body["strategy_name"] == "WeightedVote"
    assert body["status"] == "resolved"


async def test_resolve_explanation_present(client: AsyncClient):
    r = await client.post("/v1/decisions/resolve", json=RESOLVE_BODY)
    body = r.json()
    assert "summary" in body["explanation"]
    assert "score_breakdown" in body["explanation"]


async def test_resolve_no_agents_still_works(client: AsyncClient):
    body = {"question": "Go or no-go?", "proposals": [
        {"agent_id": "x", "content": "go", "confidence": 0.8},
    ]}
    r = await client.post("/v1/decisions/resolve", json=body)
    assert r.status_code == 200


async def test_resolve_requires_auth(auth_client: AsyncClient):
    r = await auth_client.post("/v1/decisions/resolve", json=RESOLVE_BODY)
    assert r.status_code == 401


async def test_resolve_auth_passes_with_token(auth_client: AsyncClient):
    r = await auth_client.post(
        "/v1/decisions/resolve",
        json=RESOLVE_BODY,
        headers={"Authorization": "Bearer secret"},
    )
    assert r.status_code == 200


async def test_resolve_auth_fails_wrong_token(auth_client: AsyncClient):
    r = await auth_client.post(
        "/v1/decisions/resolve",
        json=RESOLVE_BODY,
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401


async def test_resolve_defer_to_human(tmp_path):
    from tests.conftest import make_client, make_settings

    settings = make_settings(strategy="defer_to_human", audit_path=str(tmp_path / "test.db"))
    app, c = await make_client(settings)
    async with c:
        r = await c.post("/v1/decisions/resolve", json=RESOLVE_BODY)
    await app.state.app_state.audit_store.close()
    assert r.status_code == 200
    assert r.json()["status"] == "pending_human"
    assert r.json()["winner_proposal_id"] is None
