# SPDX-License-Identifier: Apache-2.0
"""Mock backend entry point — Epic ε #2296 · T030.

A fully-functional KOSMOS backend process that boots the complete mock
registry (all 20 mock surfaces from Phases 4A/4B/4C plus the 12 live tools),
emits an ``AdapterManifestSyncFrame`` to stdout, and then runs the standard
JSONL stdio loop (same pattern as :mod:`kosmos.ipc.mcp_server`).

This module is the canonical target for ``KOSMOS_BACKEND_CMD`` during
smoke-testing and offline demos:

    KOSMOS_BACKEND_CMD="uv run python -m kosmos.ipc.demo.mock_backend" bun run tui

Design decisions (research.md Decision 5):
- Reuses the stdio loop from ``mcp_server._run_loop`` (DRY principle).
- Imports ``kosmos.tools.mock`` EXPLICITLY after ``register_all_tools()`` so
  that the mock __init__.py side-effects register all mock surfaces into the
  per-primitive sub-registries BEFORE ``emit_manifest()`` walks them.
- ALL logging goes to stderr.  stdout is RESERVED for JSONL frames.
- NOT a ``sleep 60`` stub — runs a real async stdio loop (Codex P1 PTY-coverage).

Entry point::

    uv run python -m kosmos.ipc.demo.mock_backend

Module docstring notes ``KOSMOS_BACKEND_CMD`` invocation so any reader of the
module knows immediately how to exercise it.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Latest manifest emit log — accessible from tests / quickstart § 7
# ---------------------------------------------------------------------------

_latest_manifest_log: dict[str, Any] = {}


def latest_manifest_emit_log() -> str:
    """Return JSON dump of the most recent AdapterManifestSyncFrame entries.

    Useful for the offline / no-LLM smoke path described in quickstart.md § 7.
    Empty dict if no manifest has been emitted yet.
    """
    import json  # noqa: PLC0415

    return json.dumps(_latest_manifest_log, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# JSON-RPC helpers (same constants as mcp_server.py)
# ---------------------------------------------------------------------------

JSONRPC_PARSE_ERROR = -32700
JSONRPC_INVALID_REQUEST = -32600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_INTERNAL_ERROR = -32603


def _error_response(rpc_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}


async def _read_line(stream: asyncio.StreamReader) -> str | None:
    """Read one newline-delimited line from stdin. Return None on EOF."""
    raw = await stream.readline()
    if not raw:
        return None
    return raw.decode("utf-8").rstrip("\n")


# ---------------------------------------------------------------------------
# Minimal JSON-RPC / MCP handler (mirrors mcp_server.MCPServer routing)
# ---------------------------------------------------------------------------


async def _handle(
    request: dict[str, Any], registry: Any, routing_index: Any
) -> dict[str, Any] | None:  # noqa: E501
    """Route a single JSON-RPC 2.0 request to the appropriate handler.

    Returns the response dict, or None for notifications (no response per JSON-RPC 2.0 § 4.1).
    """
    rpc_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {}) or {}

    if not isinstance(method, str):
        return _error_response(rpc_id, JSONRPC_INVALID_REQUEST, "method missing or not a string")

    try:
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "kosmos-mock-backend", "version": "0.1.0"},
                },
            }

        if method == "notifications/initialized":
            return None  # notification — no response

        if method == "tools/list":
            tools: list[dict[str, Any]] = []
            for tool_id, tool in registry._tools.items():
                tools.append(
                    {
                        "name": tool_id,
                        "description": (
                            tool.llm_description if tool.llm_description else tool.name_ko
                        ),
                        "inputSchema": tool.input_schema.model_json_schema(),
                    }
                )
            return {"jsonrpc": "2.0", "id": rpc_id, "result": {"tools": tools}}

        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {}) or {}
            if not isinstance(name, str):
                return _error_response(rpc_id, JSONRPC_INVALID_PARAMS, "tool name missing")
            if name not in registry._tools:
                return _error_response(rpc_id, JSONRPC_INVALID_PARAMS, f"tool_not_found: {name}")
            # Return a stub response for P0 — full dispatch wiring is Epic ε Phase 5 territory.
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "status": "mock_backend_stub",
                                    "note": (
                                        "mock_backend: tools/call dispatch. "
                                        "Use the Python in-process adapter invocations in tests."
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

        return _error_response(rpc_id, JSONRPC_METHOD_NOT_FOUND, f"method not found: {method}")

    except Exception as exc:  # noqa: BLE001
        logger.exception("mock_backend: unhandled handler exception for method %r", method)
        return _error_response(rpc_id, JSONRPC_INTERNAL_ERROR, str(exc))


# ---------------------------------------------------------------------------
# Main stdio loop
# ---------------------------------------------------------------------------


async def _run_loop(registry: Any, routing_index: Any) -> None:
    """Run the JSONL stdio event loop until stdin EOF."""
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)

    stdout = sys.stdout

    while True:
        line = await _read_line(reader)
        if line is None:
            logger.info("mock_backend: stdin EOF — exiting cleanly")
            return
        if not line.strip():
            continue
        response: dict[str, Any] | None
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = _error_response(None, JSONRPC_PARSE_ERROR, str(exc))
        else:
            response = await _handle(request, registry, routing_index)

        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    """Boot the full mock registry + emit manifest + run the stdio loop.

    Boot sequence:
    1. Configure stderr-only logging (stdout reserved for JSONL).
    2. Build ToolRegistry + ToolExecutor.
    3. Call ``register_all_tools()`` — registers the active LLM/core and adapter tools.
    4. Import ``kosmos.tools.mock`` — triggers __init__.py side-effects that register all
       verify and submit mock surfaces into their per-primitive sub-registries.
       Subscribe adapters are intentionally not imported until KOSMOS has an
       app/push delivery runtime. The 2 new lookup mocks (T028/T029) are
       already registered by register_all_tools(); their re-import is idempotent.
    5. Call ``emit_manifest()`` — emits AdapterManifestSyncFrame to stdout. TUI ingests
       this before any LLM turn (FR-015 gate).
    6. Enter _run_loop() — block on stdin for JSON-RPC 2.0 requests.
    """
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
    )

    from kosmos.ipc.adapter_manifest_emitter import emit_manifest  # noqa: PLC0415
    from kosmos.tools.executor import ToolExecutor  # noqa: PLC0415
    from kosmos.tools.register_all import register_all_tools  # noqa: PLC0415
    from kosmos.tools.registry import ToolRegistry  # noqa: PLC0415

    registry = ToolRegistry()
    executor = ToolExecutor(registry)

    # Step 3: Register live + MVP surface tools (14 tools -> 16 with T028/T029).
    routing_index = register_all_tools(registry, executor)

    # Step 4: Import kosmos.tools.mock to register all 20 mock surfaces.
    # This import is idempotent — the sub-registries guard against duplicate IDs.
    import kosmos.tools.mock  # noqa: F401, PLC0415

    mock_count = 0
    for tool_id in registry._tools:
        if "mock" in tool_id:
            mock_count += 1

    logger.info(
        "mock_backend: All %d tools registered (%d mock surfaces). Emitting AdapterManifestSyncFrame ...",  # noqa: E501
        len(registry._tools),
        mock_count,
    )

    # Step 5: Emit manifest to stdout (TUI ingests before LLM turn).
    emit_manifest(sys.stdout, registry)

    # Cache the manifest info for quickstart § 7 introspection.
    try:
        from kosmos.ipc.adapter_manifest_emitter import _build_entries  # noqa: PLC0415

        entries = _build_entries(registry)
        _latest_manifest_log["entry_count"] = len(entries)
        _latest_manifest_log["tool_ids"] = [e.tool_id for e in entries]
    except Exception as exc:  # noqa: BLE001 — diagnostic logging only
        logger.debug("mock_backend: manifest log capture skipped: %s", exc)

    logger.info("mock_backend: Listening on stdio.")

    # Step 6: Run the stdio event loop.
    await _run_loop(registry, routing_index)


def run_main() -> None:
    """Synchronous wrapper around main() for ``if __name__ == '__main__'`` entry."""
    asyncio.run(main())


if __name__ == "__main__":
    run_main()
