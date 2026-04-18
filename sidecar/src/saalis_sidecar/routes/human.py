from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from saalis.models import (
    AuditEvent,
    AuditEventType,
    Explanation,
    PolicyDecision,
    Verdict,
    VerdictStatus,
)

from saalis_sidecar.state import AppState

router = APIRouter()


class HumanResponseRequest(BaseModel):
    winner_proposal_id: str
    rationale: str
    operator_id: str


@router.post("/decisions/{decision_id}/human_response", response_model=Verdict)
async def human_response(
    decision_id: str,
    body: HumanResponseRequest,
    request: Request,
) -> Verdict:
    state: AppState = request.app.state.app_state

    deferred = await state.audit_store.get_deferred(decision_id)
    if deferred is None:
        raise HTTPException(
            status_code=404,
            detail=f"No pending decision found for decision_id={decision_id!r}",
        )
    if deferred.resolved_at is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Decision {decision_id!r} was already resolved",
        )

    await state.audit_store.resolve_deferred(
        decision_id, outcome=body.winner_proposal_id, resolved_by=body.operator_id
    )
    await state.audit_store.append(
        AuditEvent(
            event_type=AuditEventType.human_responded,
            payload={
                "decision_id": decision_id,
                "winner_proposal_id": body.winner_proposal_id,
                "operator_id": body.operator_id,
            },
        )
    )

    return Verdict(
        decision_id=decision_id,
        winner_proposal_id=body.winner_proposal_id,
        strategy_name="DeferToHuman",
        explanation=Explanation(
            summary=f"Human operator '{body.operator_id}' resolved the decision",
            rationale=body.rationale,
        ),
        policy_result=PolicyDecision(allowed=True),
        status=VerdictStatus.resolved,
    )
