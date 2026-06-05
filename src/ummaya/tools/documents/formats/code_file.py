# SPDX-License-Identifier: Apache-2.0
"""Promoted bounded Python source document engine."""

from __future__ import annotations

import ast
import html
import re
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

_CODE_BODY_TARGET = "/code/body"
_CODE_LINE_RE = re.compile(r"^/code/lines/(?P<index>[1-9][0-9]*)$")


class PythonSourceDocumentEngine:
    """Bounded writer for UTF-8 Python source attachments."""

    document_format = DocumentFormat.python
    engine_id = "python-source"
    render_engine_id = "python-source-structural-svg"
    render_artifact_extension = "svg"
    render_mime_type = "image/svg+xml"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Extract Python source as line-addressable document IR."""
        source = _read_python_source(path)
        _validate_python_source(source)
        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=_paragraphs_from_source(source),
            metadata=_metadata(path, line_count=len(source.splitlines())),
        )

    def apply_patch(self, path: Path, patch: DocumentPatch) -> bytes:
        """Apply a bounded source replacement and return derivative bytes."""
        source = _read_python_source(path)
        _validate_python_source(source)
        for operation in patch.operations:
            source = _apply_code_operation(source, operation)
            _validate_python_source(source)
        return source.encode("utf-8")

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        """Render Python source as structural SVG evidence."""
        _ = output_dir
        extraction = self.inspect(path, artifact_id=artifact_id)
        lines = [paragraph.text for paragraph in extraction.paragraphs]
        return (_render_code_svg(lines, title="Python source document"),)


class PythonSourceDocumentAdapter:
    """Format adapter for promoted Python source attachments."""

    adapter_id = "python-source-document-adapter"
    known_formats: tuple[KnownDocumentFormat, ...] = (KnownDocumentFormat.python,)
    promoted_formats: tuple[DocumentFormat, ...] = (DocumentFormat.python,)

    def __init__(self, engine: PythonSourceDocumentEngine | None = None) -> None:
        self._engine = engine or PythonSourceDocumentEngine()

    @property
    def engine_id(self) -> str:
        """Return the wrapped engine id for diagnostics."""
        return self._engine.engine_id

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Inspect a Python source artifact."""
        return self._engine.inspect(path, artifact_id=artifact_id)

    def normalize_fill_patches(
        self,
        patches: tuple[DocumentFieldPatch, ...],
        *,
        extraction: DocumentExtraction | None,
    ) -> tuple[DocumentFieldPatch, ...]:
        """Return code patches unchanged; `/code/*` paths are native."""
        _ = extraction
        return patches


def _read_python_source(path: Path) -> str:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise DocumentMutationBlockedError(
            BlockedReason.unsupported_operation,
            f"Could not read Python source document: {path}",
        ) from exc
    if b"\x00" in payload:
        raise DocumentMutationBlockedError(
            BlockedReason.validation_failed,
            "Python source document contains NUL bytes.",
        )
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DocumentMutationBlockedError(
            BlockedReason.validation_failed,
            "Python source document must be UTF-8.",
        ) from exc


def _validate_python_source(source: str) -> None:
    if not source.strip():
        raise DocumentMutationBlockedError(
            BlockedReason.validation_failed,
            "Python source document cannot be empty.",
        )
    try:
        ast.parse(source)
    except SyntaxError as exc:
        raise DocumentMutationBlockedError(
            BlockedReason.validation_failed,
            f"Python source document is not syntactically valid: {exc.msg}.",
        ) from exc


def _apply_code_operation(source: str, operation: DocumentPatchOperation) -> str:
    if operation.operation_type not in {OperationType.replace_text, OperationType.set_field_value}:
        _raise_unsupported_operation(operation)
    if operation.value is None:
        _raise_unsupported_operation(operation)
    replacement = str(operation.value)
    if operation.target_path == _CODE_BODY_TARGET:
        return _with_trailing_newline(replacement)
    match = _CODE_LINE_RE.fullmatch(operation.target_path)
    if match is None:
        _raise_unsupported_operation(operation)
    lines = source.splitlines(keepends=True)
    line_index = int(match.group("index")) - 1
    if line_index >= len(lines):
        _raise_unsupported_operation(operation)
    newline = "\n" if lines[line_index].endswith("\n") else ""
    lines[line_index] = replacement.rstrip("\n") + newline
    return "".join(lines)


def _with_trailing_newline(source: str) -> str:
    return source if source.endswith("\n") else f"{source}\n"


def _paragraphs_from_source(source: str) -> list[ParagraphBlock]:
    lines = source.splitlines()
    return [
        ParagraphBlock(
            block_id=f"code-line-{index}",
            text=line,
            source_path=f"/code/lines/{index}",
        )
        for index, line in enumerate(lines, start=1)
    ]


def _metadata(path: Path, *, line_count: int) -> dict[str, MetadataValue]:
    return {
        "adapter_id": PythonSourceDocumentAdapter.adapter_id,
        "engine_id": PythonSourceDocumentEngine.engine_id,
        "format": DocumentFormat.python.value,
        "source_name": path.name,
        "line_count": line_count,
        "mutation_policy": "bounded_python_source_write_render_save",
        "render_oracle": PythonSourceDocumentEngine.render_engine_id,
        "execution_policy": "never_execute_source",
        "syntax_gate": "python_ast_parse",
    }


def _render_code_svg(lines: list[str], *, title: str) -> bytes:
    escaped_title = html.escape(title)
    safe_lines = [html.escape(line) for line in lines]
    height = max(160, 72 + len(safe_lines) * 24)
    line_nodes = [
        (
            f'<text x="32" y="{84 + index * 24}" font-size="13" '
            'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" '
            f'fill="#1f2937">{index + 1:>3}  {line}</text>'
        )
        for index, line in enumerate(safe_lines)
    ]
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="{height}" '
        f'viewBox="0 0 960 {height}">'
        '<rect width="100%" height="100%" fill="#ffffff"/>'
        '<rect x="24" y="56" width="912" height="'
        f'{max(72, len(safe_lines) * 24 + 24)}" fill="#f9fafb" stroke="#d1d5db"/>'
        f'<text x="32" y="36" font-size="22" font-family="sans-serif" '
        f'font-weight="700">{escaped_title}</text>' + "".join(line_nodes) + "</svg>"
    )
    return svg.encode("utf-8")


def _raise_unsupported_operation(operation: DocumentPatchOperation) -> NoReturn:
    raise DocumentMutationBlockedError(
        BlockedReason.unsupported_operation,
        f"Unsupported Python source operation target: {operation.target_path}",
    )
