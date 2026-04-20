# HTTP Sidecar

`saalis-sidecar` is a standalone FastAPI service that wraps the core library. Use it when you can't import Python directly — a polyglot microservice, a Docker environment, or a team that prefers REST over library imports.

## Run

=== "Docker"
    ```bash
    # From repo root
    docker build -f sidecar/Dockerfile -t saalis-sidecar .
    docker run -p 8000:8000 \
      -e SAALIS_STRATEGY=weighted_vote \
      -e SAALIS_BEARER_TOKEN=secret \
      saalis-sidecar
    ```

=== "Without Docker"
    ```bash
    SAALIS_BEARER_TOKEN=secret uv run --package saalis-sidecar \
      uvicorn saalis_sidecar.app:app --port 8000
    ```

---

## Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/decisions/resolve` | Arbitrate a decision, returns `Verdict` |
| `GET` | `/v1/decisions/{id}/audit` | Query audit events for a decision |
| `GET` | `/v1/audit/events/{id}` | Fetch a single audit event by ID |
| `POST` | `/v1/decisions/{id}/human_response` | Resolve a deferred decision |
| `GET` | `/healthz` | Liveness probe — always `{"status": "ok"}` |
| `GET` | `/readyz` | Readiness probe — checks DB connectivity |
| `GET` | `/metrics` | Prometheus metrics |

---

## POST /v1/decisions/resolve

Arbitrate a decision and get a `Verdict` back.

```bash
curl -X POST http://localhost:8000/v1/decisions/resolve \
  -H "Authorization: Bearer secret" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Should we deploy to production?",
    "agents": [
      {"id": "a1", "name": "GPT-4o", "weight": 1.0},
      {"id": "a2", "name": "Claude",  "weight": 1.5}
    ],
    "proposals": [
      {"agent_id": "a1", "id": "p1", "content": "Deploy now",     "confidence": 0.9},
      {"agent_id": "a2", "id": "p2", "content": "Wait for tests", "confidence": 0.8}
    ]
  }'
```

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `question` | string | yes | The question being arbitrated |
| `proposals` | array | yes | List of proposals (see below) |
| `agents` | array | no | Agent metadata. Inferred from proposals if omitted |
| `context` | object | no | Free-form context passed to the strategy |

**Proposal fields:**

| Field | Type | Default | Description |
|---|---|---|---|
| `agent_id` | string | — | ID of the submitting agent |
| `content` | string \| object | — | The proposal content |
| `confidence` | float | `1.0` | Confidence score 0–1 |
| `id` | string | auto | Proposal ID (UUID generated if omitted) |
| `evidence` | array | `[]` | Evidence items |

---

## POST /v1/decisions/{id}/human_response

Resolve a decision that was deferred by `DeferToHuman`.

```bash
curl -X POST http://localhost:8000/v1/decisions/DECISION_ID/human_response \
  -H "Authorization: Bearer secret" \
  -H "Content-Type: application/json" \
  -d '{
    "winner_proposal_id": "p2",
    "rationale": "Reviewed with the team — safer to wait for test results.",
    "operator_id": "alice"
  }'
```

Returns the resolved `Verdict` with `status: resolved`.

**Error codes:**

- `404` — no deferred decision found for this ID
- `409` — decision was already resolved

---

## GET /v1/decisions/{id}/audit

Query audit events for a specific decision.

```bash
curl "http://localhost:8000/v1/decisions/DECISION_ID/audit?limit=50" \
  -H "Authorization: Bearer secret"
```

Query parameters: `event_type`, `since` (ISO 8601), `until` (ISO 8601), `limit` (default 100).

---

## Authentication

Set `SAALIS_BEARER_TOKEN` to enable token auth. All requests (except `/healthz`, `/readyz`, `/metrics`) must include:

```
Authorization: Bearer <your-token>
```

If `SAALIS_BEARER_TOKEN` is empty (the default), authentication is disabled — useful for local development.

---

## Prometheus metrics

The `/metrics` endpoint exposes three counters/histograms:

| Metric | Type | Labels |
|---|---|---|
| `saalis_arbitrations_total` | Counter | `strategy`, `status` |
| `saalis_arbitration_duration_seconds` | Histogram | — |
| `saalis_audit_append_failures_total` | Counter | — |

---

## Configuration (env vars)

| Variable | Default | Description |
|---|---|---|
| `SAALIS_STRATEGY` | `weighted_vote` | `weighted_vote` \| `llm_judge` \| `defer_to_human` |
| `SAALIS_AUDIT_PATH` | `./saalis_audit.db` | Path to SQLite audit file |
| `SAALIS_BEARER_TOKEN` | `""` | Static auth token — empty disables auth |
| `SAALIS_LLM_MODEL` | `gpt-4o` | Model for `LLMJudge` |
| `SAALIS_LLM_BASE_URL` | `""` | OpenAI-compatible base URL override |
| `SAALIS_LLM_API_KEY` | `""` | Falls back to `OPENAI_API_KEY` env var |
| `SAALIS_MIN_CONFIDENCE` | `""` | Float threshold for `MinConfidenceRule` |
| `SAALIS_BLOCKLIST_AGENTS` | `""` | Comma-separated blocked agent IDs |
