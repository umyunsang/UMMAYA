# SPDX-License-Identifier: Apache-2.0
"""Test T046 — SC-008, AGENTS.md hard rule: no new runtime dependencies.

The agent swarm implementation (Epic #13) must not add any runtime
dependency to [project.dependencies] in pyproject.toml. All new
functionality must be implemented with existing dependencies or stdlib.

This test parses pyproject.toml and verifies that the declared runtime
dependency set matches the pre-Epic-13 baseline. Any addition fails CI.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------

# Baseline runtime dependencies as of pre-Epic-13 (spec 026 merge).
# Any new entry added to [project.dependencies] after this snapshot is
# a violation of AGENTS.md § Hard rules ("Never add a dependency outside
# a spec-driven PR").
_BASELINE_DEPS: frozenset[str] = frozenset(
    [
        "httpx",
        "pydantic",
        "pydantic-settings",
        "pydantic_settings",  # alternate normalised form
        "typer",
        "rich",
        "prompt-toolkit",
        "prompt_toolkit",
        "opentelemetry-sdk",
        "opentelemetry_sdk",
        "opentelemetry-exporter-otlp-proto-http",
        "opentelemetry_exporter_otlp_proto_http",
        "opentelemetry-semantic-conventions",
        "opentelemetry_semantic_conventions",
        "rank-bm25",
        "rank_bm25",
        "kiwipiepy",
        "openai",
        "presidio-analyzer",
        "presidio_analyzer",
        "sentence-transformers",
        "sentence_transformers",
        "numpy",
        "torch",
        "python-docx",
        "PyYAML",
        "pyyaml",
        # torch/numpy are always present as sentence-transformers deps
    ]
)

_PYPROJECT = Path(__file__).parents[2] / "pyproject.toml"


def _extract_dep_names(pyproject_text: str) -> set[str]:
    """Parse [project.dependencies] from pyproject.toml and return package names.

    Handles PEP 508 specifiers (>=, ==, ~=, extras, markers) by splitting on
    the first occurrence of any version or extras separator.
    """
    in_deps = False
    names: set[str] = set()
    for line in pyproject_text.splitlines():
        stripped = line.strip()
        if stripped == "dependencies = [":
            in_deps = True
            continue
        if in_deps:
            if stripped.startswith("]"):
                break
            if stripped.startswith("#") or not stripped.startswith('"'):
                continue
            # Remove surrounding quotes and comments
            dep_str = stripped.strip('"').split("#")[0].strip().rstrip('",')
            # Extract package name: split on first [>=<~!;@
            for sep in ("[", ">=", "<=", "==", "!=", "~=", ">", "<", ";", "@", " "):
                if sep in dep_str:
                    dep_str = dep_str.split(sep)[0]
            pkg_name = dep_str.strip()
            if pkg_name:
                names.add(pkg_name)
    return names


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


def test_no_new_runtime_dependencies() -> None:
    """SC-008: [project.dependencies] must not grow beyond the Epic #13 baseline."""
    assert _PYPROJECT.exists(), f"pyproject.toml not found at {_PYPROJECT}"

    text = _PYPROJECT.read_text(encoding="utf-8")
    current_names = _extract_dep_names(text)

    # Normalise both sets to lowercase with dashes converted to underscores
    def _norm(s: str) -> str:
        return s.lower().replace("-", "_")

    current_normalised = {_norm(n) for n in current_names}
    baseline_normalised = {_norm(n) for n in _BASELINE_DEPS}

    additions = current_normalised - baseline_normalised
    assert not additions, (
        f"SC-008: New runtime dependencies detected (AGENTS.md hard rule):\n"
        f"  {sorted(additions)}\n"
        f"Never add a dependency outside a spec-driven PR. "
        f"Update _BASELINE_DEPS in this test only when a new spec is merged."
    )
