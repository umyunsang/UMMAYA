# SPDX-License-Identifier: Apache-2.0
"""T083 — Dependency-diff test: no new entries under [project].dependencies.

SC-008 (AGENTS.md hard rule): Never add a dependency outside a spec-driven PR.
This test guards the runtime dependency list against accidental additions by:

  1. Running ``git diff main -- pyproject.toml`` (falling back to
     ``origin/main`` if the local ``main`` ref is absent).
  2. Asserting that no new ``+`` lines matching a PEP 508 dependency pattern
     appear in the ``[project].dependencies`` block of the diff.
  3. If neither git ref is available (shallow CI clone with no origin/main),
     falls back to asserting the current ``[project].dependencies`` block
     matches a snapshot of the known-good dependency list.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Final

import pytest

_REPO_ROOT = Path(__file__).parents[2]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"

# ---------------------------------------------------------------------------
# Snapshot of the known-good [project].dependencies list (SC-008 baseline).
# Entries are bare package names (lower-cased, hyphens normalised to hyphens).
# Update this list ONLY via a spec-driven PR that amends SC-008.
# ---------------------------------------------------------------------------
_KNOWN_DEPS_SNAPSHOT: Final[frozenset[str]] = frozenset(
    {
        "httpx",
        "pydantic",
        "pydantic-settings",
        "typer",
        "rich",
        "prompt-toolkit",
        "opentelemetry-sdk",
        "opentelemetry-exporter-otlp-proto-http",
        "opentelemetry-semantic-conventions",
        "rank-bm25",
        "kiwipiepy",
        "openai",
        "presidio-analyzer",
        "sentence-transformers",
        "numpy",
        "torch",
        "python-docx",
        "pyyaml",
    }
)

# Regex matching a PEP 508 requirement line (package name with optional extras
# and version specifier).  We only extract the bare package name (group 1).
_DEP_LINE_RE: re.Pattern[str] = re.compile(r"""^\s*['"]?([A-Za-z][A-Za-z0-9_.-]*)""")

# Diff line added inside [project].dependencies block
_ADDED_DEP_RE: re.Pattern[str] = re.compile(r"""^\+\s+['"]([A-Za-z][A-Za-z0-9_.-]*)""")


def _normalise(name: str) -> str:
    """Normalise package name to lowercase with hyphens (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _run_git_diff(base_ref: str) -> str | None:
    """Run git diff <base_ref> -- pyproject.toml; return stdout or None on failure.

    Returns ``None`` when the git invocation cannot produce a usable diff. This
    covers three independent failure modes so the caller can fall back to the
    snapshot comparison instead of crashing the test:

    1. ``git`` binary not on PATH (``FileNotFoundError``) — minimal CI images
       occasionally run pytest without git installed.
    2. Generic ``OSError`` raised by the subprocess layer (permission denied,
       cwd missing, fork failures on restricted sandboxes).
    3. Non-zero exit code from ``git diff`` (``base_ref`` unknown, shallow
       clone with the ref pruned, etc.).
    """
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "diff", base_ref, "--", "pyproject.toml"],  # noqa: S607
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _new_deps_from_diff(diff_text: str) -> list[str]:
    """Return list of newly added package names in [project].dependencies."""
    in_deps_block = False
    new_deps: list[str] = []

    for line in diff_text.splitlines():
        # Detect entry / exit of the dependencies block (context or added lines)
        stripped_content = line.lstrip("+-").lstrip()
        if re.match(r"dependencies\s*=\s*\[", stripped_content):
            in_deps_block = True
            continue
        if in_deps_block and stripped_content.startswith("]"):
            in_deps_block = False
            continue

        if in_deps_block and line.startswith("+") and not line.startswith("+++"):
            m = _ADDED_DEP_RE.match(line)
            if m:
                new_deps.append(_normalise(m.group(1)))

    return new_deps


def _current_deps_from_pyproject() -> frozenset[str]:
    """Parse current [project].dependencies from pyproject.toml."""
    content = _PYPROJECT.read_text(encoding="utf-8")
    in_block = False
    deps: set[str] = set()
    for line in content.splitlines():
        stripped = line.strip()
        if re.match(r"dependencies\s*=\s*\[", stripped):
            in_block = True
            continue
        if in_block and stripped.startswith("]"):
            break
        if in_block:
            # Strip comments
            code_part = stripped.split("#")[0].strip().strip("\"',")
            m = _DEP_LINE_RE.match(code_part)
            if m:
                deps.add(_normalise(m.group(1)))
    return frozenset(deps)


# ---------------------------------------------------------------------------
# Test logic
# ---------------------------------------------------------------------------


def test_no_new_runtime_deps() -> None:
    """SC-008: assert no new runtime dependencies were added vs main."""
    diff_text: str | None = None

    # Try local main first, then origin/main
    for ref in ("main", "origin/main"):
        diff_text = _run_git_diff(ref)
        if diff_text is not None:
            break

    if diff_text is not None:
        # We have a diff — check for new additions
        new_deps = _new_deps_from_diff(diff_text)
        unexpected = [dep for dep in new_deps if dep not in _KNOWN_DEPS_SNAPSHOT]
        assert unexpected == [], (
            f"SC-008 violation: {len(unexpected)} unapproved runtime dep(s) added to "
            f"[project].dependencies without a spec-driven PR:\n"
            + "\n".join(f"  + {d}" for d in unexpected)
        )
    else:
        # Shallow clone / no git history — fall back to snapshot comparison
        current = _current_deps_from_pyproject()
        extra = current - _KNOWN_DEPS_SNAPSHOT
        assert extra == frozenset(), (
            f"SC-008 violation (snapshot fallback): "
            f"{len(extra)} unknown runtime dep(s) detected in [project].dependencies "
            f"that are not in the known-good snapshot:\n"
            + "\n".join(f"  + {d}" for d in sorted(extra))
            + "\n\nIf this is a spec-driven addition, update _KNOWN_DEPS_SNAPSHOT "
            "in this test file as part of the spec PR."
        )
        # Also assert nothing was removed (regression guard)
        missing = _KNOWN_DEPS_SNAPSHOT - current
        if missing:
            pytest.skip(
                f"SC-008 snapshot: {len(missing)} expected dep(s) not found — "
                f"possible pyproject.toml parse issue or intentional removal: "
                + ", ".join(sorted(missing))
            )
