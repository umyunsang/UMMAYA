# SPDX-License-Identifier: Apache-2.0
"""HWPX engine-adapter boundary."""

from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path
from typing import cast
from zipfile import ZipFile

from defusedxml import ElementTree  # type: ignore[import-untyped]

from ummaya.tools.documents.engines import DocumentInspectionEngine, DocumentMutationEngine
from ummaya.tools.documents.models import (
    DocumentExtraction,
    DocumentFormat,
    DocumentPatch,
    FormField,
    OperationType,
    ParagraphBlock,
)

HWPX_CANDIDATE_ENGINES: tuple[str, ...] = (
    "hwpx-package-text",
    "python-hwpx",
    "hwpx-mcp-server",
    "rhwp",
    "direct-owpml-oracle",
)

_TEXT_TARGET_RE = re.compile(r"^/hwpx/text\[(?P<index>[1-9][0-9]*)\]$")
_SECTION_PREFIX = "Contents/section"


def validate_hwpx_engine(engine: DocumentInspectionEngine) -> DocumentInspectionEngine:
    """Validate that an injected engine is scoped to HWPX."""
    if engine.document_format is not DocumentFormat.hwpx:
        raise ValueError("HWPX adapter requires a hwpx engine")
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

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Extract HWPX text nodes as LLM-addressable paragraphs and fields."""
        paragraphs: list[ParagraphBlock] = []
        fields: list[FormField] = []
        text_index = 1
        section_count = 0

        with ZipFile(path) as archive:
            for member in _section_members(archive):
                section_count += 1
                root = ElementTree.fromstring(archive.read(member))
                for elem in _text_elements(root):
                    text = elem.text or ""
                    if not text:
                        continue
                    target_path = f"/hwpx/text[{text_index}]"
                    source_path = f"{member}#text[{text_index}]"
                    paragraphs.append(
                        ParagraphBlock(
                            block_id=f"hwpx-text-{text_index:03d}",
                            text=text,
                            source_path=source_path,
                        )
                    )
                    fields.append(
                        FormField(
                            field_id=f"hwpx-text-{text_index:03d}",
                            label=f"HWPX text node {text_index}",
                            path=target_path,
                            field_type="text",
                            required=False,
                            current_value=text,
                            source_confidence=Decimal("1"),
                        )
                    )
                    text_index += 1

        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=paragraphs,
            fields=fields,
            metadata={
                "format": DocumentFormat.hwpx.value,
                "engine_id": self.engine_id,
                "section_count": section_count,
                "text_node_count": len(paragraphs),
            },
            warnings=[
                "HWPX package text engine edits text nodes only; style and visual render "
                "fidelity remain separate promotion gates."
            ],
        )

    def apply_patch(self, path: Path, patch: DocumentPatch) -> bytes:
        """Apply ordered HWPX text-node patches and return derivative package bytes."""
        replacements = _text_replacements_from_patch(patch)
        namespace_maps: dict[str, list[tuple[str, str]]] = {}
        section_payloads: dict[str, bytes] = {}
        text_index = 1

        with ZipFile(path) as archive:
            for member in _section_members(archive):
                payload = archive.read(member)
                namespace_maps[member] = _namespace_map(payload)
                root = ElementTree.fromstring(payload)
                for elem in _text_elements(root):
                    if not elem.text:
                        continue
                    if text_index in replacements:
                        elem.text = replacements[text_index]
                    text_index += 1
                section_payloads[member] = _serialize_section(root, namespace_maps[member])

            missing = set(replacements) - set(range(1, text_index))
            if missing:
                raise ValueError(f"HWPX text target not found: {sorted(missing)}")

            output = io.BytesIO()
            with ZipFile(output, "w") as rewritten:
                for info in archive.infolist():
                    data = archive.read(info.filename)
                    if info.filename in section_payloads:
                        data = section_payloads[info.filename]
                    elif info.filename == "Preview/PrvText.txt":
                        data = _preview_text(section_payloads).encode("utf-8")
                    rewritten.writestr(info, data)
        return output.getvalue()


def _section_members(archive: ZipFile) -> list[str]:
    return sorted(
        member.filename
        for member in archive.infolist()
        if member.filename.startswith(_SECTION_PREFIX) and member.filename.endswith(".xml")
    )


def _text_elements(root: ET.Element) -> list[ET.Element]:
    return [elem for elem in root.iter() if elem.tag.rsplit("}", 1)[-1] == "t"]


def _text_replacements_from_patch(patch: DocumentPatch) -> dict[int, str]:
    replacements: dict[int, str] = {}
    for operation in patch.operations:
        if operation.operation_type not in {
            OperationType.set_field_value,
            OperationType.replace_text,
        }:
            raise ValueError(f"Unsupported HWPX text operation: {operation.operation_type.value}")
        match = _TEXT_TARGET_RE.match(operation.target_path)
        if match is None:
            raise ValueError(f"Unsupported HWPX text target path: {operation.target_path}")
        replacements[int(match.group("index"))] = (
            "" if operation.value is None else str(operation.value)
        )
    return replacements


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
