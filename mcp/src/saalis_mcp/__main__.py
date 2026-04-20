"""Entry point: python -m saalis_mcp"""
from __future__ import annotations

import asyncio

from saalis_mcp.settings import Settings
from saalis_mcp.state import build_state


async def _run_stdio(settings: Settings) -> None:
    from mcp.server.stdio import stdio_server

    from saalis_mcp.server import init_server

    state = build_state(settings)
    mcp = init_server(state)
    async with stdio_server() as (read_stream, write_stream):
        await mcp.run(
            read_stream,
            write_stream,
            mcp.create_initialization_options(),
        )
    await state.audit_store.close()


async def _run_http(settings: Settings) -> None:
    import uvicorn
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.routing import Mount, Route

    from saalis_mcp.server import init_server

    state = build_state(settings)
    mcp = init_server(state)
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        async with sse.connect_sse(
            request.scope, request.receive, request._send  # type: ignore[attr-defined]
        ) as (read_stream, write_stream):
            await mcp.run(
                read_stream,
                write_stream,
                mcp.create_initialization_options(),
            )

    starlette_app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ]
    )

    config = uvicorn.Config(
        starlette_app,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
    server_instance = uvicorn.Server(config)
    await server_instance.serve()
    await state.audit_store.close()


def main() -> None:
    settings = Settings()
    if settings.transport.lower() == "http":
        asyncio.run(_run_http(settings))
    else:
        asyncio.run(_run_stdio(settings))


if __name__ == "__main__":
    main()
