"""Stateless MCP stdio front-end on the official MCP SDK (ADR-034, ADR-041, ADR-044, 12.3)."""

import json
import sys
from typing import Any, cast

import anyio
from mcp import MCPError, types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from mcp_server.client import CorePipeClient, CorePipeError

INSTRUCTIONS = (
    "sw-mcp builds SOLIDWORKS parts from a Part Feature Graph (IR). To turn a user's request"
    " into a part: call get_authoring_guide first and follow it. If the request needs something"
    " the guide lists as unsupported, reply that you cannot fulfil it and say what is"
    " unsupported; never approximate it with something similar. Otherwise write the graph, call"
    " validate_part_graph until it is valid, tell the user what will be built, then call"
    " apply_part_graph and follow the job with get_execution_status."
)


def create_mcp_server(client: CorePipeClient) -> Server:
    """Create the low-level MCP server backed by ``client``."""

    async def _on_list_tools(
        _ctx: Any, _params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        raw_tools = await anyio.to_thread.run_sync(client.list_tools)
        tools: list[types.Tool] = []
        for item in raw_tools:
            raw_ann = item.get("annotations")
            annotations = (
                types.ToolAnnotations.model_validate(raw_ann) if isinstance(raw_ann, dict) else None
            )
            input_schema = item.get("inputSchema")
            output_schema = item.get("outputSchema")
            tools.append(
                types.Tool(
                    name=str(item["name"]),
                    description=str(item.get("description", "")),
                    input_schema=(
                        cast("dict[str, Any]", input_schema)
                        if isinstance(input_schema, dict)
                        else {"type": "object"}
                    ),
                    output_schema=(
                        cast("dict[str, Any]", output_schema)
                        if isinstance(output_schema, dict)
                        else None
                    ),
                    annotations=annotations,
                )
            )
        return types.ListToolsResult(tools=tools)

    async def _on_call_tool(_ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        arguments: dict[str, Any] = dict(params.arguments) if params.arguments is not None else {}
        try:
            raw = await anyio.to_thread.run_sync(client.call_tool, params.name, arguments)
        except CorePipeError as exc:
            raise MCPError(code=exc.code, message=exc.message, data=exc.data) from exc

        if "envelope" in raw and isinstance(raw["envelope"], dict):
            envelope = cast("dict[str, Any]", raw["envelope"])
            summary = str(raw.get("summary", ""))
        else:
            envelope = raw
            summary = json.dumps(envelope)

        is_error = not bool(envelope.get("ok", False))
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=summary)],
            structured_content=envelope,
            is_error=is_error,
        )

    return Server(
        name="sw-mcp",
        version="0.1.0",
        instructions=INSTRUCTIONS,
        on_list_tools=_on_list_tools,
        on_call_tool=_on_call_tool,
    )


async def _serve_stdio(client: CorePipeClient) -> None:
    server = create_mcp_server(client)
    init_options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, init_options)


def run_stdio_server(client: CorePipeClient | None = None) -> None:
    """Connect to the per-user core service and serve MCP over UTF-8 stdio."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")

    active_client = client if client is not None else CorePipeClient()
    active_client.connect()
    try:
        anyio.run(_serve_stdio, active_client)
    finally:
        active_client.close()


def main() -> None:
    run_stdio_server()


if __name__ == "__main__":
    main()
