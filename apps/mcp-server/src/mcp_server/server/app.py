"""Stateless MCP stdio server forwarding tool calls to the core service (ADR-041)."""

import json
import sys
from pathlib import Path
from typing import Any

from mcp_server.client import CorePipeClient


class McpServer:
    """Lightweight MCP server delegating tool operations to the CoreService pipe."""

    def __init__(
        self,
        client: CorePipeClient | None = None,
        *,
        pipe_name: str | None = None,
        token: str | None = None,
        session_file: Path | str | None = None,
    ) -> None:
        self._client = (
            client
            if client is not None
            else CorePipeClient(
                pipe_name=pipe_name,
                token=token,
                session_file=session_file,
            )
        )

    def connect(self, timeout_s: float = 5.0) -> None:
        self._client.connect(timeout_s=timeout_s)

    def close(self) -> None:
        self._client.close()

    def handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        msg_id = message.get("id")
        method = message.get("method")
        params = message.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "sw-mcp", "version": "0.1.0"},
                },
            }

        if method == "notifications/initialized":
            return None

        if method == "tools/list":
            tools = self._client.list_tools()
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": tools},
            }

        if method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            envelope = self._client.call_tool(tool_name, tool_args)
            is_error = not envelope.get("ok", False)
            content = [
                {
                    "type": "text",
                    "text": json.dumps(envelope),
                }
            ]
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": content,
                    "isError": is_error,
                },
            }

        if msg_id is not None:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method {method} not found",
                },
            }
        return None

    def run_stdio(self) -> None:
        """Run stdio loop reading from sys.stdin and writing to sys.stdout."""
        self.connect()
        try:
            for raw_line in sys.stdin:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except Exception:
                    continue
                res = self.handle_message(msg)
                if res is not None:
                    sys.stdout.write(json.dumps(res) + "\n")
                    sys.stdout.flush()
        finally:
            self.close()


def main() -> None:
    server = McpServer()
    server.run_stdio()


if __name__ == "__main__":
    main()
