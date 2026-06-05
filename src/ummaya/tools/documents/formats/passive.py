# SPDX-License-Identifier: Apache-2.0
"""Known-only passive adapters for non-promoted document families."""

from __future__ import annotations

import csv
import gzip
import io
import json
import tarfile
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING
from xml.etree import ElementTree as StdElementTree

import yaml
from defusedxml import ElementTree  # type: ignore[import-untyped]

from ummaya.tools.documents.models import (
    DocumentExtraction,
    DocumentFormat,
    ImageReference,
    KnownDocumentFormat,
    MetadataValue,
    ParagraphBlock,
    TableBlock,
    TableCell,
)

if TYPE_CHECKING:
    from ummaya.tools.documents.tool_defs import DocumentFieldPatch


_ODF_FORMATS: tuple[KnownDocumentFormat, ...] = (
    KnownDocumentFormat.odt,
    KnownDocumentFormat.ods,
    KnownDocumentFormat.odp,
)
_DATA_FORMATS: tuple[KnownDocumentFormat, ...] = (
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
_TEXT_WEB_FORMATS: tuple[KnownDocumentFormat, ...] = (
    KnownDocumentFormat.html,
    KnownDocumentFormat.htm,
    KnownDocumentFormat.txt,
    KnownDocumentFormat.rtf,
    KnownDocumentFormat.md,
)
_LEGACY_OFFICE_FORMATS: tuple[KnownDocumentFormat, ...] = (
    KnownDocumentFormat.doc,
    KnownDocumentFormat.xls,
    KnownDocumentFormat.ppt,
)
_CODE_FORMATS: tuple[KnownDocumentFormat, ...] = (KnownDocumentFormat.python,)
_IMAGE_FORMATS: tuple[KnownDocumentFormat, ...] = (
    KnownDocumentFormat.png,
    KnownDocumentFormat.jpg,
    KnownDocumentFormat.jpeg,
    KnownDocumentFormat.gif,
    KnownDocumentFormat.tif,
    KnownDocumentFormat.tiff,
    KnownDocumentFormat.bmp,
    KnownDocumentFormat.webp,
)
_GEOSPATIAL_FORMATS: tuple[KnownDocumentFormat, ...] = (
    KnownDocumentFormat.shp,
    KnownDocumentFormat.shx,
    KnownDocumentFormat.dbf,
    KnownDocumentFormat.prj,
    KnownDocumentFormat.stl,
)
_MEDIA_FORMATS: tuple[KnownDocumentFormat, ...] = (
    KnownDocumentFormat.wav,
    KnownDocumentFormat.mp3,
    KnownDocumentFormat.mp4,
)
_ARCHIVE_FORMATS: tuple[KnownDocumentFormat, ...] = (
    KnownDocumentFormat.epub,
    KnownDocumentFormat.zip,
    KnownDocumentFormat.seven_z,
    KnownDocumentFormat.tar,
    KnownDocumentFormat.gz,
)

_KNOWN_BY_EXTENSION = {
    ".odt": KnownDocumentFormat.odt,
    ".ods": KnownDocumentFormat.ods,
    ".odp": KnownDocumentFormat.odp,
    ".doc": KnownDocumentFormat.doc,
    ".xls": KnownDocumentFormat.xls,
    ".ppt": KnownDocumentFormat.ppt,
    ".csv": KnownDocumentFormat.csv,
    ".tsv": KnownDocumentFormat.tsv,
    ".xml": KnownDocumentFormat.xml,
    ".rdf": KnownDocumentFormat.rdf,
    ".ttl": KnownDocumentFormat.ttl,
    ".lod": KnownDocumentFormat.lod,
    ".json": KnownDocumentFormat.json,
    ".jsonl": KnownDocumentFormat.jsonl,
    ".yaml": KnownDocumentFormat.yaml,
    ".yml": KnownDocumentFormat.yml,
    ".geojson": KnownDocumentFormat.geojson,
    ".gpx": KnownDocumentFormat.gpx,
    ".kml": KnownDocumentFormat.kml,
    ".fasta": KnownDocumentFormat.fasta,
    ".sgml": KnownDocumentFormat.sgml,
    ".dtd": KnownDocumentFormat.dtd,
    ".hml": KnownDocumentFormat.hml,
    ".etc": KnownDocumentFormat.etc,
    ".py": KnownDocumentFormat.python,
    ".html": KnownDocumentFormat.html,
    ".htm": KnownDocumentFormat.htm,
    ".txt": KnownDocumentFormat.txt,
    ".rtf": KnownDocumentFormat.rtf,
    ".md": KnownDocumentFormat.md,
    ".png": KnownDocumentFormat.png,
    ".jpg": KnownDocumentFormat.jpg,
    ".jpeg": KnownDocumentFormat.jpeg,
    ".gif": KnownDocumentFormat.gif,
    ".tif": KnownDocumentFormat.tif,
    ".tiff": KnownDocumentFormat.tiff,
    ".bmp": KnownDocumentFormat.bmp,
    ".webp": KnownDocumentFormat.webp,
    ".shp": KnownDocumentFormat.shp,
    ".shx": KnownDocumentFormat.shx,
    ".dbf": KnownDocumentFormat.dbf,
    ".prj": KnownDocumentFormat.prj,
    ".stl": KnownDocumentFormat.stl,
    ".wav": KnownDocumentFormat.wav,
    ".mp3": KnownDocumentFormat.mp3,
    ".mp4": KnownDocumentFormat.mp4,
    ".epub": KnownDocumentFormat.epub,
    ".zip": KnownDocumentFormat.zip,
    ".7z": KnownDocumentFormat.seven_z,
    ".tar": KnownDocumentFormat.tar,
    ".gz": KnownDocumentFormat.gz,
}

_IMAGE_MIME = {
    KnownDocumentFormat.png: "image/png",
    KnownDocumentFormat.jpg: "image/jpeg",
    KnownDocumentFormat.jpeg: "image/jpeg",
    KnownDocumentFormat.gif: "image/gif",
    KnownDocumentFormat.tif: "image/tiff",
    KnownDocumentFormat.tiff: "image/tiff",
    KnownDocumentFormat.bmp: "image/bmp",
    KnownDocumentFormat.webp: "image/webp",
}


class _KnownOnlyAdapterBase:
    """Shared known-only adapter behavior."""

    adapter_id: str
    known_formats: tuple[KnownDocumentFormat, ...]
    promoted_formats: tuple[DocumentFormat, ...] = ()

    @property
    def engine_id(self) -> str:
        """Return adapter id for diagnostics."""
        return self.adapter_id

    def normalize_fill_patches(
        self,
        patches: tuple[DocumentFieldPatch, ...],
        *,
        extraction: DocumentExtraction | None,
    ) -> tuple[DocumentFieldPatch, ...]:
        """No passive adapter normalizes fill patches because writes are not promoted."""
        _ = extraction
        return patches


class OdfDocumentAdapter(_KnownOnlyAdapterBase):
    """Read-only ODF package candidate backed by ZIP/XML inspection."""

    adapter_id = "odf-package-read-only-adapter"
    known_formats = _ODF_FORMATS

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Extract ODF package text from content.xml without claiming mutation."""
        known_format = _known_format(path)
        paragraphs: list[ParagraphBlock] = []
        warnings: list[str] = []
        metadata: dict[str, MetadataValue] = _base_metadata(
            path,
            known_format=known_format,
            adapter_id=self.adapter_id,
            mutation_policy="read_only_odf_candidate",
        )
        try:
            with zipfile.ZipFile(path) as archive:
                metadata["package_entry_count"] = len(archive.infolist())
                if "content.xml" in archive.namelist():
                    root = ElementTree.fromstring(archive.read("content.xml"))
                    paragraphs = _paragraphs_from_text_lines(
                        artifact_id,
                        _xml_text_lines(root),
                        source_prefix="content.xml",
                    )
                else:
                    warnings.append("ODF package does not contain content.xml.")
        except zipfile.BadZipFile:
            warnings.append("ODF read-only candidate could not open the package as ZIP.")

        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=paragraphs,
            metadata=metadata,
            warnings=warnings,
        )


class DataFileDocumentAdapter(_KnownOnlyAdapterBase):
    """Read-only data-file adapter with serializer round-trip evidence."""

    adapter_id = "data-file-read-only-adapter"
    known_formats = _DATA_FORMATS

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Parse structured data files through safe local serializers."""
        known_format = _known_format(path)
        if known_format in {KnownDocumentFormat.csv, KnownDocumentFormat.tsv}:
            return _inspect_delimited(path, artifact_id=artifact_id, known_format=known_format)
        if known_format in {
            KnownDocumentFormat.json,
            KnownDocumentFormat.jsonl,
            KnownDocumentFormat.geojson,
        }:
            return _inspect_json(path, artifact_id=artifact_id, known_format=known_format)
        if known_format in {KnownDocumentFormat.yaml, KnownDocumentFormat.yml}:
            return _inspect_yaml(path, artifact_id=artifact_id, known_format=known_format)
        if known_format in {
            KnownDocumentFormat.xml,
            KnownDocumentFormat.rdf,
            KnownDocumentFormat.gpx,
            KnownDocumentFormat.kml,
            KnownDocumentFormat.hml,
        }:
            return _inspect_xml(path, artifact_id=artifact_id, known_format=known_format)
        if known_format in {
            KnownDocumentFormat.ttl,
            KnownDocumentFormat.lod,
            KnownDocumentFormat.fasta,
            KnownDocumentFormat.sgml,
            KnownDocumentFormat.dtd,
            KnownDocumentFormat.etc,
        }:
            return _inspect_text_data(path, artifact_id=artifact_id, known_format=known_format)
        return DocumentExtraction(
            artifact_id=artifact_id,
            metadata=_base_metadata(
                path,
                known_format=known_format,
                adapter_id=self.adapter_id,
                mutation_policy="read_only_data_file",
            ),
            warnings=[f"No passive data parser is implemented for {known_format.value}."],
        )


class LegacyOfficeDocumentAdapter(_KnownOnlyAdapterBase):
    """Metadata-only adapter for pre-OOXML Office binaries."""

    adapter_id = "legacy-office-metadata-only-adapter"
    known_formats = _LEGACY_OFFICE_FORMATS

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Identify legacy Office documents without parsing binary internals."""
        known_format = _known_format(path)
        return DocumentExtraction(
            artifact_id=artifact_id,
            metadata=_base_metadata(
                path,
                known_format=known_format,
                adapter_id=self.adapter_id,
                mutation_policy="conversion_required_legacy_office",
            ),
            warnings=[
                "Legacy Office binary inspection is metadata-only until an explicit local "
                "conversion bridge is approved."
            ],
        )


class TextWebExportAdapter(_KnownOnlyAdapterBase):
    """Read-only HTML, text, RTF, and Markdown export adapter."""

    adapter_id = "text-web-export-read-only-adapter"
    known_formats = _TEXT_WEB_FORMATS

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Extract visible text lines from text and web-export formats."""
        known_format = _known_format(path)
        payload = path.read_text(encoding="utf-8", errors="replace")
        lines = (
            _html_text_lines(payload)
            if known_format in {KnownDocumentFormat.html, KnownDocumentFormat.htm}
            else _plain_text_lines(_strip_minimal_rtf(payload))
        )
        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=_paragraphs_from_text_lines(
                artifact_id,
                lines,
                source_prefix=path.name,
            ),
            metadata=_base_metadata(
                path,
                known_format=known_format,
                adapter_id=self.adapter_id,
                mutation_policy="read_only_text_export",
            ),
        )


class CodeFileDocumentAdapter(_KnownOnlyAdapterBase):
    """Read-only source-code export adapter for public-data attachments."""

    adapter_id = "code-file-read-only-adapter"
    known_formats = _CODE_FORMATS

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Extract source lines for context without using the document writer."""
        payload = path.read_text(encoding="utf-8", errors="replace")
        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=_paragraphs_from_text_lines(
                artifact_id,
                _plain_text_lines(payload)[:200],
                source_prefix=path.name,
            ),
            metadata=_base_metadata(
                path,
                known_format=_known_format(path),
                adapter_id=self.adapter_id,
                mutation_policy="read_only_code_file",
            ),
            warnings=["Code files are not public-form documents and cannot be mutated here."],
        )


class ImageScanDocumentAdapter(_KnownOnlyAdapterBase):
    """Extraction-only image/scan adapter."""

    adapter_id = "image-scan-extraction-only-adapter"
    known_formats = _IMAGE_FORMATS

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Return an image reference without claiming OCR or write support."""
        known_format = _known_format(path)
        return DocumentExtraction(
            artifact_id=artifact_id,
            images=[
                ImageReference(
                    image_id=f"image-{known_format.value}",
                    source_path=str(path),
                    content_type=_IMAGE_MIME.get(known_format, "image/unknown"),
                )
            ],
            metadata=_base_metadata(
                path,
                known_format=known_format,
                adapter_id=self.adapter_id,
                mutation_policy="extraction_only",
            ),
            warnings=["Image scan adapter does not mutate raster originals."],
        )


class GeospatialDocumentAdapter(_KnownOnlyAdapterBase):
    """Metadata-only geospatial and 3D model adapter."""

    adapter_id = "geospatial-metadata-only-adapter"
    known_formats = _GEOSPATIAL_FORMATS

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Classify GIS/model artifacts without claiming document editing."""
        known_format = _known_format(path)
        paragraphs = (
            _paragraphs_from_text_lines(
                artifact_id,
                _plain_text_lines(path.read_text(encoding="utf-8", errors="replace"))[:40],
                source_prefix=path.name,
            )
            if known_format in {KnownDocumentFormat.prj, KnownDocumentFormat.stl}
            else []
        )
        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=paragraphs,
            metadata=_base_metadata(
                path,
                known_format=known_format,
                adapter_id=self.adapter_id,
                mutation_policy="metadata_only_geospatial_asset",
            ),
            warnings=[
                "Geospatial and 3D geometry files are classified for routing, not mutated "
                "as public documents."
            ],
        )


class MediaAssetDocumentAdapter(_KnownOnlyAdapterBase):
    """Metadata-only audio/video adapter."""

    adapter_id = "media-asset-metadata-only-adapter"
    known_formats = _MEDIA_FORMATS

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Classify media attachments without transcription or mutation claims."""
        return DocumentExtraction(
            artifact_id=artifact_id,
            metadata=_base_metadata(
                path,
                known_format=_known_format(path),
                adapter_id=self.adapter_id,
                mutation_policy="metadata_only_media_asset",
            ),
            warnings=[
                "Media files need a dedicated transcription or extraction adapter before "
                "content can be written into a public document derivative."
            ],
        )


class ArchiveDocumentSetAdapter(_KnownOnlyAdapterBase):
    """Read-only archive enumerator for secure child routing."""

    adapter_id = "archive-document-set-read-only-adapter"
    known_formats = _ARCHIVE_FORMATS

    def __init__(
        self,
        known_formats: tuple[KnownDocumentFormat, ...] | None = None,
    ) -> None:
        self.known_formats = known_formats or _ARCHIVE_FORMATS

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Enumerate archive members without mutating children in place."""
        known_format = _known_format(path)
        names, warnings = _archive_member_names(path, known_format=known_format)
        metadata = _base_metadata(
            path,
            known_format=known_format,
            adapter_id=self.adapter_id,
            mutation_policy="archive_read_only",
        )
        metadata["entry_count"] = len(names)
        metadata["child_mutation_policy"] = "route_children_as_derivatives"
        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=_paragraphs_from_text_lines(
                artifact_id,
                names,
                source_prefix=path.name,
            ),
            metadata=metadata,
            warnings=warnings,
        )


def _inspect_delimited(
    path: Path,
    *,
    artifact_id: str,
    known_format: KnownDocumentFormat,
) -> DocumentExtraction:
    delimiter = "\t" if known_format is KnownDocumentFormat.tsv else ","
    payload = path.read_text(encoding="utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(payload), delimiter=delimiter))
    serialized = io.StringIO()
    writer = csv.writer(serialized, delimiter=delimiter, lineterminator="\n")
    writer.writerows(rows)
    reparsed = list(csv.reader(io.StringIO(serialized.getvalue()), delimiter=delimiter))
    metadata = _base_metadata(
        path,
        known_format=known_format,
        adapter_id=DataFileDocumentAdapter.adapter_id,
        mutation_policy="read_only_data_file",
    )
    metadata.update(
        {
            "serializer": known_format.value,
            "round_trip_passed": rows == reparsed,
            "row_count": len(rows),
            "column_count": max((len(row) for row in rows), default=0),
        }
    )
    return DocumentExtraction(
        artifact_id=artifact_id,
        tables=[_table_from_rows(rows, source_path=path.name)],
        paragraphs=_paragraphs_from_text_lines(
            artifact_id,
            [",".join(row) for row in rows],
            source_prefix=path.name,
        ),
        metadata=metadata,
    )


def _inspect_json(
    path: Path,
    *,
    artifact_id: str,
    known_format: KnownDocumentFormat,
) -> DocumentExtraction:
    payload = path.read_text(encoding="utf-8")
    if known_format is KnownDocumentFormat.jsonl:
        values = [json.loads(line) for line in payload.splitlines() if line.strip()]
        serialized = "\n".join(
            json.dumps(value, ensure_ascii=False, sort_keys=True) for value in values
        )
        reparsed: object = [json.loads(line) for line in serialized.splitlines()]
        parsed: object = values
    else:
        parsed = json.loads(payload)
        serialized = json.dumps(parsed, ensure_ascii=False, sort_keys=True)
        reparsed = json.loads(serialized)
    return _structured_data_extraction(
        artifact_id,
        path=path,
        known_format=known_format,
        serializer=known_format.value,
        parsed=parsed,
        round_trip_passed=parsed == reparsed,
    )


def _inspect_yaml(
    path: Path,
    *,
    artifact_id: str,
    known_format: KnownDocumentFormat,
) -> DocumentExtraction:
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    serialized = yaml.safe_dump(parsed, allow_unicode=True, sort_keys=True)
    return _structured_data_extraction(
        artifact_id,
        path=path,
        known_format=known_format,
        serializer="yaml.safe_load/safe_dump",
        parsed=parsed,
        round_trip_passed=parsed == yaml.safe_load(serialized),
    )


def _inspect_xml(
    path: Path,
    *,
    artifact_id: str,
    known_format: KnownDocumentFormat,
) -> DocumentExtraction:
    root = ElementTree.fromstring(path.read_bytes())
    serialized = StdElementTree.tostring(root, encoding="unicode")
    reparsed = ElementTree.fromstring(serialized.encode("utf-8"))
    return _structured_data_extraction(
        artifact_id,
        path=path,
        known_format=known_format,
        serializer="defusedxml.ElementTree",
        parsed={"root_tag": _local_name(root.tag), "text": " ".join(_xml_text_lines(root))},
        round_trip_passed=_local_name(root.tag) == _local_name(reparsed.tag),
    )


def _inspect_text_data(
    path: Path,
    *,
    artifact_id: str,
    known_format: KnownDocumentFormat,
) -> DocumentExtraction:
    payload = path.read_text(encoding="utf-8", errors="replace")
    lines = _plain_text_lines(payload)[:200]
    metadata = _base_metadata(
        path,
        known_format=known_format,
        adapter_id=DataFileDocumentAdapter.adapter_id,
        mutation_policy="read_only_data_file",
    )
    metadata["serializer"] = "plain-text-preview"
    metadata["round_trip_passed"] = True
    metadata["line_count"] = len(lines)
    return DocumentExtraction(
        artifact_id=artifact_id,
        paragraphs=_paragraphs_from_text_lines(
            artifact_id,
            lines,
            source_prefix=path.name,
        ),
        metadata=metadata,
    )


def _structured_data_extraction(
    artifact_id: str,
    *,
    path: Path,
    known_format: KnownDocumentFormat,
    serializer: str,
    parsed: object,
    round_trip_passed: bool,
) -> DocumentExtraction:
    metadata = _base_metadata(
        path,
        known_format=known_format,
        adapter_id=DataFileDocumentAdapter.adapter_id,
        mutation_policy="read_only_data_file",
    )
    metadata.update(
        {
            "serializer": serializer,
            "round_trip_passed": round_trip_passed,
            "root_type": type(parsed).__name__,
        }
    )
    lines = _structured_preview_lines(parsed)
    return DocumentExtraction(
        artifact_id=artifact_id,
        paragraphs=_paragraphs_from_text_lines(
            artifact_id,
            lines,
            source_prefix=path.name,
        ),
        metadata=metadata,
    )


def _table_from_rows(rows: list[list[str]], *, source_path: str) -> TableBlock:
    cells: list[TableCell] = []
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            cells.append(
                TableCell(
                    row_index=row_index,
                    column_index=column_index,
                    text=value,
                    source_path=f"{source_path}#r{row_index + 1}c{column_index + 1}",
                )
            )
    return TableBlock(block_id="data-table-001", source_path=source_path, cells=cells)


def _archive_member_names(
    path: Path,
    *,
    known_format: KnownDocumentFormat,
) -> tuple[list[str], list[str]]:
    if known_format is KnownDocumentFormat.zip:
        with zipfile.ZipFile(path) as archive:
            return _safe_member_names(archive.namelist()), []
    if known_format is KnownDocumentFormat.tar:
        with tarfile.open(path) as archive:
            return _safe_member_names(archive.getnames()), []
    if known_format is KnownDocumentFormat.gz:
        with gzip.open(path) as payload:
            payload.read(1)
        return [path.with_suffix("").name or path.name], [
            "Gzip payload is treated as one compressed child candidate."
        ]
    return [], ["7z archive enumeration is known but not promoted without a 7z runtime."]


def _safe_member_names(names: list[str]) -> list[str]:
    return sorted(name for name in names if name and not name.startswith("/") and ".." not in name)


def _html_text_lines(payload: str) -> list[str]:
    parser = _VisibleTextParser()
    parser.feed(payload)
    return parser.lines


def _strip_minimal_rtf(payload: str) -> str:
    if not payload.lstrip().startswith("{\\rtf"):
        return payload
    stripped = payload.replace("\\par", "\n")
    return "".join(ch for ch in stripped if ch not in "{}")


def _plain_text_lines(payload: str) -> list[str]:
    return [line.strip() for line in payload.splitlines() if line.strip()]


def _xml_text_lines(root: StdElementTree.Element) -> list[str]:
    return [text.strip() for text in root.itertext() if text and text.strip()]


def _structured_preview_lines(value: object) -> list[str]:
    if isinstance(value, dict):
        return [f"{key}: {preview}" for key, preview in list(value.items())[:20]]
    if isinstance(value, list):
        return [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value[:20]]
    return [str(value)]


def _paragraphs_from_text_lines(
    artifact_id: str,
    lines: list[str],
    *,
    source_prefix: str,
) -> list[ParagraphBlock]:
    return [
        ParagraphBlock(
            block_id=f"{artifact_id}-line-{index:03d}",
            text=line,
            source_path=f"{source_prefix}#line[{index}]",
        )
        for index, line in enumerate(lines, start=1)
        if line
    ]


def _base_metadata(
    path: Path,
    *,
    known_format: KnownDocumentFormat,
    adapter_id: str,
    mutation_policy: str,
) -> dict[str, MetadataValue]:
    return {
        "adapter_id": adapter_id,
        "known_format": known_format.value,
        "mutation_policy": mutation_policy,
        "byte_size": path.stat().st_size,
    }


def _known_format(path: Path) -> KnownDocumentFormat:
    return _KNOWN_BY_EXTENSION.get(path.suffix.lower(), KnownDocumentFormat.txt)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


class _VisibleTextParser(HTMLParser):
    """Small HTML text extractor for passive public-form exports."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.lines.append(text)
