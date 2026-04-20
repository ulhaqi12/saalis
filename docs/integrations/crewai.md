# CrewAI Integration

`ArbitrationTool` duck-types CrewAI's `BaseTool` interface (`name`, `description`, `_run`, `_arun`) without importing `crewai`. Attach it to any CrewAI agent or call it standalone.

## Attach to a CrewAI agent

```python
from crewai import Agent, Task, Crew
from saalis.integrations.crewai import ArbitrationTool
from saalis.strategy import WeightedVote

tool = ArbitrationTool(strategies=[WeightedVote()], output_format="markdown")

agent = Agent(
    role="Decision Arbiter",
    goal="Resolve disagreements between AI agents using structured arbitration",
    backstory="You have access to a governance layer that arbitrates conflicting proposals.",
    tools=[tool],
)

task = Task(
    description="Arbitrate: should we deploy to production? GPT-4o says yes, Claude says wait.",
    agent=agent,
)

crew = Crew(agents=[agent], tasks=[task])
crew.kickoff()
```

## Call directly (no CrewAI needed)

=== "Async"
    ```python
    tool = ArbitrationTool(strategies=[WeightedVote()], output_format="text")

    result = await tool._arun(
        question="Deploy to production?",
        proposals=[
            {"id": "p1", "agent_id": "a1", "content": "Deploy now",     "confidence": 0.9},
            {"id": "p2", "agent_id": "a2", "content": "Wait for tests", "confidence": 0.7},
        ],
        agents=[
            {"id": "a1", "name": "GPT-4o", "weight": 1.0},
            {"id": "a2", "name": "Claude",  "weight": 1.5},
        ],
    )
    print(result)
    ```

=== "Sync"
    ```python
    tool = ArbitrationTool(strategies=[WeightedVote()], output_format="json")

    result = tool._run(
        question="Deploy to production?",
        proposals=[...],
        agents=[...],
    )
    import json
    data = json.loads(result)
    print(data["winner_proposal_id"])
    ```

## Output formats

| Format | Description |
|---|---|
| `"text"` | Single paragraph — good for CrewAI task output |
| `"markdown"` | Structured markdown with score table |
| `"json"` | Full verdict JSON |

```python
ArbitrationTool(output_format="text")      # default
ArbitrationTool(output_format="markdown")
ArbitrationTool(output_format="json")
```

## With policy and audit

```python
from saalis.policy import PolicyEngine, MinConfidenceRule
from saalis.audit.sqlite import SQLiteAuditStore

tool = ArbitrationTool(
    strategies=[WeightedVote()],
    policy_engine=PolicyEngine(rules=[MinConfidenceRule(threshold=0.6)]),
    audit_store=SQLiteAuditStore("sqlite+aiosqlite:///./audit.db"),
    output_format="markdown",
)
```

## Input formats

Both raw dicts and Pydantic `Proposal`/`Agent` objects are accepted for `proposals` and `agents`.

## Sync/async compatibility

`_run()` is safe to call from any context — it detects whether an event loop is already running and adapts accordingly using a thread pool executor. No manual `asyncio.run()` needed.
