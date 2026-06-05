# SPDX-License-Identifier: Apache-2.0
"""Promoted text and web-export document engines."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import NoReturn

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

_TEXT_BODY_TARGET = "/text/body"
_TEXT_LINE_RE = re.compile(r"^/text/lines/(?P<index>[1-9][0-9]*)$")
_RTF_UNICODE_RE = re.compile(r"\\u(?P<code>-?[0-9]+).")
_RTF_CONTROL_RE = re.compile(r"\\[a-zA-Z]+-?[0-9]* ?")
_TEXT_WEB_FORMATS = (
    DocumentFormat.html,
    DocumentFormat.htm,
    DocumentFormat.txt,
    DocumentFormat.rtf,
    DocumentFormat.md,
)


class TextWebDocumentEngine:
    """Bounded writer for UTF-8 text, Markdown, HTML, HTM, and RTF exports."""

    render_engine_id = "text-web-structural-svg"
    render_artifact_extension = "svg"
    render_mime_type = "image/svg+xml"

    def __init__(self, document_format: DocumentFormat) -> None:
        if document_format not in _TEXT_WEB_FORMATS:
            raise ValueError(f"unsupported text-web document format: {document_format.value}")
        self.document_format = document_format
        self.engine_id = f"text-web-{document_format.value}"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Extract visible text lines from a promoted text/web document."""
        raw_text = path.read_text(encoding="utf-8", errors="replace")
        visible_text = _visible_text(raw_text, document_format=self.document_format)
        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=_paragraphs_from_text(visible_text, source_name=path.name),
            metadata=_metadata(path, document_format=self.document_format),
        )

    def apply_patch(self, path: Path, patch: DocumentPatch) -> bytes:
        """Apply bounded text replacement and return derivative document bytes."""
        raw_text = path.read_text(encoding="utf-8", errors="replace")
        visible_text = _visible_text(raw_text, document_format=self.document_format)
        for operation in patch.operations:
            visible_text = _apply_text_operation(visible_text, operation)
        output = _serialize_text_web(visible_text, document_format=self.document_format)
        return output.encode("utf-8")

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        """Render visible text as structural SVG evidence."""
        _ = output_dir
        extraction = self.inspect(path, artifact_id=artifact_id)
        lines = [paragraph.text for paragraph in extraction.paragraphs]
        return (_render_lines_svg(lines, title=f"{self.document_format.value.upper()} document"),)


class TextWebDocumentAdapter:
    """Format adapter for promoted text and web-export engines."""

    adapter_id = "text-web-document-adapter"
    known_formats: tuple[KnownDocumentFormat, ...] = (
        KnownDocumentFormat.html,
        KnownDocumentFormat.htm,
        KnownDocumentFormat.txt,
        KnownDocumentFormat.rtf,
        KnownDocumentFormat.md,
    )
    promoted_formats: tuple[DocumentFormat, ...] = _TEXT_WEB_FORMATS

    def __init__(self, engines: dict[DocumentFormat, TextWebDocumentEngine] | None = None) -> None:
        self._engines = engines or {
            document_format: TextWebDocumentEngine(document_format)
            for document_format in _TEXT_WEB_FORMATS
        }

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Inspect a text/web artifact using its suffix-selected engine."""
        return self._engine_for_path(path).inspect(path, artifact_id=artifact_id)

    def normalize_fill_patches(
        self,
        patches: tuple[DocumentFieldPatch, ...],
        *,
        extraction: DocumentExtraction | None,
    ) -> tuple[DocumentFieldPatch, ...]:
        """Return text/web patches unchanged; `/text/*` paths are native."""
        _ = extraction
        return patches

    def _engine_for_path(self, path: Path) -> TextWebDocumentEngine:
        try:
            document_format = DocumentFormat(path.suffix.lower().lstrip("."))
        except ValueError as exc:
            raise DocumentMutationBlockedError(
                BlockedReason.unsupported_format,
                f"Unsupported text/web suffix: {path.suffix}",
            ) from exc
        engine = self._engines.get(document_format)
        if engine is None:
            raise DocumentMutationBlockedError(
                BlockedReason.unsupported_format,
                f"Unsupported text/web suffix: {path.suffix}",
            )
        return engine


class _VisibleHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if stripped:
            self._chunks.append(stripped)

    def visible_text(self) -> str:
        return "\n".join(self._chunks)


def _visible_text(raw_text: str, *, document_format: DocumentFormat) -> str:
    if document_format in {DocumentFormat.html, DocumentFormat.htm}:
        parser = _VisibleHTMLParser()
        parser.feed(raw_text)
        return parser.visible_text()
    if document_format is DocumentFormat.rtf:
        return _strip_minimal_rtf(raw_text)
    return raw_text


def _apply_text_operation(text: str, operation: DocumentPatchOperation) -> str:
    if operation.operation_type not in {OperationType.replace_text, OperationType.set_field_value}:
        _raise_unsupported_operation(operation)
    value = operation.value
    if value is None:
        _raise_unsupported_operation(operation)
    replacement = str(value)
    if operation.target_path == _TEXT_BODY_TARGET:
        return replacement
    match = _TEXT_LINE_RE.fullmatch(operation.target_path)
    if match is None:
        _raise_unsupported_operation(operation)
    lines = text.splitlines(keepends=True)
    line_index = int(match.group("index")) - 1
    if line_index >= len(lines):
        _raise_unsupported_operation(operation)
    newline = "\n" if lines[line_index].endswith("\n") else ""
    lines[line_index] = replacement.rstrip("\n") + newline
    return "".join(lines)


def _serialize_text_web(text: str, *, document_format: DocumentFormat) -> str:
    if document_format in {DocumentFormat.html, DocumentFormat.htm}:
        escaped = html.escape(text).replace("\n", "<br/>\n")
        return f"<!doctype html>\n<html><body><p>{escaped}</p></body></html>\n"
    if document_format is DocumentFormat.rtf:
        return _rtf_payload_from_text(text)
    return text


def _paragraphs_from_text(text: str, *, source_name: str) -> list[ParagraphBlock]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines and text.strip():
        lines = [text.strip()]
    return [
        ParagraphBlock(
            block_id=f"text-line-{index}",
            text=line,
            source_path=f"/text/lines/{index}",
        )
        for index, line in enumerate(lines, start=1)
    ] or [
        ParagraphBlock(
            block_id="text-line-1",
            text="",
            source_path=f"{source_name}:/text/lines/1",
        )
    ]


def _strip_minimal_rtf(raw_text: str) -> str:
    without_unicode = _RTF_UNICODE_RE.sub(lambda match: _rtf_codepoint(match), raw_text)
    stripped = without_unicode.replace("{", "").replace("}", "")
    stripped = _RTF_CONTROL_RE.sub("", stripped)
    return "\n".join(line.strip() for line in stripped.splitlines() if line.strip())


def _rtf_codepoint(match: re.Match[str]) -> str:
    value = int(match.group("code"))
    if value < 0:
        value += 65536
    return chr(value)


def _rtf_payload_from_text(text: str) -> str:
    encoded_chars: list[str] = []
    for char in text:
        if char == "\n":
            encoded_chars.append(r"\par ")
        elif char in {"\\", "{", "}"}:
            encoded_chars.append(f"\\{char}")
        elif ord(char) > 127:
            codepoint = ord(char)
            if codepoint > 32767:
                codepoint -= 65536
            encoded_chars.append(rf"\u{codepoint}?")
        else:
            encoded_chars.append(char)
    return r"{\rtf1\ansi\uc1 " + "".join(encoded_chars).strip() + "}\n"


def _metadata(path: Path, *, document_format: DocumentFormat) -> dict[str, MetadataValue]:
    return {
        "adapter_id": "text-web-document-adapter",
        "engine_id": f"text-web-{document_format.value}",
        "format": document_format.value,
        "source_name": path.name,
        "mutation_policy": "bounded_text_web_write_render_save",
        "render_oracle": "text-web-structural-svg",
    }


def _render_lines_svg(lines: list[str], *, title: str) -> bytes:
    escaped_title = html.escape(title)
    safe_lines = [html.escape(line) for line in lines if line]
    height = max(160, 72 + len(safe_lines) * 28)
    text_nodes = [
        f'<text x="32" y="{84 + index * 28}" font-size="16" font-family="sans-serif">{line}</text>'
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
        f"Text/web operation is not supported: "
        f"{operation.operation_type.value} {operation.target_path}",
    )
