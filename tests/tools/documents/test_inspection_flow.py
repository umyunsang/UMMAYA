# SPDX-License-Identifier: Apache-2.0
"""Inspection harness tests for engine-backed public document formats."""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import pytest

from ummaya.tools.documents.engines import DocumentEngineRegistry
from ummaya.tools.documents.inspection import inspect_document
from ummaya.tools.documents.models import DocumentExtraction, DocumentFormat, ParagraphBlock


class StaticInspectionEngine:
    """Test double for an external document engine behind the harness."""

    def __init__(self, *, document_format: DocumentFormat, text: str) -> None:
        self.document_format = document_format
        self.engine_id = f"test-double-{document_format.value}"
        self.text = text
        self.calls: list[Path] = []

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        self.calls.append(path)
        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=[
                ParagraphBlock(
                    block_id=f"{self.document_format.value}-paragraph-001",
                    text=self.text,
                    source_path=f"engine://{self.engine_id}/paragraph/1",
                )
            ],
            metadata={
                "engine_id": self.engine_id,
                "format": self.document_format.value,
            },
        )


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for name, payload in entries.items():
            package.writestr(name, payload)
    return buffer.getvalue()


def _write(path: Path, payload: bytes) -> Path:
    path.write_bytes(payload)
    return path


def _registry_for(engine: StaticInspectionEngine) -> DocumentEngineRegistry:
    registry = DocumentEngineRegistry()
    registry.register(engine)
    return registry


def _text(result: object) -> str:
    extraction = result.extraction
    assert extraction is not None
    paragraph_text = " ".join(block.text for block in extraction.paragraphs)
    table_text = " ".join(cell.text for table in extraction.tables for cell in table.cells)
    field_text = " ".join(field.label for field in extraction.fields)
    return f"{paragraph_text} {table_text} {field_text}"


def _hwpx_fixture(text: str) -> bytes:
    return _zip_bytes(
        {
            "version.xml": b"<version/>",
            "Contents/section0.xml": f"<section><p>{text}</p></section>".encode(),
            "META-INF/manifest.xml": b"<manifest/>",
        }
    )


def _docx_fixture(text: str) -> bytes:
    return _zip_bytes(
        {
            "[Content_Types].xml": b"<Types/>",
            "word/document.xml": (
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>"
            ).encode(),
        }
    )


def _xlsx_fixture(text: str) -> bytes:
    return _zip_bytes(
        {
            "[Content_Types].xml": b"<Types/>",
            "xl/workbook.xml": b"<workbook/>",
            "xl/sharedStrings.xml": (
                '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                f"<si><t>{text}</t></si></sst>"
            ).encode(),
            "xl/worksheets/sheet1.xml": (
                b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                b'<sheetData><row r="1"><c r="A1" t="s"><v>0</v></c></row></sheetData></worksheet>'
            ),
        }
    )


def _pptx_fixture(text: str) -> bytes:
    return _zip_bytes(
        {
            "[Content_Types].xml": b"<Types/>",
            "ppt/presentation.xml": b"<presentation/>",
            "ppt/slides/slide1.xml": (
                '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
                f"<p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>{text}</a:t></a:r></a:p>"
                "</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
            ).encode(),
        }
    )


def _pdf_fixture(text: str) -> bytes:
    return f"%PDF-1.7\n1 0 obj <<>> stream\nBT ({text}) Tj ET\nendstream\n%%EOF\n".encode()


def _hwp_fixture() -> bytes:
    return b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"HWP Document File"


@pytest.mark.parametrize(
    ("filename", "payload", "expected_text"),
    [
        ("form.hwpx", _hwpx_fixture("HWPX package marker"), "HWPX applicant name"),
        ("form.docx", _docx_fixture("DOCX package marker"), "DOCX applicant name"),
        ("form.xlsx", _xlsx_fixture("XLSX package marker"), "XLSX applicant name"),
        ("form.pptx", _pptx_fixture("PPTX package marker"), "PPTX applicant name"),
        ("form.pdf", _pdf_fixture("PDF package marker"), "PDF applicant name"),
    ],
)
def test_inspect_document_delegates_to_registered_engine_without_mutating_source(
    tmp_path: Path,
    filename: str,
    payload: bytes,
    expected_text: str,
) -> None:
    source = _write(tmp_path / filename, payload)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    document_format = DocumentFormat(Path(filename).suffix[1:])
    engine = StaticInspectionEngine(
        document_format=document_format,
        text=expected_text,
    )

    result = inspect_document(
        source,
        expected_format=document_format,
        engine_registry=_registry_for(engine),
    )

    assert result.status.value == "ok"
    assert result.blocked_reason is None
    assert expected_text in _text(result)
    assert engine.calls == [source]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_inspect_hwp_reports_read_only_binary_boundary(tmp_path: Path) -> None:
    source = _write(tmp_path / "legacy.hwp", _hwp_fixture())
    engine = StaticInspectionEngine(
        document_format=DocumentFormat.hwp,
        text="Legacy HWP readable text",
    )

    result = inspect_document(source, expected_format="hwp", engine_registry=_registry_for(engine))

    assert result.status.value == "ok"
    assert result.extraction is not None
    assert "Legacy HWP readable text" in _text(result)


def test_inspect_document_blocks_when_no_engine_is_promoted(tmp_path: Path) -> None:
    source = _write(tmp_path / "form.pdf", _pdf_fixture("PDF package marker"))

    result = inspect_document(source, expected_format="pdf")

    assert result.status.value == "blocked"
    assert result.blocked_reason is not None
    assert result.blocked_reason.value == "unsupported_operation"
    assert result.extraction is None
