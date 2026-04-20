from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from saalis.models import Agent, Decision, Evidence, EvidenceKind, Proposal, VerdictStatus

from saalis_mcp.state import AppState


async def handle_arbitrate(state: AppState, arguments: dict[str, Any]) -> str:
    question = arguments["question"]
    proposals_raw: list[dict[str, Any]] = arguments["proposals"]
    agents_raw: list[dict[str, Any]] = arguments.get("agents", [])
    context: dict[str, Any] = arguments.get("context", {})

    agents = [
        Agent(
            id=a.get("id") or str(uuid4()),
            name=a.get("name", "unknown"),
            weight=float(a.get("weight", 1.0)),
        )
        for a in agents_raw
    ]

    proposals = [
        Proposal(
            id=p.get("id") or str(uuid4()),
            agent_id=p["agent_id"],
            content=p["content"],
            confidence=float(p.get("confidence", 1.0)),
            evidence=[
                Evidence(kind=EvidenceKind(e["kind"]), payload=e.get("payload"))
                for e in p.get("evidence", [])
            ],
        )
        for p in proposals_raw
    ]

    decision = Decision(
        question=question,
        agents=agents,
        proposals=proposals,
        context=context,
    )

    verdict = await state.arbitrator.arbitrate(decision)
    state.verdict_cache[decision.id] = verdict

    if verdict.status == VerdictStatus.pending_human:
        deferred_event_id = await state.audit_store.get_deferred_event_id(decision.id) or ""
        await state.audit_store.defer(decision.id, deferred_event_id)

    return verdict.render("json")


async def handle_get_verdict(state: AppState, arguments: dict[str, Any]) -> str:
    decision_id: str = arguments["decision_id"]
    verdict = state.verdict_cache.get(decision_id)
    if verdict is None:
        return "null"
    return verdict.render("json")


async def handle_audit_query(state: AppState, arguments: dict[str, Any]) -> str:
    from datetime import datetime, timezone

    from saalis.models import AuditEventType

    decision_id: str | None = arguments.get("decision_id")
    event_type_raw: str | None = arguments.get("event_type")
    since: str | None = arguments.get("since")
    until: str | None = arguments.get("until")
    limit: int = int(arguments.get("limit", 100))

    event_type = AuditEventType(event_type_raw) if event_type_raw else None
    since_dt = datetime.fromisoformat(since).replace(tzinfo=timezone.utc) if since else None
    until_dt = datetime.fromisoformat(until).replace(tzinfo=timezone.utc) if until else None

    events = await state.audit_store.query(
        event_type=event_type,
        since=since_dt,
        until=until_dt,
        limit=limit,
    )

    if decision_id:
        events = [
            e for e in events
            if isinstance(e.payload, dict) and e.payload.get("decision_id") == decision_id
        ]

    return json.dumps([json.loads(e.model_dump_json()) for e in events])


async def handle_human_respond(state: AppState, arguments: dict[str, Any]) -> str:
    decision_id: str = arguments["decision_id"]
    winner_proposal_id: str = arguments["winner_proposal_id"]
    rationale: str = arguments.get("rationale", "")
    operator_id: str = arguments.get("operator_id", "human")

    deferred = await state.audit_store.get_deferred(decision_id)
    if deferred is None:
        raise ValueError(f"No deferred decision found for id={decision_id!r}")
    if deferred.resolved_at is not None:
        raise ValueError(f"Decision {decision_id!r} is already resolved")

    await state.audit_store.resolve_deferred(
        decision_id=decision_id,
        outcome=winner_proposal_id,
        resolved_by=operator_id,
    )

    cached = state.verdict_cache.get(decision_id)
    if cached is not None:
        from saalis.models import Explanation, Verdict, VerdictStatus
        updated = Verdict(
            decision_id=cached.decision_id,
            winner_proposal_id=winner_proposal_id,
            strategy_name=cached.strategy_name,
            status=VerdictStatus.resolved,
            explanation=Explanation(
                summary=f"Resolved by {operator_id}: {rationale}",
                rationale=rationale,
            ),
            policy_result=cached.policy_result,
        )
        state.verdict_cache[decision_id] = updated
        return updated.render("json")

    return json.dumps({
        "decision_id": decision_id,
        "winner_proposal_id": winner_proposal_id,
        "status": "resolved",
        "resolved_by": operator_id,
    })


async def handle_get_pending(state: AppState, _arguments: dict[str, Any]) -> str:
    pending = await state.audit_store.list_pending_deferred()
    return json.dumps([
        {
            "decision_id": d.decision_id,
            "deferred_at": d.deferred_at.isoformat() if d.deferred_at else None,
        }
        for d in pending
    ])
