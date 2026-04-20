# saalis — ثالث

[![CI](https://github.com/ulhaqi12/saalis/actions/workflows/ci.yml/badge.svg)](https://github.com/ulhaqi12/saalis/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/saalis.svg)](https://pypi.org/project/saalis/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Governance and evidence layer for multi-agent AI decision arbitration.

When multiple AI agents produce conflicting outputs, Saalis provides configurable resolution strategies, policy enforcement, explainability, and audit logging.

**[Full documentation →](https://ulhaqi12.github.io/saalis)**

---

## Install

```bash
pip install saalis
# or
uv add saalis
```

## Quickstart

```python
import asyncio
from saalis import build_arbitrator, Decision, Proposal, Agent

async def main():
    decision = Decision(
        question="Should we deploy to production?",
        agents=[Agent(id="a1", name="GPT-4o", weight=1.0),
                Agent(id="a2", name="Claude",  weight=1.5)],
        proposals=[
            Proposal(agent_id="a1", content="Deploy now",     confidence=0.9),
            Proposal(agent_id="a2", content="Wait for tests", confidence=0.8),
        ],
    )
    arb = build_arbitrator(strategy="weighted_vote")
    verdict = await arb.arbitrate(decision)
    print(verdict.render("markdown"))

asyncio.run(main())
```

## What's inside

| Feature | Description |
|---|---|
| **Strategies** | `WeightedVote`, `LLMJudge`, `DeferToHuman` |
| **Policy** | Pre/post-arbitration rules: min confidence, agent blocklist |
| **Audit** | Append-only event log — JSONL or SQLite |
| **Rendering** | Verdicts as plain text, Markdown, or JSON |
| **HTTP Sidecar** | Standalone FastAPI service — Docker-ready |
| **MCP Server** | Native MCP tools for Claude Desktop and any MCP orchestrator |
| **Integrations** | LangGraph node, CrewAI tool |

## Roadmap

- [x] **Protocol interoperability** — native MCP server (`saalis-mcp`) for Claude Desktop and any MCP-native orchestrator
- [ ] **Advanced arbitration** — multi-model debate, adversarial courtroom, ensemble strategies, hallucination detection
- [ ] **Security hardening** — proposal sanitization, signed agent identity, rate limiting, hash-chained audit logs
- [ ] **OpenTelemetry** — GenAI semantic convention spans, distributed trace propagation, Grafana dashboard
- [ ] **PostgreSQL + pgvector** — production-grade backend, semantic search over past decisions, persistent agent profiles
- [ ] **Evaluation framework** — benchmark harness, A/B shadow testing, human feedback loop
- [ ] **More framework adapters** — Microsoft Agent Framework, Google ADK, OpenAI Agents SDK, Pydantic AI, n8n, Dify
- [ ] **CLI + YAML config** — `saalis serve`, `saalis replay`, `saalis bench`, declarative `saalis.yaml`

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, code conventions, and how to add strategies or integration adapters.

## License

Apache 2.0 — see [LICENSE](LICENSE).
