#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Cross-check UMMAYA_* env-var surface vs. the registry in docs/configuration.md.

Contract: specs/026-secrets-infisical-oidc/contracts/audit-env-registry.md
FR: FR-020, FR-022, FR-023 | NFR-006 (10 s wall-clock budget)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------

_NAME_RE = re.compile(r"\bUMMAYA_[A-Z][A-Z0-9_]*\b")
_LANGFUSE_RE = re.compile(r"\bLANGFUSE_[A-Z][A-Z0-9_]*\b")

# Matches UMMAYA_<TOOL_ID>_API_KEY  where TOOL_ID = [A-Z][A-Z0-9_]*
_OVERRIDE_KEY_RE = re.compile(r"^UMMAYA_([A-Z][A-Z0-9_]*)_API_KEY$")

# Prefix-violation sweep: all-caps env-like tokens (3+ chars) in
# assignment/env context lines.
_ALL_CAPS_RE = re.compile(r"\b([A-Z][A-Z0-9_]{2,})\b")

# GitHub-builtin env names that are always allowed in workflow files.
_GITHUB_BUILTINS = frozenset({
    "CI",
    "GITHUB_TOKEN",
    "GITHUB_SHA",
    "GITHUB_REF",
    "GITHUB_REF_NAME",
    "GITHUB_REF_TYPE",
    "GITHUB_REPOSITORY",
    "GITHUB_REPOSITORY_OWNER",
    "GITHUB_EVENT_NAME",
    "GITHUB_WORKSPACE",
    "GITHUB_ACTOR",
    "GITHUB_RUN_ID",
    "GITHUB_RUN_NUMBER",
    "GITHUB_JOB",
    "GITHUB_WORKFLOW",
    "GITHUB_ACTIONS",
    "GITHUB_HEAD_REF",
    "GITHUB_BASE_REF",
    "RUNNER_OS",
    "RUNNER_ARCH",
    "RUNNER_TEMP",
    "RUNNER_TOOL_CACHE",
    "HOME",
    "PATH",
    "SHELL",
    "USER",
    # OTEL vendor SDK defaults — explicitly listed as allowed non-UMMAYA_ vars
    # because .env.example carries OTEL_* vars per spec §021 setup.
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_PROTOCOL",
    "OTEL_EXPORTER_OTLP_HEADERS",
    "OTEL_SEMCONV_STABILITY_OPT_IN",
    "OTEL_SDK_DISABLED",
    "OTEL_SERVICE_NAME",
    "OTEL_RESOURCE_ATTRIBUTES",
    "OTEL_DEPLOYMENT_ENVIRONMENT",
    # pytest / uv / Python infrastructure
    "PYTHONPATH",
    "PYTHONDONTWRITEBYTECODE",
    "PYTHONUTF8",
    "UV_CACHE_DIR",
    "UV_PROJECT_ENVIRONMENT",
    "PIP_DISABLE_PIP_VERSION_CHECK",
    "NO_COLOR",
    "FORCE_COLOR",
    "TERM",
    "COLUMNS",
    # Coverage / test infra
    "COVERAGE_PROCESS_START",
    # Platform-managed container ingress port (Cloud Run, Heroku-style hosts).
    "PORT",
})

# Prefix string indicating "GITHUB_" family — all such names are builtins.
_GITHUB_PREFIX = "GITHUB_"
_RUNNER_PREFIX = "RUNNER_"

# The registry table header literal used as anchor.
_REGISTRY_HEADER = "| Variable | Required |"

# The override-family placeholder that must appear in the registry.
_OVERRIDE_FAMILY_PLACEHOLDER = "UMMAYA_{TOOL_ID}_API_KEY"

# Registry deprecation sentinel.
_DEPRECATED_MARKER = "**deprecated**"

# ---------------------------------------------------------------------------
# Registry parsing
# ---------------------------------------------------------------------------


class ParseError(Exception):
    """Raised on malformed registry; carries offending line number."""

    def __init__(self, message: str, line_no: int | None = None) -> None:
        self.line_no = line_no
        super().__init__(message)


def _parse_registry(  # noqa: C901
    registry_path: Path,
) -> tuple[dict[str, int], set[str], bool]:
    """Parse the registry Markdown table.

    Returns:
        registry_vars: {name: line_number} for every non-deprecated row.
        deprecated_vars: set of deprecated variable names.
        has_override_family: True if the override-family placeholder row is present.

    Raises:
        ParseError on malformed table or missing file.
    """
    try:
        text = registry_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ParseError(f"Registry file not found: {registry_path}") from None
    except OSError as exc:
        raise ParseError(f"Cannot read registry: {exc}") from exc

    lines = text.splitlines()

    # Locate the header line.
    header_idx: int | None = None
    for idx, line in enumerate(lines):
        if line.startswith(_REGISTRY_HEADER):
            header_idx = idx
            break

    if header_idx is None:
        raise ParseError(
            f"Registry table header not found. Expected a line starting with "
            f"'{_REGISTRY_HEADER}' (case-sensitive).",
            line_no=None,
        )

    # Skip the separator line (| --- | ... |).
    data_start = header_idx + 2  # +1 = separator, +2 = first data row

    registry_vars: dict[str, int] = {}
    deprecated_vars: set[str] = set()
    has_override_family = False

    for i in range(data_start, len(lines)):
        line = lines[i]
        # Stop at blank line or next heading.
        stripped = line.strip()
        if not stripped:
            break
        if stripped.startswith("#"):
            break
        # Must be a table row.
        if not stripped.startswith("|"):
            break

        cells = line.split("|")
        # cells[0] is empty (before first |), cells[1] is Variable, etc.
        if len(cells) < 3:
            raise ParseError(
                f"Malformed table row (fewer than 2 cells): {line!r}",
                line_no=i + 1,
            )

        raw_name = cells[1].strip()
        # Strip backticks.
        name = raw_name.strip("`")

        if not name:
            continue

        # Check if this row is the override-family placeholder.
        if name == _OVERRIDE_FAMILY_PLACEHOLDER:
            has_override_family = True
            continue

        # Skip rows that are not UMMAYA_ or LANGFUSE_ (e.g., prose rows).
        if not (name.startswith("UMMAYA_") or name.startswith("LANGFUSE_")):
            continue

        # Classify by Required cell (case-insensitive to tolerate **Deprecated**).
        required_cell = cells[2].strip() if len(cells) > 2 else ""
        is_deprecated = _DEPRECATED_MARKER in required_cell.lower()

        if is_deprecated:
            deprecated_vars.add(name)
        else:
            registry_vars[name] = i + 1  # 1-based line number

    return registry_vars, deprecated_vars, has_override_family


# ---------------------------------------------------------------------------
# Code scanning
# ---------------------------------------------------------------------------


_PY_ENV_CONTEXT_RE = re.compile(
    r"os\.environ|os\.getenv|env_prefix|validation_alias"
)


def _is_assignment_line(line: str, file_kind: str) -> bool:
    """Return True if line looks like an env read/assignment, scoped per file kind.

    file_kind is one of:
      - 'shell'  : .env* files. Matches shell/dotenv `VAR=value` assignments.
      - 'yaml'   : workflow YAML. Matches `VAR: value` env-block lines and
                   shell assignments (which may appear inside `run:` blocks).
      - 'python' : src/**/*.py. Matches ONLY explicit env-read patterns
                   (os.environ / os.getenv / pydantic env_prefix /
                   validation_alias). Python module-level ALL_CAPS constants
                   are NOT flagged, because they are not env variables.
    """
    if file_kind == "python":
        return bool(_PY_ENV_CONTEXT_RE.search(line))

    stripped = line.strip()
    if file_kind == "shell":
        return bool(re.match(r"^(?:export\s+)?[A-Z][A-Z0-9_]*=", stripped))

    if file_kind == "yaml":
        if re.match(r"^[A-Z][A-Z0-9_]*:\s", stripped):
            return True
        if re.match(r"^(?:export\s+)?[A-Z][A-Z0-9_]*=", stripped):
            return True
    return False


def _classify_file(path: Path) -> str:
    """Map a path to a file_kind for `_is_assignment_line`."""
    name = path.name
    if name == ".env.example" or name.startswith(".env"):
        return "shell"
    if name.endswith((".yml", ".yaml")):
        return "yaml"
    if name.endswith(".py"):
        return "python"
    return "other"


def _scan_file(  # noqa: C901
    path: Path,
    repo_root: Path,
    ummaya_findings: dict[str, list[str]],
    langfuse_findings: dict[str, list[str]],
    prefix_violations: dict[str, list[str]],
) -> int:
    """Scan a single file for env-var tokens.

    Mutates ummaya_findings, langfuse_findings, prefix_violations in place.
    Returns number of tokens found (for stats).
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0

    token_count = 0
    # Emit repo-relative locations (e.g., `src/ummaya/foo.py:42`) so the JSON
    # report is machine-independent and matches contract examples. Fall back
    # to absolute on the off chance `path` sits outside repo_root.
    try:
        rel_path = str(path.relative_to(repo_root))
    except ValueError:
        rel_path = str(path)
    file_kind = _classify_file(path)

    for lineno, line in enumerate(text.splitlines(), start=1):
        location = f"{rel_path}:{lineno}"

        # Extract UMMAYA_ tokens.
        for match in _NAME_RE.finditer(line):
            name = match.group()
            # Skip bare prefix strings (e.g. env_prefix="UMMAYA_CLI_").
            # A trailing underscore means this is a prefix literal, not a
            # complete variable name.
            if name.endswith("_"):
                continue
            ummaya_findings.setdefault(name, []).append(location)
            token_count += 1

        # Extract LANGFUSE_ tokens.
        for match in _LANGFUSE_RE.finditer(line):
            name = match.group()
            if name.endswith("_"):
                continue
            langfuse_findings.setdefault(name, []).append(location)
            token_count += 1

        # Prefix-violation sweep — runs on all scanned file kinds, but the
        # assignment context is scoped by file kind (shell/yaml/python) so
        # Python module-level ALL_CAPS constants are not mis-flagged as env
        # variable references. Python coverage remains meaningful via the
        # explicit env-read patterns (os.environ / os.getenv / env_prefix /
        # validation_alias).
        if _is_assignment_line(line, file_kind):
            for match in _ALL_CAPS_RE.finditer(line):
                token = match.group()
                # Skip allowlisted prefixes and known builtins.
                if token.startswith("UMMAYA_"):
                    continue
                if token.startswith("LANGFUSE_"):
                    continue
                if token.startswith(_GITHUB_PREFIX):
                    continue
                if token.startswith(_RUNNER_PREFIX):
                    continue
                # OTEL_ is NOT a blanket-skip prefix — only the exact-name
                # allowlist in `_GITHUB_BUILTINS` (OTEL_EXPORTER_OTLP_*,
                # OTEL_SERVICE_NAME, etc.) is recognised. Any other OTEL_*
                # token must be catalogued in docs/configuration.md.
                if token in _GITHUB_BUILTINS:
                    continue
                # Skip very short tokens likely to be noise (e.g., "CI").
                if len(token) <= 2:
                    continue
                prefix_violations.setdefault(token, []).append(location)
                token_count += 1

    return token_count


def _collect_scan_targets(repo_root: Path) -> list[Path]:
    """Return sorted list of files to scan."""
    targets: list[Path] = []

    # src/**/*.py
    src_dir = repo_root / "src"
    if src_dir.is_dir():
        targets.extend(sorted(src_dir.rglob("*.py")))

    # .github/workflows/ci.yml
    ci_yml = repo_root / ".github" / "workflows" / "ci.yml"
    if ci_yml.is_file():
        targets.append(ci_yml)

    # .env.example
    env_example = repo_root / ".env.example"
    if env_example.is_file():
        targets.append(env_example)

    return targets


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------


def _discover_repo_root(start: Path) -> Path:
    """Walk up from start until we find a directory containing pyproject.toml."""
    current = start.resolve()
    while True:
        if (current / "pyproject.toml").exists():
            return current
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            # Reached filesystem root — fall back to cwd.
            return Path.cwd().resolve()
        current = parent


# ---------------------------------------------------------------------------
# Main audit logic
# ---------------------------------------------------------------------------


def audit(  # noqa: C901
    repo_root: Path,
    registry_path: Path,
) -> tuple[int, dict[str, object]]:
    """Run the full audit.

    Returns (exit_code, report_dict).
    exit_code: 0 = clean, 1 = drift, 2 = error.
    """
    t_start = time.monotonic()

    # --- Parse registry ---
    try:
        registry_vars, deprecated_vars, has_override_family = _parse_registry(
            registry_path
        )
    except ParseError as exc:
        err_msg = str(exc)
        if exc.line_no is not None:
            err_msg = f"{err_msg} (line {exc.line_no})"
        report: dict[str, object] = {
            "schema_version": "1",
            "generated_at": _utcnow(),
            "verdict": "malformed",
            "error": err_msg,
            "scan_stats": {
                "code_files_scanned": 0,
                "unique_names_in_code": 0,
                "registry_rows": 0,
                "duration_seconds": round(time.monotonic() - t_start, 3),
            },
            "findings": {
                "in_code_not_in_registry": [],
                "in_registry_not_in_code": [],
                "prefix_violations": [],
                "override_family_unmatched": [],
            },
        }
        return 2, report

    # --- Scan code ---
    targets = _collect_scan_targets(repo_root)
    ummaya_findings: dict[str, list[str]] = {}
    langfuse_findings: dict[str, list[str]] = {}
    prefix_violations_raw: dict[str, list[str]] = {}
    total_tokens = 0

    for path in targets:
        total_tokens += _scan_file(
            path,
            repo_root,
            ummaya_findings,
            langfuse_findings,
            prefix_violations_raw,
        )

    # Merge LANGFUSE_ into the full set for registry lookups.
    all_code_vars: dict[str, list[str]] = {}
    all_code_vars.update(ummaya_findings)
    all_code_vars.update(langfuse_findings)

    # --- Override-family analysis ---
    # Identify which UMMAYA_*_API_KEY code-vars are override-family expansions.
    override_family_members: dict[str, list[str]] = {}
    override_family_unmatched: dict[str, list[str]] = {}

    for name, locs in list(all_code_vars.items()):
        # Canonical registry rows take precedence over the override-family
        # regex — UMMAYA_KAKAO_API_KEY and UMMAYA_DATA_GO_KR_API_KEY match
        # _OVERRIDE_KEY_RE but are first-class registry entries, not
        # per-tool overrides.
        if name in registry_vars or name in deprecated_vars:
            continue
        m = _OVERRIDE_KEY_RE.match(name)
        if m:
            if has_override_family:
                # Covered by family pattern — suppress from drift findings.
                override_family_members[name] = locs
            else:
                # Family pattern missing from registry.
                override_family_unmatched[name] = locs

    # --- in_code_not_in_registry ---
    in_code_not_in_registry: dict[str, list[str]] = {}
    all_registry = set(registry_vars.keys()) | set(deprecated_vars)

    for name, locs in sorted(all_code_vars.items()):
        if name in override_family_members:
            # Suppressed — covered by family.
            continue
        if name in override_family_unmatched:
            # Will be reported under override_family_unmatched.
            continue
        if name not in all_registry:
            in_code_not_in_registry[name] = locs

    # --- in_registry_not_in_code ---
    # Deprecated vars are intentionally expected to have no code reference.
    in_registry_not_in_code: dict[str, int] = {}
    all_code_names = set(all_code_vars.keys())

    for name, line_no in registry_vars.items():
        if name not in all_code_names:
            # Check it's not covered by override family (shouldn't be since
            # override family members wouldn't have their own registry rows,
            # but be defensive).
            in_registry_not_in_code[name] = line_no

    # --- Prefix violations ---
    prefix_violations_out: dict[str, list[str]] = {}
    for name, locs in prefix_violations_raw.items():
        if name not in _GITHUB_BUILTINS:
            prefix_violations_out[name] = locs

    def _location_sort_key(location: str) -> tuple[str, int]:
        file_path, _, line_no = location.rpartition(":")
        return file_path, int(line_no) if line_no.isdigit() else 0

    # --- Build findings ---
    findings: dict[str, list[object]] = {
        "in_code_not_in_registry": [
            {
                "name": name,
                "source_files": sorted(set(locs), key=_location_sort_key),
            }
            for name, locs in sorted(in_code_not_in_registry.items())
        ],
        "in_registry_not_in_code": [
            {"name": name, "registry_line": line_no}
            for name, line_no in sorted(in_registry_not_in_code.items())
        ],
        "prefix_violations": [
            {
                "name": name,
                "source_files": sorted(set(locs), key=_location_sort_key),
                "reason": "not UMMAYA_-prefixed and not in LANGFUSE_ allowlist",
            }
            for name, locs in sorted(prefix_violations_out.items())
        ],
        "override_family_unmatched": [
            {
                "name": name,
                "source_files": sorted(set(locs), key=_location_sort_key),
            }
            for name, locs in sorted(override_family_unmatched.items())
        ],
    }

    # --- Verdict ---
    has_drift = any(findings[k] for k in findings)
    verdict = "drift" if has_drift else "clean"
    exit_code = 1 if has_drift else 0

    duration = round(time.monotonic() - t_start, 3)

    report = {
        "schema_version": "1",
        "generated_at": _utcnow(),
        "verdict": verdict,
        "scan_stats": {
            "code_files_scanned": len(targets),
            "unique_names_in_code": len(all_code_vars),
            "registry_rows": len(registry_vars) + len(deprecated_vars),
            "duration_seconds": duration,
        },
        "findings": findings,
    }

    return exit_code, report


def _utcnow() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audit-env-registry.py",
        description=(
            "Cross-check UMMAYA_* env-var surface vs. the registry in "
            "docs/configuration.md."
        ),
    )
    parser.add_argument(
        "--repo-root",
        metavar="PATH",
        default=None,
        help=(
            "Repo root to scan. Default: walk up from CWD to the directory "
            "containing pyproject.toml or .git."
        ),
    )
    parser.add_argument(
        "--registry",
        metavar="PATH",
        default=None,
        help="Registry Markdown file. Default: <repo-root>/docs/configuration.md.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.repo_root is not None:
        repo_root = Path(args.repo_root).resolve()
        if not repo_root.is_dir():
            sys.stderr.write(
                f"audit-env-registry: error: --repo-root is not a directory: {repo_root}\n"
            )
            return 2
    else:
        repo_root = _discover_repo_root(Path.cwd())

    if args.registry is not None:
        registry_path = Path(args.registry).resolve()
    else:
        registry_path = repo_root / "docs" / "configuration.md"

    exit_code, report = audit(repo_root, registry_path)

    sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    if exit_code == 2:
        sys.stderr.write(
            f"audit-env-registry: error: {report.get('error', 'parse error')}\n"
        )

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
