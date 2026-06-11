# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

from ummaya.tools.documents.fixtures import DocumentFixtureManifest, load_fixture_manifest

_FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "documents"
_ONE_MIB = 1024 * 1024


def test_fixture_matrix_covers_public_forms_and_narrative_authoring() -> None:
    manifest = load_fixture_manifest()
    entries = _all_entries(manifest)

    assert len(manifest.fixture_groups.public_forms) >= 3
    assert len(manifest.fixture_groups.narrative_authoring) >= 3
    assert {entry.authoring_flow for entry in manifest.fixture_groups.public_forms} == {
        "public_form_fill"
    }
    assert {entry.authoring_flow for entry in manifest.fixture_groups.narrative_authoring} == {
        "socratic_narrative"
    }
    assert _coverage(entries, "form_blanks")
    assert _coverage(entries, "self_introduction")
    assert _coverage(entries, "business_plan")
    assert _coverage(entries, "protected_fields")
    assert _coverage(entries, "missing_evidence")
    assert _coverage(entries, "approved_draft_mutation")

    for entry in entries:
        assert entry.source
        assert entry.size_bytes is not None
        assert entry.size_bytes < _ONE_MIB
        assert entry.sha256 is not None
        assert len(entry.sha256) == 64
        assert entry.protected_field_expectations
        assert entry.expected_fields or entry.expected_narrative_prompts
        assert entry.expected_authoring_flow
        if entry.redistribution_status != "metadata_only":
            fixture_path = _FIXTURE_ROOT / entry.path
            assert fixture_path.is_file()
            assert fixture_path.stat().st_size == entry.size_bytes


def _all_entries(manifest: DocumentFixtureManifest):
    return (
        *manifest.fixture_groups.benign,
        *manifest.fixture_groups.public_forms,
        *manifest.fixture_groups.narrative_authoring,
        *manifest.fixture_groups.hostile,
    )


def _coverage(entries: tuple[object, ...], tag: str) -> bool:
    return any(tag in entry.coverage_tags for entry in entries)
