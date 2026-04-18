# saalis

Governance and evidence layer for multi-agent AI decision arbitration.

When multiple AI agents produce conflicting outputs, Saalis provides configurable resolution strategies, policy enforcement, explainability, and audit logging.

## Install

```bash
uv add saalis
```

Or for development:

```bash
git clone https://github.com/ulhaqi12/saalis
cd saalis
uv sync --extra dev
```

## Quickstart

```python
import asyncio
from saalis import Arbitrator, Agent, Decision, Proposal
from saalis.strategy import WeightedVote
from saalis.audit.jsonl import JSONLAuditStore

async def main():
    agents = [
        Agent(id="a1", name="GPT-4o", weight=0.6),
        Agent(id="a2", name="Claude", weight=0.8),
    ]

    decision = Decision(
        question="Should we approve this PR?",
        agents=agents,
        proposals=[
            Proposal(agent_id="a1", content="Approve", confidence=0.9),
            Proposal(agent_id="a2", content="Request changes", confidence=0.7),
        ],
    )

    arb = Arbitrator(
        strategies=[WeightedVote()],
        audit_store=JSONLAuditStore("audit.jsonl"),
    )

    verdict = await arb.arbitrate(decision)
    print(f"Winner: {verdict.winner_proposal_id}")
    print(f"Summary: {verdict.explanation.summary}")
    print(f"Scores: {verdict.explanation.score_breakdown}")

asyncio.run(main())
```

## Policy enforcement

```python
from saalis.policy import PolicyEngine, MinConfidenceRule, BlocklistAgentRule

engine = PolicyEngine(rules=[
    MinConfidenceRule(threshold=0.6),
    BlocklistAgentRule(blocklist=["untrusted-agent-id"]),
])

arb = Arbitrator(strategies=[WeightedVote()], policy_engine=engine)
```

## Strategies

| Strategy | Description |
|---|---|
| `WeightedVote` | Scores proposals by `agent.weight × confidence`, picks highest |
| `DeferToHuman` | Returns a `pending_human` verdict; resolution requires a callback |

## Audit stores

| Store | Usage |
|---|---|
| `NullAuditStore` | Default, no-op |
| `JSONLAuditStore(path)` | Append-only JSONL file |
| `SQLiteAuditStore(db_url)` | SQLite via sqlalchemy async |

## Development

```bash
make test        # run tests
make lint        # ruff check
make fmt         # ruff format + fix
make typecheck   # mypy
make all         # fmt + lint + typecheck + test
```

## Roadmap

- **M4** — `LLMJudge` strategy (openai SDK, OpenAI-compatible)
- **M5** — HTTP sidecar (FastAPI: `/resolve`, `/audit`, `/human-response`)
- **M6** — LangGraph adapter
- **M7** — CrewAI adapter
- **M8** — PyPI release
