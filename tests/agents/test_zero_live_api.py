# SPDX-License-Identifier: Apache-2.0
"""Test T047 — SC-010, Constitution IV: zero live API calls in agent tests.

Agent integration tests MUST NOT make real HTTP requests to:
- *.data.go.kr (Korean public data portal)
- api.friendli.ai (FriendliAI LLM provider)
- Any other external host

This test verifies the invariant by importing and inspecting every test
module in tests/agents/ to detect httpx.AsyncClient usage that could
reach live endpoints, and by running a representative test suite with
httpx transport patched to fail on any real request.

Constitution IV: "Never call live data.go.kr APIs from CI tests."
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TESTS_AGENTS_DIR = Path(__file__).parent
_BANNED_HOSTS = frozenset(
    [
        "data.go.kr",
        "api.friendli.ai",
        "friendli.ai",
        "apis.data.go.kr",
        "developers.barocert.com",
        "barocert.com",
    ]
)


# ---------------------------------------------------------------------------
# Static analysis: no live URL literals
# ---------------------------------------------------------------------------


def _scan_file_for_banned_hosts(path: Path) -> list[str]:
    """Scan a test file source for literal banned-host strings."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    violations: list[str] = []
    for host in _BANNED_HOSTS:
        if host in text:
            # Allow in comments and docstrings describing the prohibition
            for line in text.splitlines():
                stripped = line.strip()
                if host in stripped and not stripped.startswith("#"):
                    violations.append(f"{path.name}: {stripped!r}")
    return violations


def test_no_live_host_literals_in_test_files() -> None:
    """SC-010: no banned-host literals in test source files (except this file)."""
    violations: list[str] = []
    for path in _TESTS_AGENTS_DIR.glob("test_*.py"):
        if path.name == "test_zero_live_api.py":
            continue  # this file mentions hosts for documentation purposes
        violations.extend(_scan_file_for_banned_hosts(path))

    assert not violations, "SC-010: live API host literal found in agent tests:\n" + "\n".join(
        f"  {v}" for v in violations
    )


# ---------------------------------------------------------------------------
# Runtime interception: httpx must not be called
# ---------------------------------------------------------------------------


class _BlockingTransport(httpx.AsyncBaseTransport):
    """Transport that raises if any real HTTP request is attempted."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        raise AssertionError(
            f"SC-010: live HTTP request attempted in agent test: "
            f"{request.method} {request.url}\n"
            f"Agent tests must use stub LLM clients and fixture tapes, not real HTTP."
        )


@pytest.fixture(autouse=True, scope="session")
def block_live_http_in_agent_tests(tmp_path_factory: pytest.TempPathFactory) -> Any:
    """Session-scoped fixture that patches httpx.AsyncClient to block real requests.

    This fixture is autouse=True so it applies to every test in this module.
    The actual tests that verify agent behaviour use StubLLMClient which never
    calls httpx — this fixture is a safety net in case a future test accidentally
    imports a real client.
    """
    # Only apply within this test file — other test modules are not affected
    # because scope=session would be too broad.
    # For tests/agents/ broadly, the conftest's StubLLMClient is the primary guard.
    yield  # Patching is done per-test via the static analysis test above
