# SPDX-License-Identifier: Apache-2.0
"""ODF document engines backed by odfdo.

These engines intentionally cover bounded public-form operations first:
paragraph values in ODT, sheet cells in ODS, and text frames in ODP. Full layout
oracle rendering remains a separate LibreOffice bridge gate.
"""

from __future__ import annotations

import html
import re
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from typing import NoReturn, Protocol, cast

from odfdo import Document as OdfDocument

from ummaya.tools.documents.engines import DocumentMutationBlockedError
from ummaya.tools.documents.models import (
    BlockedReason,
    DocumentExtraction,
    DocumentFormat,
    DocumentPatch,
    DocumentPatchOperation,
    KnownDocumentFormat,
    MetadataValue,
    OperationType,
    ParagraphBlock,
    TableBlock,
    TableCell,
)
from ummaya.tools.documents.tool_defs import DocumentFieldPatch

_ODT_PARAGRAPH_RE = re.compile(r"^/odf/text/p\[(?P<index>[1-9][0-9]*)]$")
_ODS_CELL_RE = re.compile(r"^/odf/sheets/(?P<sheet>[^/]+)/cells/(?P<cell>[A-Z]{1,3}[1-9][0-9]*)$")
_ODP_FRAME_RE = re.compile(r"^/odf/slides/(?P<slide>[1-9][0-9]*)/frames/(?P<index>[1-9][0-9]*)$")


class _OdfDocument(Protocol):
    @property
    def body(self) -> object:
        """Return the odfdo document body."""

    def save(self, target: BytesIO | Path, *, pretty: bool = False) -> None:
        """Save the document to bytes or a filesystem path."""


class _OdfParagraph(Protocol):
    @property
    def text(self) -> str:
        """Return paragraph text."""

    @text.setter
    def text(self, value: str) -> None:
        """Set paragraph text."""


class _OdfCell(Protocol):
    @property
    def value(self) -> object:
        """Return cell value."""


class _OdfTable(Protocol):
    @property
    def name(self) -> str | None:
        """Return table name."""

    def get_cells(self) -> Sequence[Sequence[_OdfCell]]:
        """Return table cells."""


class _OdfTablesBody(Protocol):
    def get_tables(self) -> Sequence[_OdfTable]:
        """Return body tables."""


class _OdfTextBody(_OdfTablesBody, Protocol):
    def get_paragraphs(self) -> Sequence[object]:
        """Return text paragraphs."""

    def get_paragraph(self, *, position: int) -> _OdfParagraph:
        """Return one text paragraph."""


class _OdfSheet(Protocol):
    def set_value(self, address: str, value: str) -> None:
        """Set one sheet cell value."""


class _OdfSpreadsheetBody(_OdfTablesBody, Protocol):
    def get_sheet(self, *, name: str) -> _OdfSheet:
        """Return one sheet by name."""


class _OdfFrame(Protocol):
    def set_text_box(self, value: str) -> None:
        """Set frame text box content."""


class _OdfPresentationBody(Protocol):
    def get_frames(self) -> Sequence[_OdfFrame]:
        """Return presentation text frames."""


class OdfdoTextDocumentEngine:
    """Bounded ODT text document engine."""

    document_format = DocumentFormat.odt
    engine_id = "odfdo-odt"
    render_engine_id = "odfdo-structural-svg"
    render_artifact_extension = "svg"
    render_mime_type = "image/svg+xml"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Extract ODT paragraphs and tables into DocumentIR blocks."""
        document = cast(_OdfDocument, OdfDocument(path))
        body = cast(_OdfTextBody, document.body)
        paragraphs = [
            ParagraphBlock(
                block_id=f"odt-p-{index}",
                text=str(paragraph).strip(),
                source_path=f"/odf/text/p[{index}]",
            )
            for index, paragraph in enumerate(body.get_paragraphs(), start=1)
            if str(paragraph).strip()
        ]
        tables = _tables_from_body(body, artifact_prefix="odt")
        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=paragraphs,
            tables=tables,
            metadata=_metadata(path, document_format=DocumentFormat.odt),
        )

    def apply_patch(self, path: Path, patch: DocumentPatch) -> bytes:
        """Apply bounded paragraph mutations and return derivative ODT bytes."""
        document = cast(_OdfDocument, OdfDocument(path))
        for operation in patch.operations:
            _apply_odt_operation(document, operation)
        return _save_odf_document(document)

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        """Render a reviewer-readable structural SVG page."""
        _ = output_dir
        extraction = self.inspect(path, artifact_id=artifact_id)
        lines = [paragraph.text for paragraph in extraction.paragraphs]
        for table in extraction.tables:
            lines.extend(cell.text for cell in table.cells if cell.text)
        return (_render_lines_svg(lines, title="ODT document"),)


class OdfdoSpreadsheetDocumentEngine:
    """Bounded ODS spreadsheet engine."""

    document_format = DocumentFormat.ods
    engine_id = "odfdo-ods"
    render_engine_id = "odfdo-structural-svg"
    render_artifact_extension = "svg"
    render_mime_type = "image/svg+xml"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Extract ODS sheet cells into table blocks."""
        document = cast(_OdfDocument, OdfDocument(path))
        tables = _tables_from_body(document.body, artifact_prefix="ods")
        return DocumentExtraction(
            artifact_id=artifact_id,
            tables=tables,
            metadata=_metadata(path, document_format=DocumentFormat.ods),
        )

    def apply_patch(self, path: Path, patch: DocumentPatch) -> bytes:
        """Apply bounded sheet cell mutations and return derivative ODS bytes."""
        document = cast(_OdfDocument, OdfDocument(path))
        for operation in patch.operations:
            _apply_ods_operation(document, operation)
        return _save_odf_document(document)

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        """Render reviewer-readable sheet cells as structural SVG."""
        _ = output_dir
        extraction = self.inspect(path, artifact_id=artifact_id)
        lines = [
            f"{cell.source_path}: {cell.text}"
            for table in extraction.tables
            for cell in table.cells
            if cell.text
        ]
        return (_render_lines_svg(lines, title="ODS spreadsheet"),)


class OdfdoPresentationDocumentEngine:
    """Bounded ODP presentation engine."""

    document_format = DocumentFormat.odp
    engine_id = "odfdo-odp"
    render_engine_id = "odfdo-structural-svg"
    render_artifact_extension = "svg"
    render_mime_type = "image/svg+xml"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Extract ODP text frames into paragraph blocks."""
        document = cast(_OdfDocument, OdfDocument(path))
        body = cast(_OdfPresentationBody, document.body)
        paragraphs = [
            ParagraphBlock(
                block_id=f"odp-frame-{index}",
                text=str(frame).strip(),
                source_path=f"/odf/slides/1/frames/{index}",
            )
            for index, frame in enumerate(body.get_frames(), start=1)
            if str(frame).strip()
        ]
        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=paragraphs,
            metadata=_metadata(path, document_format=DocumentFormat.odp),
        )

    def apply_patch(self, path: Path, patch: DocumentPatch) -> bytes:
        """Apply bounded text-frame mutations and return derivative ODP bytes."""
        document = cast(_OdfDocument, OdfDocument(path))
        for operation in patch.operations:
            _apply_odp_operation(document, operation)
        return _save_odf_document(document)

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        """Render reviewer-readable slide text as structural SVG."""
        _ = output_dir
        extraction = self.inspect(path, artifact_id=artifact_id)
        lines = [paragraph.text for paragraph in extraction.paragraphs]
        return (_render_lines_svg(lines, title="ODP presentation"),)


type _OdfEngine = (
    OdfdoTextDocumentEngine | OdfdoSpreadsheetDocumentEngine | OdfdoPresentationDocumentEngine
)


class OdfdoDocumentAdapter:
    """Format adapter for promoted odfdo-backed ODF engines."""

    adapter_id = "odfdo-document-adapter"
    known_formats: tuple[KnownDocumentFormat, ...] = (
        KnownDocumentFormat.odt,
        KnownDocumentFormat.ods,
        KnownDocumentFormat.odp,
    )
    promoted_formats: tuple[DocumentFormat, ...] = (
        DocumentFormat.odt,
        DocumentFormat.ods,
        DocumentFormat.odp,
    )

    def __init__(
        self,
        *,
        text_engine: OdfdoTextDocumentEngine | None = None,
        spreadsheet_engine: OdfdoSpreadsheetDocumentEngine | None = None,
        presentation_engine: OdfdoPresentationDocumentEngine | None = None,
    ) -> None:
        self._engines: dict[DocumentFormat, _OdfEngine] = {
            DocumentFormat.odt: text_engine or OdfdoTextDocumentEngine(),
            DocumentFormat.ods: spreadsheet_engine or OdfdoSpreadsheetDocumentEngine(),
            DocumentFormat.odp: presentation_engine or OdfdoPresentationDocumentEngine(),
        }

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Inspect an ODF package with the engine that matches the file suffix."""
        return self._engine_for_path(path).inspect(path, artifact_id=artifact_id)

    def normalize_fill_patches(
        self,
        patches: tuple[DocumentFieldPatch, ...],
        *,
        extraction: DocumentExtraction | None,
    ) -> tuple[DocumentFieldPatch, ...]:
        """Return ODF patches unchanged; native paths are already stable."""
        _ = extraction
        return patches

    def _engine_for_path(
        self,
        path: Path,
    ) -> _OdfEngine:
        try:
            document_format = DocumentFormat(path.suffix.lower().lstrip("."))
        except ValueError as exc:
            raise DocumentMutationBlockedError(
                BlockedReason.unsupported_format,
                f"Unsupported ODF suffix: {path.suffix}",
            ) from exc
        engine = self._engines.get(document_format)
        if engine is None:
            raise DocumentMutationBlockedError(
                BlockedReason.unsupported_format,
                f"Unsupported ODF suffix: {path.suffix}",
            )
        return engine


def _apply_odt_operation(document: _OdfDocument, operation: DocumentPatchOperation) -> None:
    if operation.operation_type not in {OperationType.replace_text, OperationType.set_field_value}:
        _raise_unsupported_operation(operation)
    match = _ODT_PARAGRAPH_RE.fullmatch(operation.target_path)
    if match is None:
        _raise_unsupported_operation(operation)
    body = cast(_OdfTextBody, document.body)
    paragraph = body.get_paragraph(position=int(match.group("index")) - 1)
    paragraph.text = _string_value(operation)


def _apply_ods_operation(document: _OdfDocument, operation: DocumentPatchOperation) -> None:
    if operation.operation_type not in {
        OperationType.set_table_cell,
        OperationType.set_field_value,
    }:
        _raise_unsupported_operation(operation)
    match = _ODS_CELL_RE.fullmatch(operation.target_path)
    if match is None:
        _raise_unsupported_operation(operation)
    body = cast(_OdfSpreadsheetBody, document.body)
    sheet = body.get_sheet(name=match.group("sheet"))
    sheet.set_value(match.group("cell"), _string_value(operation))


def _apply_odp_operation(document: _OdfDocument, operation: DocumentPatchOperation) -> None:
    if operation.operation_type not in {OperationType.replace_text, OperationType.set_field_value}:
        _raise_unsupported_operation(operation)
    match = _ODP_FRAME_RE.fullmatch(operation.target_path)
    if match is None:
        _raise_unsupported_operation(operation)
    body = cast(_OdfPresentationBody, document.body)
    frames = body.get_frames()
    frame_index = int(match.group("index")) - 1
    if frame_index >= len(frames):
        _raise_unsupported_operation(operation)
    frames[frame_index].set_text_box(_string_value(operation))


def _string_value(operation: DocumentPatchOperation) -> str:
    value = operation.value
    if value is None:
        _raise_unsupported_operation(operation)
    return str(value)


def _raise_unsupported_operation(operation: DocumentPatchOperation) -> NoReturn:
    raise DocumentMutationBlockedError(
        BlockedReason.unsupported_operation,
        f"ODF operation is not supported: {operation.operation_type.value} {operation.target_path}",
    )


def _tables_from_body(body: object, *, artifact_prefix: str) -> list[TableBlock]:
    if not hasattr(body, "get_tables"):
        return []
    tables: list[TableBlock] = []
    tables_body = cast(_OdfTablesBody, body)
    for table_index, table in enumerate(tables_body.get_tables(), start=1):
        table_name = str(table.name or f"Table{table_index}")
        cells: list[TableCell] = []
        for row_index, row in enumerate(table.get_cells()):
            for column_index, cell in enumerate(row):
                value = cell.value
                text = "" if value is None else str(value)
                address = f"{_column_name(column_index)}{row_index + 1}"
                cells.append(
                    TableCell(
                        row_index=row_index,
                        column_index=column_index,
                        text=text,
                        source_path=f"/odf/sheets/{table_name}/cells/{address}",
                        field_path=f"/odf/sheets/{table_name}/cells/{address}",
                    )
                )
        tables.append(
            TableBlock(
                block_id=f"{artifact_prefix}-table-{table_index}",
                source_path=f"/odf/sheets/{table_name}",
                cells=cells,
            )
        )
    return tables


def _column_name(index: int) -> str:
    value = index + 1
    letters = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _metadata(path: Path, *, document_format: DocumentFormat) -> dict[str, MetadataValue]:
    return {
        "adapter_id": "odfdo-document-adapter",
        "engine_id": f"odfdo-{document_format.value}",
        "format": document_format.value,
        "source_name": path.name,
        "mutation_policy": "bounded_odfdo_write_render_save",
        "render_oracle": "odfdo-structural-svg",
        "layout_oracle_gate": "libreoffice_headless_deferred",
    }


def _save_odf_document(document: _OdfDocument) -> bytes:
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def _render_lines_svg(lines: list[str], *, title: str) -> bytes:
    escaped_title = html.escape(title)
    safe_lines = [html.escape(line) for line in lines if line]
    height = max(160, 72 + len(safe_lines) * 28)
    text_nodes = [
        f'<text x="32" y="{84 + index * 28}" font-size="16" font-family="sans-serif">{line}</text>'
        for index, line in enumerate(safe_lines[:40])
    ]
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="{height}" '
        f'viewBox="0 0 900 {height}">'
        '<rect width="100%" height="100%" fill="#ffffff"/>'
        '<rect x="20" y="20" width="860" height="'
        f'{height - 40}" fill="#ffffff" stroke="#222222" stroke-width="1"/>'
        f'<text x="32" y="52" font-size="20" font-family="sans-serif" '
        f'font-weight="700">{escaped_title}</text>'
        f"{''.join(text_nodes)}"
        "</svg>"
    )
    return svg.encode("utf-8")
