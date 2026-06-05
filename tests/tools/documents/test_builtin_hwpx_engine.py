# SPDX-License-Identifier: Apache-2.0
"""Default HWPX package-text engine regression tests."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from collections.abc import Set as AbstractSet
from decimal import Decimal
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest

from ummaya.tools.documents.engines import DocumentEngineRegistry
from ummaya.tools.documents.formats.hwpx import HwpXDocumentAdapter, HwpXPackageTextEngine
from ummaya.tools.documents.models import (
    BorderDescriptor,
    DocumentFormat,
    DocumentPatch,
    DocumentPatchOperation,
    OperationType,
    StyleDescriptor,
    ToolResultStatus,
)
from ummaya.tools.documents.registry import DocumentToolRuntime, register_document_tools
from ummaya.tools.documents.tool_defs import (
    DocumentApplyFillRequest,
    DocumentCopyForEditRequest,
    DocumentExtractRequest,
    DocumentFieldPatch,
    DocumentInspectRequest,
    DocumentLocator,
    DocumentPrimitiveRequest,
    DocumentRenderRequest,
    DocumentStylePatch,
)
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.registry import ToolRegistry


def test_default_runtime_inspects_hwpx_with_package_text_engine(tmp_path: Path) -> None:
    source = _write_hwpx_fixture(tmp_path / "weekly.hwpx")
    runtime = DocumentToolRuntime(session_id="hwpx-inspect", artifact_root=tmp_path / "store")

    result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="hwpx-inspect",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwpx),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert result.extraction is not None
    assert result.extraction.metadata["engine_id"] == "hwpx-package-text"
    assert [paragraph.text for paragraph in result.extraction.paragraphs][:3] == [
        "12 주차 ",
        "2026.05.25 ~ 2026.05.31",
        "기존 특이사항",
    ]
    assert result.extraction.fields[0].path == "/hwpx/text[1]"


def test_default_runtime_extracts_hwpx_style_map_and_text_style_refs(
    tmp_path: Path,
) -> None:
    source = _write_hwpx_styled_fixture(tmp_path / "styled.hwpx")
    runtime = DocumentToolRuntime(session_id="hwpx-style-map", artifact_root=tmp_path / "store")

    result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="hwpx-style-map",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwpx),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert result.extraction is not None
    extraction = result.extraction
    styles_by_id = {style.style_id: style for style in extraction.style_map}
    assert styles_by_id["charPr-3"].font_family == "맑은 고딕"
    assert styles_by_id["charPr-3"].font_size_pt is not None
    assert styles_by_id["charPr-3"].font_size_pt.to_eng_string() == "12"
    assert styles_by_id["charPr-3"].bold is True
    assert styles_by_id["charPr-3"].font_color_rgb == "005BAC"
    assert styles_by_id["paraPr-2"].alignment == "center"
    assert styles_by_id["style-7"].font_family == "맑은 고딕"
    assert styles_by_id["style-7"].alignment == "center"
    assert extraction.paragraphs[0].style_id == "charPr-3"
    style_map_count = extraction.metadata["style_map_count"]
    assert isinstance(style_map_count, int)
    assert style_map_count >= 3


def test_hwpx_native_paragraph_style_mutation_round_trips(tmp_path: Path) -> None:
    source = _write_hwpx_styled_fixture(tmp_path / "styled.hwpx")
    derivative = tmp_path / "styled-out.hwpx"
    engine = HwpXPackageTextEngine()

    derivative.write_bytes(
        engine.apply_patch(
            source,
            DocumentPatch(
                patch_id="hwpx-paragraph-style",
                target_artifact_id="source-hwpx",
                dry_run=False,
                expected_format=DocumentFormat.hwpx,
                destination_policy="working_copy",
                operations=[
                    DocumentPatchOperation(
                        operation_id="style-title",
                        operation_type=OperationType.set_paragraph_style,
                        target_path="/hwpx/text[1]",
                        style=StyleDescriptor(
                            style_id="requested-title-style",
                            target_path="/hwpx/text[1]",
                            font_family="Malgun Gothic",
                            font_size_pt=Decimal("14"),
                            bold=True,
                            font_color_rgb="1F4E79",
                            fill_color_rgb="FFF2CC",
                            alignment="right",
                        ),
                    )
                ],
            ),
        )
    )

    with ZipFile(derivative) as archive:
        header_xml = archive.read("Contents/header.xml").decode("utf-8")
        section_xml = archive.read("Contents/section0.xml").decode("utf-8")
    assert "Malgun Gothic" in header_xml
    assert "<hh:charPr" in header_xml
    assert "<hh:paraPr" in header_xml
    assert "<hh:borderFill" in header_xml
    assert 'charPrIDRef="' in section_xml
    assert 'paraPrIDRef="' in section_xml
    assert 'styleIDRef="' in section_xml

    extraction = engine.inspect(derivative, artifact_id="hwpx-styled-out")
    assert extraction.paragraphs[0].text == "공식서식 제목"
    matching_styles = [
        style
        for style in extraction.style_map
        if style.font_family == "Malgun Gothic" and style.font_size_pt == Decimal("14")
    ]
    assert any(style.bold is True for style in matching_styles)
    assert any(style.font_color_rgb == "1F4E79" for style in matching_styles)
    assert any(style.fill_color_rgb == "FFF2CC" for style in matching_styles)
    assert any(style.alignment == "right" for style in extraction.style_map)


def test_hwpx_native_style_mutation_preserves_archive_invariants(tmp_path: Path) -> None:
    source = _write_hwpx_styled_fixture(tmp_path / "styled.hwpx")
    derivative = tmp_path / "styled-preserved.hwpx"
    engine = HwpXPackageTextEngine()
    before = _hwpx_archive_payloads(source)

    derivative.write_bytes(
        engine.apply_patch(
            source,
            DocumentPatch(
                patch_id="hwpx-archive-invariants",
                target_artifact_id="source-hwpx",
                dry_run=False,
                expected_format=DocumentFormat.hwpx,
                destination_policy="working_copy",
                operations=[
                    DocumentPatchOperation(
                        operation_id="style-title",
                        operation_type=OperationType.set_paragraph_style,
                        target_path="/hwpx/text[1]",
                        style=StyleDescriptor(
                            style_id="archive-invariant-style",
                            target_path="/hwpx/text[1]",
                            font_family="Malgun Gothic",
                            font_size_pt=Decimal("14"),
                            bold=True,
                            font_color_rgb="1F4E79",
                            fill_color_rgb="FFF2CC",
                            alignment="right",
                        ),
                    )
                ],
            ),
        )
    )

    after = _hwpx_archive_payloads(derivative)
    assert tuple(after) == tuple(before)
    assert after["mimetype"] == before["mimetype"]
    assert after["version.xml"] == before["version.xml"]
    assert after["META-INF/manifest.xml"] == before["META-INF/manifest.xml"]
    assert after["Preview/PrvText.txt"] == before["Preview/PrvText.txt"]
    assert after["Contents/header.xml"] != before["Contents/header.xml"]
    assert after["Contents/section0.xml"] != before["Contents/section0.xml"]


def test_hwpx_package_rewrite_normalizes_mimetype_order_and_storage(tmp_path: Path) -> None:
    source = _write_hwpx_fixture(tmp_path / "nonconformant-order.hwpx")
    payloads = _hwpx_archive_payloads(source)
    with ZipFile(source, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("version.xml", payloads["version.xml"])
        archive.writestr("mimetype", payloads["mimetype"])
        archive.writestr("Contents/header.xml", payloads["Contents/header.xml"])
        archive.writestr("Contents/section0.xml", payloads["Contents/section0.xml"])
        archive.writestr("META-INF/manifest.xml", payloads["META-INF/manifest.xml"])
        archive.writestr("Preview/PrvText.txt", payloads["Preview/PrvText.txt"])
    derivative = tmp_path / "normalized.hwpx"
    engine = HwpXPackageTextEngine()

    derivative.write_bytes(
        engine.apply_patch(
            source,
            DocumentPatch(
                patch_id="patch-normalize-mimetype-order-storage",
                target_artifact_id="artifact-working",
                expected_format=DocumentFormat.hwpx,
                destination_policy="working_copy",
                dry_run=False,
                operations=[
                    DocumentPatchOperation(
                        operation_id="set-week",
                        operation_type=OperationType.replace_text,
                        target_path="/hwpx/text[1]",
                        value="13 주차",
                    )
                ],
            ),
        )
    )

    with ZipFile(derivative) as archive:
        assert archive.namelist()[:2] == ["mimetype", "version.xml"]
        assert archive.getinfo("mimetype").compress_type == ZIP_STORED
        assert archive.read("mimetype") == b"application/owpml"


def test_hwpx_native_run_style_mutation_round_trips(tmp_path: Path) -> None:
    source = _write_hwpx_styled_fixture(tmp_path / "styled-run.hwpx")
    derivative = tmp_path / "styled-run-out.hwpx"
    engine = HwpXPackageTextEngine()

    derivative.write_bytes(
        engine.apply_patch(
            source,
            DocumentPatch(
                patch_id="hwpx-run-style",
                target_artifact_id="source-hwpx",
                dry_run=False,
                expected_format=DocumentFormat.hwpx,
                destination_policy="working_copy",
                operations=[
                    DocumentPatchOperation(
                        operation_id="style-title-run",
                        operation_type=OperationType.set_run_style,
                        target_path="/hwpx/text[1]",
                        style=StyleDescriptor(
                            style_id="requested-run-style",
                            target_path="/hwpx/text[1]",
                            font_family="Malgun Gothic",
                            italic=True,
                            font_color_rgb="C00000",
                        ),
                    )
                ],
            ),
        )
    )

    with ZipFile(derivative) as archive:
        section_xml = archive.read("Contents/section0.xml").decode("utf-8")
    assert 'charPrIDRef="' in section_xml

    extraction = engine.inspect(derivative, artifact_id="hwpx-run-styled-out")
    assert extraction.paragraphs[0].text == "공식서식 제목"
    assert any(
        style.font_family == "Malgun Gothic"
        and style.italic is True
        and style.font_color_rgb == "C00000"
        for style in extraction.style_map
    )


def test_hwpx_native_border_style_mutation_round_trips(tmp_path: Path) -> None:
    source = _write_hwpx_styled_fixture(tmp_path / "styled-border.hwpx")
    derivative = tmp_path / "styled-border-out.hwpx"
    engine = HwpXPackageTextEngine()

    derivative.write_bytes(
        engine.apply_patch(
            source,
            DocumentPatch(
                patch_id="hwpx-border-style",
                target_artifact_id="source-hwpx",
                dry_run=False,
                expected_format=DocumentFormat.hwpx,
                destination_policy="working_copy",
                operations=[
                    DocumentPatchOperation(
                        operation_id="style-title-border",
                        operation_type=OperationType.set_paragraph_style,
                        target_path="/hwpx/text[1]",
                        style=StyleDescriptor(
                            style_id="requested-border-style",
                            target_path="/hwpx/text[1]",
                            border=BorderDescriptor(
                                style="SOLID",
                                width_pt=Decimal("0.50"),
                                color_rgb="4472C4",
                            ),
                        ),
                    )
                ],
            ),
        )
    )

    with ZipFile(derivative) as archive:
        header_xml = archive.read("Contents/header.xml").decode("utf-8")
    assert 'type="SOLID"' in header_xml
    assert 'color="#4472C4"' in header_xml

    extraction = engine.inspect(derivative, artifact_id="hwpx-border-styled-out")
    border_styles = [
        style.border
        for style in extraction.style_map
        if style.border is not None
        and style.border.style == "SOLID"
        and style.border.color_rgb == "4472C4"
    ]
    assert any(
        border.width_pt is not None
        and abs(border.width_pt - Decimal("0.50")) <= Decimal("0.02")
        for border in border_styles
    )


def test_hwpx_native_table_cell_style_mutation_round_trips(tmp_path: Path) -> None:
    source = _write_hwpx_empty_value_table_fixture(tmp_path / "empty-cell-form.hwpx")
    derivative = tmp_path / "empty-cell-form-out.hwpx"
    target_path = "Contents/section0.xml#table[1]/r1c2"
    engine = HwpXPackageTextEngine()

    derivative.write_bytes(
        engine.apply_patch(
            source,
            DocumentPatch(
                patch_id="hwpx-cell-style",
                target_artifact_id="source-hwpx",
                dry_run=False,
                expected_format=DocumentFormat.hwpx,
                destination_policy="working_copy",
                operations=[
                    DocumentPatchOperation(
                        operation_id="fill-team",
                        operation_type=OperationType.set_table_cell,
                        target_path=target_path,
                        value="GovOn AX",
                    ),
                    DocumentPatchOperation(
                        operation_id="style-team",
                        operation_type=OperationType.set_cell_style,
                        target_path=target_path,
                        style=StyleDescriptor(
                            style_id="requested-team-style",
                            target_path=target_path,
                            font_family="Malgun Gothic",
                            font_size_pt=Decimal("12"),
                            bold=True,
                            fill_color_rgb="FFF2CC",
                            alignment="center",
                        ),
                    ),
                ],
            ),
        )
    )

    with ZipFile(derivative) as archive:
        header_xml = archive.read("Contents/header.xml").decode("utf-8")
        section_xml = archive.read("Contents/section0.xml").decode("utf-8")
    assert "Malgun Gothic" in header_xml
    assert 'charPrIDRef="' in section_xml
    assert 'paraPrIDRef="' in section_xml
    assert 'styleIDRef="' in section_xml

    extraction = engine.inspect(derivative, artifact_id="hwpx-cell-styled-out")
    team_cell = extraction.tables[0].cells[1]
    assert team_cell.text == "GovOn AX"
    team_field = next(field for field in extraction.fields if field.label == "팀명")
    assert team_field.current_value == "GovOn AX"
    assert any(
        style.font_family == "Malgun Gothic"
        and style.font_size_pt == Decimal("12")
        and style.bold is True
        for style in extraction.style_map
    )
    assert any(style.fill_color_rgb == "FFF2CC" for style in extraction.style_map)
    assert any(style.alignment == "center" for style in extraction.style_map)


def test_hwpx_native_style_mutation_blocks_unknown_target_path(tmp_path: Path) -> None:
    source = _write_hwpx_styled_fixture(tmp_path / "styled.hwpx")
    derivative = tmp_path / "should-not-exist.hwpx"
    engine = HwpXPackageTextEngine()

    with pytest.raises(ValueError, match="HWPX text target not found"):
        derivative.write_bytes(
            engine.apply_patch(
                source,
                DocumentPatch(
                    patch_id="hwpx-missing-style-target",
                    target_artifact_id="source-hwpx",
                    dry_run=False,
                    expected_format=DocumentFormat.hwpx,
                    destination_policy="working_copy",
                    operations=[
                        DocumentPatchOperation(
                            operation_id="style-missing",
                            operation_type=OperationType.set_paragraph_style,
                            target_path="/hwpx/text[99]",
                            style=StyleDescriptor(
                                style_id="requested-missing-style",
                                target_path="/hwpx/text[99]",
                                font_family="Malgun Gothic",
                                font_size_pt=Decimal("14"),
                            ),
                        )
                    ],
                ),
            )
        )
    assert not derivative.exists()


def test_hwpx_native_style_mutation_renders_rereads_and_saves(
    tmp_path: Path,
) -> None:
    source = _write_rhwp_text_fixture(tmp_path / "styled-runtime.hwpx")
    destination = tmp_path / "styled-runtime-out.hwpx"
    runtime = DocumentToolRuntime(
        session_id="hwpx-style-render-reread-save",
        artifact_root=tmp_path / "store",
    )

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="hwpx-style-render-reread-save",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwpx),
            operation="style",
            instruction=(
                "HWPX 문서 제목 스타일을 Malgun Gothic 14pt 굵게, 글자색 1F4E79, "
                "배경색 FFF2CC, 오른쪽 정렬로 보정하고 저장해줘."
            ),
            styles=(
                DocumentStylePatch(
                    target_path="/hwpx/text[1]",
                    font_family="Malgun Gothic",
                    font_size_pt=Decimal("14"),
                    bold=True,
                    font_color_rgb="1F4E79",
                    fill_color_rgb="FFF2CC",
                    alignment="right",
                ),
            ),
            destination_display_name=destination.name,
            destination_path=str(destination),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert result.diff is not None
    assert result.diff.changes[0].change_type == "style"
    assert result.saved_exports
    assert result.saved_exports[0].local_path == destination.resolve()
    assert result.saved_exports[0].sha256 == hashlib.sha256(destination.read_bytes()).hexdigest()
    assert result.render_artifacts
    assert Path(result.render_artifacts[0].render_path).is_file()

    with ZipFile(destination) as archive:
        assert archive.namelist()[:2] == ["mimetype", "version.xml"]
        assert archive.read("mimetype") in {b"application/owpml", b"application/hwp+zip"}
        assert archive.getinfo("mimetype").compress_type == ZIP_STORED
        header_xml = archive.read("Contents/header.xml").decode("utf-8")
        section_xml = archive.read("Contents/section0.xml").decode("utf-8")
    assert "Malgun Gothic" in header_xml
    assert "<hh:charPr" in header_xml
    assert "<hh:paraPr" in header_xml
    assert "<hh:borderFill" in header_xml
    assert 'charPrIDRef="' in section_xml
    assert 'paraPrIDRef="' in section_xml
    assert 'styleIDRef="' in section_xml

    reread_result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="hwpx-style-render-reread-save-reread",
            document=DocumentLocator(path=str(destination), expected_format=DocumentFormat.hwpx),
        )
    )
    assert reread_result.status is ToolResultStatus.ok
    assert reread_result.extraction is not None
    assert any(
        style.font_family == "Malgun Gothic"
        and style.font_size_pt == Decimal("14")
        and style.bold is True
        and style.font_color_rgb == "1F4E79"
        and style.fill_color_rgb == "FFF2CC"
        for style in reread_result.extraction.style_map
    )
    assert any(style.alignment == "right" for style in reread_result.extraction.style_map)


def test_default_runtime_writes_hwpx_text_nodes_on_working_copy(tmp_path: Path) -> None:
    source = _write_hwpx_fixture(tmp_path / "weekly.hwpx")
    runtime = DocumentToolRuntime(session_id="hwpx-write", artifact_root=tmp_path / "store")

    inspect_result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="hwpx-write",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwpx),
        )
    )
    assert inspect_result.artifact_refs
    copy_result = runtime.copy_for_edit(
        DocumentCopyForEditRequest(
            correlation_id="hwpx-write",
            document=DocumentLocator(artifact_id=inspect_result.artifact_refs[0]),
        )
    )
    assert copy_result.artifact_refs

    fill_result = runtime.apply_fill(
        DocumentApplyFillRequest(
            correlation_id="hwpx-write",
            document=DocumentLocator(artifact_id=copy_result.artifact_refs[-1]),
            patches=(
                DocumentFieldPatch(target_path="/hwpx/text[1]", value="13 주차 "),
                DocumentFieldPatch(
                    target_path="/hwpx/text[2]",
                    value="2026.06.01 ~ 2026.06.07",
                ),
                DocumentFieldPatch(
                    target_path="/hwpx/text[3]",
                    value="공공AX 문서 하네스 HWPX 작성 테스트 완료",
                ),
            ),
        )
    )

    assert fill_result.status is ToolResultStatus.ok
    assert fill_result.artifact_refs
    assert fill_result.diff is not None
    assert [
        (change.target_path, change.before_value, change.after_value)
        for change in fill_result.diff.changes
    ] == [
        ("/hwpx/text[1]", "12 주차 ", "13 주차 "),
        ("/hwpx/text[2]", "2026.05.25 ~ 2026.05.31", "2026.06.01 ~ 2026.06.07"),
        ("/hwpx/text[3]", "기존 특이사항", "공공AX 문서 하네스 HWPX 작성 테스트 완료"),
    ]
    extract_result = runtime.extract(
        DocumentExtractRequest(
            correlation_id="hwpx-write-reread",
            document=DocumentLocator(artifact_id=fill_result.artifact_refs[-1]),
            include_tables=True,
            include_images=True,
            include_fields=True,
        )
    )

    assert extract_result.extraction is not None
    reread_texts = [paragraph.text for paragraph in extract_result.extraction.paragraphs]
    assert reread_texts[:3] == [
        "13 주차 ",
        "2026.06.01 ~ 2026.06.07",
        "공공AX 문서 하네스 HWPX 작성 테스트 완료",
    ]


def test_default_runtime_renders_hwpx_visual_svg_with_workflow(
    tmp_path: Path,
) -> None:
    source = _write_rhwp_text_fixture(tmp_path / "weekly.hwpx")
    runtime = DocumentToolRuntime(session_id="hwpx-render-svg", artifact_root=tmp_path / "store")

    inspect_result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="hwpx-render-svg",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwpx),
        )
    )
    copy_result = runtime.copy_for_edit(
        DocumentCopyForEditRequest(
            correlation_id="hwpx-render-svg",
            document=DocumentLocator(artifact_id=inspect_result.artifact_refs[0]),
        )
    )
    render_result = runtime.render(
        DocumentRenderRequest(
            correlation_id="hwpx-render-svg",
            document=DocumentLocator(artifact_id=copy_result.artifact_refs[-1]),
        )
    )

    assert render_result.status is ToolResultStatus.ok
    assert render_result.blocked_reason is None
    assert render_result.promotion_gate_result is None
    assert render_result.render_artifacts
    first_render = render_result.render_artifacts[0]
    render_path = Path(first_render.render_path)
    assert render_path.suffix == ".svg"
    assert first_render.render_mime_type == "image/svg+xml"
    rendered_svg = render_path.read_text(encoding="utf-8")
    assert rendered_svg.startswith("<svg ")
    assert all(token in rendered_svg for token in (">1<", ">2<", ">주<", ">차<"))
    assert "font-family" in rendered_svg
    assert first_render.engine_id == "rhwp-node-wasm"
    assert [(step.step_id, step.status) for step in render_result.workflow_steps] == [
        ("inspect", "completed"),
        ("field_schema", "completed"),
        ("working_copy", "completed"),
        ("fill_style", "completed"),
        ("diff", "completed"),
        ("render", "completed"),
        ("validate", "pending"),
        ("save", "pending"),
    ]


def test_default_runtime_renders_hwpx_visual_svg_with_clean_changed_viewports(
    tmp_path: Path,
) -> None:
    source = _write_rhwp_text_fixture(tmp_path / "weekly.hwpx")
    runtime = DocumentToolRuntime(
        session_id="hwpx-render-svg-diff",
        artifact_root=tmp_path / "store",
    )

    inspect_result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="hwpx-render-svg-diff",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwpx),
        )
    )
    copy_result = runtime.copy_for_edit(
        DocumentCopyForEditRequest(
            correlation_id="hwpx-render-svg-diff",
            document=DocumentLocator(artifact_id=inspect_result.artifact_refs[0]),
        )
    )
    fill_result = runtime.apply_fill(
        DocumentApplyFillRequest(
            correlation_id="hwpx-render-svg-diff",
            document=DocumentLocator(artifact_id=copy_result.artifact_refs[-1]),
            patches=(DocumentFieldPatch(target_path="/hwpx/text[1]", value="13 주차"),),
        )
    )
    assert fill_result.status is ToolResultStatus.ok

    render_result = runtime.render(
        DocumentRenderRequest(
            correlation_id="hwpx-render-svg-diff",
            document=DocumentLocator(artifact_id=fill_result.artifact_refs[-1]),
        )
    )

    assert render_result.status is ToolResultStatus.ok
    assert render_result.diff is not None
    assert render_result.diff.render_artifacts == render_result.render_artifacts
    assert render_result.diff.baseline_render_artifacts
    assert len(render_result.diff.changed_viewports) == 1
    assert len(render_result.diff.viewport_cameras) == 1
    viewport = render_result.diff.changed_viewports[0]
    camera = render_result.diff.viewport_cameras[0]
    assert viewport.change_ids == ("change-001",)
    assert (
        viewport.source_render_artifact_id == render_result.render_artifacts[0].render_artifact_id
    )
    assert camera.change_ids == viewport.change_ids
    assert camera.viewport_rect == viewport.clip_rect
    assert camera.source_render_artifact_id == render_result.render_artifacts[0].render_artifact_id
    assert (
        camera.baseline_render_artifact_id
        == render_result.diff.baseline_render_artifacts[0].render_artifact_id
    )
    assert (
        viewport.svg_artifact_ref
        == f"viewport-{render_result.render_artifacts[0].render_artifact_id}-change-001"
    )
    assert viewport.svg_artifact_path is not None
    assert viewport.after_svg_artifact_path == viewport.svg_artifact_path
    assert viewport.before_svg_artifact_path is not None
    viewport_svg = Path(viewport.svg_artifact_path)
    assert viewport_svg.is_file()
    assert 'data-ummaya-viewport-id="' in viewport_svg.read_text(encoding="utf-8")
    before_viewport_svg = Path(viewport.before_svg_artifact_path)
    assert before_viewport_svg.is_file()
    assert viewport.anchor_strategy == "exact_text_run"
    assert "+ 13 주차" in viewport.text_fallback
    assert "changed viewport evidence" in render_result.text_summary
    rendered_svg = Path(render_result.render_artifacts[0].render_path).read_text(encoding="utf-8")
    assert 'id="ummaya-diff-overlay"' not in rendered_svg
    assert 'class="ummaya-diff-change"' not in rendered_svg
    assert "<svg" in rendered_svg


def test_default_runtime_extracts_hwpx_table_cells_and_label_value_fields(
    tmp_path: Path,
) -> None:
    source = _write_rhwp_table_fixture(tmp_path / "weekly-table.hwpx")
    runtime = DocumentToolRuntime(session_id="hwpx-table", artifact_root=tmp_path / "store")

    result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="hwpx-table",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwpx),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert result.extraction is not None
    assert len(result.extraction.tables) == 1
    table = result.extraction.tables[0]
    assert [(cell.row_index, cell.column_index, cell.text) for cell in table.cells] == [
        (0, 0, "교과목 분반"),
        (0, 1, "02 분반"),
        (1, 0, "팀명"),
        (1, 1, "GovOn"),
        (2, 0, "특이사항"),
        (2, 1, "기존 특이사항"),
    ]

    course_field = next(field for field in result.extraction.fields if field.label == "교과목 분반")
    team_field = next(field for field in result.extraction.fields if field.label == "팀명")
    note_field = next(field for field in result.extraction.fields if field.label == "특이사항")
    assert course_field.path == "/hwpx/text[2]"
    assert course_field.current_value == "02 분반"
    assert team_field.path == "/hwpx/text[4]"
    assert team_field.current_value == "GovOn"
    assert note_field.path == "/hwpx/text[6]"
    assert note_field.current_value == "기존 특이사항"
    assert result.extraction.metadata["table_count"] == 1


def test_default_runtime_normalizes_hwpx_table_cell_alias_fill_paths(
    tmp_path: Path,
) -> None:
    source = _write_hwpx_table_fixture(tmp_path / "weekly-table.hwpx")
    runtime = DocumentToolRuntime(session_id="hwpx-table-fill", artifact_root=tmp_path / "store")

    inspect_result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="hwpx-table-fill",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwpx),
        )
    )
    copy_result = runtime.copy_for_edit(
        DocumentCopyForEditRequest(
            correlation_id="hwpx-table-fill",
            document=DocumentLocator(artifact_id=inspect_result.artifact_refs[0]),
        )
    )

    fill_result = runtime.apply_fill(
        DocumentApplyFillRequest(
            correlation_id="hwpx-table-fill",
            document=DocumentLocator(artifact_id=copy_result.artifact_refs[-1]),
            patches=(
                DocumentFieldPatch(
                    target_path="/table[1]/cells[2][2]",
                    value="공공AX 문서 하네스 HWPX 작성 테스트 완료",
                ),
            ),
        )
    )

    assert fill_result.status is ToolResultStatus.ok
    assert fill_result.diff is not None
    assert [
        (change.target_path, change.before_value, change.after_value)
        for change in fill_result.diff.changes
    ] == [
        (
            "/hwpx/text[7]",
            "기존 특이사항",
            "공공AX 문서 하네스 HWPX 작성 테스트 완료",
        )
    ]

    extract_result = runtime.extract(
        DocumentExtractRequest(
            correlation_id="hwpx-table-fill-reread",
            document=DocumentLocator(artifact_id=fill_result.artifact_refs[-1]),
            include_tables=True,
            include_images=True,
            include_fields=True,
        )
    )

    assert extract_result.extraction is not None
    note_field = next(
        field for field in extract_result.extraction.fields if field.label == "특이사항"
    )
    assert note_field.path == "/hwpx/text[7]"
    assert note_field.current_value == "공공AX 문서 하네스 HWPX 작성 테스트 완료"


def test_default_runtime_fills_hwpx_empty_table_cell_alias(
    tmp_path: Path,
) -> None:
    source = _write_hwpx_empty_value_table_fixture(tmp_path / "empty-cell-form.hwpx")
    runtime = DocumentToolRuntime(
        session_id="hwpx-empty-table-fill",
        artifact_root=tmp_path / "store",
    )

    inspect_result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="hwpx-empty-table-fill",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwpx),
        )
    )
    assert inspect_result.extraction is not None
    empty_cell = inspect_result.extraction.tables[0].cells[1]
    assert empty_cell.source_path == "Contents/section0.xml#table[1]/r1c2"
    assert empty_cell.text == ""
    assert empty_cell.field_path is None

    copy_result = runtime.copy_for_edit(
        DocumentCopyForEditRequest(
            correlation_id="hwpx-empty-table-fill",
            document=DocumentLocator(artifact_id=inspect_result.artifact_refs[0]),
        )
    )

    fill_result = runtime.apply_fill(
        DocumentApplyFillRequest(
            correlation_id="hwpx-empty-table-fill",
            document=DocumentLocator(artifact_id=copy_result.artifact_refs[-1]),
            patches=(
                DocumentFieldPatch(
                    target_path="/table[1]/cells[1][2]",
                    value="GovOn AX",
                ),
            ),
        )
    )

    assert fill_result.status is ToolResultStatus.ok
    assert fill_result.diff is not None
    change = fill_result.diff.changes[0]
    assert change.change_type == "table_cell"
    assert change.target_path == "Contents/section0.xml#table[1]/r1c2"
    assert change.before_value == ""
    assert change.after_value == "GovOn AX"

    extract_result = runtime.extract(
        DocumentExtractRequest(
            correlation_id="hwpx-empty-table-fill-reread",
            document=DocumentLocator(artifact_id=fill_result.artifact_refs[-1]),
            include_tables=True,
            include_images=True,
            include_fields=True,
        )
    )

    assert extract_result.extraction is not None
    team_cell = extract_result.extraction.tables[0].cells[1]
    assert team_cell.text == "GovOn AX"
    team_field = next(
        field for field in extract_result.extraction.fields if field.label == "팀명"
    )
    assert team_field.path == "/hwpx/text[2]"
    assert team_field.current_value == "GovOn AX"


def test_hwpx_adapter_normalizes_semantic_targets_and_table_cell_aliases(
    tmp_path: Path,
) -> None:
    source = _write_rhwp_table_fixture(tmp_path / "weekly-table.hwpx")
    adapter = HwpXDocumentAdapter()
    extraction = adapter.inspect(source, artifact_id="hwpx-adapter-targets")

    normalized = adapter.normalize_fill_patches(
        (
            DocumentFieldPatch(target_path="team_name", value="GovOn AX"),
            DocumentFieldPatch(
                target_path="/table[1]/cells[3][2]",
                value="공공AX 문서 adapter target resolver 테스트 완료",
            ),
        ),
        extraction=extraction,
    )

    assert [(patch.target_path, patch.value) for patch in normalized] == [
        ("/hwpx/text[4]", "GovOn AX"),
        ("/hwpx/text[6]", "공공AX 문서 adapter target resolver 테스트 완료"),
    ]


def test_hwpx_adapter_preserves_native_table_cell_targets_from_planner(
    tmp_path: Path,
) -> None:
    source = _write_hwpx_empty_value_table_fixture(tmp_path / "empty-cell-form.hwpx")
    adapter = HwpXDocumentAdapter()
    extraction = adapter.inspect(source, artifact_id="hwpx-native-table-cell-target")

    normalized = adapter.normalize_fill_patches(
        (
            DocumentFieldPatch(
                target_path="Contents/section0.xml#table[1]/r1c2",
                value="GovOn AX",
            ),
        ),
        extraction=extraction,
    )

    assert [(patch.target_path, patch.value) for patch in normalized] == [
        ("Contents/section0.xml#table[1]/r1c2", "GovOn AX")
    ]


def test_document_primitive_maps_semantic_hwpx_patch_targets_from_extracted_labels(
    tmp_path: Path,
) -> None:
    source = _write_rhwp_table_fixture(tmp_path / "weekly-table.hwpx")
    runtime = DocumentToolRuntime(
        session_id="hwpx-semantic-targets",
        artifact_root=tmp_path / "store",
    )

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="hwpx-semantic-targets",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwpx),
            operation="fill",
            instruction="팀명과 특이사항을 작성해줘.",
            patches=(
                DocumentFieldPatch(target_path="team_name", value="GovOn AX"),
                DocumentFieldPatch(
                    target_path="special_notes",
                    value="공공AX 문서 primitive 알파 테스트 완료",
                ),
            ),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert result.tool_id == "document"
    assert result.diff is not None
    assert [
        (change.target_path, change.before_value, change.after_value)
        for change in result.diff.changes
    ] == [
        ("/hwpx/text[4]", "GovOn", "GovOn AX"),
        ("/hwpx/text[6]", "기존 특이사항", "공공AX 문서 primitive 알파 테스트 완료"),
    ]


def test_document_primitive_accepts_natural_weekly_hwpx_patch_targets(
    tmp_path: Path,
) -> None:
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(_InlineSvgHwpXTestEngine())
    source = _write_hwpx_fixture(tmp_path / "weekly.hwpx")
    runtime = DocumentToolRuntime(
        session_id="hwpx-weekly-natural-targets",
        artifact_root=tmp_path / "store",
        engine_registry=engine_registry,
    )

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="hwpx-weekly-natural-targets",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwpx),
            operation="fill",
            instruction="13주차 활동일지를 작성하고 활동기간을 갱신해줘.",
            patches=(
                DocumentFieldPatch(target_path="활동기간", value="2026.06.01~2026.06.07"),
                DocumentFieldPatch(target_path="주차", value="13"),
                DocumentFieldPatch(target_path="작성일자", value="2026.06.02"),
                DocumentFieldPatch(target_path="작성자", value="[이름]"),
            ),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert result.tool_id == "document"
    assert result.diff is not None
    assert [
        (change.target_path, change.before_value, change.after_value)
        for change in result.diff.changes
    ] == [
        ("/hwpx/text[2]", "2026.05.25 ~ 2026.05.31", "2026.06.01~2026.06.07"),
        ("/hwpx/text[1]", "12 주차 ", "13주차"),
    ]


def test_document_primitive_infers_weekly_hwpx_patches_from_instruction(
    tmp_path: Path,
) -> None:
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(_InlineSvgHwpXTestEngine())
    source = _write_hwpx_fixture(tmp_path / "weekly.hwpx")
    runtime = DocumentToolRuntime(
        session_id="hwpx-weekly-inferred-targets",
        artifact_root=tmp_path / "store",
        engine_registry=engine_registry,
    )

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="hwpx-weekly-inferred-targets",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwpx),
            operation="fill",
            instruction=(
                "이 문서를 13주차 활동일지로 작성해 주세요. "
                "활동기간은 2026.06.01~2026.06.07로 넣어 주세요."
            ),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert result.diff is not None
    assert [
        (change.target_path, change.before_value, change.after_value)
        for change in result.diff.changes
    ] == [
        ("/hwpx/text[1]", "12 주차 ", "13주차"),
        ("/hwpx/text[2]", "2026.05.25 ~ 2026.05.31", "2026.06.01~2026.06.07"),
    ]


def test_public_ax_weekly_hwp_fixture_autonomous_next_week_fill_render_and_reread(
    tmp_path: Path,
) -> None:
    source = _public_ax_weekly_hwp_fixture()
    runtime = DocumentToolRuntime(
        session_id="public-ax-weekly-real-fixture",
        artifact_root=tmp_path / "store",
    )

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="public-ax-weekly-real-fixture",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwpx),
            operation="fill",
            instruction="문서 내용을 파악하고 알아서 다음 주차 활동일지로 작성해.",
        )
    )

    assert result.status is ToolResultStatus.ok
    assert result.diff is not None
    assert [
        (change.target_path, change.before_value, change.after_value)
        for change in result.diff.changes
    ] == [
        ("/hwpx/text[2]", "13 주차 ", "14주차"),
        ("/hwpx/text[12]", "2026.06.01 ~ 2026.06.07", "2026.06.08~2026.06.14"),
    ]
    assert result.render_artifacts

    reread_result = runtime.extract(
        DocumentExtractRequest(
            correlation_id="public-ax-weekly-real-fixture-reread",
            document=DocumentLocator(artifact_id=result.diff.derivative_artifact_id),
            include_tables=True,
            include_images=True,
            include_fields=True,
        )
    )
    assert reread_result.status is ToolResultStatus.ok
    assert reread_result.extraction is not None
    values_by_path = {field.path: field.current_value for field in reread_result.extraction.fields}
    assert values_by_path["/hwpx/text[2]"] == "14주차"
    assert values_by_path["/hwpx/text[12]"] == "2026.06.08~2026.06.14"


def test_public_ax_weekly_hwp_fixture_extraction_precision_gate(
    tmp_path: Path,
) -> None:
    source = _public_ax_weekly_hwp_fixture()
    runtime = DocumentToolRuntime(
        session_id="public-ax-weekly-extraction-gate",
        artifact_root=tmp_path / "store",
    )

    result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="public-ax-weekly-extraction-gate",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwpx),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert result.extraction is not None
    extraction = result.extraction
    observed_fields = {
        (field.label, field.path, field.current_value) for field in extraction.fields
    }
    expected_fields = {
        ("주차", "/hwpx/text[2]", "13 주차 "),
        ("교과목 분반", "/hwpx/text[8]", "02 분반"),
        ("팀명", "/hwpx/text[10]", "GovOn"),
        ("활동일시", "/hwpx/text[12]", "2026.06.01 ~ 2026.06.07"),
        ("장    소", "/hwpx/text[14]", "온라인(Git hub)"),
        ("참석자", "/hwpx/text[16]", "1705817 엄윤상"),
        (
            "특이사항",
            "/hwpx/text[18]",
            "공공AX 문서 하네스 방향을 파서/컨버터가 아니라 LLM이 공문서 "
            "파일을 읽고 작성·검증·저장하는 실행 하네스로 보정하고, 실제 HWPX "
            "양식 작성 테스트를 수행함.",
        ),
        (
            "금주진행 사항 및 활동 내용",
            "/hwpx/text[22]",
            "프로젝트 명: UMMAYA- AX(행정경험) 국가 인프라 플랫폼",
        ),
        ("차주 계획", "/hwpx/text[30]", "차주계획:"),
    }
    observed_cell_text = {
        cell.text for table in extraction.tables for cell in table.cells if cell.text
    }
    expected_cell_text = {
        "교과목 분반",
        "02 분반",
        "팀명",
        "GovOn",
        "활동일시",
        "2026.06.01 ~ 2026.06.07",
        "장    소",
        "온라인(Git hub)",
        "참석자",
        "1705817 엄윤상",
        "특이사항",
    }
    observed_paragraph_text = {paragraph.text for paragraph in extraction.paragraphs}
    expected_paragraph_text = {
        "SW중심대학사업 현장미러형연계프로젝트 ",
        "주간 활동 일지",
        "팀 활동 ",
        "보고",
        "차주 ",
        "계획",
    }

    assert _precision(expected_fields, observed_fields) >= 0.90
    assert _precision(expected_cell_text, observed_cell_text) >= 0.90
    assert _precision(expected_paragraph_text, observed_paragraph_text) >= 0.90


def test_default_runtime_renders_hwpx_table_cells_as_svg_grid(tmp_path: Path) -> None:
    source = _write_rhwp_table_fixture(tmp_path / "weekly-table.hwpx")
    runtime = DocumentToolRuntime(session_id="hwpx-table-render", artifact_root=tmp_path / "store")

    inspect_result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="hwpx-table-render",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.hwpx),
        )
    )
    render_result = runtime.render(
        DocumentRenderRequest(
            correlation_id="hwpx-table-render",
            document=DocumentLocator(artifact_id=inspect_result.artifact_refs[0]),
        )
    )

    assert render_result.status is ToolResultStatus.ok
    assert render_result.render_artifacts
    rendered_svg = Path(render_result.render_artifacts[0].render_path).read_text(encoding="utf-8")
    assert rendered_svg.count("cell-clip") >= 6
    assert all(token in rendered_svg for token in (">교<", ">과<", ">목<", ">분<", ">반<"))
    assert all(token in rendered_svg for token in (">G<", ">o<", ">v<", ">O<", ">n<"))
    assert all(token in rendered_svg for token in (">특<", ">이<", ">사<", ">항<"))


@pytest.mark.asyncio
async def test_registered_document_primitive_runtime_is_scoped_to_executor_session(
    tmp_path: Path,
) -> None:
    source = _write_hwpx_fixture(tmp_path / "weekly.hwpx")
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_document_tools(registry, executor, artifact_root=tmp_path / "store")

    inspect_result = await executor.invoke_raw(
        "document",
        {
            "correlation_id": "same-correlation",
            "document": {"path": str(source), "expected_format": "hwpx"},
            "operation": "inspect",
            "instruction": "Inspect this HWPX document through the document primitive.",
        },
        request_id="req-inspect-a",
        session_identity="session-a",
    )
    assert isinstance(inspect_result, dict)
    assert inspect_result["status"] == "ok"
    assert inspect_result["tool_id"] == "document"
    artifact_id = inspect_result["artifact_refs"][0]

    same_session_result = await executor.invoke_raw(
        "document",
        {
            "correlation_id": "read-a",
            "document": {"artifact_id": artifact_id},
            "operation": "extract",
            "instruction": "Extract the inspected HWPX document in the same session.",
        },
        request_id="req-read-a",
        session_identity="session-a",
    )
    assert isinstance(same_session_result, dict)
    assert same_session_result["status"] == "ok"
    assert same_session_result["tool_id"] == "document"

    other_session_result = await executor.invoke_raw(
        "document",
        {
            "correlation_id": "read-b",
            "document": {"artifact_id": artifact_id},
            "operation": "extract",
            "instruction": "Extract the inspected HWPX document from a different session.",
        },
        request_id="req-read-b",
        session_identity="session-b",
    )
    assert isinstance(other_session_result, dict)
    assert other_session_result["status"] == "needs_input"
    assert "Unknown local document artifact" in other_session_result["text_summary"]


def _write_hwpx_fixture(path: Path) -> Path:
    section = """<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"
        xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">
  <hp:p><hp:run><hp:t /></hp:run></hp:p>
  <hp:p><hp:run><hp:t>12 주차 </hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:t>2026.05.25 ~ 2026.05.31</hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:t>기존 특이사항</hp:t></hp:run></hp:p>
</hs:sec>
""".encode()
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/owpml")
        archive.writestr("version.xml", "<version />")
        archive.writestr("Contents/header.xml", "<header />")
        archive.writestr("Contents/section0.xml", section)
        archive.writestr("META-INF/manifest.xml", "<manifest />")
        archive.writestr("Preview/PrvText.txt", "<12 주차 ><2026.05.25 ~ 2026.05.31>")
    return path


def _write_hwpx_styled_fixture(path: Path) -> Path:
    header = """<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head">
  <hh:fontfaces itemCnt="1">
    <hh:fontface lang="HANGUL" fontCnt="4">
      <hh:font id="0" face="바탕" type="TTF" isEmbedded="0" />
      <hh:font id="3" face="맑은 고딕" type="TTF" isEmbedded="0" />
    </hh:fontface>
  </hh:fontfaces>
  <hh:borderFills itemCnt="1">
    <hh:borderFill id="4" threeD="0" shadow="0" centerLine="NONE">
      <hh:slash type="NONE" />
      <hh:backSlash type="NONE" />
      <hh:leftBorder type="SOLID" width="0.12 mm" color="#111111" />
      <hh:rightBorder type="SOLID" width="0.12 mm" color="#111111" />
      <hh:topBorder type="SOLID" width="0.12 mm" color="#111111" />
      <hh:bottomBorder type="SOLID" width="0.12 mm" color="#111111" />
      <hh:fillBrush>
        <hh:winBrush faceColor="#FFF2CC" hatchColor="#000000" alpha="0" />
      </hh:fillBrush>
    </hh:borderFill>
  </hh:borderFills>
  <hh:charProperties itemCnt="1">
    <hh:charPr id="3" height="1200" textColor="#005BAC" shadeColor="none" borderFillIDRef="4">
      <hh:fontRef hangul="3" latin="3" hanja="3" japanese="3" other="3" symbol="3" user="3" />
      <hh:bold />
    </hh:charPr>
  </hh:charProperties>
  <hh:paraProperties itemCnt="1">
    <hh:paraPr id="2" tabPrIDRef="0">
      <hh:align horizontal="CENTER" vertical="BASELINE" />
    </hh:paraPr>
  </hh:paraProperties>
  <hh:styles itemCnt="1">
    <hh:style id="7" type="PARA" name="제목" engName="Title"
              paraPrIDRef="2" charPrIDRef="3"
              nextStyleIDRef="0" langID="1042" lockForm="0" />
  </hh:styles>
</hh:head>
""".encode()
    section = """<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"
        xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">
  <hp:p paraPrIDRef="2" styleIDRef="7">
    <hp:run charPrIDRef="3"><hp:t>공식서식 제목</hp:t></hp:run>
  </hp:p>
</hs:sec>
""".encode()
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/owpml")
        archive.writestr("version.xml", "<version />")
        archive.writestr("Contents/header.xml", header)
        archive.writestr("Contents/section0.xml", section)
        archive.writestr("META-INF/manifest.xml", "<manifest />")
        archive.writestr("Preview/PrvText.txt", "<공식서식 제목>")
    return path


class _InlineSvgHwpXTestEngine(HwpXPackageTextEngine):
    render_engine_id = "inline-svg-test-render"

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        _ = path
        _ = artifact_id
        output_dir.mkdir(parents=True, exist_ok=True)
        return (b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1" />',)


def _write_hwpx_table_fixture(path: Path) -> Path:
    section = """<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"
        xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">
  <hp:tbl>
    <hp:tr>
      <hp:tc><hp:p><hp:run><hp:t>팀 활동 보고</hp:t></hp:run></hp:p></hp:tc>
      <hp:tc><hp:p><hp:run><hp:t>교과목 분반</hp:t></hp:run></hp:p></hp:tc>
      <hp:tc><hp:p><hp:run><hp:t>02 분반</hp:t></hp:run></hp:p></hp:tc>
      <hp:tc><hp:p><hp:run><hp:t>팀명</hp:t></hp:run></hp:p></hp:tc>
      <hp:tc><hp:p><hp:run><hp:t>GovOn</hp:t></hp:run></hp:p></hp:tc>
    </hp:tr>
    <hp:tr>
      <hp:tc><hp:p><hp:run><hp:t>특이사항</hp:t></hp:run></hp:p></hp:tc>
      <hp:tc><hp:p><hp:run><hp:t>기존 특이사항</hp:t></hp:run></hp:p></hp:tc>
    </hp:tr>
  </hp:tbl>
</hs:sec>
""".encode()
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/owpml")
        archive.writestr("version.xml", "<version />")
        archive.writestr("Contents/header.xml", "<header />")
        archive.writestr("Contents/section0.xml", section)
        archive.writestr("META-INF/manifest.xml", "<manifest />")
        archive.writestr(
            "Preview/PrvText.txt",
            "<팀 활동 보고><교과목 분반><02 분반><팀명><GovOn><특이사항><기존 특이사항>",
        )
    return path


def _write_hwpx_empty_value_table_fixture(path: Path) -> Path:
    section = """<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"
        xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">
  <hp:tbl>
    <hp:tr>
      <hp:tc><hp:p><hp:run><hp:t>팀명</hp:t></hp:run></hp:p></hp:tc>
      <hp:tc><hp:p /></hp:tc>
    </hp:tr>
  </hp:tbl>
</hs:sec>
""".encode()
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/owpml")
        archive.writestr("version.xml", "<version />")
        archive.writestr("Contents/header.xml", "<header />")
        archive.writestr("Contents/section0.xml", section)
        archive.writestr("META-INF/manifest.xml", "<manifest />")
        archive.writestr("Preview/PrvText.txt", "<팀명>")
    return path


def _hwpx_archive_payloads(path: Path) -> dict[str, bytes]:
    with ZipFile(path) as archive:
        return {info.filename: archive.read(info.filename) for info in archive.infolist()}


_RHWP_FIXTURE_JS = r"""
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const [outputPath, mode] = process.argv.slice(1);
const packageRoot = resolve(process.env.UMMAYA_PACKAGE_ROOT || process.cwd());
const require = createRequire(pathToFileURL(join(packageRoot, 'package.json')));
const rhwpModulePath = require.resolve('@rhwp/core/rhwp.js');
const rhwpWasmPath = require.resolve('@rhwp/core/rhwp_bg.wasm');
const rhwp = await import(pathToFileURL(rhwpModulePath).href);

globalThis.measureTextWidth = (_font, text) => {
  let width = 0;
  for (const char of String(text)) {
    width += char.charCodeAt(0) > 0x7f ? 14 : 8;
  }
  return width;
};

await rhwp.default({ module_or_path: readFileSync(rhwpWasmPath) });
const doc = rhwp.HwpDocument.createEmpty();
doc.createBlankDocument();

if (mode === 'text') {
  doc.insertText(0, 0, 0, '12 주차\n2026.05.25 ~ 2026.05.31\n기존 특이사항');
} else if (mode === 'table') {
  const table = JSON.parse(doc.createTable(0, 0, 0, 3, 2));
  const values = ['교과목 분반', '02 분반', '팀명', 'GovOn', '특이사항', '기존 특이사항'];
  for (const [cellIndex, value] of values.entries()) {
    doc.insertTextInCell(0, table.paraIdx, table.controlIdx, cellIndex, 0, 0, value);
  }
} else {
  throw new Error(`Unknown fixture mode: ${mode}`);
}

mkdirSync(dirname(resolve(outputPath)), { recursive: true });
writeFileSync(resolve(outputPath), doc.exportHwpx());
"""


def _write_rhwp_text_fixture(path: Path) -> Path:
    return _write_rhwp_fixture(path, mode="text")


def _write_rhwp_table_fixture(path: Path) -> Path:
    return _write_rhwp_fixture(path, mode="table")


def _public_ax_weekly_hwp_fixture() -> Path:
    evidence_root = (
        Path(__file__).resolve().parents[3]
        / ".evidence"
        / "document-fixtures"
        / "public-ax-samples"
    )
    if not evidence_root.exists():
        pytest.skip("public AX local evidence fixture directory is not available")
    matches = [path for path in evidence_root.iterdir() if path.suffix == ".hwpx"]
    if not matches:
        pytest.skip("public AX local HWPX weekly-log fixture is not available")
    source = matches[0]
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest == "b6ac058e55144a8a680744e364b74c73bb54e11426e714297ded7bfe914fa35d"
    return source


def _precision(expected: AbstractSet[object], observed: AbstractSet[object]) -> float:
    assert expected
    return len(expected & observed) / len(expected)


def _write_rhwp_fixture(path: Path, *, mode: str) -> Path:
    node_binary = shutil.which("node")
    assert node_binary is not None, "node executable is required for RHWP fixture generation"
    repo_root = Path(__file__).resolve().parents[3]
    env = dict(os.environ)
    env["UMMAYA_PACKAGE_ROOT"] = str(repo_root)
    subprocess.run(  # noqa: S603
        [
            node_binary,
            "--input-type=module",
            "-e",
            _RHWP_FIXTURE_JS,
            str(path),
            mode,
        ],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return path
