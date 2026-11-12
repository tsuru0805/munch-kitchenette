"""The MCP face: the same tools, for any model client that speaks MCP over HTTP.

Mounted at /mcp by :func:`kitchenette.api.create_app`. Every tool accepts an
optional ``who``; without it the default role from the settings is used, so a
single-companion setup never has to mention it.

The tools are declared with their JSON schemas as written in
:mod:`kitchenette.tools`, and arguments are handed to the tool untouched: a
wrong argument is answered by the kitchen in its own words rather than by a
generic validation error.
"""
from __future__ import annotations

import anyio
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.transport_security import TransportSecuritySettings

from . import __version__, tools


def _result(res: tools.ToolResult) -> types.CallToolResult:
    structured = {"attachments": res.attachments} if res.attachments else None
    return types.CallToolResult(content=[types.TextContent(type="text", text=res.text)],
                                structuredContent=structured, isError=res.is_error)


def build() -> Server:
    """Create the MCP server. Tool wording is read from the active settings on each listing."""

    async def list_tools(ctx, params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[
            types.Tool(name=s["name"], description=s["description"], inputSchema=s["input_schema"])
            for s in tools.schemas()])

    async def call_tool(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
        res = await anyio.to_thread.run_sync(tools.call, params.name, dict(params.arguments or {}))
        return _result(res)

    return Server("kitchenette", version=__version__, on_list_tools=list_tools, on_call_tool=call_tool)


def asgi_app(server: Server):
    """The Streamable HTTP app serving /mcp. Host checking is left to whatever fronts the server
    (the bearer token is the access control), so it also works behind a tunnel or reverse proxy."""
    return server.streamable_http_app(
        streamable_http_path="/mcp",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))
