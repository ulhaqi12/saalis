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
uv sync --all-packages --extra dev
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
    print(verdict.render("markdown"))

asyncio.run(main())
```

## Strategies

| Strategy | Description |
|---|---|
| `WeightedVote` | Scores proposals by `agent.weight × confidence`, picks highest |
| `LLMJudge` | Calls an LLM to adjudicate; falls back to `WeightedVote` on failure |
| `DeferToHuman` | Returns a `pending_human` verdict; resolved via HTTP callback |

### LLMJudge

```python
from saalis.strategy import LLMJudge

arb = Arbitrator(
    strategies=[LLMJudge(
        model="gpt-4o",       # any OpenAI-compatible model
        base_url=None,        # override for Ollama, Groq, etc.
        api_key=None,         # falls back to OPENAI_API_KEY env var
        max_retries=3,
    )],
)
verdict = await arb.arbitrate(decision)
print(verdict.render("markdown"))
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

## Verdict rendering

```python
verdict.render()           # plain text paragraph
verdict.render("markdown") # structured markdown (for audit logs, Slack, docs)
verdict.render("json")     # full JSON
```

## Audit stores

| Store | Usage |
|---|---|
| `NullAuditStore` | Default, no-op |
| `JSONLAuditStore(path)` | Append-only JSONL file |
| `SQLiteAuditStore(db_url)` | SQLite via sqlalchemy async |

---

## HTTP Sidecar

A standalone FastAPI process for teams that can't import Python directly.

### Run

```bash
# From repo root
docker build -f sidecar/Dockerfile -t saalis-sidecar .
docker run -p 8000:8000 \
  -e SAALIS_STRATEGY=weighted_vote \
  -e SAALIS_BEARER_TOKEN=secret \
  saalis-sidecar
```

Or without Docker:

```bash
SAALIS_BEARER_TOKEN=secret uv run --package saalis-sidecar \
  uvicorn saalis_sidecar.app:app --port 8000
```

### Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/decisions/resolve` | Arbitrate a decision, returns `Verdict` |
| `GET` | `/v1/decisions/{id}/audit` | Query audit events for a decision |
| `GET` | `/v1/audit/events/{id}` | Fetch a single audit event |
| `POST` | `/v1/decisions/{id}/human_response` | Resolve a deferred decision |
| `GET` | `/healthz` | Liveness probe |
| `GET` | `/readyz` | Readiness probe (checks DB) |
| `GET` | `/metrics` | Prometheus metrics |

### Example

```bash
curl -X POST http://localhost:8000/v1/decisions/resolve \
  -H "Authorization: Bearer secret" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Deploy to production?",
    "agents": [{"id": "a1", "name": "GPT-4o", "weight": 0.8}],
    "proposals": [
      {"agent_id": "a1", "id": "p1", "content": "Deploy now", "confidence": 0.9},
      {"agent_id": "a1", "id": "p2", "content": "Wait", "confidence": 0.6}
    ]
  }'
```

### Configuration (env vars)

| Variable | Default | Description |
|---|---|---|
| `SAALIS_STRATEGY` | `weighted_vote` | `weighted_vote` \| `llm_judge` \| `defer_to_human` |
| `SAALIS_AUDIT_PATH` | `./saalis_audit.db` | Path to SQLite audit file |
| `SAALIS_BEARER_TOKEN` | `""` | Static auth token (empty = disabled) |
| `SAALIS_LLM_MODEL` | `gpt-4o` | Model for `LLMJudge` |
| `SAALIS_LLM_BASE_URL` | `""` | OpenAI-compatible base URL override |
| `SAALIS_MIN_CONFIDENCE` | `""` | Float threshold for `MinConfidenceRule` |
| `SAALIS_BLOCKLIST_AGENTS` | `""` | Comma-separated blocked agent IDs |

---

## Development

```bash
make install-all          # install lib + sidecar deps
make test                 # lib tests only
make test-sidecar         # sidecar tests only
make test-all             # both
make lint                 # ruff check lib
make fmt                  # ruff format + fix everything
make typecheck            # mypy lib
make typecheck-sidecar    # mypy sidecar
make all                  # fmt + lint + typecheck + test-all
```

---

## LangGraph Integration

`ArbitrationNode` is a drop-in LangGraph node. It requires no `langgraph` import — just an async callable that reads from and writes to graph state.

```python
from typing import TypedDict
from langgraph.graph import StateGraph, END
from saalis.integrations.langgraph import ArbitrationNode
from saalis.strategy import WeightedVote

class AgentState(TypedDict):
    question: str
    proposals: list
    agents: list
    verdict: object

node = ArbitrationNode(strategies=[WeightedVote()])

graph = StateGraph(AgentState)
graph.add_node("arbitrate", node)
graph.set_entry_point("arbitrate")
graph.add_edge("arbitrate", END)
app = graph.compile()

result = await app.ainvoke({
    "question": "Which approach is better?",
    "agents": [{"id": "a1", "name": "GPT-4o", "weight": 0.8}],
    "proposals": [{"agent_id": "a1", "content": "Approach A", "confidence": 0.9}],
})
print(result["verdict"].render("markdown"))
```

All state keys are configurable via `question_key`, `proposals_key`, `agents_key`, `verdict_key`. State values can be raw dicts or Pydantic objects — both accepted.

---

## Roadmap

- **M7** — CrewAI adapter
- **M8** — PyPI release
