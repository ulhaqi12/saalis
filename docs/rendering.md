# Verdict Rendering

Every `Verdict` has a `render()` method that formats the result for different audiences.

```python
verdict.render()            # plain text — default
verdict.render("text")      # same as above
verdict.render("markdown")  # structured markdown
verdict.render("json")      # full JSON (all fields)
```

---

## Text

A single readable paragraph — good for logs, CLI output, or passing to another LLM.

```python
print(verdict.render("text"))
```

```
Proposal by agent 'a2' won with score 1.125. Highest weighted confidence score.
Dissenting proposals: Proposal p1 (agent a1) scored 0.850; Proposal p3 (agent a3) scored 0.600.
```

---

## Markdown

Structured output with headers and a score table. Good for Slack messages, GitHub comments, audit reports, or any Markdown-aware surface.

```python
print(verdict.render("markdown"))
```

```markdown
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

---

## JSON

Full machine-readable output with all fields. Use this for downstream processing, storage, or API responses.

```python
import json
data = json.loads(verdict.render("json"))
```

```json
{
  "id": "3a2b1c...",
  "decision_id": "9f8e7d...",
  "winner_proposal_id": "p2",
  "strategy_name": "WeightedVote",
  "status": "resolved",
  "created_at": "2025-01-15T10:23:45.123456+00:00",
  "explanation": {
    "summary": "Proposal by agent 'a2' won with score 1.125",
    "rationale": "Highest weighted confidence score",
    "dissents": [
      "Proposal p1 (agent a1) scored 0.850",
      "Proposal p3 (agent a3) scored 0.600"
    ],
    "score_breakdown": {
      "p1": 0.850,
      "p2": 1.125,
      "p3": 0.600
    }
  },
  "policy_result": {
    "allowed": true,
    "reason": "",
    "matched_rule": null
  }
}
```

---

## Verdict status values

| Status | Meaning |
|---|---|
| `resolved` | A winner was selected |
| `pending_human` | `DeferToHuman` — waiting for human input |
| `policy_blocked` | A policy rule blocked the decision |

---

## Accessing fields directly

You can also read fields directly from the verdict object without rendering:

```python
verdict.winner_proposal_id     # str | None
verdict.strategy_name          # str
verdict.status                 # VerdictStatus
verdict.explanation.summary    # str
verdict.explanation.rationale  # str
verdict.explanation.score_breakdown  # dict[str, float]
verdict.policy_result.allowed  # bool
verdict.policy_result.reason   # str
```
