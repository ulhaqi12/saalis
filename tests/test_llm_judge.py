from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from saalis.models import Agent, Decision, Proposal, VerdictStatus
from saalis.strategy import LLMJudge, WeightedVote


def make_decision() -> Decision:
    return Decision(
        question="Should we deploy to production?",
        agents=[
            Agent(id="a1", name="GPT-4o", weight=0.8),
            Agent(id="a2", name="Claude", weight=0.9),
        ],
        proposals=[
            Proposal(id="p1", agent_id="a1", content="Deploy now", confidence=0.85),
            Proposal(id="p2", agent_id="a2", content="Wait for review", confidence=0.75),
        ],
    )


def _mock_response(winner_id: str, rationale: str = "Good reasoning") -> MagicMock:
    payload = json.dumps({
        "winner_proposal_id": winner_id,
        "rationale": rationale,
        "score_breakdown": {winner_id: 0.9},
    })
    choice = MagicMock()
    choice.message.content = payload
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.fixture
def mock_openai():
    with patch("saalis.strategy.AsyncOpenAI") as cls:
        client = MagicMock()
        cls.return_value = client
        client.chat = MagicMock()
        client.chat.completions = MagicMock()
        client.chat.completions.create = AsyncMock()
        yield client


async def test_llm_judge_picks_winner(mock_openai):
    mock_openai.chat.completions.create.return_value = _mock_response("p1")
    judge = LLMJudge(model="gpt-4o")
    verdict = await judge.resolve(make_decision())

    assert verdict.winner_proposal_id == "p1"
    assert verdict.status == VerdictStatus.resolved
    assert verdict.strategy_name == "LLMJudge"
    assert "p2" in verdict.explanation.dissents[0]


async def test_llm_judge_rationale_propagated(mock_openai):
    mock_openai.chat.completions.create.return_value = _mock_response("p2", "p2 is safer")
    verdict = await LLMJudge().resolve(make_decision())
    assert verdict.explanation.rationale == "p2 is safer"


async def test_llm_judge_retries_on_malformed(mock_openai):
    bad_choice = MagicMock()
    bad_choice.message.content = "not json at all"
    bad_response = MagicMock()
    bad_response.choices = [bad_choice]

    mock_openai.chat.completions.create.side_effect = [
        bad_response,
        bad_response,
        _mock_response("p1"),
    ]
    verdict = await LLMJudge(max_retries=3).resolve(make_decision())
    assert verdict.winner_proposal_id == "p1"
    assert mock_openai.chat.completions.create.call_count == 3


async def test_llm_judge_falls_back_after_exhausted_retries(mock_openai):
    mock_openai.chat.completions.create.side_effect = ValueError("API down")
    verdict = await LLMJudge(max_retries=3, fallback=WeightedVote()).resolve(make_decision())

    # Fallback runs — a2 weight(0.9)*conf(0.75)=0.675 vs a1 weight(0.8)*conf(0.85)=0.68 → p1 wins
    assert verdict.winner_proposal_id == "p1"
    assert verdict.strategy_name == "LLMJudge"
    assert "[LLMJudge failed" in verdict.explanation.rationale
    assert "WeightedVote" in verdict.explanation.rationale


async def test_llm_judge_falls_back_on_unknown_proposal_id(mock_openai):
    mock_openai.chat.completions.create.return_value = _mock_response("nonexistent-id")
    verdict = await LLMJudge(fallback=WeightedVote()).resolve(make_decision())

    assert verdict.strategy_name == "LLMJudge"
    assert "[LLMJudge returned unknown id" in verdict.explanation.rationale


async def test_llm_judge_uses_base_url(mock_openai):
    with patch("saalis.strategy.AsyncOpenAI") as cls:
        cls.return_value = mock_openai
        mock_openai.chat.completions.create.return_value = _mock_response("p1")
        LLMJudge(model="llama3", base_url="http://localhost:11434/v1")
        _, kwargs = cls.call_args
        assert kwargs["base_url"] == "http://localhost:11434/v1"


async def test_llm_judge_missing_fields_retries(mock_openai):
    # Response missing "rationale" field — should retry then succeed
    incomplete = MagicMock()
    incomplete.message.content = json.dumps({"winner_proposal_id": "p1"})  # no rationale
    bad_response = MagicMock()
    bad_response.choices = [incomplete]

    mock_openai.chat.completions.create.side_effect = [
        bad_response,
        _mock_response("p1", "proper rationale"),
    ]
    verdict = await LLMJudge(max_retries=3).resolve(make_decision())
    assert verdict.explanation.rationale == "proper rationale"
