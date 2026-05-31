# SPDX-License-Identifier: Apache-2.0
"""OOXML engine-adapter boundary for DOCX, XLSX, and PPTX."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import docx
from docx.document import Document as DocxDocument
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph as DocxParagraph

from ummaya.tools.documents.engines import DocumentInspectionEngine, DocumentMutationEngine
from ummaya.tools.documents.models import (
    DocumentExtraction,
    DocumentFormat,
    MetadataValue,
    ParagraphBlock,
    TableBlock,
    TableCell,
)

OOXML_CANDIDATE_ENGINES: dict[DocumentFormat, tuple[str, ...]] = {
    DocumentFormat.docx: ("python-docx", "direct-wordprocessingml-oracle"),
    DocumentFormat.xlsx: ("openpyxl", "direct-spreadsheetml-oracle"),
    DocumentFormat.pptx: ("python-pptx", "direct-presentationml-oracle"),
}


def validate_ooxml_engine(engine: DocumentInspectionEngine) -> DocumentInspectionEngine:
    """Validate that an injected engine is scoped to an OOXML format."""
    if engine.document_format not in OOXML_CANDIDATE_ENGINES:
        raise ValueError("OOXML adapter requires a docx, xlsx, or pptx engine")
    return engine


def validate_ooxml_mutation_engine(engine: DocumentInspectionEngine) -> DocumentMutationEngine:
    """Validate that an injected OOXML engine can safely mutate derivatives."""
    validate_ooxml_engine(engine)
    if not isinstance(engine, DocumentMutationEngine):
        raise ValueError("OOXML adapter requires a mutation-capable engine")
    return engine


class PythonDocxInspectionEngine:
    """Read-only DOCX engine backed by the promoted python-docx dependency."""

    document_format = DocumentFormat.docx
    engine_id = "python-docx"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Extract normalized paragraphs, tables, and core metadata from DOCX."""
        document = docx.Document(str(path))
        paragraphs: list[ParagraphBlock] = []
        tables: list[TableBlock] = []

        paragraph_index = 1
        table_index = 1
        for block in document.iter_inner_content():
            if isinstance(block, DocxParagraph):
                if block.text:
                    paragraphs.append(
                        _paragraph_block(
                            block,
                            engine_id=self.engine_id,
                            path=path,
                            index=paragraph_index,
                        )
                    )
                    paragraph_index += 1
            elif isinstance(block, DocxTable):
                tables.append(
                    _table_block(
                        block,
                        engine_id=self.engine_id,
                        path=path,
                        index=table_index,
                    )
                )
                table_index += 1

        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=paragraphs,
            tables=tables,
            metadata=_core_metadata(document),
            warnings=[
                "python-docx read scope excludes nested tables and revision-mark content "
                "from the top-level document lists."
            ],
        )


def _paragraph_block(
    paragraph: DocxParagraph,
    *,
    engine_id: str,
    path: Path,
    index: int,
) -> ParagraphBlock:
    return ParagraphBlock(
        block_id=f"docx-paragraph-{index:03d}",
        text=paragraph.text,
        source_path=f"engine://{engine_id}/{path.name}/paragraph/{index}",
        style_id=_paragraph_style_id(paragraph),
    )


def _table_block(
    table: DocxTable,
    *,
    engine_id: str,
    path: Path,
    index: int,
) -> TableBlock:
    cells: list[TableCell] = []
    for row_index, row in enumerate(table.rows):
        for column_index, cell in enumerate(row.cells):
            cells.append(
                TableCell(
                    row_index=row_index,
                    column_index=column_index,
                    text=cell.text,
                    source_path=(
                        f"engine://{engine_id}/{path.name}/table/{index}/"
                        f"r{row_index + 1}c{column_index + 1}"
                    ),
                )
            )
    return TableBlock(
        block_id=f"docx-table-{index:03d}",
        source_path=f"engine://{engine_id}/{path.name}/table/{index}",
        cells=cells,
    )


def _paragraph_style_id(paragraph: DocxParagraph) -> str | None:
    style: object | None = paragraph.style
    style_id = getattr(style, "style_id", None)
    if isinstance(style_id, str) and style_id:
        return style_id
    style_name = getattr(style, "name", None)
    if isinstance(style_name, str) and style_name:
        return style_name
    return None


def _core_metadata(document: DocxDocument) -> dict[str, MetadataValue]:
    core_properties = document.core_properties
    metadata: dict[str, MetadataValue] = {
        "engine_id": "python-docx",
        "format": "docx",
    }
    for property_name in (
        "author",
        "category",
        "comments",
        "content_status",
        "created",
        "identifier",
        "keywords",
        "language",
        "last_modified_by",
        "last_printed",
        "modified",
        "revision",
        "subject",
        "title",
        "version",
    ):
        value = getattr(core_properties, property_name)
        if _metadata_value_is_present(value):
            metadata[f"core_{property_name}"] = value
    return metadata


def _metadata_value_is_present(value: MetadataValue) -> bool:
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, datetime):
        return True
    return value is not None
