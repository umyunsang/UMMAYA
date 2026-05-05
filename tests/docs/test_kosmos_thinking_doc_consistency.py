# SPDX-License-Identifier: Apache-2.0
"""P1-4 doc-drift regression test — KOSMOS_K_EXAONE_THINKING default consistency.

Verifies that every canonical document that mentions ``KOSMOS_K_EXAONE_THINKING``
records the correct default value (``true``, matching Spec 2521 FR-010 and
the implementation in ``src/kosmos/llm/client.py``).

If this test fails it means a doc was updated with the stale "default false"
description.  Fix by updating the doc to say "default ``true``".

References:
- Spec 2521 FR-010: ``KOSMOS_K_EXAONE_THINKING`` env default MUST remain ``true``
- src/kosmos/llm/client.py:973 — canonical implementation source of truth
- AGENTS.md § L1-A (patched 2026-05-04)
- README.md § L1-A (patched 2026-05-04)
- docs/configuration.md (already correct)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Root of the KOSMOS repository — resolved relative to this test file.
_REPO_ROOT = Path(__file__).parent.parent.parent

# Documents that must state "default `true`" (not "default `false`") for
# KOSMOS_K_EXAONE_THINKING.  Only include canonical policy/L1-A docs, not
# historical research/audit specs.
_CANONICAL_DOCS = [
    _REPO_ROOT / "AGENTS.md",
    _REPO_ROOT / "README.md",
    _REPO_ROOT / "docs" / "configuration.md",
]

# Pattern that matches an occurrence of "KOSMOS_K_EXAONE_THINKING" alongside
# either "default `false`" or "default false" (stale phrasing to detect).
_STALE_PATTERN = re.compile(
    r"KOSMOS_K_EXAONE_THINKING[^\n]*default\s+`?false`?",
    re.IGNORECASE,
)

# Pattern confirming the correct phrasing is present in a doc.
_CORRECT_PATTERN = re.compile(
    r"KOSMOS_K_EXAONE_THINKING[^\n]*default\s+`?true`?",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Implementation source-of-truth check
# ---------------------------------------------------------------------------


def test_implementation_default_is_true() -> None:
    """src/kosmos/llm/client.py must hard-code default 'true' for the env var."""
    client_py = _REPO_ROOT / "src" / "kosmos" / "llm" / "client.py"
    assert client_py.exists(), f"Expected {client_py} to exist"

    content = client_py.read_text(encoding="utf-8")

    # The canonical implementation line:
    #   enable_thinking = os.environ.get("KOSMOS_K_EXAONE_THINKING", "true").lower() in (...)
    assert 'os.environ.get("KOSMOS_K_EXAONE_THINKING", "true")' in content, (
        f"client.py must use default='true' for KOSMOS_K_EXAONE_THINKING.\n"
        f"Searched in: {client_py}"
    )


# ---------------------------------------------------------------------------
# Canonical doc consistency
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("doc_path", _CANONICAL_DOCS, ids=lambda p: p.name)
def test_doc_does_not_contain_stale_false_default(doc_path: Path) -> None:
    """No canonical doc should say 'KOSMOS_K_EXAONE_THINKING ... default false'."""
    if not doc_path.exists():
        pytest.skip(f"Doc file not present: {doc_path}")

    content = doc_path.read_text(encoding="utf-8")

    # Skip docs that don't mention the env var at all — nothing to check.
    if "KOSMOS_K_EXAONE_THINKING" not in content:
        return

    matches = _STALE_PATTERN.findall(content)
    assert not matches, (
        f"Found stale 'default false' phrasing for KOSMOS_K_EXAONE_THINKING in "
        f"{doc_path.relative_to(_REPO_ROOT)}:\n"
        + "\n".join(f"  - {m!r}" for m in matches)
        + "\nFix: change 'default `false`' to 'default `true`' in the doc."
    )


@pytest.mark.parametrize("doc_path", [_REPO_ROOT / "AGENTS.md", _REPO_ROOT / "README.md"],
                         ids=lambda p: p.name)
def test_canonical_l1a_docs_state_true_default(doc_path: Path) -> None:
    """AGENTS.md and README.md must explicitly state 'default true' for the env var."""
    assert doc_path.exists(), f"Expected {doc_path} to exist"

    content = doc_path.read_text(encoding="utf-8")

    if "KOSMOS_K_EXAONE_THINKING" not in content:
        pytest.fail(
            f"{doc_path.name} must mention KOSMOS_K_EXAONE_THINKING (L1-A canonical doc)."
        )

    matches = _CORRECT_PATTERN.findall(content)
    assert matches, (
        f"{doc_path.relative_to(_REPO_ROOT)} must contain 'default true' for "
        f"KOSMOS_K_EXAONE_THINKING.\nContent lines mentioning the env var:\n"
        + "\n".join(
            f"  {i+1}: {line}"
            for i, line in enumerate(content.splitlines())
            if "KOSMOS_K_EXAONE_THINKING" in line
        )
    )
