from saalis.models import (
    Decision,
    Evidence,
    EvidenceKind,
    Explanation,
    PolicyDecision,
    Proposal,
    Verdict,
)
from saalis.policy import BlocklistAgentRule, MinConfidenceRule, PolicyEngine, RequireEvidenceRule


def make_verdict(winner_proposal_id="p1"):
    return Verdict(
        decision_id="d1",
        winner_proposal_id=winner_proposal_id,
        strategy_name="WeightedVote",
        explanation=Explanation(summary="test"),
        policy_result=PolicyDecision(allowed=True),
    )


def test_min_confidence_blocks_when_all_below_threshold():
    rule = MinConfidenceRule(threshold=0.8)
    d = Decision(
        question="Q?",
        proposals=[Proposal(agent_id="a1", content="x", confidence=0.5)],
    )
    result = rule.check_pre(d)
    assert result is not None
    assert not result.allowed
    assert result.matched_rule == "min_confidence"


def test_min_confidence_passes_when_one_meets_threshold():
    rule = MinConfidenceRule(threshold=0.8)
    d = Decision(
        question="Q?",
        proposals=[
            Proposal(agent_id="a1", content="x", confidence=0.5),
            Proposal(agent_id="a2", content="y", confidence=0.9),
        ],
    )
    assert rule.check_pre(d) is None


def test_require_evidence_blocks_no_evidence():
    rule = RequireEvidenceRule()
    d = Decision(question="Q?", proposals=[Proposal(agent_id="a1", content="x")])
    result = rule.check_pre(d)
    assert result is not None
    assert not result.allowed


def test_require_evidence_passes_with_evidence():
    rule = RequireEvidenceRule()
    e = Evidence(kind=EvidenceKind.citation, payload={})
    d = Decision(
        question="Q?",
        proposals=[Proposal(agent_id="a1", content="x", evidence=[e])],
    )
    assert rule.check_pre(d) is None


def test_blocklist_blocks_winning_agent():
    rule = BlocklistAgentRule(blocklist=["bad"])
    d = Decision(
        question="Q?",
        proposals=[Proposal(id="p1", agent_id="bad", content="x")],
    )
    verdict = make_verdict(winner_proposal_id="p1")
    result = rule.check_post(d, verdict)
    assert result is not None
    assert not result.allowed


def test_blocklist_allows_non_blocked_agent():
    rule = BlocklistAgentRule(blocklist=["bad"])
    d = Decision(
        question="Q?",
        proposals=[Proposal(id="p1", agent_id="good", content="x")],
    )
    verdict = make_verdict(winner_proposal_id="p1")
    assert rule.check_post(d, verdict) is None


def test_policy_engine_first_blocking_rule_wins():
    engine = PolicyEngine(
        rules=[MinConfidenceRule(threshold=0.9), MinConfidenceRule(threshold=0.5)]
    )
    d = Decision(
        question="Q?",
        proposals=[Proposal(agent_id="a1", content="x", confidence=0.7)],
    )
    result = engine.check_pre(d)
    assert not result.allowed
    assert result.matched_rule == "min_confidence"


def test_policy_engine_all_pass_returns_allowed():
    engine = PolicyEngine(rules=[MinConfidenceRule(threshold=0.5)])
    d = Decision(
        question="Q?",
        proposals=[Proposal(agent_id="a1", content="x", confidence=0.8)],
    )
    assert engine.check_pre(d).allowed
