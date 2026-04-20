# Saalis — ثالث

[![CI](https://github.com/ulhaqi12/saalis/actions/workflows/ci.yml/badge.svg)](https://github.com/ulhaqi12/saalis/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/saalis.svg)](https://pypi.org/project/saalis/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://github.com/ulhaqi12/saalis/blob/main/LICENSE)

**Governance and evidence layer for multi-agent AI decision arbitration.**

When multiple AI agents produce conflicting outputs, Saalis provides configurable resolution strategies, policy enforcement, explainability, and audit logging.

---

## Install

```bash
pip install saalis
# or
uv add saalis
```

## Minimal example

```python
import asyncio
from saalis import build_arbitrator, Decision, Proposal, Agent

async def main():
    decision = Decision(
        question="Should we deploy to production?",
        agents=[Agent(id="a1", name="GPT-4o", weight=1.0),
                Agent(id="a2", name="Claude", weight=1.5)],
        proposals=[
            Proposal(agent_id="a1", content="Deploy now",    confidence=0.9),
            Proposal(agent_id="a2", content="Wait for tests", confidence=0.8),
        ],
    )
    arb = build_arbitrator(strategy="weighted_vote")
    verdict = await arb.arbitrate(decision)
    print(verdict.render("markdown"))

asyncio.run(main())
```

---

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

---

## Navigation

- New here? Start with [Installation](install.md) then [Quickstart](quickstart.md).
- Looking for a specific feature? Use the tabs above.
- Want to contribute? See [Contributing](contributing.md).
