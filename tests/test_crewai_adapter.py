"""Tests for the CrewAI adapter.

No CrewAI import needed — the tool is a plain callable.
Tests drive ``_arun`` (async) and ``_run`` (sync) directly.
"""

from __future__ import annotations

import pytest

from saalis.integrations.crewai import ArbitrationTool
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

QUESTION = "Should we deploy?"


# ── tool interface ─────────────────────────────────────────────────────────

def test_tool_has_name():
    tool = ArbitrationTool()
    assert tool.name == "saalis_arbitrate"


def test_tool_has_description():
    tool = ArbitrationTool()
    assert isinstance(tool.description, str)
    assert len(tool.description) > 0


# ── async _arun ────────────────────────────────────────────────────────────

async def test_arun_returns_string():
    tool = ArbitrationTool()
    result = await tool._arun(QUESTION, PROPOSALS, AGENTS)
    assert isinstance(result, str)
    assert len(result) > 0


async def test_arun_picks_winner():
    tool = ArbitrationTool(strategies=[WeightedVote()])
    result = await tool._arun(QUESTION, PROPOSALS, AGENTS)
    # a2: 0.9*0.7=0.63 beats a1: 0.6*0.8=0.48 → p2 wins → agent a2 in output
    assert "a2" in result


async def test_arun_accepts_pydantic_objects():
    agents = [Agent(id="a1", name="X", weight=1.0)]
    proposals = [Proposal(id="p1", agent_id="a1", content="yes", confidence=0.9)]
    tool = ArbitrationTool()
    result = await tool._arun("Q?", proposals, agents)
    assert isinstance(result, str)


async def test_arun_works_without_agents():
    tool = ArbitrationTool()
    result = await tool._arun(QUESTION, PROPOSALS)
    assert isinstance(result, str)


async def test_arun_works_without_proposals():
    tool = ArbitrationTool()
    result = await tool._arun(QUESTION, [])
    assert isinstance(result, str)


async def test_arun_passes_context():
    tool = ArbitrationTool()
    result = await tool._arun(QUESTION, PROPOSALS, AGENTS, context={"env": "prod"})
    assert isinstance(result, str)


# ── output formats ─────────────────────────────────────────────────────────

async def test_output_format_text():
    tool = ArbitrationTool(output_format="text")
    result = await tool._arun(QUESTION, PROPOSALS, AGENTS)
    assert isinstance(result, str)


async def test_output_format_markdown():
    tool = ArbitrationTool(output_format="markdown")
    result = await tool._arun(QUESTION, PROPOSALS, AGENTS)
    assert "##" in result or "**" in result


async def test_output_format_json():
    import json

    tool = ArbitrationTool(output_format="json")
    result = await tool._arun(QUESTION, PROPOSALS, AGENTS)
    parsed = json.loads(result)
    assert "status" in parsed


# ── policy integration ─────────────────────────────────────────────────────

async def test_policy_blocked_reflected_in_output():
    engine = PolicyEngine(rules=[MinConfidenceRule(threshold=0.99)])
    tool = ArbitrationTool(strategies=[WeightedVote()], policy_engine=engine)
    result = await tool._arun(QUESTION, PROPOSALS, AGENTS)
    assert "policy" in result.lower() or "blocked" in result.lower()


async def test_defer_to_human_reflected_in_output():
    tool = ArbitrationTool(strategies=[DeferToHuman()])
    result = await tool._arun(QUESTION, PROPOSALS, AGENTS)
    assert "pending" in result.lower() or "human" in result.lower()


# ── sync _run ──────────────────────────────────────────────────────────────

def test_run_returns_string():
    tool = ArbitrationTool(strategies=[WeightedVote()])
    result = tool._run(QUESTION, PROPOSALS, AGENTS)
    assert isinstance(result, str)
    assert len(result) > 0


def test_run_picks_winner():
    tool = ArbitrationTool(strategies=[WeightedVote()])
    result = tool._run(QUESTION, PROPOSALS, AGENTS)
    # a2: 0.9*0.7=0.63 beats a1: 0.6*0.8=0.48 → p2 wins → agent a2 in output
    assert "a2" in result


def test_run_json_output():
    import json

    tool = ArbitrationTool(output_format="json")
    result = tool._run(QUESTION, PROPOSALS, AGENTS)
    parsed = json.loads(result)
    assert "status" in parsed


# ── audit store wiring ─────────────────────────────────────────────────────

async def test_arun_writes_to_audit_store(tmp_path):
    from saalis.audit.sqlite import SQLiteAuditStore

    store = SQLiteAuditStore(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    tool = ArbitrationTool(audit_store=store)
    await tool._arun(QUESTION, PROPOSALS, AGENTS)

    events = await store.query()
    assert len(events) > 0
    await store.close()


async def test_arun_uses_null_store_by_default():
    tool = ArbitrationTool()
    result = await tool._arun(QUESTION, PROPOSALS, AGENTS)
    assert result is not None
