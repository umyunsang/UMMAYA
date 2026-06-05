# SPDX-License-Identifier: Apache-2.0
"""Promoted structured public-data document engines."""

from __future__ import annotations

import csv
import html
import io
import json
from pathlib import Path
from typing import NoReturn

import yaml
from defusedxml import ElementTree  # type: ignore[import-untyped]

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
)
from ummaya.tools.documents.tool_defs import DocumentFieldPatch

_DATA_BODY_TARGET = "/data/body"
_DATA_FORMATS = (
    DocumentFormat.csv,
    DocumentFormat.tsv,
    DocumentFormat.xml,
    DocumentFormat.rdf,
    DocumentFormat.ttl,
    DocumentFormat.lod,
    DocumentFormat.json,
    DocumentFormat.jsonl,
    DocumentFormat.yaml,
    DocumentFormat.yml,
    DocumentFormat.geojson,
    DocumentFormat.gpx,
    DocumentFormat.kml,
    DocumentFormat.fasta,
    DocumentFormat.sgml,
    DocumentFormat.dtd,
    DocumentFormat.hml,
    DocumentFormat.etc,
)
_XML_FORMATS = {
    DocumentFormat.xml,
    DocumentFormat.rdf,
    DocumentFormat.gpx,
    DocumentFormat.kml,
    DocumentFormat.hml,
}


class DataFileDocumentEngine:
    """Bounded writer for UTF-8 structured public-data files."""

    render_engine_id = "data-file-structural-svg"
    render_artifact_extension = "svg"
    render_mime_type = "image/svg+xml"

    def __init__(self, document_format: DocumentFormat) -> None:
        if document_format not in _DATA_FORMATS:
            raise ValueError(f"unsupported data-file document format: {document_format.value}")
        self.document_format = document_format
        self.engine_id = f"data-file-{document_format.value}"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Extract compact textual records from a data file."""
        raw_text = path.read_text(encoding="utf-8", errors="replace")
        visible_text = _visible_data_text(raw_text, document_format=self.document_format)
        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=_paragraphs_from_text(visible_text),
            metadata=_metadata(path, document_format=self.document_format),
        )

    def apply_patch(self, path: Path, patch: DocumentPatch) -> bytes:
        """Replace a complete data-file body and return derivative bytes."""
        raw_text = path.read_text(encoding="utf-8", errors="replace")
        replacement = raw_text
        for operation in patch.operations:
            replacement = _apply_data_operation(replacement, operation)
        _validate_data_text(replacement, document_format=self.document_format)
        return replacement.encode("utf-8")

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        """Render compact data text as structural SVG evidence."""
        _ = output_dir
        extraction = self.inspect(path, artifact_id=artifact_id)
        lines = [paragraph.text for paragraph in extraction.paragraphs]
        return (_render_lines_svg(lines, title=f"{self.document_format.value.upper()} data"),)


class DataFileDocumentAdapter:
    """Format adapter for promoted public-data document engines."""

    adapter_id = "data-file-document-adapter"
    known_formats: tuple[KnownDocumentFormat, ...] = (
        KnownDocumentFormat.csv,
        KnownDocumentFormat.tsv,
        KnownDocumentFormat.xml,
        KnownDocumentFormat.rdf,
        KnownDocumentFormat.ttl,
        KnownDocumentFormat.lod,
        KnownDocumentFormat.json,
        KnownDocumentFormat.jsonl,
        KnownDocumentFormat.yaml,
        KnownDocumentFormat.yml,
        KnownDocumentFormat.geojson,
        KnownDocumentFormat.gpx,
        KnownDocumentFormat.kml,
        KnownDocumentFormat.fasta,
        KnownDocumentFormat.sgml,
        KnownDocumentFormat.dtd,
        KnownDocumentFormat.hml,
        KnownDocumentFormat.etc,
    )
    promoted_formats: tuple[DocumentFormat, ...] = _DATA_FORMATS

    def __init__(self, engines: dict[DocumentFormat, DataFileDocumentEngine] | None = None) -> None:
        self._engines = engines or {
            document_format: DataFileDocumentEngine(document_format)
            for document_format in _DATA_FORMATS
        }

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Inspect a data artifact using its suffix-selected engine."""
        return self._engine_for_path(path).inspect(path, artifact_id=artifact_id)

    def normalize_fill_patches(
        self,
        patches: tuple[DocumentFieldPatch, ...],
        *,
        extraction: DocumentExtraction | None,
    ) -> tuple[DocumentFieldPatch, ...]:
        """Return data patches unchanged; `/data/body` is native."""
        _ = extraction
        return patches

    def _engine_for_path(self, path: Path) -> DataFileDocumentEngine:
        try:
            document_format = DocumentFormat(path.suffix.lower().lstrip("."))
        except ValueError as exc:
            raise DocumentMutationBlockedError(
                BlockedReason.unsupported_format,
                f"Unsupported data suffix: {path.suffix}",
            ) from exc
        engine = self._engines.get(document_format)
        if engine is None:
            raise DocumentMutationBlockedError(
                BlockedReason.unsupported_format,
                f"Unsupported data suffix: {path.suffix}",
            )
        return engine


def _visible_data_text(raw_text: str, *, document_format: DocumentFormat) -> str:
    if document_format in {DocumentFormat.json, DocumentFormat.geojson}:
        return json.dumps(json.loads(raw_text), ensure_ascii=False, sort_keys=True)
    if document_format == DocumentFormat.jsonl:
        return "\n".join(
            json.dumps(json.loads(line), ensure_ascii=False, sort_keys=True)
            for line in raw_text.splitlines()
            if line.strip()
        )
    if document_format in {DocumentFormat.yaml, DocumentFormat.yml}:
        loaded = yaml.safe_load(raw_text)
        return yaml.safe_dump(loaded, allow_unicode=True, sort_keys=True).strip()
    if document_format in _XML_FORMATS:
        root = ElementTree.fromstring(raw_text.encode("utf-8"))
        return "\n".join(text.strip() for text in root.itertext() if text.strip())
    return raw_text


def _apply_data_operation(text: str, operation: DocumentPatchOperation) -> str:
    if operation.operation_type not in {OperationType.replace_text, OperationType.set_field_value}:
        _raise_unsupported_operation(operation)
    if operation.target_path != _DATA_BODY_TARGET:
        _raise_unsupported_operation(operation)
    value = operation.value
    if value is None:
        _raise_unsupported_operation(operation)
    return str(value)


def _validate_data_text(text: str, *, document_format: DocumentFormat) -> None:
    try:
        if document_format in {DocumentFormat.json, DocumentFormat.geojson}:
            json.loads(text)
            return
        if document_format == DocumentFormat.jsonl:
            for line in text.splitlines():
                if line.strip():
                    json.loads(line)
            return
        if document_format in {DocumentFormat.yaml, DocumentFormat.yml}:
            yaml.safe_load(text)
            return
        if document_format in _XML_FORMATS:
            ElementTree.fromstring(text.encode("utf-8"))
            return
        if document_format in {DocumentFormat.csv, DocumentFormat.tsv}:
            delimiter = "\t" if document_format == DocumentFormat.tsv else ","
            list(csv.reader(io.StringIO(text), delimiter=delimiter))
            return
    except (ElementTree.ParseError, json.JSONDecodeError, yaml.YAMLError, csv.Error) as exc:
        raise DocumentMutationBlockedError(
            BlockedReason.validation_failed,
            f"Replacement body is not valid {document_format.value}: {exc}",
        ) from exc
    if not text.strip():
        raise DocumentMutationBlockedError(
            BlockedReason.validation_failed,
            f"Replacement body is empty for {document_format.value}.",
        )


def _paragraphs_from_text(text: str) -> list[ParagraphBlock]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines and text.strip():
        lines = [text.strip()]
    return [
        ParagraphBlock(
            block_id=f"data-line-{index}",
            text=line,
            source_path=f"/data/lines/{index}",
        )
        for index, line in enumerate(lines[:200], start=1)
    ]


def _metadata(path: Path, *, document_format: DocumentFormat) -> dict[str, MetadataValue]:
    return {
        "adapter_id": "data-file-document-adapter",
        "engine_id": f"data-file-{document_format.value}",
        "format": document_format.value,
        "source_name": path.name,
        "mutation_policy": "bounded_data_file_write_render_save",
        "render_oracle": "data-file-structural-svg",
    }


def _render_lines_svg(lines: list[str], *, title: str) -> bytes:
    escaped_title = html.escape(title)
    safe_lines = [html.escape(line) for line in lines if line]
    height = max(160, 72 + len(safe_lines) * 28)
    text_nodes = [
        f'<text x="32" y="{84 + index * 28}" font-size="16" font-family="monospace">{line}</text>'
        for index, line in enumerate(safe_lines)
    ]
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="{height}" '
        f'viewBox="0 0 960 {height}">'
        '<rect width="100%" height="100%" fill="#ffffff"/>'
        f'<text x="32" y="40" font-size="22" font-family="sans-serif" '
        f'font-weight="700">{escaped_title}</text>' + "".join(text_nodes) + "</svg>"
    )
    return svg.encode("utf-8")


def _raise_unsupported_operation(operation: DocumentPatchOperation) -> NoReturn:
    raise DocumentMutationBlockedError(
        BlockedReason.unsupported_operation,
        f"Data-file operation is not supported: "
        f"{operation.operation_type.value} {operation.target_path}",
    )
