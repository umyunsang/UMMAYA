# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import re
from pathlib import Path
from typing import Final

_REPO_ROOT: Final = Path(__file__).resolve().parents[2]
_SCOPE_CONTRACT: Final = _REPO_ROOT / "docs" / "requirements" / "cc-tool-layer-scope-contract.md"
_MIGRATION_TREE: Final = _REPO_ROOT / "docs" / "requirements" / "ummaya-migration-tree.md"
_RESEARCH_NOTE: Final = "docs/research/cc-original-tool-layer-port-2026-06-12.md"
_EXECUTION_PLAN: Final = ".omo/plans/cc-original-tool-layer-port-lazycodex.md"

_REQUIRED_TERMS: Final = (
    "registered capability",
    "always-loaded",
    "deferred-searchable",
    "permission-gated-callable",
    "hidden",
    "unsupported",
    "national AX primitive surface",
)
_UNQUALIFIED_C6_EXCLUSION_RE: Final = re.compile(
    r"Read/Write/Edit/Bash/Glob/Grep/NotebookEdit\) .*excluded|"
    r"제외 \(Read/Write/Edit/Bash/Glob/Grep/NotebookEdit\)"
)


def test_scope_contract_separates_capability_from_exposure() -> None:
    scope_text = _read_required(_SCOPE_CONTRACT)
    normalized_scope = " ".join(scope_text.split())

    missing_terms = [term for term in _REQUIRED_TERMS if term not in scope_text]
    assert missing_terms == [], (
        f"The CC tool-layer scope contract is missing required terms: {missing_terms}"
    )

    assert re.search(
        r"registered capability.{0,160}not an exposure state",
        normalized_scope,
        flags=re.IGNORECASE,
    ), (
        "The CC tool-layer scope contract must define registered capability as "
        "not an exposure state."
    )
    assert _RESEARCH_NOTE in scope_text and "input evidence" in scope_text, (
        "The scope contract must name the research note as input evidence."
    )
    assert _EXECUTION_PLAN in scope_text and "execution plan artifact" in scope_text, (
        "The scope contract must name the LazyCodex plan as the execution plan artifact."
    )

    migration_tree = _read_required(_MIGRATION_TREE)
    assert _UNQUALIFIED_C6_EXCLUSION_RE.search(migration_tree) is None, (
        "The historical C6 helper-tool exclusion must not remain as an active "
        "unqualified exclusion."
    )


def _read_required(path: Path) -> str:
    assert path.exists(), (
        f"Required scope contract artifact does not exist: {path.relative_to(_REPO_ROOT)}"
    )
    return path.read_text(encoding="utf-8")
