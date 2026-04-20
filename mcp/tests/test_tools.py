from __future__ import annotations

import json

import pytest

from saalis_mcp.tools import (
    handle_arbitrate,
    handle_audit_query,
    handle_get_pending,
    handle_get_verdict,
    handle_human_respond,
)

AGENTS = [
    {"id": "a1", "name": "GPT-4o", "weight": 0.6},
    {"id": "a2", "name": "Claude", "weight": 0.9},
]
PROPOSALS = [
    {"id": "p1", "agent_id": "a1", "content": "Deploy now", "confidence": 0.85},
    {"id": "p2", "agent_id": "a2", "content": "Wait for review", "confidence": 0.75},
]
QUESTION = "Should we deploy to production?"


async def test_arbitrate_returns_verdict_json(weighted_state):
    result = await handle_arbitrate(weighted_state, {
        "question": QUESTION,
        "proposals": PROPOSALS,
        "agents": AGENTS,
    })
    data = json.loads(result)
    assert data["winner_proposal_id"] is not None
    assert data["status"] == "resolved"
    assert data["strategy_name"] == "WeightedVote"


async def test_arbitrate_populates_verdict_cache(weighted_state):
    result = await handle_arbitrate(weighted_state, {
        "question": QUESTION,
        "proposals": PROPOSALS,
        "agents": AGENTS,
    })
    data = json.loads(result)
    decision_id = data["decision_id"]
    assert decision_id in weighted_state.verdict_cache


async def test_arbitrate_deferred_status(deferred_state):
    result = await handle_arbitrate(deferred_state, {
        "question": QUESTION,
        "proposals": PROPOSALS,
        "agents": AGENTS,
    })
    data = json.loads(result)
    assert data["status"] == "pending_human"
    assert data["decision_id"] in deferred_state.verdict_cache


async def test_get_verdict_from_cache(weighted_state):
    arb_result = await handle_arbitrate(weighted_state, {
        "question": QUESTION,
        "proposals": PROPOSALS,
        "agents": AGENTS,
    })
    decision_id = json.loads(arb_result)["decision_id"]

    result = await handle_get_verdict(weighted_state, {"decision_id": decision_id})
    data = json.loads(result)
    assert data["decision_id"] == decision_id


async def test_get_verdict_unknown_returns_null(weighted_state):
    result = await handle_get_verdict(weighted_state, {"decision_id": "nonexistent-id"})
    assert result == "null"


async def test_audit_query_returns_events(weighted_state):
    await handle_arbitrate(weighted_state, {
        "question": QUESTION,
        "proposals": PROPOSALS,
        "agents": AGENTS,
    })
    result = await handle_audit_query(weighted_state, {})
    events = json.loads(result)
    assert len(events) >= 2


async def test_audit_query_filter_by_event_type(weighted_state):
    await handle_arbitrate(weighted_state, {
        "question": QUESTION,
        "proposals": PROPOSALS,
        "agents": AGENTS,
    })
    result = await handle_audit_query(weighted_state, {"event_type": "arbitration_started"})
    events = json.loads(result)
    assert all(e["event_type"] == "arbitration_started" for e in events)
    assert len(events) >= 1


async def test_human_respond_resolves_decision(deferred_state):
    arb_result = await handle_arbitrate(deferred_state, {
        "question": QUESTION,
        "proposals": PROPOSALS,
        "agents": AGENTS,
    })
    decision_id = json.loads(arb_result)["decision_id"]

    result = await handle_human_respond(deferred_state, {
        "decision_id": decision_id,
        "winner_proposal_id": "p1",
        "rationale": "p1 looks good",
        "operator_id": "reviewer-1",
    })
    data = json.loads(result)
    assert data["status"] == "resolved"
    assert data["winner_proposal_id"] == "p1"


async def test_human_respond_unknown_decision_raises(deferred_state):
    with pytest.raises(ValueError, match="No deferred decision"):
        await handle_human_respond(deferred_state, {
            "decision_id": "ghost-id",
            "winner_proposal_id": "p1",
        })


async def test_human_respond_already_resolved_raises(deferred_state):
    arb_result = await handle_arbitrate(deferred_state, {
        "question": QUESTION,
        "proposals": PROPOSALS,
        "agents": AGENTS,
    })
    decision_id = json.loads(arb_result)["decision_id"]

    await handle_human_respond(deferred_state, {
        "decision_id": decision_id,
        "winner_proposal_id": "p1",
    })

    with pytest.raises(ValueError, match="already resolved"):
        await handle_human_respond(deferred_state, {
            "decision_id": decision_id,
            "winner_proposal_id": "p2",
        })


async def test_get_pending_empty(weighted_state):
    result = await handle_get_pending(weighted_state, {})
    pending = json.loads(result)
    assert pending == []


async def test_get_pending_shows_deferred(deferred_state):
    arb_result = await handle_arbitrate(deferred_state, {
        "question": QUESTION,
        "proposals": PROPOSALS,
        "agents": AGENTS,
    })
    decision_id = json.loads(arb_result)["decision_id"]

    result = await handle_get_pending(deferred_state, {})
    pending = json.loads(result)
    assert any(d["decision_id"] == decision_id for d in pending)
