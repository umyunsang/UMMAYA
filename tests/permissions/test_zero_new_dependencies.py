# SPDX-License-Identifier: Apache-2.0
"""SC-008 zero-deps gate — Spec 033 (Epic #1297) Task #11.

AGENTS.md hard rule: "Never add a dependency outside a spec-driven PR."
Spec 033 declares zero new runtime dependencies (plan.md §Technical Context,
spec.md §SC-008).  This test proves the rule at the source-tree level by
diffing the current ``[project].dependencies`` block against ``main``.

Strategy:
  * Parse ``pyproject.toml`` via stdlib ``tomllib`` (Python 3.11+).
  * Resolve the merge-base between ``HEAD`` and ``main``; read the historical
    ``pyproject.toml`` at that commit via ``git show`` (stdlib ``subprocess``).
  * Compare ``[project].dependencies`` sets.  Any **addition** is a SC-008
    regression.  Version pin *changes* are allowed (security pinning is
    explicitly permitted by AGENTS.md).
  * Optional dependencies (``[project.optional-dependencies].dev``) are
    excluded — dev-only tooling is not a runtime dep.

If the test runs outside a git worktree (e.g., tarball install) it is
skipped rather than failing; the CI worktree always has git.
"""

from __future__ import annotations

import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_SPEC_DRIVEN_RUNTIME_ADDITIONS = frozenset(
    {
        # Spec 2802 Public AX document harness promotes python-docx for
        # read-only DOCX inspection after fixture-backed gate evidence.
        "python-docx",
        # Spec 2802 promotes bounded OOXML/PDF runtime engines after
        # fixture-backed adapter, render/re-read, and Evidence Fabric gates.
        "defusedxml",
        "fonttools",
        "openpyxl",
        "pypdf",
        "pypdfium2",
        "python-pptx",
        # Spec 2802 promotes read-only legacy HWP inspection after
        # fixture-backed extraction evidence; write remains blocked.
        "unhwp",
        # Spec 2802 promotes bounded ODT/ODS/ODP writer support after
        # ODF standard, license, and local fixture evidence.
        "odfdo",
    }
)


def _git(*args: str) -> str:
    """Run a git command inside the repo root and return stdout (stripped)."""
    proc = subprocess.run(  # noqa: S603 — test-only, static argv, git on PATH
        ["git", *args],  # noqa: S607 — git resolved via PATH in CI/dev shells
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()!r}")
    return proc.stdout.strip()


def _canonical_name(dep: str) -> str:
    """Reduce a PEP 508 specifier to its normalized project name.

    Examples:
        ``'pydantic >= 2.13'``  → ``'pydantic'``
        ``'httpx[http2]>=0.27'`` → ``'httpx'``
    """
    name = dep.strip()
    for sep in ("[", ">=", "<=", "==", "~=", ">", "<", "!=", ";", " "):
        idx = name.find(sep)
        if idx >= 0:
            name = name[:idx]
    return name.lower()


def _load_deps_at(ref: str | None) -> set[str]:
    """Return the set of ``[project].dependencies`` project names.

    When ``ref`` is ``None``, read the working-tree ``pyproject.toml``.
    Otherwise ``git show <ref>:pyproject.toml`` is parsed.
    """
    if ref is None:
        raw = _PYPROJECT.read_bytes()
    else:
        raw = subprocess.run(  # noqa: S603 — test-only, static argv, git on PATH
            ["git", "show", f"{ref}:pyproject.toml"],  # noqa: S607 — git on PATH
            cwd=str(_REPO_ROOT),
            capture_output=True,
            check=True,
        ).stdout

    doc = tomllib.loads(raw.decode("utf-8"))
    project = doc.get("project", {})
    deps = project.get("dependencies", [])
    return {_canonical_name(d) for d in deps}


@pytest.fixture(scope="module")
def base_ref() -> str:
    """Resolve the base ref for the diff.

    Priority:
        1. ``UMMAYA_SC008_BASE_REF`` env var override (CI injection).
        2. ``origin/main`` if fetched.
        3. ``main`` local branch.
    """
    import os

    override = os.environ.get("UMMAYA_SC008_BASE_REF")
    if override:
        return override

    # Prefer origin/main (CI has it); fall back to local main.
    for candidate in ("origin/main", "main"):
        try:
            _git("rev-parse", "--verify", candidate)
            return candidate
        except RuntimeError:
            continue
    pytest.skip("No base ref available — skipping SC-008 gate (not a git worktree).")


def test_git_available() -> None:
    """Skip the suite cleanly when git is not on PATH (tarball install)."""
    if shutil.which("git") is None:
        pytest.skip("git binary not available — SC-008 gate skipped.")


def test_no_new_runtime_dependencies(base_ref: str) -> None:
    """Fail if Spec 033 added any new ``[project].dependencies`` entry.

    Allowed:
        * Pin tightening (e.g., ``httpx >= 0.27`` → ``httpx >= 0.28``).
        * Removing a dep (handled separately — this test only asserts no
          additions).
    Forbidden:
        * Any new project name appearing in ``dependencies`` that was absent
          on ``main``.
    """
    if shutil.which("git") is None:
        pytest.skip("git binary not available — SC-008 gate skipped.")

    current = _load_deps_at(None)
    try:
        baseline = _load_deps_at(base_ref)
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"Could not read pyproject.toml at {base_ref!r}: {exc}")

    added = current - baseline - _SPEC_DRIVEN_RUNTIME_ADDITIONS
    assert not added, (
        f"SC-008 regression: Spec 033 must not add runtime dependencies. "
        f"New entries found vs {base_ref!r}: {sorted(added)!r}.  "
        "AGENTS.md hard rule: 'Never add a dependency outside a spec-driven PR' "
        "— Spec 033 plan.md §Technical Context declares zero new dependencies. "
        "Spec-driven additions must be listed in this test with their owning "
        "spec and promotion evidence."
    )
