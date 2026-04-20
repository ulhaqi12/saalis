# LangGraph Integration

`ArbitrationNode` is a drop-in LangGraph node that runs Saalis arbitration as a step in any graph.

It requires **no `langgraph` import** — it's a plain async callable that reads from and writes to a state dict. This means it works with LangGraph, or any other framework that uses the `async (state) -> partial_state` node protocol.

## Basic usage

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
    "agents":   [{"id": "a1", "name": "GPT-4o", "weight": 1.0}],
    "proposals":[{"agent_id": "a1", "content": "Approach A", "confidence": 0.9}],
})

print(result["verdict"].render("markdown"))
```

## Custom state keys

All four state keys are configurable. Use this when your graph already has a schema with different field names:

```python
node = ArbitrationNode(
    strategies=[WeightedVote()],
    question_key="task",        # reads from state["task"]
    proposals_key="candidates", # reads from state["candidates"]
    agents_key="participants",  # reads from state["participants"]
    verdict_key="decision",     # writes to state["decision"]
)
```

## Input formats

Both raw dicts and Pydantic objects are accepted for `proposals` and `agents`:

=== "Pydantic objects"
    ```python
    from saalis.models import Agent, Proposal

    state = {
        "question": "...",
        "agents":   [Agent(id="a1", name="X", weight=1.0)],
        "proposals":[Proposal(agent_id="a1", content="Y", confidence=0.9)],
    }
    ```

=== "Raw dicts"
    ```python
    state = {
        "question": "...",
        "agents":   [{"id": "a1", "name": "X", "weight": 1.0}],
        "proposals":[{"agent_id": "a1", "content": "Y", "confidence": 0.9}],
    }
    ```

## With policy and audit

```python
from saalis.policy import PolicyEngine, MinConfidenceRule
from saalis.audit.sqlite import SQLiteAuditStore

node = ArbitrationNode(
    strategies=[WeightedVote()],
    policy_engine=PolicyEngine(rules=[MinConfidenceRule(threshold=0.6)]),
    audit_store=SQLiteAuditStore("sqlite+aiosqlite:///./audit.db"),
)
```

## Placing the node in a multi-agent graph

```python
graph = StateGraph(AgentState)
graph.add_node("collect_proposals", collect_node)
graph.add_node("arbitrate", ArbitrationNode(strategies=[WeightedVote()]))
graph.add_node("act_on_verdict", action_node)

graph.set_entry_point("collect_proposals")
graph.add_edge("collect_proposals", "arbitrate")
graph.add_edge("arbitrate", "act_on_verdict")
graph.add_edge("act_on_verdict", END)
```

The `verdict` written to state is a full `Verdict` Pydantic object — call `.render()` or access fields directly in downstream nodes.
