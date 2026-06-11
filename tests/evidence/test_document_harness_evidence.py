# SPDX-License-Identifier: Apache-2.0
"""Evidence Fabric joins for Public AX document harness reports."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

_HASH_A = "a" * 64
_HASH_B = "b" * 64
_HASH_C = "c" * 64
_HASH_D = "d" * 64


def test_document_evidence_record_joins_reports_without_document_bytes() -> None:
    from ummaya.evidence.document_harness import DocumentEvidenceRecord

    record = DocumentEvidenceRecord(
        record_id="doc-ev-001",
        scenario_id="DOC-US4-001",
        correlation_id="corr-doc-001",
        source_artifact_id="artifact-source-001",
        source_sha256=_HASH_A,
        derivative_artifact_id="artifact-derivative-001",
        derivative_sha256=_HASH_B,
        structured_diff_id="diff-001",
        structured_diff_sha256=_HASH_C,
        render_artifact_ids=("render-page-001",),
        validation_report_id="validation-001",
        validation_report_sha256=_HASH_D,
        readiness="ready_for_review",
    )

    encoded = json.loads(record.model_dump_json())

    assert encoded["correlation_id"] == "corr-doc-001"
    assert encoded["source_sha256"] == _HASH_A
    assert encoded["derivative_sha256"] == _HASH_B
    assert encoded["render_artifact_ids"] == ["render-page-001"]
    assert "document_bytes" not in encoded
    assert "text" not in encoded
    assert "after_value" not in encoded


def test_document_evidence_record_rejects_inline_document_bytes() -> None:
    from ummaya.evidence.document_harness import DocumentEvidenceRecord

    with pytest.raises(ValidationError, match="document_bytes"):
        DocumentEvidenceRecord(
            record_id="doc-ev-001",
            scenario_id="DOC-US4-001",
            correlation_id="corr-doc-001",
            source_artifact_id="artifact-source-001",
            source_sha256=_HASH_A,
            derivative_artifact_id="artifact-derivative-001",
            derivative_sha256=_HASH_B,
            structured_diff_id="diff-001",
            structured_diff_sha256=_HASH_C,
            render_artifact_ids=("render-page-001",),
            validation_report_id="validation-001",
            validation_report_sha256=_HASH_D,
            readiness="ready_for_review",
            document_bytes=b"raw document payload",
        )


def test_document_harness_scenario_covers_us4_without_live_calls() -> None:
    from ummaya.evidence.document_harness import load_document_harness_scenario

    scenario = load_document_harness_scenario(Path("evidence/scenarios/document_harness_v1.yaml"))

    assert scenario.scenario_id == "document_harness_v1"
    assert scenario.network_policy == "offline_only"
    assert scenario.acceptance_gates.live_government_calls == "forbidden"
    assert scenario.acceptance_gates.render_reread_evidence == "required"
    assert scenario.required_sequence == ("document",)
    assert {fixture.format for fixture in scenario.fixtures} == {
        "hwpx",
        "docx",
        "xlsx",
        "pdf",
        "pptx",
    }
    assert all(fixture.expected_correlation_id for fixture in scenario.fixtures)
    assert all(fixture.source_sha256 and fixture.derivative_sha256 for fixture in scenario.fixtures)


def test_document_harness_scenario_covers_phase11_lifecycle_matrix() -> None:
    from ummaya.evidence.document_harness import load_document_harness_scenario

    scenario = load_document_harness_scenario(Path("evidence/scenarios/document_harness_v1.yaml"))

    assert {record.stage for record in scenario.lifecycle_records} >= {
        "intake",
        "classification",
        "capability",
        "adapter_selection",
        "permission",
        "mutation",
        "render",
        "reread",
        "validation",
        "diff",
        "tui_frame",
    }
    assert all(record.correlation_id for record in scenario.lifecycle_records)
    assert all(record.evidence_ref for record in scenario.lifecycle_records)
    assert any(
        record.frame_hash for record in scenario.lifecycle_records if record.stage == "tui_frame"
    )


def test_document_harness_scenario_covers_phase11_beta_and_negative_matrices() -> None:
    from ummaya.evidence.document_harness import load_document_harness_scenario

    scenario = load_document_harness_scenario(Path("evidence/scenarios/document_harness_v1.yaml"))

    assert {case.domain for case in scenario.beta_cases} == {
        "weekly_log",
        "contest_proposal",
        "consent",
        "pledge",
        "spreadsheet",
        "pdf_form",
        "presentation",
        "public_data_csv_json",
        "static_pdf",
        "scanned_image",
        "archive_bundle",
    }
    assert {case.known_format for case in scenario.beta_cases} >= {
        "hwpx",
        "hwp",
        "docx",
        "pdf",
        "xlsx",
        "pptx",
        "csv",
        "json",
        "png",
        "zip",
    }
    assert {case.trigger for case in scenario.negative_cases} == {
        "missing_file",
        "ambiguous_file_candidates",
        "unsupported_known_format",
        "blocked_hwp_write",
        "static_pdf_fill",
        "macro_active_content",
        "path_traversal",
        "oversized_archive",
        "external_link",
    }
    assert all(case.derivative_save == "forbidden" for case in scenario.negative_cases)


def test_document_harness_scenario_covers_authoring_gate_matrix() -> None:
    from ummaya.evidence.document_harness import load_document_harness_scenario

    scenario = load_document_harness_scenario(Path("evidence/scenarios/document_harness_v1.yaml"))

    cases_by_class = {case.scenario_class: case for case in scenario.authoring_cases}
    assert set(cases_by_class) == {
        "public_form_completion",
        "narrative_authoring",
        "unsupported_plausible_writing",
        "protected_field",
        "direct_hwp_path",
        "render_comparison",
    }
    assert cases_by_class["public_form_completion"].expected_status == "ready_for_review"
    assert cases_by_class["public_form_completion"].mutation_allowed is True
    assert cases_by_class["narrative_authoring"].requires_socratic_loop is True
    assert cases_by_class["narrative_authoring"].requires_user_approval is True
    assert cases_by_class["unsupported_plausible_writing"].expected_status == "blocked"
    assert cases_by_class["unsupported_plausible_writing"].mutation_allowed is False
    assert cases_by_class["protected_field"].expected_status == "needs_input"
    assert cases_by_class["protected_field"].mutation_allowed is False
    assert cases_by_class["direct_hwp_path"].hwp_direct_write_state == "blocked"
    assert cases_by_class["direct_hwp_path"].mutation_allowed is False
    assert cases_by_class["render_comparison"].render_comparison_required is True
    assert all(case.correlation_id for case in scenario.authoring_cases)
    assert all(case.evidence_ref for case in scenario.authoring_cases)


def test_document_records_attach_to_evidence_runner_output() -> None:
    from ummaya.evidence.document_harness import (
        DocumentEvidenceRecord,
        attach_document_evidence_records,
    )
    from ummaya.evidence.runner import run_dataset

    run_evidence = run_dataset(
        scenario_path=Path("evidence/scenarios/national_ax_citizen_requests_v1.yaml"),
        source_ref="test",
    )
    record = DocumentEvidenceRecord(
        record_id="doc-ev-001",
        scenario_id="DOC-US4-001",
        correlation_id="corr-doc-001",
        source_artifact_id="artifact-source-001",
        source_sha256=_HASH_A,
        derivative_artifact_id="artifact-derivative-001",
        derivative_sha256=_HASH_B,
        structured_diff_id="diff-001",
        structured_diff_sha256=_HASH_C,
        render_artifact_ids=("render-page-001",),
        validation_report_id="validation-001",
        validation_report_sha256=_HASH_D,
        readiness="ready_for_review",
    )

    envelope = attach_document_evidence_records(run_evidence, (record,))

    assert envelope.run_evidence.schema_version == "evidence.v2"
    assert envelope.document_evidence_records == (record,)
    assert "correlation_id" in envelope.run_evidence.trace_join_keys
    encoded = json.loads(envelope.model_dump_json())
    assert encoded["document_evidence_records"][0]["correlation_id"] == "corr-doc-001"


def test_evidence_cli_payload_includes_document_harness_records() -> None:
    from ummaya.evidence.runner import build_evidence_output_payload, run_dataset

    run_evidence = run_dataset(
        scenario_path=Path("evidence/scenarios/national_ax_citizen_requests_v1.yaml"),
        source_ref="test",
    )

    payload = build_evidence_output_payload(
        run_evidence,
        hwp_bridge_probe_env={},
        odf_probe_env={},
        odf_probe_search_path=(),
        odf_probe_importable_modules=frozenset({"odfdo"}),
        pdfa_probe_env={},
        pdfa_probe_search_path=(),
        archive_probe_env={},
        archive_probe_search_path=(),
        passive_probe_env={},
        passive_probe_search_path=(),
        passive_probe_importable_modules=frozenset(),
        legacy_office_probe_env={},
        legacy_office_probe_search_path=(),
    )

    assert payload["schema_version"] == "evidence.v2"
    records = payload["document_evidence_records"]
    assert isinstance(records, list)
    assert records
    assert {record["scenario_id"] for record in records} == {"document_harness_v1"}
    assert all(record["correlation_id"] for record in records)
    lifecycle_records = payload["document_lifecycle_records"]
    assert {record["stage"] for record in lifecycle_records} >= {
        "intake",
        "classification",
        "capability",
        "adapter_selection",
        "permission",
        "mutation",
        "render",
        "reread",
        "validation",
        "diff",
        "tui_frame",
    }
    assert payload["document_beta_cases"]
    assert payload["document_negative_cases"]
    authoring_cases = payload["document_authoring_cases"]
    assert {case["scenario_class"] for case in authoring_cases} == {
        "public_form_completion",
        "narrative_authoring",
        "unsupported_plausible_writing",
        "protected_field",
        "direct_hwp_path",
        "render_comparison",
    }
    assert any(
        case["scenario_class"] == "render_comparison" and case["render_comparison_required"] is True
        for case in authoring_cases
    )
    assert any(
        case["scenario_class"] == "direct_hwp_path" and case["hwp_direct_write_state"] == "blocked"
        for case in authoring_cases
    )
    bridge_records = payload["document_bridge_probe_records"]
    assert bridge_records == [
        {
            "candidate_id": "hwpforge-cli-convert-hwp5",
            "status": "missing",
            "source_format": "hwp",
            "output_format": "hwpx",
            "executable": None,
            "recommended_args": [
                "--json",
                "convert-hwp5",
                "{source}",
                "--output",
                "{output}",
            ],
            "recommended_env": {
                "UMMAYA_HWP_TO_HWPX_CONVERTER_ARGS_JSON": (
                    '["--json", "convert-hwp5", "{source}", "--output", "{output}"]'
                ),
                "UMMAYA_HWP_TO_HWPX_CONVERTER_ENGINE_ID": "hwpforge-cli-convert-hwp5",
                "UMMAYA_HWP_TO_HWPX_CONVERTER_TIMEOUT_SECONDS": "120",
            },
            "reasons": ["hwpforge_cli_not_found"],
            "evidence_refs": [
                "upstream:hwpforge-cli-v0.6.0-convert-hwp5",
                "adr:docs/adr/ADR-011-hwp-conversion-bridge.md",
            ],
        }
    ]
    odf_records = payload["document_odf_probe_records"]
    assert len(odf_records) == 3
    assert {record["known_format"] for record in odf_records} == {"odt", "ods", "odp"}
    assert {record["status"] for record in odf_records} == {"promoted_bounded"}
    assert {record["read_adapter_id"] for record in odf_records} == {"odfdo-document-adapter"}
    assert {record["writer_package"] for record in odf_records} == {"odfdo"}
    assert all(record["writer_available"] for record in odf_records)
    assert all(not record["render_oracle_available"] for record in odf_records)
    assert all("odf_runtime_promoted_bounded" in record["reasons"] for record in odf_records)
    assert all("odfdo_package_registered" in record["reasons"] for record in odf_records)
    assert all("libreoffice_layout_oracle_deferred" in record["reasons"] for record in odf_records)
    assert all(
        "upstream:oasis-open-document-v1.4" in record["evidence_refs"] for record in odf_records
    )
    pdfa_records = payload["document_pdfa_probe_records"]
    assert len(pdfa_records) == 1
    assert pdfa_records[0]["known_format"] == "pdfa"
    assert pdfa_records[0]["runtime_format"] == "pdf"
    assert pdfa_records[0]["status"] == "blocked"
    assert pdfa_records[0]["validator_id"] == "verapdf-pdfa-conformance-validator"
    assert not pdfa_records[0]["validator_available"]
    assert "pdfa_runtime_aliases_pdf_adapter" in pdfa_records[0]["reasons"]
    assert "pdfa_conformance_write_not_promoted" in pdfa_records[0]["reasons"]
    assert "pypdf_pdfa_conformance_not_claimed" in pdfa_records[0]["reasons"]
    assert "verapdf_cli_not_found" in pdfa_records[0]["reasons"]
    assert "upstream:verapdf-cli-validation" in pdfa_records[0]["evidence_refs"]
    archive_records = payload["document_archive_probe_records"]
    assert len(archive_records) == 5
    assert {record["known_format"] for record in archive_records} == {
        "epub",
        "zip",
        "7z",
        "tar",
        "gz",
    }
    archive_by_format = {record["known_format"]: record for record in archive_records}
    assert archive_by_format["zip"]["status"] == "candidate_available"
    assert archive_by_format["zip"]["container_runtime_id"] == "python-stdlib-zipfile"
    assert archive_by_format["zip"]["child_routing_available"]
    assert "archive_child_derivative_promoted" in archive_by_format["zip"]["reasons"]
    assert "no_in_place_archive_mutation" in archive_by_format["zip"]["reasons"]
    assert archive_by_format["7z"]["status"] == "blocked"
    assert not archive_by_format["7z"]["runtime_available"]
    assert archive_by_format["7z"]["container_runtime_id"] == "libarchive-bsdtar-7zip"
    assert "bsdtar_7zip_runtime_not_found" in archive_by_format["7z"]["reasons"]
    assert all(
        "upstream:owasp-file-upload-archive-limits" in record["evidence_refs"]
        for record in archive_records
    )
    passive_records = payload["document_passive_probe_records"]
    assert len(passive_records) == 16
    passive_by_format = {record["known_format"]: record for record in passive_records}
    assert passive_by_format["png"]["status"] == "blocked"
    assert "tesseract_cli_not_found" in passive_by_format["png"]["reasons"]
    assert passive_by_format["mp3"]["status"] == "blocked"
    assert "ffprobe_cli_not_found" in passive_by_format["mp3"]["reasons"]
    assert passive_by_format["shp"]["status"] == "blocked"
    assert "geospatial_runtime_not_found" in passive_by_format["shp"]["reasons"]
    assert "py" not in passive_by_format
    legacy_records = payload["document_legacy_office_probe_records"]
    assert len(legacy_records) == 3
    assert {record["known_format"] for record in legacy_records} == {"doc", "xls", "ppt"}
    assert {record["output_format"] for record in legacy_records} == {
        "docx",
        "xlsx",
        "pptx",
    }
    assert {record["status"] for record in legacy_records} == {"blocked"}
    assert {record["read_adapter_id"] for record in legacy_records} == {
        "legacy-office-metadata-only-adapter"
    }
    assert all(not record["converter_available"] for record in legacy_records)
    assert all(
        "legacy_office_runtime_not_promoted" in record["reasons"] for record in legacy_records
    )
    assert all("libreoffice_cli_not_found" in record["reasons"] for record in legacy_records)
    ppt_probe = next(record for record in legacy_records if record["known_format"] == "ppt")
    assert ppt_probe["converter_id"] == ("microsoft-powerpoint-applescript-ppt-to-pptx-unverified")
    assert (
        "microsoft_powerpoint_app_found_but_applescript_bridge_unverified" in ppt_probe["reasons"]
        or "microsoft_powerpoint_app_or_osascript_not_found_for_ppt" in ppt_probe["reasons"]
    )
    completion = payload["document_format_completion_audit"]
    assert completion["all_formats_complete"] is False
    assert completion["complete_formats"] == [
        "hwpx",
        "hml",
        "owpml",
        "docx",
        "xlsx",
        "pptx",
        "pdf",
        "odt",
        "ods",
        "odp",
        "html",
        "htm",
        "txt",
        "rtf",
        "md",
        "epub",
        "csv",
        "tsv",
        "xml",
        "rdf",
        "ttl",
        "lod",
        "json",
        "jsonl",
        "yaml",
        "yml",
        "geojson",
        "gpx",
        "kml",
        "fasta",
        "sgml",
        "dtd",
        "py",
        "png",
        "jpg",
        "jpeg",
        "gif",
        "tif",
        "tiff",
        "bmp",
        "webp",
        "shp",
        "shx",
        "dbf",
        "prj",
        "stl",
        "wav",
        "mp3",
        "mp4",
        "zip",
        "7z",
        "tar",
        "gz",
        "etc",
    ]
    assert "hwp" in completion["incomplete_formats"]
    assert "odt" not in completion["incomplete_formats"]
    assert "doc" in completion["incomplete_formats"]
    assert "png" not in completion["incomplete_formats"]
    assert "mp3" not in completion["incomplete_formats"]
    assert "shp" not in completion["incomplete_formats"]
    completion_records = completion["records"]
    assert len(completion_records) > len(completion["complete_formats"])
    assert {
        record["known_format"]: record["completion_state"]
        for record in completion_records
        if record["known_format"]
        in {
            "hwp",
            "odt",
            "html",
            "doc",
            "pdfa",
            "csv",
            "py",
            "png",
            "shp",
            "mp3",
            "zip",
            "7z",
        }
    } == {
        "hwp": "probe_blocked",
        "odt": "write_render_save_promoted",
        "html": "write_render_save_promoted",
        "doc": "probe_blocked",
        "pdfa": "probe_blocked",
        "csv": "write_render_save_promoted",
        "py": "write_render_save_promoted",
        "png": "attachment_derivative_write_render_save_promoted",
        "shp": "attachment_derivative_write_render_save_promoted",
        "mp3": "attachment_derivative_write_render_save_promoted",
        "zip": "write_render_save_promoted",
        "7z": "write_render_save_promoted",
    }


def test_evidence_payload_discovers_local_hwpxjs_bridge_from_project_node_bin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ummaya.evidence.runner import build_evidence_output_payload, run_dataset

    repo_root = Path(__file__).resolve().parents[2]
    node_bin = tmp_path / "node_modules" / ".bin"
    node_bin.mkdir(parents=True)
    hwpxjs = node_bin / "hwpxjs"
    hwpxjs.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    hwpxjs.chmod(0o755)
    monkeypatch.chdir(tmp_path)

    run_evidence = run_dataset(
        scenario_path=repo_root / "evidence/scenarios/national_ax_citizen_requests_v1.yaml",
        source_ref="test",
    )

    payload = build_evidence_output_payload(
        run_evidence,
        odf_probe_env={},
        odf_probe_search_path=(),
        odf_probe_importable_modules=frozenset({"odfdo"}),
        legacy_office_probe_env={},
        legacy_office_probe_search_path=(),
    )

    bridge_record = payload["document_bridge_probe_records"][0]
    assert bridge_record["candidate_id"] == "hwpxjs-cli-convert-hwp"
    assert bridge_record["status"] == "available"
    assert bridge_record["executable"] == str(hwpxjs.resolve())
    assert bridge_record["recommended_args"] == ["convert:hwp", "{source}", "{output}"]
    assert "hwpxjs_cli_found_for_default_registration" in bridge_record["reasons"]
