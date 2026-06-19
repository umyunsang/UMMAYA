# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_INTAKE_NOTE = _REPO_ROOT / "docs" / "onboarding" / "cc-tool-layer-lazycodex-intake.md"
_REQUIRED_TERMS = (
    "$start-work",
    "$ulw-loop",
    ".omo/plans/cc-original-tool-layer-port-lazycodex.md",
    "LazyCodex",
    "2803",
    "closed",
    "dirty worktree",
    "git status -sb --untracked-files=all",
    "Do not create GitHub issues or a PR",
)


def test_plan_names_lazycodex_pipeline_and_dirty_worktree_guard() -> None:
    text = _INTAKE_NOTE.read_text(encoding="utf-8")

    missing_terms = [term for term in _REQUIRED_TERMS if term not in text]

    assert missing_terms == [], (
        "LazyCodex CC tool-layer intake note is missing required execution guards: "
        + ", ".join(missing_terms)
    )
