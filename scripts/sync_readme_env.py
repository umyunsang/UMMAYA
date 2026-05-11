#!/usr/bin/env -S uv run python
# SPDX-License-Identifier: Apache-2.0
"""Sync a README env-var snippet from `docs/configuration.md`.

Usage:
    uv run python scripts/sync_readme_env.py            # write README
    uv run python scripts/sync_readme_env.py --check    # CI drift gate
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "configuration.md"
README_PATH = REPO_ROOT / "README.md"

REGISTRY_HEADER = "| Variable | Required |"
ROW_REGEX = re.compile(r"^(UMMAYA|LANGFUSE)_[A-Z0-9_]+$")
OVERRIDE_KEY = "UMMAYA_{TOOL_ID}_API_KEY"

START_MARKER = "<!-- AUTO-GENERATED README ENV TABLE START -->"
END_MARKER = "<!-- AUTO-GENERATED README ENV TABLE END -->"
NOTICE_LINE = (
    "<!-- AUTO-GENERATED: from docs/configuration.md (Quick Reference Table), "
    "Do not edit manually. -->"
)


@dataclass(frozen=True)
class EnvRow:
    variable: str
    required: str
    default: str
    consumed_by: str


def _parse_registry(path: Path) -> list[EnvRow]:
    lines = path.read_text(encoding="utf-8").splitlines()

    header_idx = None
    for idx, line in enumerate(lines):
        if line.startswith(REGISTRY_HEADER):
            header_idx = idx
            break
    if header_idx is None:
        raise RuntimeError(
            f"Could not find env registry header in {path}."
        )

    rows: list[EnvRow] = []
    for line in lines[header_idx + 2 :]:
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("|-"):
            break
        if not stripped:
            break

        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 6:
            break

        raw_name = cells[0].strip("`").strip()
        if not raw_name:
            continue

        if not (
            ROW_REGEX.fullmatch(raw_name) or raw_name == OVERRIDE_KEY
        ):
            continue

        rows.append(
            EnvRow(
                variable=raw_name,
                required=cells[1] or "—",
                default=cells[2] or "—",
                consumed_by=cells[4] or "—",
            )
        )

    if not rows:
        raise RuntimeError(f"No valid env rows found in {path}.")
    return rows


def _render_block(rows: list[EnvRow]) -> str:
    lines = []

    # Preserve the legacy L1-A phrasing required by tests and contributor docs:
    # variable mention + default value on the same line.
    for row in rows:
        if row.variable == "UMMAYA_K_EXAONE_THINKING":
            lines.append(f"- `{row.variable}` (default {row.default}): {row.consumed_by}")
            break

    lines.extend(
        [
            "| Variable | Required | Default | Consumed by |",
            "|---|---|---|---|",
        ]
    )
    for row in rows:
        lines.append(
            f"| `{row.variable}` | {row.required} | {row.default} | {row.consumed_by} |"
        )
    return "\n".join(lines)


def _extract_snippet(readme_text: str) -> tuple[int, int]:
    start = readme_text.find(START_MARKER)
    if start < 0:
        raise RuntimeError(f"Missing start marker: {START_MARKER}")
    end = readme_text.find(END_MARKER, start + len(START_MARKER))
    if end < 0:
        raise RuntimeError(f"Missing end marker: {END_MARKER}")
    return start, end


def main(argv: list[str]) -> int:
    rows = _parse_registry(DOC_PATH)
    rendered = _render_block(rows)
    expected_payload = f"\n{NOTICE_LINE}\n{rendered}\n"

    readme_text = README_PATH.read_text(encoding="utf-8")
    start, end = _extract_snippet(readme_text)

    existing_payload = readme_text[start + len(START_MARKER) : end]
    if "--check" in argv:
        if existing_payload.strip() == expected_payload.strip():
            return 0
        return 1

    replacement = f"{START_MARKER}{expected_payload}{END_MARKER}"
    next_part = readme_text[end + len(END_MARKER) :]
    README_PATH.write_text(f"{readme_text[:start]}{replacement}{next_part}", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
