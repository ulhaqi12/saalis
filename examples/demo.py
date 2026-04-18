"""
Saalis end-to-end demo — no real LLM required.

Covers:
  1. WeightedVote arbitration
  2. Policy enforcement (MinConfidenceRule, BlocklistAgentRule)
  3. DeferToHuman + manual resolution
  4. Verdict rendering (text / markdown / json)
  5. JSONLAuditStore
  6. SQLiteAuditStore
  7. LangGraph adapter
  8. CrewAI adapter
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from saalis import Agent, Arbitrator, Decision, Proposal
from saalis.audit.jsonl import JSONLAuditStore
from saalis.audit.sqlite import SQLiteAuditStore
from saalis.integrations.crewai import ArbitrationTool
from saalis.integrations.langgraph import ArbitrationNode
from saalis.policy import BlocklistAgentRule, MinConfidenceRule, PolicyEngine
from saalis.strategy import DeferToHuman, WeightedVote

# ── shared fixtures ────────────────────────────────────────────────────────

AGENTS = [
    Agent(id="a1", name="GPT-4o",  weight=0.6),
    Agent(id="a2", name="Claude",  weight=0.9),
    Agent(id="a3", name="Gemini",  weight=0.7),
]

PROPOSALS = [
    Proposal(id="p1", agent_id="a1", content="Deploy immediately", confidence=0.85),
    Proposal(id="p2", agent_id="a2", content="Deploy after review", confidence=0.75),
    Proposal(id="p3", agent_id="a3", content="Rollback and wait",  confidence=0.60),
]

QUESTION = "Should we deploy the new model to production?"


def make_decision() -> Decision:
    return Decision(question=QUESTION, agents=AGENTS, proposals=PROPOSALS)


def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print('─' * 60)


# ── 1. WeightedVote ────────────────────────────────────────────────────────

async def demo_weighted_vote() -> None:
    section("1. WeightedVote")

    arb = Arbitrator(strategies=[WeightedVote()])
    verdict = await arb.arbitrate(make_decision())

    print(f"Winner:   {verdict.winner_proposal_id}")
    print(f"Strategy: {verdict.strategy_name}")
    print(f"Status:   {verdict.status}")
    # a1: 0.6×0.85=0.51  a2: 0.9×0.75=0.675  a3: 0.7×0.60=0.42 → p2 wins
    print("\nScore breakdown:")
    for pid, score in verdict.explanation.score_breakdown.items():
        print(f"  {pid}: {score:.3f}")


# ── 2. Policy — MinConfidenceRule ──────────────────────────────────────────

async def demo_policy_min_confidence() -> None:
    section("2. Policy — MinConfidenceRule (threshold=0.90)")

    engine = PolicyEngine(rules=[MinConfidenceRule(threshold=0.90)])
    arb = Arbitrator(strategies=[WeightedVote()], policy_engine=engine)
    verdict = await arb.arbitrate(make_decision())

    print(f"Status:  {verdict.status}")           # policy_blocked
    print(f"Reason:  {verdict.policy_result.reason}")
    print(f"Allowed: {verdict.policy_result.allowed}")


# ── 3. Policy — BlocklistAgentRule ────────────────────────────────────────

async def demo_policy_blocklist() -> None:
    section("3. Policy — BlocklistAgentRule (blocks a2/Claude)")

    engine = PolicyEngine(rules=[BlocklistAgentRule(blocklist=["a2"])])
    arb = Arbitrator(strategies=[WeightedVote()], policy_engine=engine)
    verdict = await arb.arbitrate(make_decision())

    # WeightedVote picks p2 (a2), but post-policy blocks it
    print(f"Status:  {verdict.status}")
    print(f"Reason:  {verdict.policy_result.reason}")


# ── 4. DeferToHuman ────────────────────────────────────────────────────────

async def demo_defer_to_human() -> None:
    section("4. DeferToHuman")

    arb = Arbitrator(strategies=[DeferToHuman(reason="Requires legal sign-off")])
    verdict = await arb.arbitrate(make_decision())

    print(f"Status:  {verdict.status}")           # pending_human
    print(f"Summary: {verdict.explanation.summary}")
    print("\n  → In production: POST /v1/decisions/{id}/human_response to resolve")


# ── 5. Verdict rendering ───────────────────────────────────────────────────

async def demo_rendering() -> None:
    section("5. Verdict rendering")

    arb = Arbitrator(strategies=[WeightedVote()])
    verdict = await arb.arbitrate(make_decision())

    print("\n--- text ---")
    print(verdict.render("text"))

    print("\n--- markdown ---")
    print(verdict.render("markdown"))

    print("\n--- json (truncated) ---")
    data = json.loads(verdict.render("json"))
    print(json.dumps({k: data[k] for k in ("status", "winner_proposal_id", "strategy_name")}, indent=2))


# ── 6. JSONLAuditStore ─────────────────────────────────────────────────────

async def demo_jsonl_audit(tmp: Path) -> None:
    section("6. JSONLAuditStore")

    path = tmp / "audit.jsonl"
    store = JSONLAuditStore(path)
    arb = Arbitrator(strategies=[WeightedVote()], audit_store=store)
    await arb.arbitrate(make_decision())

    events = await store.query()
    print(f"Events written: {len(events)}")
    for ev in events:
        print(f"  {ev.event_type.value}")


# ── 7. SQLiteAuditStore ────────────────────────────────────────────────────

async def demo_sqlite_audit(tmp: Path) -> None:
    section("7. SQLiteAuditStore")

    store = SQLiteAuditStore(f"sqlite+aiosqlite:///{tmp}/audit.db")
    arb = Arbitrator(strategies=[WeightedVote()], audit_store=store)
    await arb.arbitrate(make_decision())

    events = await store.query()
    print(f"Events written: {len(events)}")
    for ev in events:
        print(f"  {ev.event_type.value}")
    await store.close()


# ── 8. LangGraph adapter ───────────────────────────────────────────────────

async def demo_langgraph() -> None:
    section("8. LangGraph adapter (ArbitrationNode)")

    node = ArbitrationNode(strategies=[WeightedVote()])

    state = {
        "question": QUESTION,
        "agents":    [a.model_dump() for a in AGENTS],
        "proposals": [p.model_dump() for p in PROPOSALS],
    }

    result = await node(state)
    verdict = result["verdict"]
    print(f"Winner:   {verdict.winner_proposal_id}")
    print(f"Status:   {verdict.status}")

    # custom keys
    node2 = ArbitrationNode(question_key="task", verdict_key="decision")
    result2 = await node2({**state, "task": QUESTION})
    print(f"Custom verdict key present: {'decision' in result2}")


# ── 9. CrewAI adapter ──────────────────────────────────────────────────────

async def demo_crewai() -> None:
    section("9. CrewAI adapter (ArbitrationTool)")

    proposals_raw = [p.model_dump() for p in PROPOSALS]
    agents_raw    = [a.model_dump() for a in AGENTS]

    # async
    tool = ArbitrationTool(strategies=[WeightedVote()], output_format="text")
    result = await tool._arun(QUESTION, proposals_raw, agents_raw)
    print("async _arun output:")
    print(f"  {result}")

    # sync
    tool_md = ArbitrationTool(strategies=[WeightedVote()], output_format="json")
    sync_result = tool_md._run(QUESTION, proposals_raw, agents_raw)
    data = json.loads(sync_result)
    print(f"\nsync _run winner: {data['winner_proposal_id']}")


# ── main ───────────────────────────────────────────────────────────────────

async def main() -> None:
    print("\n🔷 Saalis end-to-end demo")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        await demo_weighted_vote()
        await demo_policy_min_confidence()
        await demo_policy_blocklist()
        await demo_defer_to_human()
        await demo_rendering()
        await demo_jsonl_audit(tmp_path)
        await demo_sqlite_audit(tmp_path)
        await demo_langgraph()
        await demo_crewai()

    print(f"\n{'─' * 60}")
    print("  All demos complete.")
    print('─' * 60)


if __name__ == "__main__":
    asyncio.run(main())
