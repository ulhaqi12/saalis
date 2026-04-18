from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return str(uuid.uuid4())


class EvidenceKind(StrEnum):
    citation = "citation"
    tool_call = "tool_call"
    chain_of_thought = "chain_of_thought"
    human = "human"


class Evidence(BaseModel):
    id: str = Field(default_factory=_new_id)
    kind: EvidenceKind
    payload: Any


class Agent(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Proposal(BaseModel):
    id: str = Field(default_factory=_new_id)
    agent_id: str
    content: str | dict[str, Any]
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(default_factory=list)


class Decision(BaseModel):
    id: str = Field(default_factory=_new_id)
    question: str
    proposals: list[Proposal] = Field(default_factory=list)
    agents: list[Agent] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)

    def agent_by_id(self, agent_id: str) -> Agent | None:
        return next((a for a in self.agents if a.id == agent_id), None)


class Explanation(BaseModel):
    summary: str
    rationale: str = ""
    dissents: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, float] = Field(default_factory=dict)

    def text(self) -> str:
        parts = [self.summary]
        if self.rationale:
            parts.append(self.rationale)
        if self.dissents:
            parts.append("Dissenting proposals: " + "; ".join(self.dissents) + ".")
        return " ".join(parts)

    def markdown(self, strategy_name: str = "", status: str = "") -> str:
        lines = ["## Decision Summary", f"{self.summary}", ""]
        if strategy_name or status:
            meta: list[str] = []
            if strategy_name:
                meta.append(f"**Strategy:** {strategy_name}")
            if status:
                meta.append(f"**Status:** {status}")
            lines += ["  ".join(meta), ""]
        if self.rationale:
            lines += ["### Rationale", self.rationale, ""]
        if self.score_breakdown:
            lines += ["### Score Breakdown", "| Proposal | Score |", "|---|---|"]
            for pid, score in sorted(self.score_breakdown.items(), key=lambda x: -x[1]):
                lines.append(f"| {pid} | {score:.3f} |")
            lines.append("")
        if self.dissents:
            lines += ["### Dissenting Proposals"]
            lines += [f"- {d}" for d in self.dissents]
            lines.append("")
        return "\n".join(lines)


class PolicyDecision(BaseModel):
    allowed: bool
    reason: str = ""
    matched_rule: str | None = None


class VerdictStatus(StrEnum):
    resolved = "resolved"
    pending_human = "pending_human"
    policy_blocked = "policy_blocked"


class Verdict(BaseModel):
    id: str = Field(default_factory=_new_id)
    decision_id: str
    winner_proposal_id: str | None = None
    strategy_name: str
    explanation: Explanation
    policy_result: PolicyDecision
    status: VerdictStatus = VerdictStatus.resolved
    created_at: datetime = Field(default_factory=_utcnow)

    def render(self, format: str = "text") -> str:  # noqa: A002
        if format == "markdown":
            return self.explanation.markdown(
                strategy_name=self.strategy_name, status=self.status
            )
        if format == "json":
            return self.model_dump_json(indent=2)
        return self.explanation.text()


class AuditEventType(StrEnum):
    arbitration_started = "arbitration_started"
    policy_checked = "policy_checked"
    strategy_resolved = "strategy_resolved"
    verdict_issued = "verdict_issued"
    human_deferred = "human_deferred"
    human_responded = "human_responded"


class AuditEvent(BaseModel):
    id: str = Field(default_factory=_new_id)
    event_type: AuditEventType
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_utcnow)
