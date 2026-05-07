# SPDX-License-Identifier: Apache-2.0
"""stdio-MCP server stub for the KOSMOS tool surface (Spec 1634 FR-021).

This module exposes the active primitive surface (`lookup`, `submit`, `verify`)
plus the auxiliary tool set to an MCP-speaking client over
stdio. It implements a minimal JSON-RPC 2.0 + MCP protocol layer on top of
stdin/stdout; it intentionally does **not** re-implement any Spec 032
transport concern (framing, ring-buffer, backpressure, heartbeat) — those
live in :mod:`kosmos.ipc.stdio` and are reused by the main KOSMOS harness
pipe. This server is a separate subprocess that a TUI-side
:file:`tui/src/ipc/mcp.ts` client can spawn and connect to when it wants
to consume the KOSMOS tool registry via MCP.

Protocol coverage (per ``specs/1634-tool-system-wiring/contracts/mcp-bridge.md``):

- ``initialize`` handshake (§ 2)
- ``notifications/initialized`` (§ 2)
- ``tools/list`` (§ 2 + § 1 closed set)
- ``tools/call`` (§ 3)

Out of scope (per contract § 6):

- ``resources/*`` and ``prompts/*`` MCP capabilities — advertised as ``{}``
  in the ``initialize`` response. No commitment to add.

Failure surface (per contract § 2.3):

- Backend process exit during handshake → stdio EOF is detected by the
  client's ``bridge.ts``; this server simply exits (no server-side recovery).
- ``tools/list`` returns an empty list → the client MUST treat as a failure;
  this server never returns empty unless the registry is genuinely empty,
  which is caught earlier by :func:`kosmos.tools.register_all.register_all_tools`
  (boot fails with ``SystemExit(78)`` via ``build_routing_index()``).
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from typing import Any

from kosmos.ipc.adapter_manifest_emitter import emit_manifest
from kosmos.tools.executor import ToolExecutor
from kosmos.tools.register_all import register_all_tools
from kosmos.tools.registry import ToolRegistry
from kosmos.tools.routing_index import RoutingIndex

logger = logging.getLogger(__name__)

MCP_PROTOCOL_VERSION = "2025-06-18"
"""The MCP protocol version KOSMOS speaks. Bump in lockstep with ``mcp.ts``
behind a single ADR per plan.md § Principle I reference mapping."""

SERVER_NAME = "kosmos-backend"
SERVER_VERSION = "0.1.0"  # Epic #1634 P3 MVP

# ---------------------------------------------------------------------------
# JSON-RPC 2.0 error codes (per spec https://www.jsonrpc.org/specification)
# plus MCP-specific codes we use.
# ---------------------------------------------------------------------------
JSONRPC_PARSE_ERROR = -32700
JSONRPC_INVALID_REQUEST = -32600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_INTERNAL_ERROR = -32603


class MCPServer:
    """Thin MCP-over-stdio server backed by the KOSMOS tool registry."""

    def __init__(self, registry: ToolRegistry, routing_index: RoutingIndex) -> None:
        self._registry = registry
        self._routing_index = routing_index
        self._initialized = False
        self._handshake_start_ns: int | None = None
        self._handshake_complete_ns: int | None = None

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------
    async def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Route a single JSON-RPC 2.0 request to the right handler.

        Returns the response envelope, or None for notifications (which
        receive no response per JSON-RPC 2.0 § 4.1).
        """
        rpc_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {}) or {}

        if not isinstance(method, str):
            return _error_response(
                rpc_id,
                JSONRPC_INVALID_REQUEST,
                "method missing or not a string",
            )

        try:
            if method == "initialize":
                return self._initialize(rpc_id, params)
            if method == "notifications/initialized":
                self._initialized = True
                self._handshake_complete_ns = time.perf_counter_ns()
                return None  # notification — no response
            if method == "tools/list":
                return self._tools_list(rpc_id)
            if method == "tools/call":
                return await self._tools_call(rpc_id, params)
            return _error_response(rpc_id, JSONRPC_METHOD_NOT_FOUND, f"method not found: {method}")
        except Exception as exc:  # pragma: no cover — defensive
            logger.exception("Unhandled MCP handler exception for method %r", method)
            return _error_response(rpc_id, JSONRPC_INTERNAL_ERROR, str(exc))

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------
    def _initialize(self, rpc_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        self._handshake_start_ns = time.perf_counter_ns()
        client_version = params.get("protocolVersion")
        if client_version and client_version != MCP_PROTOCOL_VERSION:
            logger.warning(
                "MCP client protocolVersion=%r differs from server=%r",
                client_version,
                MCP_PROTOCOL_VERSION,
            )
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {"listChanged": False},
                    # resources/prompts advertised as empty per contract § 6
                },
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }

    def _tools_list(self, rpc_id: Any) -> dict[str, Any]:
        tools: list[dict[str, Any]] = []
        for tool_id, tool in self._registry._tools.items():
            tools.append(
                {
                    "name": tool_id,
                    "description": (tool.llm_description if tool.llm_description else tool.name_ko),
                    "inputSchema": tool.input_schema.model_json_schema(),
                }
            )
        return {"jsonrpc": "2.0", "id": rpc_id, "result": {"tools": tools}}

    async def _tools_call(self, rpc_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments", {}) or {}
        if not isinstance(name, str):
            return _error_response(rpc_id, JSONRPC_INVALID_PARAMS, "tool name missing")
        if name not in self._registry._tools:
            return _error_response(rpc_id, JSONRPC_INVALID_PARAMS, f"tool_not_found: {name}")

        # Tool-call dispatch: for P3 MVP we route through the existing
        # executor machinery. A full implementation would invoke the
        # primitive layer (kosmos.primitives.*) for submit/verify
        # and the Spec 022 lookup for lookup — but that wiring lives in
        # T028 (registry closure fan-in) and is exercised by T029's
        # integration test. This stub returns a structured placeholder
        # so the handshake + tools/list paths can be verified independently.
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "status": "stub",
                                "note": (
                                    "MCP tools/call dispatch stub; T028/T029 complete the "
                                    "primitive wiring."
                                ),
                                "echo": {"name": name, "arguments": arguments},
                            },
                            ensure_ascii=False,
                        ),
                    }
                ],
                "isError": False,
            },
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _error_response(rpc_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "error": {"code": code, "message": message},
    }


async def _read_line(stream: asyncio.StreamReader) -> str | None:
    """Read one JSON-encoded line from stdin; return None on EOF."""
    raw = await stream.readline()
    if not raw:
        return None
    return raw.decode("utf-8").rstrip("\n")


async def _run_loop(server: MCPServer) -> None:
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)

    stdout = sys.stdout

    while True:
        line = await _read_line(reader)
        if line is None:
            logger.info("stdin EOF — MCP server exiting cleanly")
            return
        if not line.strip():
            continue
        response: dict[str, Any] | None
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = _error_response(None, JSONRPC_PARSE_ERROR, str(exc))
        else:
            response = await server.handle(request)

        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()


async def main() -> None:
    """Entry point — build registry + routing index, then run the stdio loop."""
    logging.basicConfig(
        level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s"
    )
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    routing_index = register_all_tools(registry, executor)
    logger.info(
        "MCP server ready: %d tools across %d primitives",
        len(registry._tools),
        len(routing_index.by_primitive),
    )
    # Epic ε #2296 T008 — emit adapter manifest sync frame (FR-015).
    # First non-handshake frame; TUI ingests it before any LLM turn.
    emit_manifest(sys.stdout, registry)
    server = MCPServer(registry, routing_index)
    await _run_loop(server)


if __name__ == "__main__":
    asyncio.run(main())
