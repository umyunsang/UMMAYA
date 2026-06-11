# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from ummaya.tools.documents.fixtures import DocumentFixtureManifest

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "documents"
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
RAW_SOURCE_PATH = "/Users/example/private/civil-form.pdf"
RAW_BYTES_MARKER = "%PDF-1.7 raw document bytes"

_FORBIDDEN_KEYS = frozenset(
    {
        "document_bytes",
        "raw_bytes",
        "source_bytes",
        "source_path",
    }
)
_RAW_PII_PATTERNS = (
    re.compile(r"\b\d{6}-\d{7}\b"),
    re.compile(r"\b01[016789]-\d{3,4}-\d{4}\b"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
)


def json_dict(payload: str) -> dict[str, Any]:
    decoded = json.loads(payload)
    assert isinstance(decoded, dict)
    return decoded


def assert_identifier_scoped(payload: Mapping[str, Any]) -> None:
    forbidden_key_paths = _find_forbidden_key_paths(payload)
    assert forbidden_key_paths == []
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert RAW_SOURCE_PATH not in encoded
    assert RAW_BYTES_MARKER not in encoded


def fixture_privacy_payloads(manifest: DocumentFixtureManifest) -> Iterator[str]:
    yield json.dumps(manifest.model_dump(), ensure_ascii=False, sort_keys=True)
    for entry in (
        *manifest.fixture_groups.benign,
        *manifest.fixture_groups.public_forms,
        *manifest.fixture_groups.narrative_authoring,
        *manifest.fixture_groups.hostile,
    ):
        if entry.redistribution_status == "metadata_only":
            continue
        fixture_path = FIXTURE_ROOT / entry.path
        assert fixture_path.is_file()
        yield fixture_path.read_text(encoding="utf-8", errors="ignore")


def raw_pii_found(value: str) -> bool:
    return any(pattern.search(value) for pattern in _RAW_PII_PATTERNS)


def _find_forbidden_key_paths(value: object, prefix: str = "$") -> list[str]:
    if isinstance(value, Mapping):
        matches: list[str] = []
        for key, item in value.items():
            path = f"{prefix}.{key}"
            if key in _FORBIDDEN_KEYS:
                matches.append(path)
            matches.extend(_find_forbidden_key_paths(item, path))
        return matches
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        matches = []
        for index, item in enumerate(value):
            matches.extend(_find_forbidden_key_paths(item, f"{prefix}[{index}]"))
        return matches
    return []
