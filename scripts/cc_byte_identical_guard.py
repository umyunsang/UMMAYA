#!/usr/bin/env python3
"""CC byte-identical SHA-256 guard (Epic #2639 · Spec 2639-s3-ui-guard).

Walks every .ts/.tsx file under the S3 slice (tui/src/components/, screens/,
outputStyles/, moreright/, plus 3 top-level launchers) and checks the
SHA-256 against the vendored CC baseline. Divergences that are not
listed in the whitelist YAML cause the script to exit 1.

Run locally:
    python3 scripts/cc_byte_identical_guard.py \\
        --baseline specs/2639-s3-ui-guard/fixtures/cc-baseline-shas.txt \\
        --whitelist tui/src/.cc-byte-identical-whitelist.yaml \\
        --slice-root tui/src

CI usage: invoked from .github/workflows/cc-byte-identical-guard.yml.

Audit reference: specs/cc-migration-audit/scope-S3-components-screens.md
Spec: specs/2639-s3-ui-guard/spec.md (FR-001~FR-005)
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    print(f"::error::PyYAML required (pip install pyyaml). {exc}", file=sys.stderr)
    sys.exit(2)


SLICE_DIRS = ["components", "screens", "outputStyles", "moreright"]
SLICE_TOP = ["dialogLaunchers.tsx", "interactiveHelpers.tsx", "replLauncher.tsx"]
SUFFIXES = (".ts", ".tsx")

# Files in the CC baseline that are intentionally NOT ported to KOSMOS
# (1P-Anthropic business surfaces — see tui/src/components/.never-port.md).
# These paths are accepted as "missing in KOSMOS" without triggering the
# deletion-detection failure; everything else missing is treated as a
# regression (e.g. accidental `git rm`).
NEVER_PORT = frozenset({
    "components/Feedback.tsx",
    "components/grove/Grove.tsx",
    "components/LogoV2/GuestPassesUpsell.tsx",
    "components/LogoV2/OverageCreditUpsell.tsx",
    "components/Passes/Passes.tsx",
    "components/Settings/Usage.tsx",
    "components/TeleportResumeWrapper.tsx",
})


def parse_baseline(path: Path) -> dict[str, str]:
    """Parse `<sha>  <relative-path>` lines into {rel: sha}."""
    table: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        # shasum -a 256 format: "<hex_sha>  <path>" (two-space separator).
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            print(f"::warning::malformed baseline line: {line!r}", file=sys.stderr)
            continue
        sha, rel = parts[0], parts[1].lstrip()
        table[rel] = sha
    return table


def parse_whitelist(path: Path) -> dict[str, dict]:
    """Parse the YAML whitelist into {repo_relative_path: entry}."""
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise SystemExit(f"::error file={path}::whitelist must be a YAML mapping")
    entries = data.get("entries", [])
    if not isinstance(entries, list):
        raise SystemExit(f"::error file={path}::whitelist 'entries' must be a list")
    table: dict[str, dict] = {}
    for entry in entries:
        if not isinstance(entry, dict) or "path" not in entry:
            raise SystemExit(f"::error file={path}::whitelist entry missing 'path': {entry!r}")
        if "cause" not in entry or "spec_ref" not in entry:
            raise SystemExit(
                f"::error file={path}::whitelist entry for {entry['path']} "
                "missing 'cause' or 'spec_ref'"
            )
        if entry["path"] in table:
            raise SystemExit(
                f"::error file={path}::duplicate whitelist entry: {entry['path']}"
            )
        table[entry["path"]] = entry
    return table


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def enumerate_slice(slice_root: Path) -> list[Path]:
    """Yield absolute paths under the slice for .ts/.tsx files."""
    files: list[Path] = []
    for sub in SLICE_DIRS:
        d = slice_root / sub
        if d.is_dir():
            files.extend(p for p in d.rglob("*") if p.is_file() and p.suffix in SUFFIXES)
    for top in SLICE_TOP:
        p = slice_root / top
        if p.is_file():
            files.append(p)
    return sorted(files)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path,
                        help="Path to fixtures/cc-baseline-shas.txt")
    parser.add_argument("--whitelist", required=True, type=Path,
                        help="Path to tui/src/.cc-byte-identical-whitelist.yaml")
    parser.add_argument("--slice-root", required=True, type=Path,
                        help="Root of the KOSMOS slice (typically tui/src)")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress PASS summary output")
    args = parser.parse_args()

    if not args.baseline.is_file():
        print(f"::error::baseline file not found: {args.baseline}", file=sys.stderr)
        return 2
    if not args.whitelist.is_file():
        print(f"::error::whitelist file not found: {args.whitelist}", file=sys.stderr)
        return 2
    if not args.slice_root.is_dir():
        print(f"::error::slice root not found: {args.slice_root}", file=sys.stderr)
        return 2

    baseline = parse_baseline(args.baseline)
    whitelist = parse_whitelist(args.whitelist)
    slice_root = args.slice_root.resolve()
    slice_files = enumerate_slice(slice_root)

    # repo_root inferred so we can build whitelist-style paths (tui/src/...)
    # relative to the baseline file (which lives under specs/...).
    # Heuristic: assume slice_root is repo_root/<...>/src or repo_root/tui/src.
    # We only need a stable prefix to match whitelist 'path' values, so
    # we derive repo_root from the slice_root's parents until we find one
    # with a `tui` segment, falling back to slice_root.parent.parent.
    repo_root = slice_root
    while repo_root.name and repo_root.name != "tui" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name == "tui":
        repo_root = repo_root.parent
    else:
        repo_root = slice_root.parent.parent

    stats = {
        "total": 0,
        "byte_identical": 0,
        "whitelisted": 0,
        "kosmos_only": 0,
        "missing_never_port": 0,
        "failed": 0,
    }
    failures: list[tuple[str, str]] = []

    # FR-003 + Codex P1 (PR #2723) — deletion guard.
    # Walk the BASELINE side first to catch CC-tracked files that have been
    # removed from KOSMOS without an explicit NEVER-PORT carve-out. This is
    # the inverse of the divergence walk below: if we only walked KOSMOS
    # files, a `git rm tui/src/components/App.tsx` would silently pass.
    kosmos_rels = {p.relative_to(slice_root).as_posix() for p in slice_files}
    for cc_rel in baseline:
        if cc_rel in kosmos_rels:
            continue
        if cc_rel in NEVER_PORT:
            stats["missing_never_port"] += 1
            continue
        repo_rel = f"tui/src/{cc_rel}"
        failures.append((
            repo_rel,
            f"CC-baselined file is missing from tui/src (deletion or rename "
            f"detected). Either restore the file (it must remain byte-identical "
            f"with CC, or carry a whitelist entry), or add the path to the "
            f"NEVER_PORT set in scripts/cc_byte_identical_guard.py with a "
            f"CORE THESIS justification.",
        ))
        stats["failed"] += 1

    for kosmos_path in slice_files:
        stats["total"] += 1
        rel_to_slice = kosmos_path.relative_to(slice_root).as_posix()
        actual_sha = sha256_of(kosmos_path)

        cc_sha = baseline.get(rel_to_slice)
        if cc_sha is None:
            # KOSMOS-only file — no CC baseline. PASS (these are KOSMOS-original
            # additions per audit § 6, e.g. 5-primitive renderers, onboarding,
            # citizen UI extensions).
            stats["kosmos_only"] += 1
            continue

        if actual_sha == cc_sha:
            stats["byte_identical"] += 1
            continue

        # Divergent. Lookup in whitelist using repo-root relative path.
        try:
            repo_rel = kosmos_path.resolve().relative_to(repo_root).as_posix()
        except ValueError:
            repo_rel = f"tui/src/{rel_to_slice}"

        wl = whitelist.get(repo_rel)
        if wl is None:
            failures.append((
                repo_rel,
                f"SHA-256 mismatch and not in whitelist (got {actual_sha[:12]}, "
                f"expected CC {cc_sha[:12]}). Add an entry to "
                f"tui/src/.cc-byte-identical-whitelist.yaml with cause + spec_ref, "
                f"or revert to byte-identical.",
            ))
            stats["failed"] += 1
            continue

        # Pinned content check (optional).
        expected = wl.get("expected_sha256")
        if expected and expected != actual_sha:
            failures.append((
                repo_rel,
                f"SHA-256 differs from whitelist pin (got {actual_sha[:12]}, "
                f"pinned {str(expected)[:12]}). Update expected_sha256 if the "
                f"divergence intentionally changed.",
            ))
            stats["failed"] += 1
            continue

        stats["whitelisted"] += 1

    for repo_rel, msg in failures:
        # GitHub Actions error annotation.
        print(f"::error file={repo_rel}::{msg}")

    if stats["failed"]:
        # `failed` aggregates two failure modes: (a) divergent KOSMOS file
        # without a whitelist entry, and (b) CC-baselined file missing from
        # tui/src without a NEVER_PORT carve-out (deletion guard). Worded
        # to cover both per Copilot review on PR #2723.
        print(
            f"::error::cc-byte-identical-guard FAILED · {stats['failed']} "
            f"unjustified divergence(s) (missing-from-kosmos OR sha-mismatch-without-whitelist). "
            f"Total scanned: {stats['total']}.",
            file=sys.stderr,
        )
        return 1

    if not args.quiet:
        print(
            f"PASS · scanned {stats['total']} files · "
            f"{stats['byte_identical']} byte-identical · "
            f"{stats['whitelisted']} whitelisted · "
            f"{stats['kosmos_only']} KOSMOS-only · "
            f"{stats['missing_never_port']} NEVER-PORT (CC-only, intentional) · "
            f"{stats['failed']} failed"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
