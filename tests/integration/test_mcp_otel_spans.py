# SPDX-License-Identifier: Apache-2.0
"""T040 — MCP bridge OTEL span attributes + SC-004 handshake timing assertion.

Per contracts/mcp-bridge.md § 4.3 + SC-004:
- ``ummaya.mcp.handshake_ms``: emitted on every initialize + initialized exchange.
  Cold-start budget: < 500 ms. Warm: < 100 ms.
- ``ummaya.mcp.tool_call_id``: emitted on every tools/call request.
- ``ummaya.mcp.protocol_version``: emitted on initialize response.

This test exercises ``ummaya.ipc.mcp_server.MCPServer`` in-process (no
subprocess) to verify the handler produces the correct response envelopes
and to MEASURE the handshake latency directly. The protocol-version + tool
list shape checks are the load-bearing parts; the timing assertions use
generous budgets (5x the SC-004 values) to avoid flakiness in CI — the real
budget is enforced by the integrated PR's manual ``bun run tui`` run (SC-007).

Full OTEL span emission instrumentation inside ``mcp_server.py`` is deferred
to a post-P3 follow-up (see spec.md Deferred Items): P3 asserts shape +
timing at the handler boundary; real OTEL span export into Langfuse (Spec
028 OTLP collector) is exercised by Spec 021 / Spec 028 integration tests.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from ummaya.ipc.mcp_server import (
    MCP_PROTOCOL_VERSION,
    MCPServer,
)
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.register_all import register_all_tools
from ummaya.tools.registry import ToolRegistry


@pytest.fixture(scope="module")
def mcp_server() -> MCPServer:
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    routing_index = register_all_tools(registry, executor)
    return MCPServer(registry, routing_index)


class TestMCPHandshake:
    """contracts/mcp-bridge.md § 2 — initialize handshake shape."""

    def test_initialize_returns_correct_protocol_version(self, mcp_server: MCPServer) -> None:
        response = asyncio.run(
            mcp_server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": MCP_PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "0"},
                    },
                }
            )
        )
        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["result"]["protocolVersion"] == MCP_PROTOCOL_VERSION
        assert response["result"]["capabilities"]["tools"]["listChanged"] is False
        assert response["result"]["serverInfo"]["name"] == "ummaya-backend"

    def test_initialized_notification_has_no_response(self, mcp_server: MCPServer) -> None:
        response = asyncio.run(
            mcp_server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
        )
        assert response is None


class TestMCPToolsListShape:
    """contracts/mcp-bridge.md § 2 + § 1 — closed tool surface."""

    def test_tools_list_returns_expected_registered_count(self, mcp_server: MCPServer) -> None:
        response = asyncio.run(
            mcp_server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        )
        assert response is not None
        tools = response["result"]["tools"]
        # Subscribe is deferred out of the active surface until UMMAYA owns an
        # app/push delivery runtime. The MCP tool list mirrors the active
        # registry: 69 tools after Spec #2798's 16-adapter live expansion plus
        # the explicit live MobileID check adapter.
        assert len(tools) == 69, f"Tool list count drift: got {len(tools)}, expected 69"

    def test_tools_list_entries_have_required_keys(self, mcp_server: MCPServer) -> None:
        response = asyncio.run(
            mcp_server.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}})
        )
        assert response is not None
        for tool in response["result"]["tools"]:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert isinstance(tool["inputSchema"], dict)


class TestMCPErrorHandling:
    """contracts/mcp-bridge.md § 3.4 — JSON-RPC 2.0 error envelope."""

    def test_unknown_method_returns_method_not_found(self, mcp_server: MCPServer) -> None:
        response = asyncio.run(
            mcp_server.handle({"jsonrpc": "2.0", "id": 4, "method": "unknown/method"})
        )
        assert response is not None
        assert response["error"]["code"] == -32601  # method not found

    def test_missing_method_returns_invalid_request(self, mcp_server: MCPServer) -> None:
        response = asyncio.run(mcp_server.handle({"jsonrpc": "2.0", "id": 5}))
        assert response is not None
        assert response["error"]["code"] == -32600  # invalid request


class TestSC004HandshakeLatencyBudget:
    """SC-004 — handshake < 500 ms cold / < 100 ms warm.

    Assertions here use a 5x safety margin to avoid CI flakiness; the real
    SC-004 budget is enforced by the integrated PR's manual bun run tui
    (SC-007) on a developer machine. See contracts/mcp-bridge.md § 2.2.
    """

    def test_handshake_under_cold_budget(self, mcp_server: MCPServer) -> None:
        start = time.perf_counter_ns()
        response = asyncio.run(
            mcp_server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 6,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": MCP_PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": {"name": "latency-test", "version": "0"},
                    },
                }
            )
        )
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
        assert response is not None
        # In-process call should be far faster than 500 ms (typically sub-millisecond);
        # the 2500 ms ceiling = 5x the SC-004 cold budget to absorb CI jitter.
        assert elapsed_ms < 2500, f"handshake took {elapsed_ms:.2f}ms (budget 2500ms)"

    def test_tools_list_under_warm_budget(self, mcp_server: MCPServer) -> None:
        start = time.perf_counter_ns()
        response = asyncio.run(
            mcp_server.handle({"jsonrpc": "2.0", "id": 7, "method": "tools/list", "params": {}})
        )
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
        assert response is not None
        # 500 ms ceiling = 5x the 100 ms warm budget.
        assert elapsed_ms < 500, f"tools/list took {elapsed_ms:.2f}ms (budget 500ms)"
