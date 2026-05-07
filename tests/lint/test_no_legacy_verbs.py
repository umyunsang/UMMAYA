# SPDX-License-Identifier: Apache-2.0
"""T082 — Lint test: no legacy top-level verb registrations remain.

Spec 031 / AGENTS.md feedback_main_verb_primitive: the six legacy verb names
listed below MUST NOT appear as registered top-level tool_id values anywhere
under src/kosmos/primitives/ or src/kosmos/tools/ or in adapter registrations.

The failure criterion is a *registration* call with a matching tool_id:
  - AdapterRegistration(tool_id="pay", ...)
  - register_submit_adapter(registration=AdapterRegistration(tool_id="pay", ...))
  - or any pattern: tool_id = "pay" / tool_id="pay" at the registration site

String occurrences inside pure docstrings or comments are NOT a violation and
are expressly tolerated (e.g., audit.py documents the pruned set in a comment).

Legacy verb ban list (T080 pruning, Phase 8):
  check_eligibility, reserve_slot, subscribe_alert,
  pay, issue_certificate, submit_application
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parents[2]

_SCAN_ROOTS: list[Path] = [
    _REPO_ROOT / "src" / "kosmos" / "primitives",
    _REPO_ROOT / "src" / "kosmos" / "tools",
]

_BANNED_VERBS: frozenset[str] = frozenset(
    {
        "check_eligibility",
        "reserve_slot",
        "subscribe_alert",
        "pay",
        "issue_certificate",
        "submit_application",
    }
)

# Matches assignment or kwarg patterns like:
#   tool_id="pay"
#   tool_id = 'pay'
#   tool_id=  "pay"
# Captures the verb in group 1 so we can filter to banned set.
_REGISTRATION_PATTERN: re.Pattern[str] = re.compile(r"""tool_id\s*=\s*['"]([a-z_]+)['"]""")


def _is_comment_or_docstring_line(line: str) -> bool:
    """Return True if the line is a pure comment or clearly inside a docstring."""
    stripped = line.strip()
    # Pure comment lines (start with #)
    if stripped.startswith("#"):
        return True
    # Lines that are only a string literal (docstring body / standalone string)
    return bool(stripped.startswith(('"', "'")) and not re.search(r"tool_id\s*=", stripped))


def _collect_violations() -> list[tuple[str, int, str]]:
    """Return (relative_path, line_number, matched_verb) for each violation."""
    violations: list[tuple[str, int, str]] = []

    for root in _SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, PermissionError):
                continue

            for lineno, line in enumerate(lines, start=1):
                # Skip comment-only lines — docstring mentions are allowed
                if _is_comment_or_docstring_line(line):
                    continue
                for match in _REGISTRATION_PATTERN.finditer(line):
                    verb = match.group(1)
                    if verb in _BANNED_VERBS:
                        rel = path.relative_to(_REPO_ROOT)
                        violations.append((str(rel), lineno, verb))

    return violations


_VIOLATIONS = _collect_violations()


@pytest.mark.skipif(
    not _VIOLATIONS,
    reason="No legacy verb registrations found — scan passed.",
)
@pytest.mark.parametrize("rel_path, lineno, verb", _VIOLATIONS)
def test_no_legacy_verb_registration(rel_path: str, lineno: int, verb: str) -> None:
    pytest.fail(
        f"Legacy verb registration detected: {rel_path!r} line {lineno} — "
        f"tool_id={verb!r} is a banned top-level verb (Spec 031 T080 pruning).\n"
        f"Replace with a primitive envelope call (lookup/submit/verify) "
        f"or remove the registration."
    )


def test_legacy_verb_scan_completed_without_violation() -> None:
    """Assert the legacy-verb scan found zero registration violations."""
    assert _VIOLATIONS == [], (
        f"Spec 031 SC: {len(_VIOLATIONS)} legacy verb registration(s) detected:\n"
        + "\n".join(f"  {p}:{ln} — tool_id={v!r}" for p, ln, v in _VIOLATIONS)
    )
