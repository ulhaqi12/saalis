# MCP Server

`saalis-mcp` exposes Saalis arbitration as native [Model Context Protocol](https://modelcontextprotocol.io) tools. Any Claude, GPT-4o, or Gemini agent running in an MCP-native orchestrator can call Saalis directly — no Python import or REST call required.

## Run

=== "stdio (Claude Desktop)"
    ```bash
    cd mcp
    SAALIS_MCP_STRATEGY=weighted_vote python -m saalis_mcp
    ```

=== "HTTP/SSE (server deployment)"
    ```bash
    SAALIS_MCP_TRANSPORT=http \
    SAALIS_MCP_PORT=3000 \
    python -m saalis_mcp
    ```

---

## Claude Desktop setup

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "saalis": {
      "command": "python",
      "args": ["-m", "saalis_mcp"],
      "cwd": "/path/to/saalis/mcp",
      "env": {
        "SAALIS_MCP_STRATEGY": "weighted_vote"
      }
    }
  }
}
```

Restart Claude Desktop. You'll see Saalis tools available in the tool list.

---

## Tools

### `saalis_arbitrate`

Submit a decision for arbitration. Returns a full `Verdict` as JSON.

**Inputs:**

| Field | Type | Required | Description |
|---|---|---|---|
| `question` | string | yes | The question to arbitrate |
| `proposals` | array | yes | Proposals — each needs `agent_id`, `content`, optional `confidence` |
| `agents` | array | no | Agent metadata with `id`, `name`, `weight` |
| `context` | object | no | Free-form context |

**Example (as an LLM tool call):**
```json
{
  "question": "Which database should we migrate to?",
  "proposals": [
    {"agent_id": "a1", "content": "PostgreSQL", "confidence": 0.9},
    {"agent_id": "a2", "content": "MySQL",      "confidence": 0.6}
  ],
  "agents": [
    {"id": "a1", "name": "Arch-Agent", "weight": 1.5},
    {"id": "a2", "name": "Dev-Agent",  "weight": 1.0}
  ]
}
```

---

### `saalis_get_verdict`

Retrieve a cached verdict by `decision_id`. Returns the verdict JSON or `null` if not found.

```json
{"decision_id": "9f8e7d..."}
```

!!! note
    The verdict cache is in-memory and resets when the server restarts. Use the audit store for persistent lookups.

---

### `saalis_audit_query`

Query audit events from the store.

| Field | Type | Description |
|---|---|---|
| `decision_id` | string | Filter events for a specific decision |
| `event_type` | string | One of the `AuditEventType` values |
| `since` | string | ISO 8601 datetime lower bound |
| `until` | string | ISO 8601 datetime upper bound |
| `limit` | integer | Max events to return (default 100) |

---

### `saalis_human_respond`

Resolve a `pending_human` decision. Returns the updated verdict.

| Field | Type | Required | Description |
|---|---|---|---|
| `decision_id` | string | yes | ID of the deferred decision |
| `winner_proposal_id` | string | yes | Which proposal wins |
| `rationale` | string | no | Human explanation |
| `operator_id` | string | no | Who resolved it (default `"human"`) |

**Errors:**

- Decision not found → raises `ValueError`
- Decision already resolved → raises `ValueError`

---

### `saalis_get_pending`

List all decisions currently awaiting human input. Returns an array of `{decision_id, deferred_at}` objects. Returns `[]` when none are pending.

---

## Resources

### `saalis://health`

Liveness check. Returns `{"status": "ok", "version": "0.2.0"}`.

### `saalis://decisions/{decision_id}/audit`

Full audit trail for a specific decision. Returns the same format as `saalis_audit_query` filtered to that decision.

---

## DeferToHuman flow over MCP

```
LLM calls saalis_arbitrate  →  status: pending_human
LLM calls saalis_get_pending →  [{decision_id: "..."}]
Human reviews ...
LLM calls saalis_human_respond → status: resolved
```

---

## Configuration (env vars)

| Variable | Default | Description |
|---|---|---|
| `SAALIS_MCP_TRANSPORT` | `stdio` | `stdio` \| `http` |
| `SAALIS_MCP_HOST` | `0.0.0.0` | Bind host for HTTP mode |
| `SAALIS_MCP_PORT` | `3000` | Port for HTTP/SSE mode |
| `SAALIS_MCP_STRATEGY` | `weighted_vote` | `weighted_vote` \| `llm_judge` \| `defer_to_human` |
| `SAALIS_MCP_AUDIT_PATH` | `./saalis_mcp_audit.db` | SQLite audit file path |
| `SAALIS_MCP_LLM_MODEL` | `gpt-4o` | Model for `LLMJudge` |
| `SAALIS_MCP_LLM_BASE_URL` | `""` | OpenAI-compatible base URL override |
| `SAALIS_MCP_LLM_API_KEY` | `""` | Falls back to `OPENAI_API_KEY` |
| `SAALIS_MCP_MIN_CONFIDENCE` | `""` | Float threshold for `MinConfidenceRule` |
| `SAALIS_MCP_BLOCKLIST_AGENTS` | `""` | Comma-separated blocked agent IDs |

---

## Running the demo

The `examples/mcp_demo.py` script calls all 5 tool handlers directly (no MCP client needed):

```bash
uv run --package saalis-mcp python examples/mcp_demo.py
```
