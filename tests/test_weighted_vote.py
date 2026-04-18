import pytest

from saalis.models import Agent, Decision, Proposal, VerdictStatus
from saalis.strategy import WeightedVote


@pytest.fixture
def two_agent_decision():
    a1 = Agent(id="a1", name="GPT-4o", weight=0.6)
    a2 = Agent(id="a2", name="Claude", weight=0.8)
    return Decision(
        question="Should we deploy?",
        agents=[a1, a2],
        proposals=[
            Proposal(id="p1", agent_id="a1", content="Yes", confidence=0.9),
            Proposal(id="p2", agent_id="a2", content="No", confidence=0.7),
        ],
    )


async def test_weighted_vote_picks_highest_score(two_agent_decision):
    # a1: 0.6 * 0.9 = 0.54
    # a2: 0.8 * 0.7 = 0.56  ← should win
    strategy = WeightedVote()
    verdict = await strategy.resolve(two_agent_decision)
    assert verdict.winner_proposal_id == "p2"
    assert verdict.status == VerdictStatus.resolved
    assert verdict.strategy_name == "WeightedVote"


async def test_weighted_vote_score_breakdown(two_agent_decision):
    verdict = await WeightedVote().resolve(two_agent_decision)
    breakdown = verdict.explanation.score_breakdown
    assert "p1" in breakdown
    assert "p2" in breakdown
    assert abs(breakdown["p1"] - 0.54) < 1e-9
    assert abs(breakdown["p2"] - 0.56) < 1e-9


async def test_weighted_vote_no_proposals():
    d = Decision(question="Q?")
    verdict = await WeightedVote().resolve(d)
    assert verdict.winner_proposal_id is None


async def test_weighted_vote_agent_weight_override():
    a = Agent(id="a1", name="X", weight=0.1)
    d = Decision(
        question="Q?",
        agents=[a],
        proposals=[Proposal(id="p1", agent_id="a1", content="yes", confidence=1.0)],
    )
    # Override weight to 0.9 → score = 0.9
    verdict = await WeightedVote(agent_weights={"a1": 0.9}).resolve(d)
    assert verdict.winner_proposal_id == "p1"
    assert abs(verdict.explanation.score_breakdown["p1"] - 0.9) < 1e-9


async def test_weighted_vote_unknown_agent_defaults_weight_one():
    d = Decision(
        question="Q?",
        agents=[],
        proposals=[Proposal(id="p1", agent_id="unknown", content="yes", confidence=0.5)],
    )
    verdict = await WeightedVote().resolve(d)
    assert verdict.winner_proposal_id == "p1"
    assert abs(verdict.explanation.score_breakdown["p1"] - 0.5) < 1e-9
