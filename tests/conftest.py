# SPDX-License-Identifier: Apache-2.0
"""Root test configuration — live marker skip logic and .env loading.

Ensures ``@pytest.mark.live`` tests are skipped by default and only run
when explicitly selected via ``pytest -m live``. Also loads ``.env`` from
the repository root into ``os.environ`` so tool adapters that read env
vars via ``os.environ.get()`` (e.g. Kakao, data.go.kr) see the same
configuration the CLI entry point sees.
"""

from __future__ import annotations

import re

import pytest

from ummaya._dotenv import load_repo_dotenv

load_repo_dotenv()


def _marker_selected(marker_name: str, expr: str) -> bool:
    """Return True if ``marker_name`` is affirmatively selected in ``-m expr``.

    Handles compound boolean marker expressions such as
    ``"live or live_embedder"`` or ``"live_embedder and slow"``.
    Ignores occurrences preceded by ``not`` so that ``"not live_embedder"``
    does NOT count as selecting the marker.

    Args:
        marker_name: Bare marker identifier (e.g. ``"live_embedder"``).
        expr: The raw ``-m`` expression as passed on the command line.

    Returns:
        True when ``marker_name`` appears as a selecting token.
    """
    if not expr.strip():
        return False
    pattern = re.compile(rf"\b{re.escape(marker_name)}\b")
    for match in pattern.finditer(expr):
        preceding = expr[: match.start()].rstrip()
        # Treat as negated iff 'not' is the token immediately before the match.
        if not re.search(r"\bnot\Z", preceding):
            return True
    return False


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip live-marked tests unless the corresponding marker is explicitly selected.

    Skips:
    - ``@pytest.mark.live``: requires explicit ``-m live``.
    - ``@pytest.mark.live_embedder``: requires explicit ``-m live_embedder``
      (downloads/uses HF model weights — NFR-NoNetAtRuntime, spec 026 T024).

    Compound expressions like ``-m "live or live_embedder"`` are supported.
    """
    marker_expr = str(config.getoption("-m", default=""))

    # ``live`` family
    if not _marker_selected("live", marker_expr):
        skip_live = pytest.mark.skip(reason="live tests require -m live")
        for item in items:
            if item.get_closest_marker("live") is not None:
                item.add_marker(skip_live)

    # ``live_embedder`` family (spec 026, NFR-NoNetAtRuntime)
    if not _marker_selected("live_embedder", marker_expr):
        skip_embedder = pytest.mark.skip(
            reason="live_embedder tests require -m live_embedder (downloads HF weights)"
        )
        for item in items:
            if item.get_closest_marker("live_embedder") is not None:
                item.add_marker(skip_embedder)
