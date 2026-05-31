# SPDX-License-Identifier: Apache-2.0
"""P1-4 doc-drift regression test — UMMAYA_K_EXAONE_THINKING default consistency.

Verifies that every canonical document that mentions ``UMMAYA_K_EXAONE_THINKING``
records the correct production default value (``false``, matching the
implementation in ``src/ummaya/llm/client.py``).

If this test fails it means a doc was updated with the stale "default true"
description.  Fix by updating the doc to say "default ``false``".

References:
- Runtime packaging rule: default user-visible answers MUST arrive on ``delta.content``
- src/ummaya/llm/client.py:973 — canonical implementation source of truth
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

# Root of the UMMAYA repository — resolved relative to this test file.
_REPO_ROOT = Path(__file__).parent.parent.parent

# Documents that must state "default `false`" (not "default `true`") for
# UMMAYA_K_EXAONE_THINKING.  Only include canonical policy/L1-A docs, not
# historical research/audit specs.  Local agent instruction files such as
# AGENTS.md and CLAUDE.md are intentionally untracked and ignored.
_CANONICAL_DOCS = [
    _REPO_ROOT / "README.md",
    _REPO_ROOT / "docs" / "configuration.md",
]

# Pattern that matches an occurrence of "UMMAYA_K_EXAONE_THINKING" alongside
# either "default `true`" or "default true" (stale phrasing to detect).
_STALE_PATTERN = re.compile(
    r"UMMAYA_K_EXAONE_THINKING[^\n]*default\s+`?true`?",
    re.IGNORECASE,
)

# Pattern confirming the correct phrasing is present in a doc.
_CORRECT_PATTERN = re.compile(
    r"UMMAYA_K_EXAONE_THINKING[^\n]*default\s+`?false`?",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Implementation source-of-truth check
# ---------------------------------------------------------------------------


def test_implementation_default_is_false() -> None:
    """The resolver must keep default provider thinking disabled."""
    from ummaya.llm.reasoning import resolve_reasoning_policy

    policy = resolve_reasoning_policy(env={})

    assert policy.mode == "balanced"
    assert policy.enable_thinking is False
    assert policy.include_reasoning is False


# ---------------------------------------------------------------------------
# Canonical doc consistency
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("doc_path", _CANONICAL_DOCS, ids=lambda p: p.name)
def test_doc_does_not_contain_stale_true_default(doc_path: Path) -> None:
    """No canonical doc should say 'UMMAYA_K_EXAONE_THINKING ... default true'."""
    if not doc_path.exists():
        pytest.skip(f"Doc file not present: {doc_path}")

    content = doc_path.read_text(encoding="utf-8")

    # Skip docs that don't mention the env var at all — nothing to check.
    if "UMMAYA_K_EXAONE_THINKING" not in content:
        return

    matches = _STALE_PATTERN.findall(content)
    assert not matches, (
        f"Found stale 'default true' phrasing for UMMAYA_K_EXAONE_THINKING in "
        f"{doc_path.relative_to(_REPO_ROOT)}:\n"
        + "\n".join(f"  - {m!r}" for m in matches)
        + "\nFix: change 'default `true`' to 'default `false`' in the doc."
    )


@pytest.mark.parametrize("doc_path", [_REPO_ROOT / "README.md"], ids=lambda p: p.name)
def test_canonical_l1a_docs_state_false_default(doc_path: Path) -> None:
    """Tracked L1-A docs must explicitly state 'default false' for the env var."""
    assert doc_path.exists(), f"Expected {doc_path} to exist"

    content = doc_path.read_text(encoding="utf-8")

    if "UMMAYA_K_EXAONE_THINKING" not in content:
        pytest.fail(f"{doc_path.name} must mention UMMAYA_K_EXAONE_THINKING (L1-A canonical doc).")

    matches = _CORRECT_PATTERN.findall(content)
    assert matches, (
        f"{doc_path.relative_to(_REPO_ROOT)} must contain 'default false' for "
        f"UMMAYA_K_EXAONE_THINKING.\nContent lines mentioning the env var:\n"
        + "\n".join(
            f"  {i + 1}: {line}"
            for i, line in enumerate(content.splitlines())
            if "UMMAYA_K_EXAONE_THINKING" in line
        )
    )
