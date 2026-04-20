# Policy Enforcement

The `PolicyEngine` runs rules in two phases:

- **Pre-arbitration** (`check_pre`) — runs before the strategy. Can block the decision entirely.
- **Post-arbitration** (`check_post`) — runs after the strategy. Can override the verdict if the winning proposal violates a rule.

When a rule fires, the verdict gets `status=policy_blocked` and `policy_result.allowed=False`.

---

## PolicyEngine

```python
from saalis.policy import PolicyEngine, MinConfidenceRule, BlocklistAgentRule

engine = PolicyEngine(rules=[
    MinConfidenceRule(threshold=0.6),
    BlocklistAgentRule(blocklist=["untrusted-bot"]),
])

arb = Arbitrator(strategies=[WeightedVote()], policy_engine=engine)
```

Rules are evaluated in order. The first rule that fires blocks or overrides — remaining rules are not evaluated.

---

## Built-in rules

### MinConfidenceRule

Blocks arbitration if **no proposal** meets the minimum confidence threshold.

```python
MinConfidenceRule(threshold=0.7)
```

- Phase: **pre**
- Blocks when: all proposals have `confidence < threshold`
- Use case: reject low-quality inputs before spending LLM tokens

```python
engine = PolicyEngine(rules=[MinConfidenceRule(threshold=0.7)])
arb = Arbitrator(strategies=[WeightedVote()], policy_engine=engine)

verdict = await arb.arbitrate(decision)
# If all proposals have confidence < 0.7:
# verdict.status == VerdictStatus.policy_blocked
# verdict.policy_result.reason == "No proposal meets min_confidence=0.7"
```

### BlocklistAgentRule

Blocks the verdict if the **winning proposal** was submitted by a blocklisted agent.

```python
BlocklistAgentRule(blocklist=["untrusted-bot", "deprecated-agent-v1"])
```

- Phase: **post**
- Blocks when: `verdict.winner_proposal_id` belongs to a blocklisted agent
- Use case: prevent compromised or retired agents from winning

```python
engine = PolicyEngine(rules=[BlocklistAgentRule(blocklist=["a2"])])
arb = Arbitrator(strategies=[WeightedVote()], policy_engine=engine)

verdict = await arb.arbitrate(decision)
# If the highest-scoring proposal belongs to "a2":
# verdict.status == VerdictStatus.policy_blocked
# verdict.policy_result.reason == "Winning agent 'a2' is blocklisted"
```

### RequireEvidenceRule

Blocks arbitration if no proposal has any attached evidence.

```python
from saalis.policy import RequireEvidenceRule

RequireEvidenceRule()
```

- Phase: **pre**
- Blocks when: every proposal has an empty `evidence` list
- Use case: enforce that agents must provide citations or chain-of-thought before being arbitrated

---

## Combining rules

```python
engine = PolicyEngine(rules=[
    MinConfidenceRule(threshold=0.6),   # checked first (pre)
    RequireEvidenceRule(),               # checked second (pre)
    BlocklistAgentRule(blocklist=["bad-agent"]),  # checked after verdict (post)
])
```

Pre rules run in order before the strategy; post rules run in order after. First failure wins.

---

## Writing a custom rule

Subclass `PolicyRule` and implement `check_pre` and/or `check_post`:

```python
from saalis.policy import PolicyRule
from saalis.models import Decision, PolicyDecision, Verdict

class MaxProposalsRule(PolicyRule):
    """Block decisions with more than N proposals."""
    name = "max_proposals"

    def __init__(self, max_count: int = 5) -> None:
        self.max_count = max_count

    def check_pre(self, decision: Decision) -> PolicyDecision | None:
        if len(decision.proposals) > self.max_count:
            return PolicyDecision(
                allowed=False,
                reason=f"Too many proposals: {len(decision.proposals)} > {self.max_count}",
                matched_rule=self.name,
            )
        return None  # pass
```

Return `None` to pass, or a `PolicyDecision(allowed=False, ...)` to block.

---

## Policy result in the verdict

Every verdict carries a `policy_result`:

```python
verdict.policy_result.allowed       # bool
verdict.policy_result.reason        # str — human-readable explanation
verdict.policy_result.matched_rule  # str | None — which rule fired
```

When no rule fires, `policy_result.allowed=True` and `reason=""`.
