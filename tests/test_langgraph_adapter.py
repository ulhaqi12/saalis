"""Tests for the LangGraph adapter.

No LangGraph import needed — the node is a plain async callable.
Tests drive it directly with state dicts, exactly as LangGraph would.
"""

from __future__ import annotations

import pytest

from saalis.integrations.langgraph import ArbitrationNode
from saalis.models import Agent, Proposal, VerdictStatus
from saalis.policy import MinConfidenceRule, PolicyEngine
from saalis.strategy import DeferToHuman, WeightedVote

# ── helpers ────────────────────────────────────────────────────────────────

AGENTS = [
    {"id": "a1", "name": "GPT-4o", "weight": 0.6},
    {"id": "a2", "name": "Claude", "weight": 0.9},
]

PROPOSALS = [
    {"id": "p1", "agent_id": "a1", "content": "Deploy now", "confidence": 0.8},
    {"id": "p2", "agent_id": "a2", "content": "Wait for review", "confidence": 0.7},
]

BASE_STATE: dict = {
    "question": "Should we deploy?",
    "agents": AGENTS,
    "proposals": PROPOSALS,
}


# ── basic arbitration ──────────────────────────────────────────────────────

async def test_node_returns_verdict_key():
    node = ArbitrationNode()
    result = await node(BASE_STATE)
    assert "verdict" in result


async def test_node_picks_winner():
    node = ArbitrationNode(strategies=[WeightedVote()])
    result = await node(BASE_STATE)
    verdict = result["verdict"]
    # a1: 0.6*0.8=0.48, a2: 0.9*0.7=0.63 → p2 wins
    assert verdict.winner_proposal_id == "p2"
    assert verdict.status == VerdictStatus.resolved


async def test_node_strategy_name_in_verdict():
    node = ArbitrationNode(strategies=[WeightedVote()])
    result = await node(BASE_STATE)
    assert result["verdict"].strategy_name == "WeightedVote"


async def test_node_accepts_pydantic_objects_in_state():
    agents = [Agent(id="a1", name="X", weight=1.0)]
    proposals = [Proposal(id="p1", agent_id="a1", content="yes", confidence=0.9)]
    state = {"question": "Q?", "agents": agents, "proposals": proposals}
    node = ArbitrationNode()
    result = await node(state)
    assert result["verdict"].winner_proposal_id == "p1"


async def test_node_works_without_agents_key():
    state = {"question": "Q?", "proposals": PROPOSALS}
    node = ArbitrationNode()
    result = await node(state)
    assert result["verdict"] is not None


async def test_node_works_without_proposals():
    state = {"question": "Q?"}
    node = ArbitrationNode()
    result = await node(state)
    # No proposals → WeightedVote returns None winner
    assert result["verdict"].winner_proposal_id is None


# ── context propagation ────────────────────────────────────────────────────

async def test_node_passes_context_to_decision():
    state = {**BASE_STATE, "context": {"env": "production", "reviewer": "alice"}}
    node = ArbitrationNode()
    result = await node(state)
    assert result["verdict"] is not None


async def test_node_ignores_non_dict_context():
    state = {**BASE_STATE, "context": "not a dict"}
    node = ArbitrationNode()
    result = await node(state)
    assert result["verdict"] is not None


# ── configurable keys ──────────────────────────────────────────────────────

async def test_custom_question_key():
    state = {"task": "Deploy?", "proposals": PROPOSALS, "agents": AGENTS}
    node = ArbitrationNode(question_key="task")
    result = await node(state)
    assert "verdict" in result


async def test_custom_verdict_key():
    node = ArbitrationNode(verdict_key="arbitration_result")
    result = await node(BASE_STATE)
    assert "arbitration_result" in result
    assert "verdict" not in result


async def test_missing_question_key_raises():
    node = ArbitrationNode()
    with pytest.raises(KeyError):
        await node({"proposals": PROPOSALS})


# ── policy integration ─────────────────────────────────────────────────────

async def test_node_respects_policy_engine():
    engine = PolicyEngine(rules=[MinConfidenceRule(threshold=0.99)])
    node = ArbitrationNode(strategies=[WeightedVote()], policy_engine=engine)
    result = await node(BASE_STATE)
    assert result["verdict"].status == VerdictStatus.policy_blocked


async def test_node_defer_to_human():
    node = ArbitrationNode(strategies=[DeferToHuman()])
    result = await node(BASE_STATE)
    assert result["verdict"].status == VerdictStatus.pending_human


# ── audit store wiring ─────────────────────────────────────────────────────

async def test_node_writes_to_audit_store(tmp_path):
    from saalis.audit.sqlite import SQLiteAuditStore

    store = SQLiteAuditStore(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    node = ArbitrationNode(audit_store=store)
    await node(BASE_STATE)

    events = await store.query()
    assert len(events) > 0
    await store.close()


async def test_node_uses_null_store_by_default():
    # Should not raise even without an explicit audit store
    node = ArbitrationNode()
    result = await node(BASE_STATE)
    assert result["verdict"] is not None
