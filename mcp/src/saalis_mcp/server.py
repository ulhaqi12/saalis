from __future__ import annotations

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Resource, TextContent, Tool

from saalis_mcp.resources import handle_decision_audit, handle_health
from saalis_mcp.state import AppState
from saalis_mcp.tools import (
    handle_arbitrate,
    handle_audit_query,
    handle_get_pending,
    handle_get_verdict,
    handle_human_respond,
)

server: Server = Server("saalis")
_state: AppState  # set via init_server()


def init_server(state: AppState) -> Server:
    global _state
    _state = state
    return server


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="saalis_arbitrate",
            description="Submit a decision for arbitration. Returns a Verdict JSON.",
            inputSchema={
                "type": "object",
                "required": ["question", "proposals"],
                "properties": {
                    "question": {"type": "string", "description": "The question to arbitrate"},
                    "proposals": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["agent_id", "content"],
                            "properties": {
                                "id": {"type": "string"},
                                "agent_id": {"type": "string"},
                                "content": {"type": "string"},
                                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                                "evidence": {"type": "array", "items": {"type": "object"}},
                            },
                        },
                    },
                    "agents": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "name"],
                            "properties": {
                                "id": {"type": "string"},
                                "name": {"type": "string"},
                                "weight": {"type": "number", "minimum": 0},
                            },
                        },
                    },
                    "context": {"type": "object"},
                },
            },
        ),
        Tool(
            name="saalis_get_verdict",
            description="Get the verdict for a previously arbitrated decision by its ID.",
            inputSchema={
                "type": "object",
                "required": ["decision_id"],
                "properties": {
                    "decision_id": {"type": "string"},
                },
            },
        ),
        Tool(
            name="saalis_audit_query",
            description="Query audit events. Filter by decision_id, event_type, and time range.",
            inputSchema={
                "type": "object",
                "properties": {
                    "decision_id": {"type": "string"},
                    "event_type": {"type": "string"},
                    "since": {"type": "string", "description": "ISO 8601 datetime"},
                    "until": {"type": "string", "description": "ISO 8601 datetime"},
                    "limit": {"type": "integer", "default": 100},
                },
            },
        ),
        Tool(
            name="saalis_human_respond",
            description="Resolve a deferred (pending_human) decision with a human verdict.",
            inputSchema={
                "type": "object",
                "required": ["decision_id", "winner_proposal_id"],
                "properties": {
                    "decision_id": {"type": "string"},
                    "winner_proposal_id": {"type": "string"},
                    "rationale": {"type": "string"},
                    "operator_id": {"type": "string", "default": "human"},
                },
            },
        ),
        Tool(
            name="saalis_get_pending",
            description="List all unresolved deferred decisions waiting for human response.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:  # type: ignore[type-arg]
    match name:
        case "saalis_arbitrate":
            result = await handle_arbitrate(_state, arguments)
        case "saalis_get_verdict":
            result = await handle_get_verdict(_state, arguments)
        case "saalis_audit_query":
            result = await handle_audit_query(_state, arguments)
        case "saalis_human_respond":
            result = await handle_human_respond(_state, arguments)
        case "saalis_get_pending":
            result = await handle_get_pending(_state, arguments)
        case _:
            raise ValueError(f"Unknown tool: {name!r}")
    return [TextContent(type="text", text=result)]


@server.list_resources()
async def list_resources() -> list[Resource]:
    return [
        Resource(
            uri="saalis://health",  # type: ignore[arg-type]
            name="health",
            description="Liveness check — returns server status and version.",
            mimeType="application/json",
        ),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:  # type: ignore[override]
    uri_str = str(uri)
    if uri_str == "saalis://health":
        return await handle_health(_state)
    if uri_str.startswith("saalis://decisions/") and uri_str.endswith("/audit"):
        decision_id = uri_str.removeprefix("saalis://decisions/").removesuffix("/audit")
        return await handle_decision_audit(_state, decision_id)
    raise ValueError(f"Unknown resource URI: {uri_str!r}")


def get_initialization_options() -> InitializationOptions:
    return server.create_initialization_options()
