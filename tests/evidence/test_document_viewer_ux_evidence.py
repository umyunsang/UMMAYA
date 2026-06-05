# SPDX-License-Identifier: Apache-2.0
"""Evidence Fabric UX records for local document viewer captures."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import zlib
from pathlib import Path

import pytest

PNG_BYTES: bytes
BLANK_PNG_BYTES: bytes


def test_document_viewer_ux_capture_records_playwright_png_join_metadata(
    tmp_path: Path,
) -> None:
    from ummaya.evidence.document_viewer_ux import capture_document_viewer_ux_artifact

    viewer_html = _write_viewer(tmp_path)

    def fake_playwright_capture(*, viewer_url: str, output_path: Path) -> None:
        assert viewer_url.startswith("http://127.0.0.1:")
        output_path.write_bytes(PNG_BYTES)

    artifact = capture_document_viewer_ux_artifact(
        viewer_html_path=viewer_html,
        output_dir=tmp_path / "ux",
        source_ref="test-source",
        correlation_id="corr-doc-render-001",
        capture=fake_playwright_capture,
    )

    encoded = artifact.model_dump(mode="json")

    assert encoded["capture_tool"] == "playwright"
    assert encoded["viewer_artifact_id"] == "document-viewer-test"
    assert encoded["mode"] == "compact"
    assert encoded["correlation_id"] == "corr-doc-render-001"
    assert encoded["document_diff_id"] == "diff-hwpx-001"
    assert encoded["source_render_artifact_id"] == "render-after-001"
    assert encoded["baseline_render_artifact_id"] == "render-before-001"
    assert encoded["change_ids"] == ["change-001"]
    assert encoded["viewport_rect"] == {"x": 10.0, "y": 20.0, "width": 240.0, "height": 140.0}
    assert encoded["screenshot_sha256"] == hashlib.sha256(PNG_BYTES).hexdigest()
    assert encoded["frame_hash"] == f"sha256:{hashlib.sha256(PNG_BYTES).hexdigest()}"
    assert Path(encoded["screenshot_path"]).exists()
    assert "html" not in encoded
    assert "document_bytes" not in json.dumps(encoded)


def test_document_viewer_ux_capture_rejects_blank_playwright_png(tmp_path: Path) -> None:
    from ummaya.evidence.document_viewer_ux import (
        DocumentViewerUxEvidenceError,
        capture_document_viewer_ux_artifact,
    )

    viewer_html = _write_viewer(tmp_path)

    def fake_blank_capture(*, viewer_url: str, output_path: Path) -> None:
        del viewer_url
        output_path.write_bytes(BLANK_PNG_BYTES)

    with pytest.raises(DocumentViewerUxEvidenceError, match="blank"):
        capture_document_viewer_ux_artifact(
            viewer_html_path=viewer_html,
            output_dir=tmp_path / "ux",
            source_ref="test-source",
            correlation_id="corr-doc-render-001",
            capture=fake_blank_capture,
        )


def test_evidence_payload_can_attach_document_viewer_ux_artifacts(tmp_path: Path) -> None:
    from ummaya.evidence.document_viewer_ux import capture_document_viewer_ux_artifact
    from ummaya.evidence.runner import build_evidence_output_payload, run_dataset

    viewer_html = _write_viewer(tmp_path)

    def fake_playwright_capture(*, viewer_url: str, output_path: Path) -> None:
        del viewer_url
        output_path.write_bytes(PNG_BYTES)

    ux_artifact = capture_document_viewer_ux_artifact(
        viewer_html_path=viewer_html,
        output_dir=tmp_path / "ux",
        source_ref="test-source",
        correlation_id="corr-doc-hwpx-001",
        capture=fake_playwright_capture,
    )
    evidence = run_dataset(
        scenario_path=Path("evidence/scenarios/national_ax_citizen_requests_v1.yaml"),
        source_ref="test",
    )

    payload = build_evidence_output_payload(
        evidence,
        document_viewer_ux_artifacts=(ux_artifact,),
    )

    ux_records = payload["ux_artifacts"]
    assert ux_records[0]["artifact_kind"] == "document_viewer_png"
    assert ux_records[0]["document_diff_id"] == "diff-hwpx-001"
    assert ux_records[0]["viewer_manifest_path"].endswith("viewer-manifest.json")
    assert ux_records[0]["frame_hash"].startswith("sha256:")
    assert next(gate for gate in payload["gates"] if gate["name"] == "ux")["status"] == "pass"


def test_evidence_payload_rejects_unjoined_document_viewer_ux_artifact(
    tmp_path: Path,
) -> None:
    from ummaya.evidence.document_harness import DocumentHarnessEvidenceError
    from ummaya.evidence.document_viewer_ux import DocumentViewerUxArtifact
    from ummaya.evidence.runner import build_evidence_output_payload, run_dataset

    evidence = run_dataset(
        scenario_path=Path("evidence/scenarios/national_ax_citizen_requests_v1.yaml"),
        source_ref="test",
    )
    ux_artifact = DocumentViewerUxArtifact(
        artifact_id="ux-unjoined",
        source_ref="test-source",
        viewer_artifact_id="document-viewer-test",
        mode="compact",
        correlation_id="corr-doc-hwpx-001",
        document_diff_id="diff-not-in-scenario",
        viewer_html_path=str(tmp_path / "viewer.html"),
        viewer_manifest_path=str(tmp_path / "viewer-manifest.json"),
        screenshot_path=str(tmp_path / "capture.png"),
        screenshot_sha256="1" * 64,
        frame_hash=f"sha256:{'1' * 64}",
        page_index=0,
        source_render_artifact_id="render-after-001",
        baseline_render_artifact_id="render-before-001",
        viewport_rect={"x": 10.0, "y": 20.0, "width": 240.0, "height": 140.0},
        change_ids=("change-001",),
        local_only=True,
    )

    with pytest.raises(DocumentHarnessEvidenceError, match="does not join"):
        build_evidence_output_payload(
            evidence,
            document_viewer_ux_artifacts=(ux_artifact,),
        )


def test_evidence_cli_accepts_document_viewer_html_argument(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    from pytest import MonkeyPatch

    from ummaya.evidence.document_viewer_ux import DocumentViewerUxArtifact
    from ummaya.evidence.runner import main

    typed_monkeypatch = monkeypatch
    assert isinstance(typed_monkeypatch, MonkeyPatch)
    viewer_html = _write_viewer(tmp_path)
    out_path = tmp_path / "run.json"

    def fake_capture_document_viewer_ux_artifact(
        *,
        viewer_html_path: Path,
        output_dir: Path,
        source_ref: str,
        correlation_id: str | None = None,
        document_diff_id: str | None = None,
    ) -> DocumentViewerUxArtifact:
        del output_dir
        return DocumentViewerUxArtifact(
            artifact_id="ux-document-viewer-test",
            source_ref=source_ref,
            viewer_artifact_id="document-viewer-test",
            mode="compact",
            correlation_id=correlation_id or "corr-doc-hwpx-001",
            document_diff_id=document_diff_id or "diff-hwpx-001",
            viewer_html_path=str(viewer_html_path),
            viewer_manifest_path=str(viewer_html_path.parent / "viewer-manifest.json"),
            screenshot_path=str(tmp_path / "capture.png"),
            screenshot_sha256="1" * 64,
            frame_hash=f"sha256:{'1' * 64}",
            page_index=0,
            source_render_artifact_id="render-after-001",
            baseline_render_artifact_id="render-before-001",
            viewport_rect={"x": 10.0, "y": 20.0, "width": 240.0, "height": 140.0},
            change_ids=("change-001",),
            local_only=True,
        )

    typed_monkeypatch.setattr(
        "ummaya.evidence.document_viewer_ux.capture_document_viewer_ux_artifact",
        fake_capture_document_viewer_ux_artifact,
    )
    typed_monkeypatch.setattr(
        "sys.argv",
        [
            "python -m ummaya.evidence",
            "--source-ref",
            "cli-test",
            "--document-viewer-html",
            str(viewer_html),
            "--document-viewer-ux-out-dir",
            str(tmp_path / "ux"),
            "--out",
            str(out_path),
        ],
    )

    main()

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["ux_artifacts"][0]["viewer_artifact_id"] == "document-viewer-test"
    assert next(gate for gate in payload["gates"] if gate["name"] == "ux")["status"] == "pass"


def test_playwright_cli_capture_uses_socket_safe_session_names(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    from pytest import MonkeyPatch

    from ummaya.evidence.document_viewer_ux import capture_with_playwright_cli

    typed_monkeypatch = monkeypatch
    assert isinstance(typed_monkeypatch, MonkeyPatch)
    codex_home = tmp_path / "codex-home"
    wrapper = codex_home / "skills" / "playwright" / "scripts" / "playwright_cli.sh"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    commands: list[tuple[str, ...]] = []

    def fake_run(
        command: tuple[str, ...],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        env: dict[str, str],
    ) -> subprocess.CompletedProcess[str]:
        del check, capture_output, text, env
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    typed_monkeypatch.setenv("CODEX_HOME", str(codex_home))
    typed_monkeypatch.setattr("subprocess.run", fake_run)

    capture_with_playwright_cli(
        viewer_url="file:///tmp/document-viewer-test/viewer.html",
        output_path=tmp_path / "capture.png",
    )

    session_args = [
        arg.removeprefix("-s=") for command in commands for arg in command if arg.startswith("-s=")
    ]
    assert session_args
    assert all(len(session) <= 24 for session in session_args)


def _write_viewer(tmp_path: Path) -> Path:
    viewer_dir = tmp_path / "document-viewer-test"
    viewer_dir.mkdir()
    viewer_html = viewer_dir / "viewer.html"
    viewer_html.write_text("<!doctype html><title>Document viewer</title>", encoding="utf-8")
    (viewer_dir / "viewer-manifest.json").write_text(
        json.dumps(
            {
                "viewer_artifact_id": "document-viewer-test",
                "mode": "compact",
                "page_index": 0,
                "correlation_id": "corr-doc-hwpx-001",
                "document_diff_id": "diff-hwpx-001",
                "source_render_artifact_id": "render-after-001",
                "baseline_render_artifact_id": "render-before-001",
                "viewport_rect": {"x": 10, "y": 20, "width": 240, "height": 140},
                "change_ids": ["change-001"],
                "local_only": True,
            }
        ),
        encoding="utf-8",
    )
    return viewer_html


def _single_pixel_png(rgb: tuple[int, int, int]) -> bytes:
    raw = b"\x00" + bytes(rgb)
    payload = b"".join(
        (
            _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)),
            _png_chunk(b"IDAT", zlib.compress(raw)),
            _png_chunk(b"IEND", b""),
        )
    )
    return b"\x89PNG\r\n\x1a\n" + payload


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type)
    crc = zlib.crc32(data, crc)
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc & 0xFFFFFFFF)


PNG_BYTES = _single_pixel_png((0, 0, 0))
BLANK_PNG_BYTES = _single_pixel_png((255, 255, 255))
