# SPDX-License-Identifier: Apache-2.0
"""Diagnostics for PDF/A conformance promotion candidates."""

from __future__ import annotations

from pathlib import Path

from ummaya.tools.documents.adapter_registry import build_default_document_adapter_registry
from ummaya.tools.documents.models import DocumentFormat, KnownDocumentFormat
from ummaya.tools.documents.pdfa_conformance import (
    PDFA_EXPORTER_ID,
    PDFA_VALIDATOR_ID,
    LocalPdfaConformanceBridge,
)
from ummaya.tools.documents.pdfa_promotion_probe import probe_pdfa_promotion


def test_probe_reports_pdfa_as_conformance_blocked_without_verapdf() -> None:
    report = probe_pdfa_promotion(env={}, search_path=())

    assert report.known_format is KnownDocumentFormat.pdfa
    assert report.runtime_format is DocumentFormat.pdf
    assert report.status == "blocked"
    assert report.validator_id == "verapdf-pdfa-conformance-validator"
    assert report.exporter_id == "ghostscript-pdfa2b-pdfwrite-exporter"
    assert not report.validator_available
    assert not report.exporter_available
    assert report.validator_executable is None
    assert report.exporter_executable is None
    assert "pdfa_runtime_aliases_pdf_adapter" in report.reasons
    assert "pdfa_conformance_write_not_promoted" in report.reasons
    assert "pypdf_pdfa_conformance_not_claimed" in report.reasons
    assert "verapdf_cli_not_found" in report.reasons
    assert "ghostscript_pdfa_exporter_not_found" in report.reasons
    assert "upstream:verapdf-cli-validation" in report.evidence_refs
    assert "upstream:ghostscript-pdfa-pdfwrite" in report.evidence_refs

    registry = build_default_document_adapter_registry()

    assert registry.require_known(KnownDocumentFormat.pdfa).promoted_formats == (
        DocumentFormat.pdf,
    )


def test_probe_detects_verapdf_cli_without_ghostscript_exporter_as_blocked(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "verapdf"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)

    report = probe_pdfa_promotion(env={}, search_path=(str(tmp_path),))

    assert report.status == "blocked"
    assert report.validator_available
    assert report.validator_executable == executable.resolve()
    assert not report.exporter_available
    assert "verapdf_cli_found" in report.reasons
    assert "ghostscript_pdfa_exporter_not_found" in report.reasons
    assert "pdfa_conformance_write_not_promoted" in report.reasons


def test_probe_promotes_candidate_when_verapdf_and_ghostscript_assets_exist(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    verapdf = _write_executable(bin_dir / "verapdf", "exit 0\n")
    ghostscript = _write_executable(bin_dir / "gs", "exit 0\n")
    asset_root = tmp_path / "share" / "ghostscript"
    (asset_root / "lib").mkdir(parents=True)
    (asset_root / "iccprofiles").mkdir(parents=True)
    pdfa_def = asset_root / "lib" / "PDFA_def.ps"
    srgb_icc = asset_root / "iccprofiles" / "srgb.icc"
    pdfa_def.write_text("% PDF/A prefix\n", encoding="utf-8")
    srgb_icc.write_bytes(b"icc")

    report = probe_pdfa_promotion(env={}, search_path=(str(bin_dir),))

    assert report.status == "candidate_available"
    assert report.validator_id == PDFA_VALIDATOR_ID
    assert report.exporter_id == PDFA_EXPORTER_ID
    assert report.validator_available
    assert report.exporter_available
    assert report.validator_executable == verapdf.resolve()
    assert report.exporter_executable == ghostscript.resolve()
    assert report.pdfa_def_path == pdfa_def.resolve()
    assert report.srgb_icc_path == srgb_icc.resolve()
    assert "pdfa_postwrite_conformance_gate_available" in report.reasons


def test_local_pdfa_bridge_exports_and_validates_payload_with_pinned_clis(
    tmp_path: Path,
) -> None:
    ghostscript = _write_executable(
        tmp_path / "gs",
        "\n".join(
            [
                'for arg in "$@"; do',
                '  case "$arg" in',
                '    -sOutputFile=*) out="${arg#-sOutputFile=}" ;;',
                "  esac",
                "done",
                "printf '%s\\n' '%PDF-1.7' '1 0 obj <<>> endobj' '%%EOF' > \"$out\"",
                "",
            ]
        ),
    )
    verapdf = _write_executable(tmp_path / "verapdf", 'echo "PASS $4 2b"\n')
    pdfa_def = tmp_path / "PDFA_def.ps"
    srgb_icc = tmp_path / "srgb.icc"
    pdfa_def.write_text("% PDF/A prefix\n", encoding="utf-8")
    srgb_icc.write_bytes(b"icc")
    bridge = LocalPdfaConformanceBridge(
        ghostscript_executable=ghostscript,
        verapdf_executable=verapdf,
        pdfa_def_path=pdfa_def,
        srgb_icc_path=srgb_icc,
    )

    result = bridge.export_pdfa(b"%PDF-1.7\n%%EOF\n")

    assert result.payload.startswith(b"%PDF-")
    assert result.report.exporter_id == PDFA_EXPORTER_ID
    assert result.report.validator_id == PDFA_VALIDATOR_ID
    assert result.report.pdfa_flavour == "2b"
    assert result.report.byte_size == len(result.payload)
    assert "PASS" in result.report.summary


def _write_executable(path: Path, body: str) -> Path:
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path
