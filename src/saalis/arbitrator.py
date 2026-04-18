from __future__ import annotations

import structlog

from saalis.audit.base import AuditStore, NullAuditStore
from saalis.models import (
    AuditEvent,
    AuditEventType,
    Decision,
    Verdict,
    VerdictStatus,
)
from saalis.policy import PolicyEngine
from saalis.strategy import Strategy

log = structlog.get_logger(__name__)


class Arbitrator:
    def __init__(
        self,
        strategies: list[Strategy],
        policy_engine: PolicyEngine | None = None,
        audit_store: AuditStore | None = None,
    ) -> None:
        if not strategies:
            raise ValueError("At least one strategy is required")
        self._strategies = strategies
        self._policy = policy_engine or PolicyEngine()
        self._audit = audit_store or NullAuditStore()

    async def arbitrate(self, decision: Decision) -> Verdict:
        await self._audit.append(
            AuditEvent(
                event_type=AuditEventType.arbitration_started,
                payload={"decision_id": decision.id, "question": decision.question},
            )
        )
        log.info("arbitration_started", decision_id=decision.id)

        pre_check = self._policy.check_pre(decision)
        await self._audit.append(
            AuditEvent(
                event_type=AuditEventType.policy_checked,
                payload={"phase": "pre", "allowed": pre_check.allowed, "reason": pre_check.reason},
            )
        )

        if not pre_check.allowed:
            verdict = Verdict(
                decision_id=decision.id,
                winner_proposal_id=None,
                strategy_name="policy",
                explanation=__import__("saalis.models", fromlist=["Explanation"]).Explanation(
                    summary=f"Blocked by policy: {pre_check.reason}"
                ),
                policy_result=pre_check,
                status=VerdictStatus.policy_blocked,
            )
            await self._emit_verdict(decision, verdict)
            return verdict

        strategy = self._strategies[0]
        verdict = await strategy.resolve(decision)
        await self._audit.append(
            AuditEvent(
                event_type=AuditEventType.strategy_resolved,
                payload={
                    "strategy": strategy.name,
                    "winner_proposal_id": verdict.winner_proposal_id,
                },
            )
        )

        post_check = self._policy.check_post(decision, verdict)
        if not post_check.allowed:
            verdict = verdict.model_copy(
                update={"policy_result": post_check, "status": VerdictStatus.policy_blocked}
            )

        if verdict.status == VerdictStatus.pending_human:
            await self._audit.append(
                AuditEvent(
                    event_type=AuditEventType.human_deferred,
                    payload={"decision_id": decision.id, "verdict_id": verdict.id},
                )
            )

        await self._emit_verdict(decision, verdict)
        log.info("arbitration_complete", decision_id=decision.id, verdict_id=verdict.id)
        return verdict

    async def _emit_verdict(self, decision: Decision, verdict: Verdict) -> None:
        await self._audit.append(
            AuditEvent(
                event_type=AuditEventType.verdict_issued,
                payload={
                    "decision_id": decision.id,
                    "verdict_id": verdict.id,
                    "status": verdict.status,
                    "winner_proposal_id": verdict.winner_proposal_id,
                },
            )
        )
