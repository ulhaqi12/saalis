from datetime import UTC

import pytest
from pydantic import ValidationError

from saalis.models import (
    Agent,
    AuditEvent,
    AuditEventType,
    Decision,
    Evidence,
    EvidenceKind,
    Explanation,
    PolicyDecision,
    Proposal,
    Verdict,
    VerdictStatus,
)


def test_agent_defaults():
    agent = Agent(name="GPT-4o")
    assert agent.id
    assert agent.weight == 1.0
    assert agent.metadata == {}


def test_agent_weight_bounds():
    with pytest.raises(ValidationError):
        Agent(name="bad", weight=1.5)
    with pytest.raises(ValidationError):
        Agent(name="bad", weight=-0.1)


def test_proposal_defaults():
    p = Proposal(agent_id="a1", content="Approve")
    assert p.id
    assert p.confidence == 1.0
    assert p.evidence == []


def test_proposal_confidence_bounds():
    with pytest.raises(ValidationError):
        Proposal(agent_id="a1", content="x", confidence=1.1)


def test_proposal_dict_content():
    p = Proposal(agent_id="a1", content={"answer": 42})
    assert p.content == {"answer": 42}


def test_evidence_kinds():
    for kind in EvidenceKind:
        e = Evidence(kind=kind, payload={"data": kind.value})
        assert e.kind == kind


def test_decision_agent_by_id():
    a = Agent(name="Claude")
    d = Decision(question="Q?", agents=[a])
    assert d.agent_by_id(a.id) is a
    assert d.agent_by_id("nonexistent") is None


def test_decision_created_at_utc():
    d = Decision(question="Q?")
    assert d.created_at.tzinfo is not None
    assert d.created_at.tzinfo == UTC


def test_explanation_defaults():
    e = Explanation(summary="Winner is A")
    assert e.rationale == ""
    assert e.dissents == []
    assert e.score_breakdown == {}


def test_policy_decision():
    pd = PolicyDecision(allowed=True)
    assert pd.reason == ""
    assert pd.matched_rule is None

    pd2 = PolicyDecision(allowed=False, reason="blocked", matched_rule="min_confidence")
    assert not pd2.allowed


def test_verdict_fields():
    v = Verdict(
        decision_id="d1",
        winner_proposal_id="p1",
        strategy_name="WeightedVote",
        explanation=Explanation(summary="A wins"),
        policy_result=PolicyDecision(allowed=True),
    )
    assert v.status == VerdictStatus.resolved
    assert v.id


def test_audit_event():
    ev = AuditEvent(event_type=AuditEventType.verdict_issued, payload={"verdict_id": "v1"})
    assert ev.id
    assert ev.timestamp.tzinfo == UTC
