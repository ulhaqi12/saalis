# Quickstart

This page walks through a complete arbitration flow in under 30 lines. No LLM API key required.

## Core concepts

| Concept | Description |
|---|---|
| `Agent` | A participant in the decision — has an `id`, `name`, and `weight` (importance multiplier) |
| `Proposal` | What an agent recommends — has `content` and a `confidence` score (0–1) |
| `Decision` | The question being arbitrated, with its agents and proposals |
| `Arbitrator` | Runs the strategy, applies policy rules, writes to the audit log |
| `Verdict` | The result — winner, rationale, score breakdown, status |

## Example

```python
import asyncio
from saalis import Arbitrator, Agent, Decision, Proposal
from saalis.strategy import WeightedVote
from saalis.audit.jsonl import JSONLAuditStore

async def main():
    agents = [
        Agent(id="a1", name="GPT-4o",  weight=1.0),
        Agent(id="a2", name="Claude",  weight=1.5),  # 1.5× more influential
        Agent(id="a3", name="Gemini",  weight=1.0),
    ]

    decision = Decision(
        question="Should we deploy the new model to production?",
        agents=agents,
        proposals=[
            Proposal(agent_id="a1", content="Deploy immediately",  confidence=0.85),
            Proposal(agent_id="a2", content="Deploy after review", confidence=0.75),
            Proposal(agent_id="a3", content="Rollback and wait",   confidence=0.60),
        ],
    )

    arb = Arbitrator(
        strategies=[WeightedVote()],
        audit_store=JSONLAuditStore("audit.jsonl"),
    )

    verdict = await arb.arbitrate(decision)
    print(verdict.render("markdown"))

asyncio.run(main())
```

### Expected output

```
## Decision Summary
Proposal by agent 'a2' won with score 1.125

**Strategy:** WeightedVote  **Status:** resolved

### Rationale
Highest weighted confidence score

### Score Breakdown
| Proposal | Score |
|---|---|
| p2 | 1.125 |
| p1 | 0.850 |
| p3 | 0.600 |

### Dissenting Proposals
- Proposal p1 (agent a1) scored 0.850
- Proposal p3 (agent a3) scored 0.600
```

The winning proposal is `p2` because `a2.weight × p2.confidence = 1.5 × 0.75 = 1.125` beats all others.

## One-liner with `build_arbitrator`

If you don't need to configure each piece individually, use the convenience factory:

```python
from saalis import build_arbitrator

arb = build_arbitrator(
    strategy="weighted_vote",     # or "llm_judge" / "defer_to_human"
    min_confidence=0.5,           # optional: blocks proposals below threshold
    blocklist_agents=["bad-bot"], # optional: blocks specific agents
)
verdict = await arb.arbitrate(decision)
```

`build_arbitrator` accepts all the same config options as the sidecar and MCP server environment variables — useful for scripting or testing.

## What happens under the hood

1. `Arbitrator.arbitrate()` emits an `arbitration_started` audit event
2. Pre-policy check runs (e.g. `MinConfidenceRule`) — blocks if violated
3. The strategy resolves the decision and produces a `Verdict`
4. Post-policy check runs (e.g. `BlocklistAgentRule`) — can override the verdict
5. If status is `pending_human`, a `human_deferred` event is written
6. A `verdict_issued` audit event is written
7. The `Verdict` is returned

## Next steps

- [Strategies](strategies.md) — pick the right resolution strategy
- [Policy Enforcement](policy.md) — add guardrails
- [Audit Stores](audit.md) — persist your audit trail
- [Verdict Rendering](rendering.md) — format verdicts for humans or machines
