from __future__ import annotations

from abc import ABC, abstractmethod

from saalis.models import (
    Decision,
    Explanation,
    PolicyDecision,
    Verdict,
    VerdictStatus,
)


class Strategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def resolve(self, decision: Decision) -> Verdict: ...


class WeightedVote(Strategy):
    """Scores each proposal by its agent's weight × proposal confidence, picks highest."""

    name = "WeightedVote"

    def __init__(self, agent_weights: dict[str, float] | None = None) -> None:
        # agent_weights overrides the weight on Agent objects when provided
        self._overrides = agent_weights or {}

    async def resolve(self, decision: Decision) -> Verdict:
        scores: dict[str, float] = {}
        agent_map = {a.id: a for a in decision.agents}

        for proposal in decision.proposals:
            agent = agent_map.get(proposal.agent_id)
            agent_weight = self._overrides.get(proposal.agent_id, agent.weight if agent else 1.0)
            scores[proposal.id] = agent_weight * proposal.confidence

        if not scores:
            return Verdict(
                decision_id=decision.id,
                winner_proposal_id=None,
                strategy_name=self.name,
                explanation=Explanation(summary="No proposals to evaluate"),
                policy_result=PolicyDecision(allowed=True),
                status=VerdictStatus.resolved,
            )

        winner_id = max(scores, key=lambda pid: scores[pid])
        winner = next(p for p in decision.proposals if p.id == winner_id)

        dissents = [
            f"Proposal {p.id} (agent {p.agent_id}) scored {scores[p.id]:.3f}"
            for p in decision.proposals
            if p.id != winner_id
        ]

        return Verdict(
            decision_id=decision.id,
            winner_proposal_id=winner_id,
            strategy_name=self.name,
            explanation=Explanation(
                summary=(
                    f"Proposal by agent '{winner.agent_id}' won"
                    f" with score {scores[winner_id]:.3f}"
                ),
                rationale="Highest weighted confidence score",
                dissents=dissents,
                score_breakdown=scores,
            ),
            policy_result=PolicyDecision(allowed=True),
            status=VerdictStatus.resolved,
        )


class DeferToHuman(Strategy):
    """Always defers the decision to a human; returns a pending verdict."""

    name = "DeferToHuman"

    def __init__(self, reason: str = "Human review required") -> None:
        self._reason = reason

    async def resolve(self, decision: Decision) -> Verdict:
        return Verdict(
            decision_id=decision.id,
            winner_proposal_id=None,
            strategy_name=self.name,
            explanation=Explanation(
                summary=self._reason,
                rationale="Decision deferred to human arbitrator",
            ),
            policy_result=PolicyDecision(allowed=True),
            status=VerdictStatus.pending_human,
        )
