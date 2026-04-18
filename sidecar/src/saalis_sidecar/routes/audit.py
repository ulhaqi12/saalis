from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request
from saalis.models import AuditEvent, AuditEventType

from saalis_sidecar.state import AppState

router = APIRouter()


@router.get("/decisions/{decision_id}/audit", response_model=list[AuditEvent])
async def audit_by_decision(
    decision_id: str,
    request: Request,
    event_type: AuditEventType | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[AuditEvent]:
    state: AppState = request.app.state.app_state
    all_events = await state.audit_store.query(
        event_type=event_type, since=since, until=until, limit=limit
    )
    return [e for e in all_events if e.payload.get("decision_id") == decision_id]


@router.get("/audit/events/{event_id}", response_model=AuditEvent)
async def get_event(event_id: str, request: Request) -> AuditEvent:
    state: AppState = request.app.state.app_state
    event = await state.audit_store.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id!r} not found")
    return event
