# SPDX-License-Identifier: Apache-2.0
"""T056 — Spec 032 SC-008 lint gate: no new runtime dependencies.

Extends the Spec 031 ``tests/lint/test_no_new_runtime_deps.py`` pattern to
cover **both** sides of the IPC bridge:

1. ``pyproject.toml`` — Python backend (``[project].dependencies``)
2. ``tui/package.json`` — TypeScript TUI (``dependencies`` only; devDeps
   are out of scope because they do not ship with the runtime binary).

The lint is run as a git diff against ``main`` (fallback ``origin/main``)
and, when no git ref is available, falls back to a snapshot comparison.
Snapshot values MUST only be edited as part of a spec-driven PR that
updates SC-008 (AGENTS.md hard rule).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Final

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_TUI_PACKAGE_JSON = _REPO_ROOT / "tui" / "package.json"

# ---------------------------------------------------------------------------
# Snapshots — known-good runtime dependency lists at the Spec 032 baseline.
# Update ONLY via a spec-driven PR that amends SC-008.
# ---------------------------------------------------------------------------

_PY_DEPS_SNAPSHOT: Final[frozenset[str]] = frozenset(
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

_TUI_DEPS_SNAPSHOT: Final[frozenset[str]] = frozenset(
    {
        # Epic #1632 P0 baseline — CC 2.1.88 port brings the full CC
        # runtime dep set into tui/package.json. Each addition is tracked
        # in specs/1632-baseline-runnable/spec.md FR-001 and covered by
        # spec-driven review (updating this snapshot is the spec step).
        # Epic #1633 dead-code-elimination may remove several after the
        # Anthropic-only paths are deleted.
        "@alcalzone/ansi-tokenize",
        "@anthropic-ai/claude-agent-sdk",
        "@anthropic-ai/mcpb",
        "@anthropic-ai/sandbox-runtime",
        "@anthropic-ai/sdk",
        "@aws-sdk/client-bedrock-runtime",
        "@commander-js/extra-typings",
        "@growthbook/growthbook",
        "@inkjs/ui",
        "@modelcontextprotocol/sdk",
        "@opentelemetry/api",
        "@opentelemetry/api-logs",
        "@opentelemetry/core",
        "@opentelemetry/resources",
        "@opentelemetry/sdk-logs",
        "@opentelemetry/sdk-metrics",
        "@opentelemetry/sdk-trace-base",
        # Spec 2637 (Epic A) — instrumentation.ts byte-copy PORT (CC 825 LOC)
        # dynamic-imports OTLP/gRPC exporters. plan.md Technical Context +
        # research.md D1 cite. AGENTS.md hard rule "spec-driven PR" satisfied.
        "@opentelemetry/semantic-conventions",
        "@opentelemetry/exporter-trace-otlp-http",
        "@opentelemetry/exporter-trace-otlp-grpc",
        "@opentelemetry/exporter-logs-otlp-http",
        "@opentelemetry/exporter-logs-otlp-grpc",
        "@opentelemetry/exporter-metrics-otlp-http",
        "@opentelemetry/exporter-metrics-otlp-grpc",
        # Codex P1 review fix on PR #2660 — http/protobuf branch (instrumentation.ts L185)
        # dynamic-imports the *-otlp-proto variants. Added in same spec-driven PR.
        "@opentelemetry/exporter-trace-otlp-proto",
        "@opentelemetry/exporter-logs-otlp-proto",
        "@opentelemetry/exporter-metrics-otlp-proto",
        "@grpc/grpc-js",
        "ajv",
        "asciichart",
        "auto-bind",
        "axios",
        "bidi-js",
        # PR #3040 — CC restored source parity for bun:bundle feature gates.
        "bundle",
        "chalk",
        "chokidar",
        "cli-boxes",
        "code-excerpt",
        "color-diff-napi",
        "diff",
        "env-paths",
        "execa",
        "fuse.js",
        "google-auth-library",
        "highlight.js",
        "https-proxy-agent",
        "ignore",
        "ink",
        "jsonc-parser",
        "lodash-es",
        "lru-cache",
        "marked",
        "p-map",
        # Spec 1635 P4 UI L2 — FR-010 inline PDF preview (Apache-2.0, WASM)
        "pdf-to-img",
        # Spec 1635 P4 UI L2 — FR-032 /export PDF assembly (MIT)
        "pdf-lib",
        # Spec audit-prod — Korean PDF export embeds a bundled Hangul font via pdf-lib.
        "@pdf-lib/fontkit",
        "proper-lockfile",
        "qrcode",
        "react",
        # PR #3040 — CC restored Ink renderer depends on react-reconciler.
        "react-reconciler",
        "semver",
        "shell-quote",
        "supports-hyperlinks",
        "tree-kill",
        "undici",
        "usehooks-ts",
        "vscode-languageserver-protocol",
        "xss",
        "yaml",
        "zod",
    }
)

# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

_DEP_LINE_RE: re.Pattern[str] = re.compile(r"""^\s*['"]?([A-Za-z][A-Za-z0-9_.-]*)""")
_ADDED_PY_DEP_RE: re.Pattern[str] = re.compile(r"""^\+\s+['"]([A-Za-z][A-Za-z0-9_.-]*)""")
_ADDED_TUI_DEP_RE: re.Pattern[str] = re.compile(r"""^\+\s+"(@?[A-Za-z][A-Za-z0-9_./-]*)"\s*:""")


def _normalise(name: str) -> str:
    """Normalise package name to lowercase with hyphens (PEP 503 for Python)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _run_git_diff(base_ref: str, path: Path) -> str | None:
    """Run ``git diff <base_ref> -- <path>``; return stdout or None on failure."""
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "diff", base_ref, "--", str(path.relative_to(_REPO_ROOT))],  # noqa: S607
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _best_effort_diff(path: Path) -> str | None:
    for ref in ("main", "origin/main"):
        diff = _run_git_diff(ref, path)
        if diff is not None:
            return diff
    return None


# ---------------------------------------------------------------------------
# Python side — [project].dependencies
# ---------------------------------------------------------------------------


def _new_py_deps_from_diff(diff_text: str) -> list[str]:
    in_deps_block = False
    new_deps: list[str] = []
    for line in diff_text.splitlines():
        stripped = line.lstrip("+-").lstrip()
        if re.match(r"dependencies\s*=\s*\[", stripped):
            in_deps_block = True
            continue
        if in_deps_block and stripped.startswith("]"):
            in_deps_block = False
            continue
        if in_deps_block and line.startswith("+") and not line.startswith("+++"):
            m = _ADDED_PY_DEP_RE.match(line)
            if m:
                new_deps.append(_normalise(m.group(1)))
    return new_deps


def _current_py_deps() -> frozenset[str]:
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
            code_part = stripped.split("#")[0].strip().strip("\"',")
            m = _DEP_LINE_RE.match(code_part)
            if m:
                deps.add(_normalise(m.group(1)))
    return frozenset(deps)


def test_no_new_python_runtime_deps() -> None:
    """SC-008 (Python side): no new entries in pyproject.toml [project].dependencies."""
    diff_text = _best_effort_diff(_PYPROJECT)
    if diff_text is not None:
        new_deps = _new_py_deps_from_diff(diff_text)
        unexpected = [dep for dep in new_deps if dep not in _PY_DEPS_SNAPSHOT]
        assert unexpected == [], (
            f"SC-008 violation (Python): {len(unexpected)} unapproved runtime dep(s) added:\n"
            + "\n".join(f"  + {d}" for d in unexpected)
        )
        return

    current = _current_py_deps()
    extra = current - _PY_DEPS_SNAPSHOT
    assert extra == frozenset(), (
        f"SC-008 violation (Python snapshot): {len(extra)} unknown dep(s):\n"
        + "\n".join(f"  + {d}" for d in sorted(extra))
    )
    missing = _PY_DEPS_SNAPSHOT - current
    if missing:
        pytest.skip(
            f"SC-008 snapshot drift: {len(missing)} expected dep(s) not found — "
            + ", ".join(sorted(missing))
        )


# ---------------------------------------------------------------------------
# TUI side — package.json dependencies (runtime only)
# ---------------------------------------------------------------------------


def _new_tui_deps_from_diff(diff_text: str) -> list[str]:
    in_deps_block = False
    new_deps: list[str] = []
    for line in diff_text.splitlines():
        stripped = line.lstrip("+-").lstrip()
        if re.match(r'"dependencies"\s*:\s*\{', stripped):
            in_deps_block = True
            continue
        if in_deps_block and stripped.startswith("}"):
            in_deps_block = False
            continue
        if in_deps_block and line.startswith("+") and not line.startswith("+++"):
            m = _ADDED_TUI_DEP_RE.match(line)
            if m:
                new_deps.append(m.group(1))
    return new_deps


def _current_tui_deps() -> frozenset[str]:
    payload = json.loads(_TUI_PACKAGE_JSON.read_text(encoding="utf-8"))
    deps = payload.get("dependencies", {})
    return frozenset(deps.keys())


def test_no_new_tui_runtime_deps() -> None:
    """SC-008 (TUI side): no new entries in tui/package.json "dependencies"."""
    diff_text = _best_effort_diff(_TUI_PACKAGE_JSON)
    if diff_text is not None:
        new_deps = _new_tui_deps_from_diff(diff_text)
        assert new_deps == [], (
            f"SC-008 violation (TUI): {len(new_deps)} new runtime dep(s) added:\n"
            + "\n".join(f"  + {d}" for d in new_deps)
        )
        return

    current = _current_tui_deps()
    extra = current - _TUI_DEPS_SNAPSHOT
    assert extra == frozenset(), (
        f"SC-008 violation (TUI snapshot): {len(extra)} unknown dep(s):\n"
        + "\n".join(f"  + {d}" for d in sorted(extra))
    )
    missing = _TUI_DEPS_SNAPSHOT - current
    if missing:
        pytest.skip(
            f"TUI snapshot drift: {len(missing)} expected dep(s) not found — "
            + ", ".join(sorted(missing))
        )
