# SPDX-License-Identifier: Apache-2.0
"""Tests for document fixture manifest loading."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ummaya.tools.documents.fixtures import (
    DocumentFixtureManifest,
    load_fixture_manifest,
)


def test_load_fixture_manifest_reads_offline_corpus_manifest() -> None:
    manifest = load_fixture_manifest()

    assert isinstance(manifest, DocumentFixtureManifest)
    assert manifest.manifest_id == "public_doc_harness_corpus_v1"
    assert manifest.live_network_allowed is False
    assert manifest.formats == ("hwpx", "hwp", "docx", "pdf", "xlsx", "pptx")


def test_fixture_manifest_rejects_live_network_usage(tmp_path: Path) -> None:
    manifest_path = tmp_path / "corpus_manifest.yaml"
    manifest_path.write_text(
        "\n".join(
            [
                "version: 1",
                "manifest_id: bad",
                "created_at: '2026-06-01'",
                "source_policy: offline_fixtures_only",
                "live_network_allowed: true",
                "formats: [hwpx]",
                "fixture_groups:",
                "  benign: []",
                "  public_forms: []",
                "  hostile: []",
                "requirements: {}",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_fixture_manifest(manifest_path)


def test_fixture_manifest_exposes_empty_groups_as_tuples() -> None:
    manifest = load_fixture_manifest()

    assert manifest.fixture_groups.benign == ()
    assert manifest.fixture_groups.public_forms == ()
    assert manifest.fixture_groups.hostile == ()
