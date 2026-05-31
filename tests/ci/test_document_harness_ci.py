# SPDX-License-Identifier: Apache-2.0
"""CI guards for the Public AX document harness offline boundary."""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

_REPO_ROOT = Path(__file__).resolve().parents[2]

_SCAN_TARGETS = (
    _REPO_ROOT / "specs" / "2802-public-doc-harness",
    _REPO_ROOT / "evidence" / "scenarios" / "document_harness_v1.yaml",
    _REPO_ROOT / "tests" / "tools" / "documents",
    _REPO_ROOT / "tests" / "evidence",
)
_TEXT_SUFFIXES = {".json", ".md", ".py", ".toml", ".yaml", ".yml"}

_REFERENCE_URL_DOCS: frozenset[Path] = frozenset(
    {
        Path("specs/2802-public-doc-harness/plan.md"),
        Path("specs/2802-public-doc-harness/research.md"),
        Path("specs/2802-public-doc-harness/parallel-evaluation-plan.md"),
    }
)

_URL_RE = re.compile(r"https?://[^\s\"'`<>)\]}]+", re.IGNORECASE)
_QUOTED_HOST_RE = re.compile(
    r"(?P<quote>['\"])(?P<host>(?:[a-z0-9-]+\.)*(?:"
    r"data\.go\.kr|api\.odcloud\.kr|apihub\.kma\.go\.kr|gov\.kr|"
    r"[a-z0-9-]+\.go\.kr"
    r"))(?P=quote)",
    re.IGNORECASE,
)
_NETWORK_CALL_RE = re.compile(
    r"\b(?:requests\.(?:get|post|put|delete|request)|"
    r"httpx\.(?:get|post|put|delete|request|AsyncClient|Client)|"
    r"aiohttp\.ClientSession|urllib\.request|socket\.create_connection|"
    r"subprocess\.(?:run|check_call|check_output)\([^)]*\bcurl\b)",
    re.IGNORECASE | re.DOTALL,
)
_PYTEST_LIVE_MARK_RE = re.compile(r"@pytest\.mark\.live|\bpytest\.mark\.live\b")
_LIVE_FLAG_RE = re.compile(
    r"\b(?:live_network_allowed\s*[:=]\s*true|"
    r"network_policy\s*[:=]\s*(?!['\"]?offline_only\b)['\"]?[a-z_]+|"
    r"live_government_calls\s*[:=]\s*(?!['\"]?forbidden\b)['\"]?[a-z_]+)",
    re.IGNORECASE,
)


class Finding(NamedTuple):
    path: Path
    line: int
    reason: str
    value: str


def test_document_harness_ci_fixtures_never_reference_live_public_endpoints() -> None:
    findings = [
        finding
        for path in _iter_scan_files()
        for finding in _find_live_endpoint_or_flag_references(path)
    ]

    assert findings == [], _format_findings(findings)


def _iter_scan_files() -> list[Path]:
    files: list[Path] = []
    for target in _SCAN_TARGETS:
        if target.is_file():
            files.append(target)
            continue
        files.extend(path for path in target.rglob("*") if path.is_file())

    return sorted(path for path in files if path.suffix in _TEXT_SUFFIXES)


def _find_live_endpoint_or_flag_references(path: Path) -> list[Finding]:
    rel_path = path.relative_to(_REPO_ROOT)
    text = path.read_text(encoding="utf-8")
    findings: list[Finding] = []

    for match in _URL_RE.finditer(text):
        url = match.group(0)
        if _is_banned_public_host(urlsplit(url).hostname) and rel_path not in _REFERENCE_URL_DOCS:
            findings.append(
                Finding(
                    path=rel_path,
                    line=_line_number(text, match.start()),
                    reason="live public endpoint URL",
                    value=url,
                )
            )

    if path.suffix != ".md":
        for match in _QUOTED_HOST_RE.finditer(text):
            host = match.group("host")
            if _is_banned_public_host(host):
                findings.append(
                    Finding(
                        path=rel_path,
                        line=_line_number(text, match.start()),
                        reason="live public endpoint host",
                        value=host,
                    )
                )

    if path.suffix == ".py":
        for pattern, reason in (
            (_NETWORK_CALL_RE, "live network call surface"),
            (_PYTEST_LIVE_MARK_RE, "pytest live marker"),
        ):
            for match in pattern.finditer(text):
                findings.append(
                    Finding(
                        path=rel_path,
                        line=_line_number(text, match.start()),
                        reason=reason,
                        value=match.group(0).splitlines()[0],
                    )
                )
    else:
        for match in _LIVE_FLAG_RE.finditer(text):
            findings.append(
                Finding(
                    path=rel_path,
                    line=_line_number(text, match.start()),
                    reason="permissive live-network flag",
                    value=match.group(0),
                )
            )

    return findings


def _is_banned_public_host(host: str | None) -> bool:
    if host is None:
        return False
    normalized = host.lower().strip(".")
    return normalized in {"data.go.kr", "api.odcloud.kr", "apihub.kma.go.kr", "gov.kr"} or (
        normalized.endswith(".go.kr")
    )


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _format_findings(findings: list[Finding]) -> str:
    lines = [
        "Document harness CI/test fixtures must stay offline-only; remove live endpoint "
        "references or permissive live-network flags:"
    ]
    lines.extend(
        f"- {finding.path}:{finding.line}: {finding.reason}: {finding.value}"
        for finding in findings
    )
    return "\n".join(lines)
