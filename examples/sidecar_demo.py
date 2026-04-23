"""
Saalis HTTP sidecar demo — no running server required.

Uses httpx + ASGITransport to call the FastAPI app in-process,
so the demo works out of the box without `uvicorn` or Docker.

Covers:
  1. POST /v1/decisions/resolve    — WeightedVote arbitration
  2. POST /v1/decisions/resolve    — DeferToHuman (pending_human)
  3. GET  /v1/decisions/{id}/audit — query audit events for a decision
  4. POST /v1/decisions/{id}/human_response — resolve a deferred decision
  5. GET  /v1/audit/events/{id}    — fetch a single audit event
  6. Bearer token authentication   — 401 on missing token
  7. GET  /healthz + /readyz       — liveness and readiness probes
  8. GET  /metrics                 — Prometheus metrics

To run against a real server instead, replace ASGITransport with:
    client = httpx.AsyncClient(base_url="http://localhost:8000",
                               headers={"Authorization": "Bearer secret"})
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from saalis_sidecar.app import create_app
from saalis_sidecar.settings import Settings
from saalis_sidecar.state import build_state

# ── shared request body ────────────────────────────────────────────────────

AGENTS = [
    {"id": "a1", "name": "GPT-4o", "weight": 1.0},
    {"id": "a2", "name": "Claude",  "weight": 1.5},
    {"id": "a3", "name": "Gemini", "weight": 1.0},
]

PROPOSALS = [
    {"id": "p1", "agent_id": "a1", "content": "Deploy immediately",  "confidence": 0.85},
    {"id": "p2", "agent_id": "a2", "content": "Deploy after review", "confidence": 0.75},
    {"id": "p3", "agent_id": "a3", "content": "Rollback and wait",   "confidence": 0.60},
]

QUESTION = "Should we deploy the new model to production?"


def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print("─" * 60)


def pp(data: dict | list) -> None:
    print(json.dumps(data, indent=2))


# ── app factory ────────────────────────────────────────────────────────────

def make_client(db_path: Path, strategy: str = "weighted_vote", token: str = "") -> tuple:
    settings = Settings(
        strategy=strategy,
        audit_path=str(db_path),
        bearer_token=token,
    )
    app = create_app(settings)
    app.state.app_state = build_state(settings)
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    return app, client


# ── 1. WeightedVote resolve ────────────────────────────────────────────────

async def demo_resolve(tmp: Path) -> str:
    section("1. POST /v1/decisions/resolve  (WeightedVote)")

    app, client = make_client(tmp / "arb.db")
    async with client:
        resp = await client.post("/v1/decisions/resolve", json={
            "question": QUESTION,
            "agents": AGENTS,
            "proposals": PROPOSALS,
        })
        data = resp.json()

    print(f"Status code:  {resp.status_code}")
    print(f"Winner:       {data['winner_proposal_id']}")
    print(f"Strategy:     {data['strategy_name']}")
    print(f"Verdict status: {data['status']}")
    await app.state.app_state.audit_store.close()
    return data["decision_id"]


# ── 2. DeferToHuman ────────────────────────────────────────────────────────

async def demo_defer(tmp: Path) -> tuple[str, object]:
    section("2. POST /v1/decisions/resolve  (DeferToHuman)")

    app, client = make_client(tmp / "defer.db", strategy="defer_to_human")
    async with client:
        resp = await client.post("/v1/decisions/resolve", json={
            "question": QUESTION,
            "agents": AGENTS,
            "proposals": PROPOSALS,
        })
        data = resp.json()

    print(f"Status code:    {resp.status_code}")
    print(f"Verdict status: {data['status']}")   # pending_human
    print(f"Summary:        {data['explanation']['summary']}")
    return data["decision_id"], app


# ── 3. Audit query ─────────────────────────────────────────────────────────

async def demo_audit(tmp: Path) -> None:
    section("3. GET /v1/decisions/{id}/audit")

    app, client = make_client(tmp / "audit.db")
    async with client:
        # Arbitrate first so there are events to query
        resolve_resp = await client.post("/v1/decisions/resolve", json={
            "question": QUESTION,
            "agents": AGENTS,
            "proposals": PROPOSALS,
        })
        decision_id = resolve_resp.json()["decision_id"]

        resp = await client.get(f"/v1/decisions/{decision_id}/audit")
        events = resp.json()

    print(f"Status code:  {resp.status_code}")
    print(f"Event count:  {len(events)}")
    for ev in events:
        print(f"  {ev['event_type']}")

    await app.state.app_state.audit_store.close()


# ── 4. Human response ──────────────────────────────────────────────────────

async def demo_human_response(tmp: Path) -> None:
    section("4. POST /v1/decisions/{id}/human_response")

    app, client = make_client(tmp / "human.db", strategy="defer_to_human")
    async with client:
        # Create a deferred decision
        resolve_resp = await client.post("/v1/decisions/resolve", json={
            "question": QUESTION,
            "agents": AGENTS,
            "proposals": PROPOSALS,
        })
        decision_id = resolve_resp.json()["decision_id"]
        print(f"Deferred decision id: {decision_id}")
        print(f"Initial status: {resolve_resp.json()['status']}")

        # Resolve it
        resp = await client.post(f"/v1/decisions/{decision_id}/human_response", json={
            "winner_proposal_id": "p2",
            "rationale": "Reviewed with the team — deploy after review is safest.",
            "operator_id": "alice",
        })
        data = resp.json()

    print(f"\nAfter human response:")
    print(f"  Status code:    {resp.status_code}")
    print(f"  Verdict status: {data['status']}")
    print(f"  Winner:         {data['winner_proposal_id']}")
    print(f"  Resolved by:    {data['explanation']['summary']}")

    await app.state.app_state.audit_store.close()


# ── 5. Fetch single audit event ────────────────────────────────────────────

async def demo_single_event(tmp: Path) -> None:
    section("5. GET /v1/audit/events/{event_id}")

    app, client = make_client(tmp / "event.db")
    async with client:
        resolve_resp = await client.post("/v1/decisions/resolve", json={
            "question": QUESTION,
            "agents": AGENTS,
            "proposals": PROPOSALS,
        })
        decision_id = resolve_resp.json()["decision_id"]

        # Get the audit trail and pick the first event
        audit_resp = await client.get(f"/v1/decisions/{decision_id}/audit")
        event_id = audit_resp.json()[0]["id"]

        resp = await client.get(f"/v1/audit/events/{event_id}")
        event = resp.json()

    print(f"Status code: {resp.status_code}")
    print(f"Event type:  {event['event_type']}")
    print(f"Event id:    {event['id']}")

    await app.state.app_state.audit_store.close()


# ── 6. Auth — 401 on missing token ────────────────────────────────────────

async def demo_auth(tmp: Path) -> None:
    section("6. Bearer token authentication")

    app, client = make_client(tmp / "auth.db", token="supersecret")
    async with client:
        # No token → 401
        resp_no_token = await client.post("/v1/decisions/resolve", json={
            "question": QUESTION, "agents": AGENTS, "proposals": PROPOSALS,
        })
        print(f"No token:     {resp_no_token.status_code} (expected 401)")

        # Wrong token → 401
        resp_wrong = await client.post("/v1/decisions/resolve",
            json={"question": QUESTION, "agents": AGENTS, "proposals": PROPOSALS},
            headers={"Authorization": "Bearer wrongtoken"},
        )
        print(f"Wrong token:  {resp_wrong.status_code} (expected 401)")

        # Correct token → 200
        resp_ok = await client.post("/v1/decisions/resolve",
            json={"question": QUESTION, "agents": AGENTS, "proposals": PROPOSALS},
            headers={"Authorization": "Bearer supersecret"},
        )
        print(f"Valid token:  {resp_ok.status_code} (expected 200)")

    await app.state.app_state.audit_store.close()


# ── 7. Health + readiness probes ───────────────────────────────────────────

async def demo_health(tmp: Path) -> None:
    section("7. GET /healthz  +  GET /readyz")

    app, client = make_client(tmp / "health.db")
    async with client:
        healthz = await client.get("/healthz")
        readyz  = await client.get("/readyz")

    print(f"/healthz → {healthz.status_code}  {healthz.json()}")
    print(f"/readyz  → {readyz.status_code}  {readyz.json()}")

    await app.state.app_state.audit_store.close()


# ── 8. Prometheus metrics ──────────────────────────────────────────────────

async def demo_metrics(tmp: Path) -> None:
    section("8. GET /metrics  (Prometheus)")

    app, client = make_client(tmp / "metrics.db")
    async with client:
        # Arbitrate once so counters are non-zero
        await client.post("/v1/decisions/resolve", json={
            "question": QUESTION, "agents": AGENTS, "proposals": PROPOSALS,
        })
        resp = await client.get("/metrics")

    lines = [l for l in resp.text.splitlines() if "saalis_" in l and not l.startswith("#")]
    print(f"Status code: {resp.status_code}")
    print("saalis_* metrics:")
    for line in lines:
        print(f"  {line}")

    await app.state.app_state.audit_store.close()


# ── main ───────────────────────────────────────────────────────────────────

async def main() -> None:
    print("\n🔷 Saalis HTTP sidecar demo")
    print("   (httpx ASGITransport — no server process needed)")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        await demo_resolve(tmp_path)
        await demo_defer(tmp_path)
        await demo_audit(tmp_path)
        await demo_human_response(tmp_path)
        await demo_single_event(tmp_path)
        await demo_auth(tmp_path)
        await demo_health(tmp_path)
        await demo_metrics(tmp_path)

    print(f"\n{'─' * 60}")
    print("  All sidecar demos complete.")
    print("─" * 60)


if __name__ == "__main__":
    asyncio.run(main())
