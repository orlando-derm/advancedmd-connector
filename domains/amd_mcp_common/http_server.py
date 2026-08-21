"""HTTP/SSE adapter for AMD MCP domain servers.

Wraps a built Server instance with Starlette + MCP SSE transport so
it can be served over HTTP instead of stdio. Intended for Coolify /
container deployments where a persistent HTTP listener is required.

Usage from a domain server's main_http():
    server = build_server(settings=s, login=True)
    serve_http(server, port=int(os.environ.get("AMD_MCP_PORT", "8801")))
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import uvicorn
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route

if TYPE_CHECKING:
    from mcp.server import Server


def _make_app(server: "Server") -> Starlette:
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(
                streams[0],
                streams[1],
                server.create_initialization_options(),
            )

    return Starlette(routes=[
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ])


def serve_http(
    server: "Server",
    *,
    port: int,
    host: str = "0.0.0.0",
    log_level: str = "info",
) -> None:
    """Start uvicorn serving the MCP server over SSE/HTTP."""
    uvicorn.run(_make_app(server), host=host, port=port, log_level=log_level)
