# Strategies

A strategy is responsible for choosing the winning proposal from a `Decision`. Each strategy implements one method:

```python
async def resolve(decision: Decision) -> Verdict
```

The `Arbitrator` calls exactly one strategy per arbitration. For fallback behaviour, compose strategies explicitly (e.g. `LLMJudge(fallback=WeightedVote())`).

---

## WeightedVote

Scores each proposal by `agent.weight × proposal.confidence` and picks the highest.

```python
from saalis.strategy import WeightedVote

arb = Arbitrator(strategies=[WeightedVote()])
```

**Scoring example** with three agents:

| Agent | Weight | Proposal | Confidence | Score |
|---|---|---|---|---|
| GPT-4o | 1.0 | Deploy now | 0.85 | **0.850** |
| Claude | 1.5 | Wait for review | 0.75 | **1.125** ← winner |
| Gemini | 1.0 | Rollback | 0.60 | **0.600** |

### Agent weight

`weight` is an unbounded positive multiplier (`≥ 0`). Use it to express relative trust or importance:

- `weight=1.0` — baseline
- `weight=2.0` — this agent's votes count twice
- `weight=0.5` — this agent's votes count half

There is no upper bound. You don't need to normalize weights to sum to 1.

### Optional weight overrides

You can override agent weights at strategy construction time without modifying the `Agent` objects:

```python
WeightedVote(agent_weights={"a1": 0.3, "a2": 2.0})
```

Runtime overrides take precedence over `Agent.weight`.

---

## LLMJudge

Calls an LLM to read the question and proposals, then picks a winner with a written rationale. Uses any OpenAI-compatible endpoint.

```python
from saalis.strategy import LLMJudge

arb = Arbitrator(
    strategies=[LLMJudge(
        model="gpt-4o",      # any OpenAI-compatible model
        base_url=None,       # override for Ollama, Groq, Together, etc.
        api_key=None,        # falls back to OPENAI_API_KEY env var
        timeout=30.0,
        max_retries=3,
    )],
)
```

### How it works

1. Serialises the `Decision` (question + proposals) into a structured prompt
2. Calls the model with `response_format=json_object`
3. Parses `winner_proposal_id`, `rationale`, and `score_breakdown` from the response
4. If the response is malformed — retries up to `max_retries`
5. If all retries fail — runs the fallback strategy

### Fallback behaviour

On exhausted retries or an invalid winner ID, `LLMJudge` falls back to `WeightedVote` (default) and flags the rationale:

```
[LLMJudge failed after 3 retries (...), fell back to WeightedVote] Highest weighted confidence score
```

You can provide a custom fallback:

```python
LLMJudge(fallback=WeightedVote(agent_weights={"trusted": 2.0}))
```

### Using local models (Ollama, Groq, Together)

```python
# Ollama (local)
LLMJudge(model="llama3.2", base_url="http://localhost:11434/v1", api_key="ollama")

# Groq
LLMJudge(model="llama-3.1-70b-versatile", base_url="https://api.groq.com/openai/v1")

# Together AI
LLMJudge(model="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
         base_url="https://api.together.xyz/v1")
```

---

## DeferToHuman

Always returns a `pending_human` verdict immediately. The decision is logged as deferred and awaits resolution via the HTTP sidecar (`POST /v1/decisions/{id}/human_response`) or MCP tool (`saalis_human_respond`).

```python
from saalis.strategy import DeferToHuman

arb = Arbitrator(
    strategies=[DeferToHuman(reason="Legal sign-off required")]
)
verdict = await arb.arbitrate(decision)
# verdict.status == VerdictStatus.pending_human
```

Use this for decisions that must always have a human in the loop — regulatory approvals, financial transactions, policy changes.

---

## Writing a custom strategy

Subclass `Strategy` and implement `name` and `resolve`:

```python
from saalis.strategy import Strategy
from saalis.models import Decision, Explanation, PolicyDecision, Verdict, VerdictStatus

class MajorityVote(Strategy):
    name = "MajorityVote"

    async def resolve(self, decision: Decision) -> Verdict:
        # Count votes (one vote per agent, regardless of confidence)
        votes: dict[str, int] = {}
        for proposal in decision.proposals:
            votes[proposal.id] = votes.get(proposal.id, 0) + 1

        winner_id = max(votes, key=lambda pid: votes[pid])

        return Verdict(
            decision_id=decision.id,
            winner_proposal_id=winner_id,
            strategy_name=self.name,
            explanation=Explanation(
                summary=f"Proposal {winner_id} won by majority vote",
                rationale=f"Received {votes[winner_id]} of {len(decision.proposals)} votes",
                score_breakdown={pid: float(v) for pid, v in votes.items()},
            ),
            policy_result=PolicyDecision(allowed=True),
            status=VerdictStatus.resolved,
        )
```

Then use it like any built-in strategy:

```python
arb = Arbitrator(strategies=[MajorityVote()])
```
