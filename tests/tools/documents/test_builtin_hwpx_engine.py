# SPDX-License-Identifier: Apache-2.0
"""Default HWPX package-text engine regression tests."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from ummaya.tools.documents.models import DocumentFormat, ToolResultStatus
from ummaya.tools.documents.registry import DocumentToolRuntime
from ummaya.tools.documents.tool_defs import (
    DocumentApplyFillRequest,
    DocumentCopyForEditRequest,
    DocumentExtractRequest,
    DocumentFieldPatch,
    DocumentInspectRequest,
    DocumentLocator,
)


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
