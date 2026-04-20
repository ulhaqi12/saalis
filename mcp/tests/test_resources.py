from __future__ import annotations

import json

from saalis_mcp.resources import handle_decision_audit, handle_health
from saalis_mcp.tools import handle_arbitrate

AGENTS = [
    {"id": "a1", "name": "GPT-4o", "weight": 0.6},
    {"id": "a2", "name": "Claude", "weight": 0.9},
]
PROPOSALS = [
    {"id": "p1", "agent_id": "a1", "content": "Deploy now", "confidence": 0.85},
    {"id": "p2", "agent_id": "a2", "content": "Wait for review", "confidence": 0.75},
]
QUESTION = "Should we deploy to production?"


async def test_health_resource_returns_ok(weighted_state):
    result = await handle_health(weighted_state)
    data = json.loads(result)
    assert data["status"] == "ok"
    assert "version" in data


async def test_audit_resource_for_decision(weighted_state):
    arb_result = await handle_arbitrate(weighted_state, {
        "question": QUESTION,
        "proposals": PROPOSALS,
        "agents": AGENTS,
    })
    decision_id = json.loads(arb_result)["decision_id"]

    result = await handle_decision_audit(weighted_state, decision_id)
    events = json.loads(result)
    assert isinstance(events, list)
    assert len(events) >= 2
