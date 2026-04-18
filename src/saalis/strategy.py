from __future__ import annotations

import json
from abc import ABC, abstractmethod

import structlog
from openai import AsyncOpenAI

from saalis.models import (
    Decision,
    Explanation,
    PolicyDecision,
    Verdict,
    VerdictStatus,
)

_log = structlog.get_logger(__name__)

_JUDGE_SYSTEM_PROMPT = """\
You are an impartial arbitrator. Given a question and a list of proposals from AI agents, \
select the best proposal. You MUST respond with valid JSON only — no prose outside the JSON.

Schema:
{
  "winner_proposal_id": "<id of winning proposal>",
  "rationale": "<one paragraph explaining why>",
  "score_breakdown": {"<proposal_id>": <float 0.0-1.0>, ...}
}
"""


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


class LLMJudge(Strategy):
    """Calls an LLM to adjudicate between proposals. Falls back to WeightedVote on failure."""

    name = "LLMJudge"

    def __init__(
        self,
        model: str = "gpt-4o",
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        fallback: Strategy | None = None,
    ) -> None:
        self._model = model
        self._client = AsyncOpenAI(
            api_key=api_key,  # falls back to OPENAI_API_KEY env var when None
            base_url=base_url,
            timeout=timeout,
        )
        self._max_retries = max_retries
        self._fallback: Strategy = fallback if fallback is not None else WeightedVote()

    def _build_user_message(self, decision: Decision) -> str:
        lines = [f"Question: {decision.question}", "", "Proposals:"]
        for p in decision.proposals:
            content = p.content if isinstance(p.content, str) else json.dumps(p.content)
            lines += [
                f"  ID: {p.id}",
                f"  Agent: {p.agent_id}",
                f"  Content: {content}",
                f"  Confidence: {p.confidence}",
                f"  Evidence: {len(p.evidence)} item(s)",
                "",
            ]
        return "\n".join(lines)

    async def _call_judge(self, user_msg: str) -> dict[str, object]:
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                )
                raw = response.choices[0].message.content or ""
                parsed: dict[str, object] = json.loads(raw)
                if "winner_proposal_id" not in parsed or "rationale" not in parsed:
                    raise ValueError(f"Missing required fields in judge response: {parsed}")
                return parsed
            except Exception as exc:
                _log.warning(
                    "llmjudge_attempt_failed",
                    attempt=attempt,
                    max_retries=self._max_retries,
                    error=str(exc),
                )
                if attempt == self._max_retries:
                    raise
        raise RuntimeError("unreachable")

    async def resolve(self, decision: Decision) -> Verdict:
        user_msg = self._build_user_message(decision)
        try:
            result = await self._call_judge(user_msg)
        except Exception as exc:
            _log.error("llmjudge_exhausted_retries", error=str(exc), fallback=self._fallback.name)
            fallback_verdict = await self._fallback.resolve(decision)
            return fallback_verdict.model_copy(
                update={
                    "strategy_name": self.name,
                    "explanation": fallback_verdict.explanation.model_copy(
                        update={
                            "rationale": (
                                f"[LLMJudge failed after {self._max_retries} retries"
                                f" ({exc}), fell back to {self._fallback.name}] "
                                + fallback_verdict.explanation.rationale
                            )
                        }
                    ),
                }
            )

        winner_id = str(result["winner_proposal_id"])
        rationale = str(result["rationale"])
        raw_scores = result.get("score_breakdown", {})
        score_breakdown = (
            {str(k): float(v) for k, v in raw_scores.items()}
            if isinstance(raw_scores, dict)
            else {}
        )

        proposal_ids = {p.id for p in decision.proposals}
        if winner_id not in proposal_ids:
            _log.warning(
                "llmjudge_unknown_proposal_id",
                winner_id=winner_id,
                fallback=self._fallback.name,
            )
            fallback_verdict = await self._fallback.resolve(decision)
            return fallback_verdict.model_copy(
                update={
                    "strategy_name": self.name,
                    "explanation": fallback_verdict.explanation.model_copy(
                        update={
                            "rationale": (
                                f"[LLMJudge returned unknown id {winner_id!r},"
                                f" fell back to {self._fallback.name}] "
                                + fallback_verdict.explanation.rationale
                            )
                        }
                    ),
                }
            )

        winner = next(p for p in decision.proposals if p.id == winner_id)
        dissents = [
            f"Proposal {p.id} (agent {p.agent_id})"
            for p in decision.proposals
            if p.id != winner_id
        ]

        return Verdict(
            decision_id=decision.id,
            winner_proposal_id=winner_id,
            strategy_name=self.name,
            explanation=Explanation(
                summary=f"LLM judge selected proposal by agent '{winner.agent_id}'",
                rationale=rationale,
                dissents=dissents,
                score_breakdown=score_breakdown,
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
