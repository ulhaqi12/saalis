"""
Saalis MCP server demo — no real LLM or MCP client required.

Demonstrates the five MCP tools by calling their handlers directly,
exactly as the MCP server would when an LLM (Claude, GPT-4o, etc.) invokes them.

Covers:
  1. saalis_arbitrate      — submit a decision, get a Verdict
  2. saalis_get_verdict    — retrieve a cached verdict by decision_id
  3. saalis_audit_query    — query audit events (all + filtered by type)
  4. saalis_get_pending    — list decisions awaiting human input
  5. saalis_human_respond  — resolve a deferred (DeferToHuman) decision

Running the server (for real Claude Desktop / MCP client use):
  # stdio mode — Claude Desktop
  cd mcp
  SAALIS_MCP_STRATEGY=weighted_vote python -m saalis_mcp

  # HTTP/SSE mode — server deployment
  SAALIS_MCP_TRANSPORT=http SAALIS_MCP_PORT=3000 python -m saalis_mcp

Claude Desktop config  (~/ Library/Application Support/Claude/claude_desktop_config.json):
  {
    "mcpServers": {
      "saalis": {
        "command": "python",
        "args": ["-m", "saalis_mcp"],
        "cwd": "/path/to/saalis/mcp",
        "env": {"SAALIS_MCP_STRATEGY": "weighted_vote"}
      }
    }
  }
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from saalis.arbitrator import Arbitrator
from saalis.audit.sqlite import SQLiteAuditStore
from saalis.strategy import DeferToHuman, WeightedVote
from saalis_mcp.resources import handle_decision_audit, handle_health
from saalis_mcp.state import AppState
from saalis_mcp.tools import (
    handle_arbitrate,
    handle_audit_query,
    handle_get_pending,
    handle_get_verdict,
    handle_human_respond,
)

# ── shared fixtures ────────────────────────────────────────────────────────

AGENTS = [
    {"id": "a1", "name": "GPT-4o", "weight": 0.6},
    {"id": "a2", "name": "Claude", "weight": 0.9},
    {"id": "a3", "name": "Gemini", "weight": 0.7},
]

PROPOSALS = [
    {"id": "p1", "agent_id": "a1", "content": "Deploy immediately", "confidence": 0.85},
    {"id": "p2", "agent_id": "a2", "content": "Deploy after review", "confidence": 0.75},
    {"id": "p3", "agent_id": "a3", "content": "Rollback and wait",  "confidence": 0.60},
]

QUESTION = "Should we deploy the new model to production?"


def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print("─" * 60)


def pp(raw_json: str) -> None:
    """Pretty-print a JSON string (or pass through non-JSON values like 'null')."""
    try:
        print(json.dumps(json.loads(raw_json), indent=2))
    except json.JSONDecodeError:
        print(raw_json)


# ── helpers ────────────────────────────────────────────────────────────────

def make_weighted_state(db_path: Path) -> AppState:
    store = SQLiteAuditStore(f"sqlite+aiosqlite:///{db_path}")
    arb = Arbitrator(strategies=[WeightedVote()], audit_store=store)
    return AppState(arbitrator=arb, audit_store=store)


def make_deferred_state(db_path: Path) -> AppState:
    store = SQLiteAuditStore(f"sqlite+aiosqlite:///{db_path}")
    arb = Arbitrator(strategies=[DeferToHuman(reason="Legal sign-off required")], audit_store=store)
    return AppState(arbitrator=arb, audit_store=store)


# ── 1. saalis_arbitrate ────────────────────────────────────────────────────

async def demo_arbitrate(tmp: Path) -> str:
    section("1. saalis_arbitrate")

    state = make_weighted_state(tmp / "arb.db")
    result = await handle_arbitrate(state, {
        "question": QUESTION,
        "proposals": PROPOSALS,
        "agents": AGENTS,
    })

    data = json.loads(result)
    print(f"Winner:   {data['winner_proposal_id']}")
    print(f"Strategy: {data['strategy_name']}")
    print(f"Status:   {data['status']}")

    await state.audit_store.close()
    return data["decision_id"]


# ── 2. saalis_get_verdict ──────────────────────────────────────────────────

async def demo_get_verdict(tmp: Path) -> None:
    section("2. saalis_get_verdict")

    state = make_weighted_state(tmp / "verdict.db")

    result = await handle_arbitrate(state, {
        "question": QUESTION,
        "proposals": PROPOSALS,
        "agents": AGENTS,
    })
    decision_id = json.loads(result)["decision_id"]

    # fetch it back from the in-memory cache
    cached = await handle_get_verdict(state, {"decision_id": decision_id})
    print(f"Cached verdict status: {json.loads(cached)['status']}")

    # unknown id returns null
    missing = await handle_get_verdict(state, {"decision_id": "ghost-id"})
    print(f"Unknown decision_id:   {missing}")

    await state.audit_store.close()


# ── 3. saalis_audit_query ──────────────────────────────────────────────────

async def demo_audit_query(tmp: Path) -> None:
    section("3. saalis_audit_query")

    state = make_weighted_state(tmp / "audit.db")
    await handle_arbitrate(state, {
        "question": QUESTION,
        "proposals": PROPOSALS,
        "agents": AGENTS,
    })

    # all events
    all_events = json.loads(await handle_audit_query(state, {}))
    print(f"Total audit events: {len(all_events)}")
    for ev in all_events:
        print(f"  {ev['event_type']}")

    # filter by event type
    started = json.loads(
        await handle_audit_query(state, {"event_type": "arbitration_started"})
    )
    print(f"\nFiltered to 'arbitration_started': {len(started)} event(s)")

    await state.audit_store.close()


# ── 4. saalis_get_pending + 5. saalis_human_respond ───────────────────────

async def demo_deferred_flow(tmp: Path) -> None:
    section("4. saalis_get_pending  +  5. saalis_human_respond")

    state = make_deferred_state(tmp / "deferred.db")

    # arbitrate — DeferToHuman returns pending_human immediately
    result = await handle_arbitrate(state, {
        "question": QUESTION,
        "proposals": PROPOSALS,
        "agents": AGENTS,
    })
    data = json.loads(result)
    decision_id = data["decision_id"]
    print(f"Verdict status after DeferToHuman: {data['status']}")

    # list pending
    pending = json.loads(await handle_get_pending(state, {}))
    print(f"Pending decisions: {len(pending)}")
    print(f"  decision_id: {pending[0]['decision_id']}")

    # human resolves it
    resolved = json.loads(await handle_human_respond(state, {
        "decision_id": decision_id,
        "winner_proposal_id": "p2",
        "rationale": "p2 is safest — deploy after review.",
        "operator_id": "alice",
    }))
    print(f"\nAfter human response:")
    print(f"  Status:   {resolved['status']}")
    print(f"  Winner:   {resolved['winner_proposal_id']}")

    # pending list is now empty
    still_pending = json.loads(await handle_get_pending(state, {}))
    print(f"Pending decisions after resolution: {len(still_pending)}")

    await state.audit_store.close()


# ── resource: saalis://health ──────────────────────────────────────────────

async def demo_resources(tmp: Path) -> None:
    section("Resources — saalis://health  +  saalis://decisions/{id}/audit")

    state = make_weighted_state(tmp / "resources.db")
    result = await handle_arbitrate(state, {
        "question": QUESTION,
        "proposals": PROPOSALS,
        "agents": AGENTS,
    })
    decision_id = json.loads(result)["decision_id"]

    health = json.loads(await handle_health(state))
    print(f"health status:  {health['status']}")
    print(f"health version: {health['version']}")

    audit_events = json.loads(await handle_decision_audit(state, decision_id))
    print(f"\naudit events for decision: {len(audit_events)}")

    await state.audit_store.close()


# ── main ───────────────────────────────────────────────────────────────────

async def main() -> None:
    print("\n🔷 Saalis MCP server demo")
    print("   (tool handlers called directly — no MCP client needed)")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        await demo_arbitrate(tmp_path)
        await demo_get_verdict(tmp_path)
        await demo_audit_query(tmp_path)
        await demo_deferred_flow(tmp_path)
        await demo_resources(tmp_path)

    print(f"\n{'─' * 60}")
    print("  All MCP tool demos complete.")
    print("─" * 60)


if __name__ == "__main__":
    asyncio.run(main())
