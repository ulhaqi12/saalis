from __future__ import annotations

import importlib.metadata
import json

from saalis_mcp.state import AppState


async def handle_health(state: AppState) -> str:
    try:
        version = importlib.metadata.version("saalis-mcp")
    except importlib.metadata.PackageNotFoundError:
        version = "dev"
    return json.dumps({"status": "ok", "version": version})


async def handle_decision_audit(state: AppState, decision_id: str) -> str:
    all_events = await state.audit_store.query(limit=1000)
    events = [
        e for e in all_events
        if isinstance(e.payload, dict) and e.payload.get("decision_id") == decision_id
    ]
    return json.dumps([json.loads(e.model_dump_json()) for e in events])
