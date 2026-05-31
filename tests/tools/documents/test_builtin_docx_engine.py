# SPDX-License-Identifier: Apache-2.0
"""Default DOCX engine promotion tests for the document harness."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from ummaya.tools.documents.models import DocumentFormat, ToolResultStatus
from ummaya.tools.documents.registry import DocumentToolRuntime
from ummaya.tools.documents.tool_defs import DocumentInspectRequest, DocumentLocator


def test_default_runtime_inspects_docx_with_promoted_python_docx_engine(
    tmp_path: Path,
) -> None:
    source = _write_docx_fixture(tmp_path / "civil-application.docx")
    runtime = DocumentToolRuntime(
        session_id="builtin-docx-engine",
        artifact_root=tmp_path / "artifacts",
    )

    result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="corr-docx-default-engine",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert result.extraction is not None
    assert result.extraction.metadata["engine_id"] == "python-docx"
    assert result.extraction.metadata["format"] == "docx"
    assert "민원 신청서" in " ".join(block.text for block in result.extraction.paragraphs)
    assert "홍길동" in " ".join(
        cell.text for table in result.extraction.tables for cell in table.cells
    )


def test_default_runtime_normalizes_inferred_docx_format_to_enum(tmp_path: Path) -> None:
    source = _write_docx_fixture(tmp_path / "civil-application.docx")
    runtime = DocumentToolRuntime(
        session_id="builtin-docx-engine-inferred-format",
        artifact_root=tmp_path / "artifacts",
    )

    result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="corr-docx-inferred-format",
            document=DocumentLocator(path=str(source)),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert result.artifact_refs == ["source-corr-docx-inferred-format"]
    artifact = runtime._artifacts["source-corr-docx-inferred-format"]
    assert artifact.format is DocumentFormat.docx


def test_default_docx_engine_parse_error_returns_typed_blocked_result(
    tmp_path: Path,
) -> None:
    source = tmp_path / "structurally-incomplete.docx"
    with zipfile.ZipFile(source, "w") as package:
        package.writestr("[Content_Types].xml", "<Types/>")
        package.writestr("word/document.xml", "<w:document/>")
    runtime = DocumentToolRuntime(
        session_id="builtin-docx-engine-corrupt",
        artifact_root=tmp_path / "artifacts",
    )

    result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id="corr-docx-parse-error",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
        )
    )

    assert result.status is ToolResultStatus.blocked
    assert result.blocked_reason is not None
    assert result.blocked_reason.value == "corrupt"
    assert result.findings
    assert result.findings[0].finding_id == "inspection-engine-parse-error"


def _write_docx_fixture(path: Path) -> Path:
    path.write_bytes(_docx_fixture_bytes())
    return path


def _docx_fixture_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr(
            "[Content_Types].xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
                '  <Default Extension="rels" ContentType="'
                'application/vnd.openxmlformats-package.relationships+xml"/>\n'
                '  <Default Extension="xml" ContentType="application/xml"/>\n'
                '  <Override PartName="/word/document.xml" ContentType="'
                "application/vnd.openxmlformats-officedocument."
                'wordprocessingml.document.main+xml"/>\n'
                '  <Override PartName="/docProps/core.xml" ContentType="'
                'application/vnd.openxmlformats-package.core-properties+xml"/>\n'
                "</Types>"
            ),
        )
        package.writestr(
            "_rels/.rels",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships xmlns="'
                'http://schemas.openxmlformats.org/package/2006/relationships">\n'
                '  <Relationship Id="rId1" Type="'
                "http://schemas.openxmlformats.org/officeDocument/2006/"
                'relationships/officeDocument" Target="word/document.xml"/>\n'
                '  <Relationship Id="rId2" Type="'
                "http://schemas.openxmlformats.org/package/2006/relationships/"
                'metadata/core-properties" Target="docProps/core.xml"/>\n'
                "</Relationships>"
            ),
        )
        package.writestr(
            "docProps/core.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
  xmlns:dc="http://purl.org/dc/elements/1.1/"
  xmlns:dcterms="http://purl.org/dc/terms/"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>공공 민원 신청서</dc:title>
  <dc:creator>UMMAYA fixture</dc:creator>
  <cp:lastModifiedBy>UMMAYA fixture</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">2026-06-01T00:00:00Z</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">2026-06-01T00:00:00Z</dcterms:modified>
</cp:coreProperties>""",
        )
        package.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:t>민원 신청서</w:t></w:r>
    </w:p>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>신청인</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>홍길동</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
  </w:body>
</w:document>""",
        )
    return buffer.getvalue()
