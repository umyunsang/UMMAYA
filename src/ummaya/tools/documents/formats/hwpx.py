# SPDX-License-Identifier: Apache-2.0
"""HWPX engine-adapter boundary."""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, cast
from zipfile import ZIP_STORED, BadZipFile, ZipFile, ZipInfo

from defusedxml import ElementTree  # type: ignore[import-untyped]

from ummaya.tools.documents.engines import DocumentInspectionEngine, DocumentMutationEngine
from ummaya.tools.documents.models import (
    BorderDescriptor,
    DocumentExtraction,
    DocumentFormat,
    DocumentPatch,
    FormField,
    KnownDocumentFormat,
    OperationType,
    ParagraphBlock,
    StyleAlignment,
    StyleDescriptor,
    TableBlock,
    TableCell,
)

if TYPE_CHECKING:
    from ummaya.tools.documents.tool_defs import DocumentFieldPatch

HWPX_CANDIDATE_ENGINES: tuple[str, ...] = (
    "hwpx-package-text",
    "rhwp-node-wasm",
    "python-hwpx",
    "hwpx-mcp-server",
    "rhwp",
    "direct-owpml-oracle",
)

_TEXT_TARGET_RE = re.compile(r"^/hwpx/text\[(?P<index>[1-9][0-9]*)\]$")
_HWPX_TABLE_CELL_ALIAS_RE = re.compile(
    r"^(?:/body/section\[[1-9][0-9]*\])?/table\[(?P<table>[1-9][0-9]*)\]/"
    r"(?:(?:cells\[(?P<row_bracket>[1-9][0-9]*)\]\[(?P<col_bracket>[1-9][0-9]*)\])|"
    r"(?:cell\[(?P<row_csv>[1-9][0-9]*),(?P<col_csv>[1-9][0-9]*)\]))$"
)
_HWPX_TABLE_CELL_SOURCE_RE = re.compile(
    r"^(?P<member>Contents/section[0-9]+\.xml)#table\[(?P<table>[1-9][0-9]*)\]/"
    r"r(?P<row>[1-9][0-9]*)c(?P<column>[1-9][0-9]*)$"
)
_HWPX_ACTIVITY_PERIOD_VALUE_RE = re.compile(
    r"\b[0-9]{4}\.[0-9]{2}\.[0-9]{2}\s*~\s*[0-9]{4}\.[0-9]{2}\.[0-9]{2}\b"
)
_DOCUMENT_WEEK_VALUE_RE = re.compile(r"[0-9]{1,3}")
_SECTION_PREFIX = "Contents/section"


_HWPX_COMPATIBLE_FORMATS = frozenset({DocumentFormat.hwpx, DocumentFormat.owpml})


@dataclass(frozen=True)
class _HwpXTextRecord:
    element: ET.Element
    char_style_id: str | None
    para_style_id: str | None
    named_style_id: str | None


@dataclass(frozen=True)
class _HwpXTableCellTarget:
    member: str
    table_index: int
    row_index: int
    column_index: int


@dataclass(frozen=True)
class _HwpXStyleRefs:
    char_pr_id: str | None = None
    para_pr_id: str | None = None
    style_id: str | None = None


@dataclass(frozen=True)
class _HwpXPatchBuckets:
    text_replacements: dict[int, str]
    table_cell_replacements: dict[_HwpXTableCellTarget, str]
    text_styles: dict[int, StyleDescriptor]
    table_cell_styles: dict[_HwpXTableCellTarget, StyleDescriptor]

    @property
    def has_style_mutations(self) -> bool:
        return bool(self.text_styles or self.table_cell_styles)


def validate_hwpx_engine(engine: DocumentInspectionEngine) -> DocumentInspectionEngine:
    """Validate that an injected engine is scoped to an OWPML/HWPX package."""
    if engine.document_format not in _HWPX_COMPATIBLE_FORMATS:
        raise ValueError("HWPX adapter requires a hwpx-compatible engine")
    return engine


def validate_hwpx_mutation_engine(engine: DocumentInspectionEngine) -> DocumentMutationEngine:
    """Validate that an injected HWPX engine can safely mutate derivatives."""
    validate_hwpx_engine(engine)
    if not isinstance(engine, DocumentMutationEngine):
        raise ValueError("HWPX adapter requires a mutation-capable engine")
    return engine


class HwpXPackageTextEngine:
    """Text-node HWPX engine for deterministic local package edits."""

    document_format = DocumentFormat.hwpx
    engine_id = "hwpx-package-text"
    render_engine_id = "rhwp-node-wasm"
    render_artifact_extension = "svg"
    render_mime_type = "image/svg+xml"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Extract HWPX text nodes as LLM-addressable paragraphs and fields."""
        paragraphs: list[ParagraphBlock] = []
        fields: list[FormField] = []
        tables: list[TableBlock] = []
        text_index = 1
        section_count = 0
        text_records: list[tuple[int, str, str, str]] = []
        semantic_labels: dict[int, str] = {}
        style_map: list[StyleDescriptor] = []

        with ZipFile(path) as archive:
            style_map = _style_map_from_header(archive)
            for member in _section_members(archive):
                section_count += 1
                root = ElementTree.fromstring(archive.read(member))
                text_index_by_element_id: dict[int, int] = {}
                for record in _text_records(root):
                    elem = record.element
                    text = elem.text or ""
                    if not text:
                        continue
                    target_path = f"/hwpx/text[{text_index}]"
                    source_path = f"{member}#text[{text_index}]"
                    text_index_by_element_id[id(elem)] = text_index
                    paragraphs.append(
                        ParagraphBlock(
                            block_id=f"hwpx-text-{text_index:03d}",
                            text=text,
                            source_path=source_path,
                            style_id=record.char_style_id
                            or record.named_style_id
                            or record.para_style_id,
                        )
                    )
                    text_records.append((text_index, text, target_path, source_path))
                    text_index += 1
                tables.extend(
                    _table_blocks(
                        root,
                        member=member,
                        table_start_index=len(tables) + 1,
                        text_index_by_element_id=text_index_by_element_id,
                        semantic_labels=semantic_labels,
                    )
                )

        for record_index, text, target_path, _source_path in text_records:
            fields.append(
                FormField(
                    field_id=f"hwpx-text-{record_index:03d}",
                    label=semantic_labels.get(record_index)
                    or _semantic_label_for_text_value(text)
                    or f"HWPX text node {record_index}",
                    path=target_path,
                    field_type="text",
                    required=False,
                    current_value=text,
                    source_confidence=Decimal("1"),
                )
            )

        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=paragraphs,
            tables=tables,
            fields=fields,
            metadata={
                "format": self.document_format.value,
                "engine_id": self.engine_id,
                "section_count": section_count,
                "text_node_count": len(paragraphs),
                "table_count": len(tables),
                "style_map_count": len(style_map),
            },
            style_map=style_map,
            warnings=[
                "HWPX package text engine edits text nodes only; page SVG render evidence is "
                "delegated to the RHWP Node/WASM bridge."
            ],
        )

    def apply_patch(self, path: Path, patch: DocumentPatch) -> bytes:
        """Apply ordered HWPX text-node patches and return derivative package bytes."""
        patch_buckets = _hwpx_patch_buckets_from_patch(patch)
        namespace_maps: dict[str, list[tuple[str, str]]] = {}
        section_payloads: dict[str, bytes] = {}
        text_index = 1
        table_index = 1
        applied_table_cell_targets: set[_HwpXTableCellTarget] = set()
        applied_text_style_targets: set[int] = set()
        applied_table_cell_style_targets: set[_HwpXTableCellTarget] = set()

        with ZipFile(path) as archive:
            text_style_refs, table_cell_style_refs, header_payload = _hwpx_style_refs_from_buckets(
                archive, patch_buckets
            )

            for member in _section_members(archive):
                payload = archive.read(member)
                namespace_maps[member] = _namespace_map(payload)
                root = ElementTree.fromstring(payload)
                (
                    text_index,
                    table_index,
                    applied_targets,
                    applied_style_indexes,
                    applied_style_targets,
                ) = _apply_hwpx_section_mutations(
                    root,
                    member=member,
                    text_index=text_index,
                    table_index=table_index,
                    text_replacements=patch_buckets.text_replacements,
                    table_cell_replacements=patch_buckets.table_cell_replacements,
                    text_style_refs=text_style_refs,
                    table_cell_style_refs=table_cell_style_refs,
                )
                applied_table_cell_targets.update(applied_targets)
                applied_text_style_targets.update(applied_style_indexes)
                applied_table_cell_style_targets.update(applied_style_targets)
                section_payloads[member] = _serialize_section(root, namespace_maps[member])

            _raise_for_missing_hwpx_patch_targets(
                patch_buckets=patch_buckets,
                text_style_refs=text_style_refs,
                table_cell_style_refs=table_cell_style_refs,
                text_index=text_index,
                applied_table_cell_targets=applied_table_cell_targets,
                applied_text_style_targets=applied_text_style_targets,
                applied_table_cell_style_targets=applied_table_cell_style_targets,
            )
            return _rewrite_hwpx_package(
                archive,
                section_payloads=section_payloads,
                header_payload=header_payload,
            )

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        """Render HWPX page SVG evidence through the RHWP Node/WASM bridge."""
        _ = artifact_id
        if _uses_hwpxjs_html_render(path):
            output_dir.mkdir(parents=True, exist_ok=True)
            return (_render_with_hwpxjs_html(path),)
        return _render_with_rhwp_node(path, output_dir=output_dir)

    def render_artifact_extension_for(self, path: Path) -> str:
        """Return the render artifact extension selected by HWPX package structure."""
        return "html" if _uses_hwpxjs_html_render(path) else self.render_artifact_extension

    def render_mime_type_for(self, path: Path) -> str:
        """Return the render MIME selected by HWPX package structure."""
        return "text/html" if _uses_hwpxjs_html_render(path) else self.render_mime_type

    def render_engine_id_for(self, path: Path) -> str:
        """Return the render engine selected by HWPX package structure."""
        return "hwpxjs-html-render" if _uses_hwpxjs_html_render(path) else self.render_engine_id


class OwpmlPackageTextEngine(HwpXPackageTextEngine):
    """OWPML extension alias backed by the same package text engine as HWPX."""

    document_format = DocumentFormat.owpml
    engine_id = "owpml-package-text"


class HwpXDocumentAdapter:
    """HWPX adapter for native package inspection and target normalization."""

    known_formats: tuple[KnownDocumentFormat, ...] = (
        KnownDocumentFormat.hwpx,
        KnownDocumentFormat.owpml,
    )
    promoted_formats: tuple[DocumentFormat, ...] = (DocumentFormat.hwpx, DocumentFormat.owpml)

    def __init__(self, *, inspection_engine: DocumentInspectionEngine | None = None) -> None:
        engine = inspection_engine or HwpXPackageTextEngine()
        self._inspection_engine = validate_hwpx_engine(engine)
        self.adapter_id = f"{self._inspection_engine.engine_id}-adapter"

    @property
    def engine_id(self) -> str:
        """Return the wrapped HWPX engine id for diagnostics."""
        return self._inspection_engine.engine_id

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Inspect a local HWPX package through the wrapped engine."""
        return self._inspection_engine.inspect(path, artifact_id=artifact_id)

    def normalize_fill_patches(
        self,
        patches: tuple[DocumentFieldPatch, ...],
        *,
        extraction: DocumentExtraction | None,
    ) -> tuple[DocumentFieldPatch, ...]:
        """Map semantic/table aliases to native HWPX text-node targets."""
        if extraction is None:
            return patches

        normalized_patches: list[DocumentFieldPatch] = []
        for patch in patches:
            normalized_target = _normalized_fill_target(patch.target_path, extraction)
            if (
                not patch.target_path.strip().startswith("/")
                and normalized_target == patch.target_path
                and _semantic_target_group(_semantic_field_key(patch.target_path)) is None
                and not _is_known_hwpx_native_fill_target(patch.target_path, extraction)
            ):
                continue
            normalized_value = _normalized_fill_value(
                patch.value,
                original_target=patch.target_path,
                normalized_target=normalized_target,
                extraction=extraction,
            )
            normalized_patches.append(
                patch.model_copy(
                    update={"target_path": normalized_target, "value": normalized_value}
                )
            )
        return tuple(normalized_patches)


def _is_known_hwpx_native_fill_target(
    target_path: str,
    extraction: DocumentExtraction,
) -> bool:
    if target_path in {field.path for field in extraction.fields}:
        return True
    return target_path in set(_hwpx_table_cell_alias_map(extraction).values())


def _normalized_fill_target(
    target_path: str,
    extraction: DocumentExtraction,
) -> str:
    semantic_target = _semantic_hwpx_field_target(target_path, extraction)
    if semantic_target is not None:
        return semantic_target
    alias_map = _hwpx_table_cell_alias_map(extraction)
    if target_path in alias_map:
        return alias_map[target_path]
    match = _HWPX_TABLE_CELL_ALIAS_RE.match(target_path)
    if match is None:
        return target_path
    row = match.group("row_bracket") or match.group("row_csv")
    column = match.group("col_bracket") or match.group("col_csv")
    if row is None or column is None:
        return target_path
    coordinate_key = f"/table[{match.group('table')}]/cells[{row}][{column}]"
    return alias_map.get(coordinate_key, target_path)


def _normalized_fill_value(
    value: object,
    *,
    original_target: str,
    normalized_target: str,
    extraction: DocumentExtraction,
) -> object:
    target_group = _semantic_target_group(_semantic_field_key(original_target))
    if target_group is None:
        target_group = _semantic_group_for_extracted_path(normalized_target, extraction)
    if target_group != "week_label":
        return value
    week_value = _numeric_week_value(value)
    return f"{week_value}주차" if week_value is not None else value


def _semantic_group_for_extracted_path(
    target_path: str,
    extraction: DocumentExtraction,
) -> str | None:
    for field in extraction.fields:
        if field.path != target_path:
            continue
        if not isinstance(field.current_value, str):
            continue
        if re.fullmatch(r"[0-9]+주차", _semantic_field_key(field.current_value)):
            return "week_label"
    return None


def _semantic_label_for_text_value(value: str) -> str | None:
    normalized = unicodedata.normalize("NFKC", value)
    value_key = _semantic_field_key(normalized)
    if re.fullmatch(r"[0-9]+주차", value_key):
        return "주차"
    if _HWPX_ACTIVITY_PERIOD_VALUE_RE.search(normalized):
        return "활동기간"
    if value_key in {"특이사항", "비고"}:
        return None
    if "특이사항" in value_key:
        return "특이사항"
    return None


def _numeric_week_value(value: object) -> str | None:
    if isinstance(value, int):
        return str(value)
    if not isinstance(value, str):
        return None
    normalized = unicodedata.normalize("NFKC", value).strip()
    if _DOCUMENT_WEEK_VALUE_RE.fullmatch(normalized) is None:
        return None
    return normalized.lstrip("0") or "0"


def _semantic_hwpx_field_target(
    target_path: str,
    extraction: DocumentExtraction,
) -> str | None:
    """Map conservative semantic field names to extracted HWPX form labels."""
    normalized_target = _semantic_field_key(target_path)
    if not normalized_target or target_path.strip().startswith("/"):
        return None

    exact_matches = [
        field.path
        for field in extraction.fields
        if _semantic_field_key(field.label) == normalized_target
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]

    target_group = _semantic_target_group(normalized_target)
    if target_group is None:
        return None

    group_matches = [
        field.path
        for field in extraction.fields
        if _semantic_label_group(_semantic_field_key(field.label)) == target_group
    ]
    unique_matches = list(dict.fromkeys(group_matches))
    if len(unique_matches) == 1:
        return unique_matches[0]

    value_matches = _semantic_hwpx_value_matches(target_group, extraction)
    return value_matches[0] if len(value_matches) == 1 else None


def _semantic_hwpx_value_matches(
    target_group: str,
    extraction: DocumentExtraction,
) -> list[str]:
    matches: list[str] = []
    for field in extraction.fields:
        if not isinstance(field.current_value, str):
            continue
        value = unicodedata.normalize("NFKC", field.current_value)
        value_key = _semantic_field_key(value)
        if (target_group == "activity_period" and _HWPX_ACTIVITY_PERIOD_VALUE_RE.search(value)) or (
            target_group == "week_label" and re.fullmatch(r"[0-9]+주차", value_key)
        ):
            matches.append(field.path)
    return list(dict.fromkeys(matches))


def _semantic_field_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^0-9a-z가-힣]+", "", normalized)


def _semantic_target_group(normalized_target: str) -> str | None:
    if not normalized_target:
        return None
    if _matches_special_notes_target(normalized_target):
        return "special_notes"
    if _matches_team_name_target(normalized_target):
        return "team_name"
    if _matches_week_label_target(normalized_target):
        return "week_label"
    if _matches_activity_period_target(normalized_target):
        return "activity_period"
    return None


def _matches_special_notes_target(normalized_target: str) -> bool:
    return any(
        token in normalized_target
        for token in ("특이", "비고", "special", "remark", "remarks", "note", "notes")
    )


def _matches_team_name_target(normalized_target: str) -> bool:
    return (
        "팀명" in normalized_target
        or ("team" in normalized_target and "name" in normalized_target)
        or normalized_target == "team"
    )


def _matches_week_label_target(normalized_target: str) -> bool:
    return "주차" in normalized_target or normalized_target in {
        "week",
        "weeknumber",
        "weeklabel",
    }


def _matches_activity_period_target(normalized_target: str) -> bool:
    return (
        "활동일시" in normalized_target
        or "활동기간" in normalized_target
        or (
            "activity" in normalized_target
            and any(token in normalized_target for token in ("period", "date", "time"))
        )
        or "weekperiod" in normalized_target
        or normalized_target.endswith("period")
    )


def _semantic_label_group(normalized_label: str) -> str | None:
    if "특이사항" in normalized_label or normalized_label == "비고":
        return "special_notes"
    if normalized_label == "팀명":
        return "team_name"
    if "주차" in normalized_label:
        return "week_label"
    if normalized_label in {"활동일시", "활동기간"}:
        return "activity_period"
    return None


def _hwpx_table_cell_alias_map(extraction: DocumentExtraction) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for table_index, table in enumerate(extraction.tables, start=1):
        for cell in table.cells:
            native_target = cell.field_path or cell.source_path
            row = cell.row_index + 1
            column = cell.column_index + 1
            aliases[cell.source_path] = native_target
            aliases[f"/table[{table_index}]/cell[{row},{column}]"] = native_target
            aliases[f"/table[{table_index}]/cells[{row}][{column}]"] = native_target
            aliases[f"/body/section[1]/table[{table_index}]/cell[{row},{column}]"] = native_target
            aliases[f"/body/section[1]/table[{table_index}]/cells[{row}][{column}]"] = native_target
    return aliases


def _section_members(archive: ZipFile) -> list[str]:
    return sorted(
        member.filename
        for member in archive.infolist()
        if member.filename.startswith(_SECTION_PREFIX) and member.filename.endswith(".xml")
    )


def _text_elements(root: ET.Element) -> list[ET.Element]:
    return [elem for elem in root.iter() if elem.tag.rsplit("}", 1)[-1] == "t"]


def _text_records(root: ET.Element) -> list[_HwpXTextRecord]:
    records: list[_HwpXTextRecord] = []
    parent_by_id = _parent_by_element_id(root)
    for text_element in _text_elements(root):
        run = _nearest_ancestor_by_local_name(text_element, "run", parent_by_id)
        paragraph = _nearest_ancestor_by_local_name(text_element, "p", parent_by_id)
        if paragraph is None:
            continue
        para_pr_id = _local_attr(paragraph, "paraPrIDRef")
        named_style_id = _local_attr(paragraph, "styleIDRef")
        char_pr_id = _local_attr(run, "charPrIDRef") if run is not None else None
        records.append(
            _HwpXTextRecord(
                element=text_element,
                char_style_id=f"charPr-{char_pr_id}" if char_pr_id else None,
                para_style_id=f"paraPr-{para_pr_id}" if para_pr_id else None,
                named_style_id=f"style-{named_style_id}" if named_style_id else None,
            )
        )
    return records


def _parent_by_element_id(root: ET.Element) -> dict[int, ET.Element]:
    return {id(child): parent for parent in root.iter() for child in list(parent)}


def _nearest_ancestor_by_local_name(
    element: ET.Element,
    name: str,
    parent_by_id: dict[int, ET.Element],
) -> ET.Element | None:
    current = parent_by_id.get(id(element))
    while current is not None:
        if _local_name(current.tag) == name:
            return current
        current = parent_by_id.get(id(current))
    return None


def _style_map_from_header(archive: ZipFile) -> list[StyleDescriptor]:
    try:
        header = ElementTree.fromstring(archive.read("Contents/header.xml"))
    except (KeyError, ElementTree.ParseError):
        return []
    font_faces = _font_faces_by_id(header)
    border_fills = _border_fill_styles_by_id(header)
    char_styles = _char_styles_by_id(header, font_faces=font_faces, border_fills=border_fills)
    para_styles = _para_styles_by_id(header)
    named_styles = _named_styles_by_id(
        header,
        char_styles=char_styles,
        para_styles=para_styles,
    )
    return [
        *border_fills.values(),
        *char_styles.values(),
        *para_styles.values(),
        *named_styles.values(),
    ]


def _font_faces_by_id(root: ET.Element) -> dict[str, str]:
    faces: dict[str, str] = {}
    for fontface in _elements_by_local_name(root, "fontface"):
        lang = (_local_attr(fontface, "lang") or "").casefold()
        if lang not in {"hangul", "korean", "latin", ""}:
            continue
        for font in _child_elements_by_local_name(fontface, "font"):
            font_id = _local_attr(font, "id")
            face = _local_attr(font, "face")
            if font_id is not None and face:
                faces.setdefault(font_id, face)
    return faces


def _border_fill_styles_by_id(root: ET.Element) -> dict[str, StyleDescriptor]:
    styles: dict[str, StyleDescriptor] = {}
    for border_fill in _elements_by_local_name(root, "borderFill"):
        border_fill_id = _local_attr(border_fill, "id")
        if border_fill_id is None:
            continue
        fill_color = _border_fill_color(border_fill)
        border = _border_descriptor(border_fill)
        styles[border_fill_id] = StyleDescriptor(
            style_id=f"borderFill-{border_fill_id}",
            target_path=f"Contents/header.xml#borderFill[{border_fill_id}]",
            fill_color_rgb=fill_color,
            border=border,
        )
    return styles


def _char_styles_by_id(
    root: ET.Element,
    *,
    font_faces: dict[str, str],
    border_fills: dict[str, StyleDescriptor],
) -> dict[str, StyleDescriptor]:
    styles: dict[str, StyleDescriptor] = {}
    for char_pr in _elements_by_local_name(root, "charPr"):
        char_pr_id = _local_attr(char_pr, "id")
        if char_pr_id is None:
            continue
        border_fill_id = _local_attr(char_pr, "borderFillIDRef")
        border_fill = border_fills.get(border_fill_id or "")
        font_id = _font_ref_id(char_pr)
        font_color = _rgb(_local_attr(char_pr, "textColor"))
        shade_color = _rgb(_local_attr(char_pr, "shadeColor"))
        styles[char_pr_id] = StyleDescriptor(
            style_id=f"charPr-{char_pr_id}",
            target_path=f"Contents/header.xml#charPr[{char_pr_id}]",
            font_family=font_faces.get(font_id or ""),
            font_size_pt=_hwpx_height_to_points(_local_attr(char_pr, "height")),
            bold=_has_child(char_pr, "bold") or None,
            italic=_has_child(char_pr, "italic") or None,
            underline=_has_child(char_pr, "underline") or None,
            font_color_rgb=font_color,
            fill_color_rgb=shade_color or (border_fill.fill_color_rgb if border_fill else None),
            border=border_fill.border if border_fill else None,
        )
    return styles


def _para_styles_by_id(root: ET.Element) -> dict[str, StyleDescriptor]:
    styles: dict[str, StyleDescriptor] = {}
    for para_pr in _elements_by_local_name(root, "paraPr"):
        para_pr_id = _local_attr(para_pr, "id")
        if para_pr_id is None:
            continue
        styles[para_pr_id] = StyleDescriptor(
            style_id=f"paraPr-{para_pr_id}",
            target_path=f"Contents/header.xml#paraPr[{para_pr_id}]",
            alignment=_hwpx_alignment(_first_child_by_local_name(para_pr, "align")),
        )
    return styles


def _named_styles_by_id(
    root: ET.Element,
    *,
    char_styles: dict[str, StyleDescriptor],
    para_styles: dict[str, StyleDescriptor],
) -> dict[str, StyleDescriptor]:
    styles: dict[str, StyleDescriptor] = {}
    for style in _elements_by_local_name(root, "style"):
        style_id = _local_attr(style, "id")
        if style_id is None:
            continue
        char_style = char_styles.get(_local_attr(style, "charPrIDRef") or "")
        para_style = para_styles.get(_local_attr(style, "paraPrIDRef") or "")
        styles[style_id] = _merge_hwpx_styles(
            style_id=f"style-{style_id}",
            target_path=f"Contents/header.xml#style[{style_id}]",
            char_style=char_style,
            para_style=para_style,
        )
    return styles


def _merge_hwpx_styles(
    *,
    style_id: str,
    target_path: str,
    char_style: StyleDescriptor | None,
    para_style: StyleDescriptor | None,
) -> StyleDescriptor:
    return StyleDescriptor(
        style_id=style_id,
        target_path=target_path,
        font_family=char_style.font_family if char_style else None,
        font_size_pt=char_style.font_size_pt if char_style else None,
        bold=char_style.bold if char_style else None,
        italic=char_style.italic if char_style else None,
        underline=char_style.underline if char_style else None,
        font_color_rgb=char_style.font_color_rgb if char_style else None,
        fill_color_rgb=char_style.fill_color_rgb if char_style else None,
        alignment=para_style.alignment if para_style else None,
        line_spacing=para_style.line_spacing if para_style else None,
        border=char_style.border if char_style else None,
        number_format=char_style.number_format if char_style else None,
    )


def _font_ref_id(char_pr: ET.Element) -> str | None:
    font_ref = _first_child_by_local_name(char_pr, "fontRef")
    if font_ref is None:
        return None
    return (
        _local_attr(font_ref, "hangul")
        or _local_attr(font_ref, "latin")
        or _local_attr(font_ref, "hanja")
        or _local_attr(font_ref, "other")
    )


def _border_fill_color(border_fill: ET.Element) -> str | None:
    for brush_name in ("winBrush", "gradation", "imgBrush"):
        brush = _first_descendant_by_local_name(border_fill, brush_name)
        if brush is None:
            continue
        color = _rgb(_local_attr(brush, "faceColor") or _local_attr(brush, "color"))
        if color is not None:
            return color
    return None


def _border_descriptor(border_fill: ET.Element) -> BorderDescriptor | None:
    for border_name in ("leftBorder", "topBorder", "rightBorder", "bottomBorder"):
        border = _first_child_by_local_name(border_fill, border_name)
        if border is None:
            continue
        border_type = _local_attr(border, "type")
        if border_type is None or border_type == "NONE":
            continue
        return BorderDescriptor(
            style=border_type,
            width_pt=_hwpx_measure_to_points(_local_attr(border, "width")),
            color_rgb=_rgb(_local_attr(border, "color")),
        )
    return None


def _hwpx_height_to_points(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value) / Decimal("100")
    except ArithmeticError:
        return None


def _hwpx_measure_to_points(value: str | None) -> Decimal | None:
    if value is None:
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*mm", value)
    if match is None:
        return None
    try:
        return (Decimal(match.group(1)) * Decimal("2.834645669")).quantize(Decimal("0.01"))
    except ArithmeticError:
        return None


def _hwpx_alignment(align: ET.Element | None) -> StyleAlignment | None:
    if align is None:
        return None
    horizontal = (_local_attr(align, "horizontal") or "").casefold()
    alignment_by_hwpx_value: dict[str, StyleAlignment] = {
        "left": "left",
        "center": "center",
        "right": "right",
        "justify": "justify",
        "distributed": "distributed",
    }
    return alignment_by_hwpx_value.get(horizontal)


def _rgb(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or normalized.casefold() == "none":
        return None
    if normalized.startswith("#"):
        normalized = normalized[1:]
    return normalized.upper() if re.fullmatch(r"[0-9A-Fa-f]{6}", normalized) else None


def _local_attr(element: ET.Element, name: str) -> str | None:
    for key, value in element.attrib.items():
        if _local_name(key) == name:
            return value
    return None


def _has_child(element: ET.Element, name: str) -> bool:
    return _first_child_by_local_name(element, name) is not None


def _first_child_by_local_name(element: ET.Element, name: str) -> ET.Element | None:
    for child in list(element):
        if _local_name(child.tag) == name:
            return child
    return None


def _first_descendant_by_local_name(element: ET.Element, name: str) -> ET.Element | None:
    for descendant in element.iter():
        if descendant is not element and _local_name(descendant.tag) == name:
            return descendant
    return None


def _table_blocks(
    root: ET.Element,
    *,
    member: str,
    table_start_index: int,
    text_index_by_element_id: dict[int, int],
    semantic_labels: dict[int, str],
) -> list[TableBlock]:
    tables: list[TableBlock] = []
    for table_offset, table in enumerate(_elements_by_local_name(root, "tbl")):
        table_index = table_start_index + table_offset
        cells: list[TableCell] = []
        for row_index, row in enumerate(_child_elements_by_local_name(table, "tr")):
            row_cells = _child_elements_by_local_name(row, "tc")
            row_text_nodes: list[list[ET.Element]] = []
            for column_index, cell in enumerate(row_cells):
                text_nodes = [elem for elem in _text_elements(cell) if elem.text]
                row_text_nodes.append(text_nodes)
                text = "".join(elem.text or "" for elem in text_nodes)
                first_text_index = (
                    text_index_by_element_id.get(id(text_nodes[0])) if text_nodes else None
                )
                cells.append(
                    TableCell(
                        row_index=row_index,
                        column_index=column_index,
                        text=text,
                        row_span=_span_attribute(cell, "rowSpan"),
                        column_span=_span_attribute(cell, "colSpan"),
                        source_path=(
                            f"{member}#table[{table_index}]/r{row_index + 1}c{column_index + 1}"
                        ),
                        field_path=(
                            f"/hwpx/text[{first_text_index}]"
                            if first_text_index is not None
                            else None
                        ),
                    )
                )
            pair_start = 1 if len(row_cells) > 2 and len(row_cells) % 2 == 1 else 0
            for label_column in range(pair_start, len(row_cells) - 1, 2):
                label = _cell_text(row_cells[label_column]).strip()
                value_text_nodes = row_text_nodes[label_column + 1]
                if not label or not value_text_nodes:
                    continue
                first_value_index = text_index_by_element_id.get(id(value_text_nodes[0]))
                if first_value_index is not None:
                    semantic_labels[first_value_index] = label
        tables.append(
            TableBlock(
                block_id=f"hwpx-table-{table_index:03d}",
                source_path=f"{member}#table[{table_index}]",
                cells=cells,
            )
        )
    return tables


def _elements_by_local_name(root: ET.Element, name: str) -> list[ET.Element]:
    return [elem for elem in root.iter() if _local_name(elem.tag) == name]


def _child_elements_by_local_name(root: ET.Element, name: str) -> list[ET.Element]:
    return [elem for elem in list(root) if _local_name(elem.tag) == name]


def _cell_text(cell: ET.Element) -> str:
    return "".join(elem.text or "" for elem in _text_elements(cell) if elem.text)


def _span_attribute(cell: ET.Element, name: str) -> int:
    for key, value in cell.attrib.items():
        if _local_name(key) == name:
            try:
                return max(1, int(value))
            except ValueError:
                return 1
    return 1


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _hwpx_patch_buckets_from_patch(patch: DocumentPatch) -> _HwpXPatchBuckets:
    text_replacements: dict[int, str] = {}
    table_cell_replacements: dict[_HwpXTableCellTarget, str] = {}
    text_styles: dict[int, StyleDescriptor] = {}
    table_cell_styles: dict[_HwpXTableCellTarget, StyleDescriptor] = {}
    for operation in patch.operations:
        if operation.operation_type in {
            OperationType.set_field_value,
            OperationType.replace_text,
            OperationType.set_table_cell,
        }:
            value = "" if operation.value is None else str(operation.value)
            text_match = _TEXT_TARGET_RE.match(operation.target_path)
            if text_match is not None:
                text_replacements[int(text_match.group("index"))] = value
                continue
            table_cell_target = _hwpx_table_cell_target(operation.target_path)
            if table_cell_target is not None:
                table_cell_replacements[table_cell_target] = value
                continue
            if operation.operation_type is OperationType.set_table_cell:
                raise ValueError(
                    f"Unsupported HWPX table cell target path: {operation.target_path}"
                )
            raise ValueError(f"Unsupported HWPX text target path: {operation.target_path}")
        if operation.operation_type in {
            OperationType.set_paragraph_style,
            OperationType.set_run_style,
            OperationType.set_cell_style,
        }:
            if operation.style is None:
                raise ValueError("HWPX style operation requires style")
            text_match = _TEXT_TARGET_RE.match(operation.target_path)
            if text_match is not None:
                text_styles[int(text_match.group("index"))] = operation.style
                continue
            table_cell_target = _hwpx_table_cell_target(operation.target_path)
            if table_cell_target is not None:
                table_cell_styles[table_cell_target] = operation.style
                continue
            raise ValueError(f"Unsupported HWPX style target path: {operation.target_path}")
        raise ValueError(f"Unsupported HWPX operation: {operation.operation_type.value}")
    return _HwpXPatchBuckets(
        text_replacements=text_replacements,
        table_cell_replacements=table_cell_replacements,
        text_styles=text_styles,
        table_cell_styles=table_cell_styles,
    )


def _hwpx_header_payload(archive: ZipFile) -> bytes:
    try:
        return archive.read("Contents/header.xml")
    except KeyError:
        return b'<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" />'


def _hwpx_style_refs_from_buckets(
    archive: ZipFile,
    patch_buckets: _HwpXPatchBuckets,
) -> tuple[dict[int, _HwpXStyleRefs], dict[_HwpXTableCellTarget, _HwpXStyleRefs], bytes | None]:
    if not patch_buckets.has_style_mutations:
        return {}, {}, None
    header_source = _hwpx_header_payload(archive)
    header_namespaces = _namespace_map(header_source)
    header_root = ElementTree.fromstring(header_source)
    text_style_refs = {
        target_index: _ensure_hwpx_style_refs(header_root, style)
        for target_index, style in patch_buckets.text_styles.items()
    }
    table_cell_style_refs = {
        target: _ensure_hwpx_style_refs(header_root, style)
        for target, style in patch_buckets.table_cell_styles.items()
    }
    return (
        text_style_refs,
        table_cell_style_refs,
        _serialize_section(
            header_root,
            header_namespaces,
        ),
    )


def _raise_for_missing_hwpx_patch_targets(
    *,
    patch_buckets: _HwpXPatchBuckets,
    text_style_refs: dict[int, _HwpXStyleRefs],
    table_cell_style_refs: dict[_HwpXTableCellTarget, _HwpXStyleRefs],
    text_index: int,
    applied_table_cell_targets: set[_HwpXTableCellTarget],
    applied_text_style_targets: set[int],
    applied_table_cell_style_targets: set[_HwpXTableCellTarget],
) -> None:
    missing = set(patch_buckets.text_replacements) - set(range(1, text_index))
    if missing:
        raise ValueError(f"HWPX text target not found: {sorted(missing)}")
    missing_text_style_targets = set(text_style_refs) - applied_text_style_targets
    if missing_text_style_targets:
        raise ValueError(f"HWPX text target not found: {sorted(missing_text_style_targets)}")
    missing_table_cell_targets = (
        set(patch_buckets.table_cell_replacements) - applied_table_cell_targets
    )
    _raise_for_missing_hwpx_table_cell_targets(missing_table_cell_targets)
    missing_table_cell_style_targets = set(table_cell_style_refs) - applied_table_cell_style_targets
    _raise_for_missing_hwpx_table_cell_targets(missing_table_cell_style_targets)


def _raise_for_missing_hwpx_table_cell_targets(
    missing_targets: set[_HwpXTableCellTarget],
) -> None:
    if not missing_targets:
        return
    missing_paths = [
        _hwpx_table_cell_target_path(target)
        for target in sorted(missing_targets, key=_hwpx_table_cell_target_sort_key)
    ]
    raise ValueError(f"HWPX table cell target not found: {missing_paths}")


def _rewrite_hwpx_package(
    archive: ZipFile,
    *,
    section_payloads: dict[str, bytes],
    header_payload: bytes | None,
) -> bytes:
    output = io.BytesIO()
    with ZipFile(output, "w") as rewritten:
        wrote_header = False
        infos = archive.infolist()
        mimetype_info = next((info for info in infos if info.filename == "mimetype"), None)
        if mimetype_info is not None:
            rewritten.writestr(
                _stored_hwpx_mimetype_info(mimetype_info),
                archive.read(mimetype_info.filename),
            )
        for info in infos:
            if info.filename == "mimetype":
                continue
            data = archive.read(info.filename)
            if info.filename in section_payloads:
                data = section_payloads[info.filename]
            elif info.filename == "Contents/header.xml" and header_payload is not None:
                data = header_payload
                wrote_header = True
            elif info.filename == "Preview/PrvText.txt":
                data = _preview_text(section_payloads).encode("utf-8")
            rewritten.writestr(info, data)
        if header_payload is not None and not wrote_header:
            rewritten.writestr("Contents/header.xml", header_payload)
    return output.getvalue()


def _stored_hwpx_mimetype_info(info: ZipInfo) -> ZipInfo:
    stored = ZipInfo(info.filename, date_time=info.date_time)
    stored.compress_type = ZIP_STORED
    stored.comment = info.comment
    stored.extra = info.extra
    stored.external_attr = info.external_attr
    stored.create_system = info.create_system
    return stored


def _ensure_hwpx_style_refs(root: ET.Element, style: StyleDescriptor) -> _HwpXStyleRefs:
    char_pr_id = _append_hwpx_char_pr(root, style) if _hwpx_style_has_char_props(style) else None
    para_pr_id = _append_hwpx_para_pr(root, style) if _hwpx_style_has_para_props(style) else None
    style_id = (
        _append_hwpx_named_style(root, char_pr_id=char_pr_id, para_pr_id=para_pr_id)
        if char_pr_id is not None or para_pr_id is not None
        else None
    )
    return _HwpXStyleRefs(
        char_pr_id=char_pr_id,
        para_pr_id=para_pr_id,
        style_id=style_id,
    )


def _hwpx_style_has_char_props(style: StyleDescriptor) -> bool:
    return any(
        value is not None
        for value in (
            style.font_family,
            style.font_size_pt,
            style.bold,
            style.italic,
            style.underline,
            style.font_color_rgb,
            style.fill_color_rgb,
            style.border,
        )
    )


def _hwpx_style_has_para_props(style: StyleDescriptor) -> bool:
    return style.alignment is not None or style.line_spacing is not None


def _append_hwpx_char_pr(root: ET.Element, style: StyleDescriptor) -> str:
    container = _find_or_create_direct_child(root, "charProperties")
    char_pr_id = str(_next_numeric_id(root, "charPr"))
    attributes: dict[str, str] = {"id": char_pr_id}
    if style.font_size_pt is not None:
        attributes["height"] = _hwpx_points_to_height(style.font_size_pt)
    if style.font_color_rgb is not None:
        attributes["textColor"] = _hwpx_color(style.font_color_rgb)
    if style.fill_color_rgb is not None:
        attributes["shadeColor"] = _hwpx_color(style.fill_color_rgb)
    if style.fill_color_rgb is not None or style.border is not None:
        attributes["borderFillIDRef"] = _append_hwpx_border_fill(root, style)
    char_pr = ET.Element(_qualified_child_tag(container, "charPr"), attributes)
    if style.font_family is not None:
        font_id = _ensure_hwpx_font(root, style.font_family)
        char_pr.append(
            ET.Element(
                _qualified_child_tag(char_pr, "fontRef"),
                {
                    "hangul": font_id,
                    "latin": font_id,
                    "hanja": font_id,
                    "japanese": font_id,
                    "other": font_id,
                    "symbol": font_id,
                    "user": font_id,
                },
            )
        )
    if style.bold is True:
        char_pr.append(ET.Element(_qualified_child_tag(char_pr, "bold")))
    if style.italic is True:
        char_pr.append(ET.Element(_qualified_child_tag(char_pr, "italic")))
    if style.underline is True:
        char_pr.append(ET.Element(_qualified_child_tag(char_pr, "underline")))
    container.append(char_pr)
    _refresh_item_count(container, "charPr")
    return char_pr_id


def _append_hwpx_para_pr(root: ET.Element, style: StyleDescriptor) -> str:
    container = _find_or_create_direct_child(root, "paraProperties")
    para_pr_id = str(_next_numeric_id(root, "paraPr"))
    para_pr = ET.Element(
        _qualified_child_tag(container, "paraPr"),
        {"id": para_pr_id, "tabPrIDRef": "0"},
    )
    if style.alignment is not None:
        para_pr.append(
            ET.Element(
                _qualified_child_tag(para_pr, "align"),
                {"horizontal": style.alignment.upper(), "vertical": "BASELINE"},
            )
        )
    container.append(para_pr)
    _refresh_item_count(container, "paraPr")
    return para_pr_id


def _append_hwpx_named_style(
    root: ET.Element,
    *,
    char_pr_id: str | None,
    para_pr_id: str | None,
) -> str:
    container = _find_or_create_direct_child(root, "styles")
    style_id = str(_next_numeric_id(root, "style"))
    attributes = {
        "id": style_id,
        "type": "PARA",
        "name": f"UMMAYAStyle{style_id}",
        "engName": f"UMMAYAStyle{style_id}",
        "nextStyleIDRef": "0",
        "langID": "1042",
        "lockForm": "0",
    }
    if para_pr_id is not None:
        attributes["paraPrIDRef"] = para_pr_id
    if char_pr_id is not None:
        attributes["charPrIDRef"] = char_pr_id
    container.append(ET.Element(_qualified_child_tag(container, "style"), attributes))
    _refresh_item_count(container, "style")
    return style_id


def _append_hwpx_border_fill(root: ET.Element, style: StyleDescriptor) -> str:
    container = _find_or_create_direct_child(root, "borderFills")
    border_fill_id = str(_next_numeric_id(root, "borderFill"))
    border_type = style.border.style.upper() if style.border is not None else "NONE"
    border_width = (
        _hwpx_points_to_mm(style.border.width_pt)
        if style.border is not None and style.border.width_pt is not None
        else "0.10 mm"
    )
    border_color = (
        _hwpx_color(style.border.color_rgb)
        if style.border is not None and style.border.color_rgb is not None
        else "#000000"
    )
    border_fill = ET.Element(
        _qualified_child_tag(container, "borderFill"),
        {"id": border_fill_id, "threeD": "0", "shadow": "0", "centerLine": "NONE"},
    )
    for border_name in ("slash", "backSlash"):
        border_fill.append(
            ET.Element(_qualified_child_tag(border_fill, border_name), {"type": "NONE"})
        )
    for border_name in ("leftBorder", "rightBorder", "topBorder", "bottomBorder"):
        border_fill.append(
            ET.Element(
                _qualified_child_tag(border_fill, border_name),
                {"type": border_type, "width": border_width, "color": border_color},
            )
        )
    if style.fill_color_rgb is not None:
        fill_brush = ET.Element(_qualified_child_tag(border_fill, "fillBrush"))
        fill_brush.append(
            ET.Element(
                _qualified_child_tag(fill_brush, "winBrush"),
                {
                    "faceColor": _hwpx_color(style.fill_color_rgb),
                    "hatchColor": "#000000",
                    "alpha": "0",
                },
            )
        )
        border_fill.append(fill_brush)
    container.append(border_fill)
    _refresh_item_count(container, "borderFill")
    return border_fill_id


def _ensure_hwpx_font(root: ET.Element, font_family: str) -> str:
    fontfaces = _find_or_create_direct_child(root, "fontfaces")
    fontface = _first_child_by_local_name(fontfaces, "fontface")
    if fontface is None:
        fontface = ET.Element(
            _qualified_child_tag(fontfaces, "fontface"),
            {"lang": "HANGUL", "fontCnt": "0"},
        )
        fontfaces.append(fontface)
    for font in _child_elements_by_local_name(fontface, "font"):
        if _local_attr(font, "face") == font_family:
            font_id = _local_attr(font, "id")
            if font_id is not None:
                return font_id
    font_id = str(_next_numeric_id(root, "font"))
    fontface.append(
        ET.Element(
            _qualified_child_tag(fontface, "font"),
            {"id": font_id, "face": font_family, "type": "TTF", "isEmbedded": "0"},
        )
    )
    fontface.set("fontCnt", str(len(_child_elements_by_local_name(fontface, "font"))))
    _refresh_item_count(fontfaces, "fontface")
    return font_id


def _find_or_create_direct_child(root: ET.Element, name: str) -> ET.Element:
    existing = _first_child_by_local_name(root, name)
    if existing is not None:
        return existing
    child = ET.Element(_qualified_child_tag(root, name))
    root.append(child)
    return child


def _next_numeric_id(root: ET.Element, name: str) -> int:
    used_ids: list[int] = []
    for element in _elements_by_local_name(root, name):
        raw_id = _local_attr(element, "id")
        if raw_id is None:
            continue
        try:
            used_ids.append(int(raw_id))
        except ValueError:
            continue
    return max(used_ids, default=-1) + 1


def _refresh_item_count(container: ET.Element, child_name: str) -> None:
    container.set("itemCnt", str(len(_child_elements_by_local_name(container, child_name))))


def _hwpx_color(value: str) -> str:
    return f"#{_rgb(value) or value.upper()}"


def _hwpx_points_to_height(points: Decimal) -> str:
    return str(int((points * Decimal("100")).to_integral_value()))


def _hwpx_points_to_mm(points: Decimal) -> str:
    millimeters = (points / Decimal("2.834645669")).quantize(Decimal("0.01"))
    return f"{millimeters} mm"


def _apply_hwpx_section_mutations(
    root: ET.Element,
    *,
    member: str,
    text_index: int,
    table_index: int,
    text_replacements: dict[int, str],
    table_cell_replacements: dict[_HwpXTableCellTarget, str],
    text_style_refs: dict[int, _HwpXStyleRefs],
    table_cell_style_refs: dict[_HwpXTableCellTarget, _HwpXStyleRefs],
) -> tuple[
    int,
    int,
    set[_HwpXTableCellTarget],
    set[int],
    set[_HwpXTableCellTarget],
]:
    applied_table_cell_targets: set[_HwpXTableCellTarget] = set()
    applied_text_style_targets: set[int] = set()
    applied_table_cell_style_targets: set[_HwpXTableCellTarget] = set()
    parent_by_id = _parent_by_element_id(root)
    for elem in _text_elements(root):
        if not elem.text:
            continue
        if text_index in text_replacements:
            elem.text = text_replacements[text_index]
        refs = text_style_refs.get(text_index)
        if refs is not None:
            _apply_hwpx_style_refs_to_text(elem, refs, parent_by_id)
            applied_text_style_targets.add(text_index)
        text_index += 1
    for table in _elements_by_local_name(root, "tbl"):
        applied_table_cell_targets.update(
            _apply_hwpx_table_cell_replacements(
                table,
                member=member,
                table_index=table_index,
                table_cell_replacements=table_cell_replacements,
            )
        )
        applied_table_cell_style_targets.update(
            _apply_hwpx_table_cell_styles(
                table,
                member=member,
                table_index=table_index,
                table_cell_style_refs=table_cell_style_refs,
            )
        )
        table_index += 1
    return (
        text_index,
        table_index,
        applied_table_cell_targets,
        applied_text_style_targets,
        applied_table_cell_style_targets,
    )


def _apply_hwpx_style_refs_to_text(
    text: ET.Element,
    refs: _HwpXStyleRefs,
    parent_by_id: dict[int, ET.Element],
) -> None:
    paragraph = _nearest_ancestor_by_local_name(text, "p", parent_by_id)
    run = _nearest_ancestor_by_local_name(text, "run", parent_by_id)
    if paragraph is None or run is None:
        raise ValueError("HWPX text style target has no paragraph/run container")
    _set_hwpx_style_refs(paragraph=paragraph, run=run, refs=refs)


def _apply_hwpx_table_cell_styles(
    table: ET.Element,
    *,
    member: str,
    table_index: int,
    table_cell_style_refs: dict[_HwpXTableCellTarget, _HwpXStyleRefs],
) -> set[_HwpXTableCellTarget]:
    applied_targets: set[_HwpXTableCellTarget] = set()
    for target, refs in table_cell_style_refs.items():
        if target.member != member or target.table_index != table_index:
            continue
        cell = _hwpx_table_cell_element(
            table,
            row_index=target.row_index,
            column_index=target.column_index,
        )
        paragraphs = _elements_by_local_name(cell, "p")
        if not paragraphs:
            paragraph, run = _ensure_hwpx_cell_paragraph_and_run(cell)
            _set_hwpx_style_refs(paragraph=paragraph, run=run, refs=refs)
        for paragraph in paragraphs:
            runs = _child_elements_by_local_name(paragraph, "run")
            if not runs:
                run = ET.Element(_qualified_child_tag(paragraph, "run"))
                paragraph.append(run)
                runs = [run]
            for run in runs:
                _set_hwpx_style_refs(paragraph=paragraph, run=run, refs=refs)
        applied_targets.add(target)
    return applied_targets


def _set_hwpx_style_refs(
    *,
    paragraph: ET.Element,
    run: ET.Element,
    refs: _HwpXStyleRefs,
) -> None:
    if refs.para_pr_id is not None:
        paragraph.set("paraPrIDRef", refs.para_pr_id)
    if refs.style_id is not None:
        paragraph.set("styleIDRef", refs.style_id)
    if refs.char_pr_id is not None:
        run.set("charPrIDRef", refs.char_pr_id)


def _apply_hwpx_table_cell_replacements(
    table: ET.Element,
    *,
    member: str,
    table_index: int,
    table_cell_replacements: dict[_HwpXTableCellTarget, str],
) -> set[_HwpXTableCellTarget]:
    applied_targets: set[_HwpXTableCellTarget] = set()
    for target, value in table_cell_replacements.items():
        if target.member != member or target.table_index != table_index:
            continue
        _set_hwpx_table_cell_text(
            table,
            row_index=target.row_index,
            column_index=target.column_index,
            value=value,
        )
        applied_targets.add(target)
    return applied_targets


def _hwpx_table_cell_target(target_path: str) -> _HwpXTableCellTarget | None:
    match = _HWPX_TABLE_CELL_SOURCE_RE.match(target_path)
    if match is None:
        return None
    return _HwpXTableCellTarget(
        member=match.group("member"),
        table_index=int(match.group("table")),
        row_index=int(match.group("row")),
        column_index=int(match.group("column")),
    )


def _hwpx_table_cell_target_path(target: _HwpXTableCellTarget) -> str:
    return f"{target.member}#table[{target.table_index}]/r{target.row_index}c{target.column_index}"


def _hwpx_table_cell_target_sort_key(
    target: _HwpXTableCellTarget,
) -> tuple[str, int, int, int]:
    return (target.member, target.table_index, target.row_index, target.column_index)


def _set_hwpx_table_cell_text(
    table: ET.Element,
    *,
    row_index: int,
    column_index: int,
    value: str,
) -> None:
    cell = _hwpx_table_cell_element(table, row_index=row_index, column_index=column_index)
    text_nodes = _text_elements(cell)
    if text_nodes:
        text_nodes[0].text = value
        for extra_text_node in text_nodes[1:]:
            extra_text_node.text = ""
        return
    _paragraph, _run = _ensure_hwpx_cell_paragraph_and_run(cell)
    text = _first_child_by_local_name(_run, "t")
    if text is None:
        text = ET.Element(_qualified_child_tag(_run, "t"))
        _run.append(text)
    text.text = value


def _hwpx_table_cell_element(
    table: ET.Element,
    *,
    row_index: int,
    column_index: int,
) -> ET.Element:
    rows = _child_elements_by_local_name(table, "tr")
    if row_index > len(rows):
        raise ValueError(f"HWPX table row target not found: {row_index}")
    cells = _child_elements_by_local_name(rows[row_index - 1], "tc")
    if column_index > len(cells):
        raise ValueError(f"HWPX table cell target not found: {row_index},{column_index}")
    return cells[column_index - 1]


def _ensure_hwpx_cell_paragraph_and_run(cell: ET.Element) -> tuple[ET.Element, ET.Element]:
    paragraph = _first_child_by_local_name(cell, "p")
    if paragraph is None:
        paragraph = ET.Element(_qualified_child_tag(cell, "p"))
        cell.append(paragraph)
    run = _first_child_by_local_name(paragraph, "run")
    if run is None:
        run = ET.Element(_qualified_child_tag(paragraph, "run"))
        paragraph.append(run)
    return paragraph, run


def _qualified_child_tag(parent: ET.Element, local_name: str) -> str:
    if parent.tag.startswith("{") and "}" in parent.tag:
        namespace = parent.tag.split("}", 1)[0][1:]
        return f"{{{namespace}}}{local_name}"
    return local_name


def _namespace_map(payload: bytes) -> list[tuple[str, str]]:
    namespaces: list[tuple[str, str]] = []
    for _event, namespace in ElementTree.iterparse(io.BytesIO(payload), events=("start-ns",)):
        prefix, uri = namespace
        namespaces.append((str(prefix), str(uri)))
    return namespaces


def _serialize_section(root: ET.Element, namespaces: list[tuple[str, str]]) -> bytes:
    for prefix, uri in namespaces:
        ET.register_namespace(prefix, uri)
    return cast(
        bytes,
        ET.tostring(root, encoding="utf-8", xml_declaration=True, short_empty_elements=True),
    )


def _preview_text(section_payloads: dict[str, bytes]) -> str:
    texts: list[str] = []
    for member in sorted(section_payloads):
        root = ElementTree.fromstring(section_payloads[member])
        texts.extend(elem.text or "" for elem in _text_elements(root) if elem.text)
    return "".join(f"<{text}>" for text in texts)


def _uses_hwpxjs_html_render(path: Path) -> bool:
    """Return whether this HWPX package needs the hwpxjs HTML renderer."""
    try:
        with ZipFile(path) as archive:
            for member in _section_members(archive):
                root = ElementTree.fromstring(archive.read(member))
                for table in _elements_by_local_name(root, "tbl"):
                    if _table_missing_rhwp_geometry(table):
                        return True
    except (BadZipFile, ElementTree.ParseError):
        return False
    return False


def _table_missing_rhwp_geometry(table: ET.Element) -> bool:
    if not _has_direct_child(table, "sz") or not _has_direct_child(table, "pos"):
        return True
    for row in _child_elements_by_local_name(table, "tr"):
        for cell in _child_elements_by_local_name(row, "tc"):
            if not _has_direct_child(cell, "cellAddr"):
                return True
            if not _has_direct_child(cell, "cellSpan"):
                return True
            if not _has_direct_child(cell, "cellSz"):
                return True
    return False


def _has_direct_child(element: ET.Element, name: str) -> bool:
    return any(_local_name(child.tag) == name for child in list(element))


def _render_with_hwpxjs_html(path: Path) -> bytes:
    executable = _hwpxjs_binary()
    completed = subprocess.run(  # noqa: S603 - executable is resolved local CLI, no shell.
        [str(executable), "html", str(path)],
        cwd=str(_rhwp_package_root()),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=_RHWP_NODE_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        output_summary = stderr or completed.stdout.strip()
        raise RuntimeError(f"hwpxjs HTML render bridge failed: {output_summary}")
    body = completed.stdout.strip()
    if not body:
        raise RuntimeError("hwpxjs HTML render bridge produced no reviewer evidence")
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        "<style>"
        "body{font-family:-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo',sans-serif;"
        "margin:24px;color:#111;line-height:1.45}"
        "table.hwpx-table{border-collapse:collapse;margin:12px 0;width:100%}"
        "table.hwpx-table td,table.hwpx-table th{border:1px solid #555;padding:6px 8px;"
        "vertical-align:top}"
        '</style></head><body data-ummaya-render-engine="hwpxjs-html-render">'
        f"{body}</body></html>"
    ).encode()


def _hwpxjs_binary() -> Path:
    configured = os.environ.get("UMMAYA_HWPXJS")
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            resolved = shutil.which(configured)
            if resolved is not None:
                candidate = Path(resolved)
        candidate = candidate.resolve(strict=False)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
        raise RuntimeError(f"UMMAYA_HWPXJS is not executable: {configured}")

    path_candidate = shutil.which("hwpxjs")
    if path_candidate is not None:
        candidate = Path(path_candidate).resolve(strict=False)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    for root in (Path.cwd(), _rhwp_package_root()):
        candidate = root / "node_modules" / ".bin" / "hwpxjs"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve(strict=False)
    raise RuntimeError("hwpxjs executable is required for HWPX HTML rendering")


_RHWP_NODE_TIMEOUT_SECONDS = 45

_RHWP_RENDER_BRIDGE_JS = r"""
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const [inputPath, outputDir] = process.argv.slice(1);
if (!inputPath || !outputDir) {
  throw new Error('Usage: rhwp render bridge requires <inputPath> <outputDir>');
}

const packageRoot = resolve(process.env.UMMAYA_PACKAGE_ROOT || process.cwd());
const packageJsonPath = join(packageRoot, 'package.json');
if (!existsSync(packageJsonPath)) {
  throw new Error(`UMMAYA package root does not contain package.json: ${packageRoot}`);
}

globalThis.measureTextWidth = (_font, text) => {
  let width = 0;
  for (const char of String(text)) {
    width += char.charCodeAt(0) > 0x7f ? 14 : 8;
  }
  return width;
};

const require = createRequire(pathToFileURL(packageJsonPath));
const rhwpModulePath = require.resolve('@rhwp/core/rhwp.js');
const rhwpWasmPath = require.resolve('@rhwp/core/rhwp_bg.wasm');
const rhwp = await import(pathToFileURL(rhwpModulePath).href);

await rhwp.default({ module_or_path: readFileSync(rhwpWasmPath) });

const data = readFileSync(resolve(inputPath));
const doc = new rhwp.HwpDocument(new Uint8Array(data));
const pageCount = doc.pageCount();
mkdirSync(resolve(outputDir), { recursive: true });

const artifacts = [];
for (let index = 0; index < pageCount; index += 1) {
  const svg = doc.renderPageSvg(index);
  const pageNumber = index + 1;
  const outputName = `rhwp-page-${String(pageNumber).padStart(3, '0')}.svg`;
  const outputPath = join(resolve(outputDir), outputName);
  writeFileSync(outputPath, svg);
  artifacts.push({
    pageNumber,
    path: outputPath,
    sha256: createHash('sha256').update(svg).digest('hex'),
  });
}

console.log(JSON.stringify({
  engineId: 'rhwp-node-wasm',
  rhwpVersion: rhwp.version(),
  pageCount,
  artifacts,
}));
"""


def _render_with_rhwp_node(path: Path, *, output_dir: Path) -> tuple[bytes, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(  # noqa: S603
        [
            _node_binary(),
            "--input-type=module",
            "-e",
            _RHWP_RENDER_BRIDGE_JS,
            str(path),
            str(output_dir),
        ],
        cwd=str(_rhwp_package_root()),
        env=_rhwp_bridge_env(),
        capture_output=True,
        text=True,
        timeout=_RHWP_NODE_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise RuntimeError(f"RHWP render bridge failed: {stderr or completed.stdout.strip()}")

    bridge_result = _parse_rhwp_bridge_result(completed.stdout)
    payloads: list[bytes] = []
    for artifact_path in bridge_result:
        _require_render_path_inside(artifact_path, output_dir)
        payloads.append(artifact_path.read_bytes())
    if not payloads:
        raise RuntimeError("RHWP render bridge produced no page SVG artifacts")
    return tuple(payloads)


def _node_binary() -> str:
    configured = os.environ.get("UMMAYA_NODE")
    if configured:
        resolved = shutil.which(configured) if not Path(configured).is_absolute() else configured
        if resolved:
            return resolved
        raise RuntimeError(f"UMMAYA_NODE is not executable: {configured}")

    detected = shutil.which("node")
    if detected is None:
        raise RuntimeError("node executable is required for RHWP HWPX rendering")
    return detected


def _rhwp_package_root() -> Path:
    candidates = [
        os.environ.get("UMMAYA_PACKAGE_ROOT"),
        str(Path.cwd()),
        str(Path(__file__).resolve().parents[5]),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        root = Path(candidate).expanduser().resolve()
        if (root / "package.json").is_file():
            return root
    return Path.cwd().resolve()


def _rhwp_bridge_env() -> dict[str, str]:
    env = dict(os.environ)
    env["UMMAYA_PACKAGE_ROOT"] = str(_rhwp_package_root())
    return env


def _parse_rhwp_bridge_result(stdout: str) -> list[Path]:
    parsed = json.loads(stdout)
    if not isinstance(parsed, dict):
        raise RuntimeError("RHWP render bridge returned a non-object result")
    artifacts = parsed.get("artifacts")
    if not isinstance(artifacts, list):
        raise RuntimeError("RHWP render bridge result is missing artifacts")

    paths: list[Path] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise RuntimeError("RHWP render bridge artifact is not an object")
        path_value = artifact.get("path")
        if not isinstance(path_value, str):
            raise RuntimeError("RHWP render bridge artifact is missing path")
        paths.append(Path(path_value).expanduser().resolve())
    return paths


def _require_render_path_inside(candidate: Path, root: Path) -> None:
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    if resolved_candidate != resolved_root and resolved_root not in resolved_candidate.parents:
        raise RuntimeError(
            f"RHWP render bridge path escapes output directory: {resolved_candidate}"
        )
