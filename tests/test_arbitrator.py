import pytest

from saalis.arbitrator import Arbitrator
from saalis.models import Agent, Decision, Evidence, EvidenceKind, Proposal, VerdictStatus
from saalis.policy import BlocklistAgentRule, MinConfidenceRule, PolicyEngine, RequireEvidenceRule
from saalis.strategy import DeferToHuman, WeightedVote


def make_decision(proposals=None, agents=None):
    agents = agents or [Agent(id="a1", name="A", weight=1.0)]
    proposals = proposals or [Proposal(id="p1", agent_id="a1", content="yes", confidence=0.9)]
    return Decision(question="Q?", agents=agents, proposals=proposals)


async def test_arbitrator_basic_resolution():
    arb = Arbitrator(strategies=[WeightedVote()])
    verdict = await arb.arbitrate(make_decision())
    assert verdict.winner_proposal_id == "p1"
    assert verdict.status == VerdictStatus.resolved


async def test_arbitrator_requires_at_least_one_strategy():
    with pytest.raises(ValueError):
        Arbitrator(strategies=[])


async def test_arbitrator_uses_null_store_by_default():
    arb = Arbitrator(strategies=[WeightedVote()])
    verdict = await arb.arbitrate(make_decision())
    assert verdict is not None


async def test_arbitrator_pre_policy_blocks():
    engine = PolicyEngine(rules=[MinConfidenceRule(threshold=0.95)])
    arb = Arbitrator(strategies=[WeightedVote()], policy_engine=engine)
    verdict = await arb.arbitrate(make_decision())
    assert verdict.status == VerdictStatus.policy_blocked
    assert not verdict.policy_result.allowed


async def test_arbitrator_post_policy_blocks_winner():
    a = Agent(id="badagent", name="Bad", weight=1.0)
    p = Proposal(id="p1", agent_id="badagent", content="yes", confidence=1.0)
    d = Decision(question="Q?", agents=[a], proposals=[p])
    engine = PolicyEngine(rules=[BlocklistAgentRule(blocklist=["badagent"])])
    arb = Arbitrator(strategies=[WeightedVote()], policy_engine=engine)
    verdict = await arb.arbitrate(d)
    assert verdict.status == VerdictStatus.policy_blocked


async def test_arbitrator_defer_to_human():
    arb = Arbitrator(strategies=[DeferToHuman()])
    verdict = await arb.arbitrate(make_decision())
    assert verdict.status == VerdictStatus.pending_human
    assert verdict.winner_proposal_id is None


async def test_arbitrator_require_evidence_blocks():
    engine = PolicyEngine(rules=[RequireEvidenceRule()])
    arb = Arbitrator(strategies=[WeightedVote()], policy_engine=engine)
    # Proposals have no evidence → should block
    verdict = await arb.arbitrate(make_decision())
    assert verdict.status == VerdictStatus.policy_blocked


async def test_arbitrator_require_evidence_passes_with_evidence():
    engine = PolicyEngine(rules=[RequireEvidenceRule()])
    arb = Arbitrator(strategies=[WeightedVote()], policy_engine=engine)
    e = Evidence(kind=EvidenceKind.citation, payload={"url": "https://example.com"})
    p = Proposal(id="p1", agent_id="a1", content="yes", confidence=0.9, evidence=[e])
    d = Decision(question="Q?", agents=[Agent(id="a1", name="A")], proposals=[p])
    verdict = await arb.arbitrate(d)
    assert verdict.status == VerdictStatus.resolved
