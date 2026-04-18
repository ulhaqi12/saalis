from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request
from pydantic import BaseModel
from saalis.models import Agent, Decision, Evidence, EvidenceKind, Proposal, Verdict, VerdictStatus

from saalis_sidecar.metrics import record_arbitration
from saalis_sidecar.state import AppState

router = APIRouter()


class EvidenceIn(BaseModel):
    kind: EvidenceKind
    payload: Any


class ProposalIn(BaseModel):
    id: str | None = None
    agent_id: str
    content: str | dict[str, Any]
    confidence: float = 1.0
    evidence: list[EvidenceIn] = []


class AgentIn(BaseModel):
    id: str | None = None
    name: str
    weight: float = 1.0


class ResolveRequest(BaseModel):
    question: str
    proposals: list[ProposalIn]
    agents: list[AgentIn] = []
    context: dict[str, Any] = {}


@router.post("/decisions/resolve", response_model=Verdict)
async def resolve(body: ResolveRequest, request: Request) -> Verdict:
    state: AppState = request.app.state.app_state

    agents = [
        Agent(id=a.id or str(uuid4()), name=a.name, weight=a.weight) for a in body.agents
    ]
    proposals = [
        Proposal(
            id=p.id or str(uuid4()),
            agent_id=p.agent_id,
            content=p.content,
            confidence=p.confidence,
            evidence=[Evidence(kind=e.kind, payload=e.payload) for e in p.evidence],
        )
        for p in body.proposals
    ]
    decision = Decision(
        question=body.question,
        agents=agents,
        proposals=proposals,
        context=body.context,
    )

    t0 = time.monotonic()
    verdict = await state.arbitrator.arbitrate(decision)
    duration = time.monotonic() - t0

    record_arbitration(verdict.strategy_name, verdict.status, duration)

    if verdict.status == VerdictStatus.pending_human:
        deferred_event_id = await state.audit_store.get_deferred_event_id(decision.id) or ""
        await state.audit_store.defer(decision.id, deferred_event_id)

    return verdict
