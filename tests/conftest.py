"""Shared fixtures for the Saalis test suite."""

from __future__ import annotations

from saalis.models import Agent, Decision, Proposal


def make_agents(
    *,
    a1_weight: float = 1.0,
    a2_weight: float = 0.9,
) -> list[Agent]:
    return [
        Agent(id="a1", name="GPT-4o", weight=a1_weight),
        Agent(id="a2", name="Claude", weight=a2_weight),
    ]


def make_proposals() -> list[Proposal]:
    return [
        Proposal(id="p1", agent_id="a1", content="Deploy now", confidence=0.8),
        Proposal(id="p2", agent_id="a2", content="Wait for review", confidence=0.7),
    ]


def make_decision(
    question: str = "Should we deploy?",
    proposals: list[Proposal] | None = None,
    agents: list[Agent] | None = None,
) -> Decision:
    return Decision(
        question=question,
        agents=agents if agents is not None else make_agents(),
        proposals=proposals if proposals is not None else make_proposals(),
    )
