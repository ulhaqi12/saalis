from __future__ import annotations

from dataclasses import dataclass, field

from saalis.models import Decision, PolicyDecision, Verdict


@dataclass
class PolicyRule:
    name: str

    def check_pre(self, decision: Decision) -> PolicyDecision | None:
        """Called before strategy resolution. Return non-None to block."""
        return None

    def check_post(self, decision: Decision, verdict: Verdict) -> PolicyDecision | None:
        """Called after strategy resolution. Return non-None to override verdict."""
        return None


@dataclass
class MinConfidenceRule(PolicyRule):
    """Block arbitration if no proposal meets the minimum confidence threshold."""

    threshold: float = 0.5
    name: str = field(default="min_confidence", init=False)

    def check_pre(self, decision: Decision) -> PolicyDecision | None:
        passing = [p for p in decision.proposals if p.confidence >= self.threshold]
        if not passing:
            return PolicyDecision(
                allowed=False,
                reason=f"No proposal meets min_confidence={self.threshold}",
                matched_rule=self.name,
            )
        return None


@dataclass
class RequireEvidenceRule(PolicyRule):
    """Block arbitration if no proposal has any evidence."""

    name: str = field(default="require_evidence", init=False)

    def check_pre(self, decision: Decision) -> PolicyDecision | None:
        has_evidence = any(len(p.evidence) > 0 for p in decision.proposals)
        if not has_evidence:
            return PolicyDecision(
                allowed=False,
                reason="At least one proposal must include evidence",
                matched_rule=self.name,
            )
        return None


@dataclass
class BlocklistAgentRule(PolicyRule):
    """Block arbitration if a blocklisted agent has a winning proposal."""

    blocklist: list[str] = field(default_factory=list)
    name: str = field(default="blocklist_agent", init=False)

    def check_post(self, decision: Decision, verdict: Verdict) -> PolicyDecision | None:
        if verdict.winner_proposal_id is None:
            return None
        winner = next((p for p in decision.proposals if p.id == verdict.winner_proposal_id), None)
        if winner and winner.agent_id in self.blocklist:
            return PolicyDecision(
                allowed=False,
                reason=f"Winning agent '{winner.agent_id}' is blocklisted",
                matched_rule=self.name,
            )
        return None


class PolicyEngine:
    def __init__(self, rules: list[PolicyRule] | None = None) -> None:
        self._rules = rules or []

    def add_rule(self, rule: PolicyRule) -> None:
        self._rules.append(rule)

    def check_pre(self, decision: Decision) -> PolicyDecision:
        for rule in self._rules:
            result = rule.check_pre(decision)
            if result is not None and not result.allowed:
                return result
        return PolicyDecision(allowed=True)

    def check_post(self, decision: Decision, verdict: Verdict) -> PolicyDecision:
        for rule in self._rules:
            result = rule.check_post(decision, verdict)
            if result is not None and not result.allowed:
                return result
        return PolicyDecision(allowed=True)
