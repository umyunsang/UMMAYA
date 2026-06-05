# SPDX-License-Identifier: Apache-2.0
"""Promoted archive/container document engines."""

from __future__ import annotations

import gzip
import html
import io
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import NoReturn

from ummaya.tools.documents.engines import DocumentMutationBlockedError
from ummaya.tools.documents.models import (
    BlockedReason,
    DocumentExtraction,
    DocumentFormat,
    DocumentPatch,
    DocumentPatchOperation,
    FormField,
    MetadataValue,
    OperationType,
    ParagraphBlock,
)

_ARCHIVE_FORMATS = (
    DocumentFormat.epub,
    DocumentFormat.zip,
    DocumentFormat.seven_z,
    DocumentFormat.tar,
    DocumentFormat.gz,
)
_ARCHIVE_BODY_RE = re.compile(r"^/archive/(?P<member>.+)/body$")
_GZIP_BODY_TARGET = "/gzip/payload"
_MAX_INLINE_TEXT_BYTES = 128 * 1024
_BSDTAR_TIMEOUT_SECONDS = 15


class ArchiveContainerDocumentEngine:
    """Bounded writer for archive containers with child-payload replacement."""

    render_engine_id = "archive-container-structural-svg"
    render_artifact_extension = "svg"
    render_mime_type = "image/svg+xml"

    def __init__(self, document_format: DocumentFormat) -> None:
        if document_format not in _ARCHIVE_FORMATS:
            raise ValueError(f"unsupported archive document format: {document_format.value}")
        self.document_format = document_format
        self.engine_id = f"archive-container-{document_format.value}"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        """Inspect archive members without extracting to the workspace."""
        entries = _read_entries(path, document_format=self.document_format)
        paragraphs = [
            ParagraphBlock(
                block_id=f"archive-member-{index}",
                text=entry.preview,
                source_path=entry.target_path,
            )
            for index, entry in enumerate(entries, start=1)
        ]
        fields = [
            FormField(
                field_id=f"archive-member-{index}",
                label=entry.name,
                path=entry.target_path,
                field_type="text",
                required=False,
                current_value=entry.text,
                source_confidence=Decimal("0.85"),
            )
            for index, entry in enumerate(entries, start=1)
            if entry.editable
        ]
        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=paragraphs,
            fields=fields,
            metadata=_metadata(
                path,
                document_format=self.document_format,
                entry_count=len(entries),
            ),
        )

    def apply_patch(self, path: Path, patch: DocumentPatch) -> bytes:
        """Return a repacked archive derivative after replacing child payloads."""
        replacements: dict[str, bytes] = {}
        gzip_replacement: bytes | None = None
        for operation in patch.operations:
            target_name = _operation_target_name(operation)
            replacement = _operation_replacement(operation)
            if self.document_format is DocumentFormat.gz:
                if target_name != _GZIP_BODY_TARGET:
                    _raise_unsupported_operation(operation)
                gzip_replacement = replacement
                continue
            member_name = _member_name_from_target(target_name)
            replacements[member_name] = replacement

        if self.document_format is DocumentFormat.gz:
            if gzip_replacement is None:
                raise DocumentMutationBlockedError(
                    BlockedReason.validation_failed,
                    "Gzip archive patch did not include /gzip/payload.",
                )
            return _write_gzip_payload(gzip_replacement)
        if not replacements:
            raise DocumentMutationBlockedError(
                BlockedReason.validation_failed,
                "Archive patch did not include a child member replacement.",
            )
        if self.document_format in {DocumentFormat.zip, DocumentFormat.epub}:
            return _replace_zip_members(
                path,
                replacements,
                preserve_epub_mimetype=self.document_format is DocumentFormat.epub,
            )
        if self.document_format is DocumentFormat.seven_z:
            return _replace_7z_members(path, replacements)
        if self.document_format is DocumentFormat.tar:
            return _replace_tar_members(path, replacements)
        raise DocumentMutationBlockedError(
            BlockedReason.unsupported_format,
            f"Unsupported archive format: {self.document_format.value}",
        )

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        """Render archive member previews as structural SVG evidence."""
        _ = output_dir
        extraction = self.inspect(path, artifact_id=artifact_id)
        lines = [paragraph.text for paragraph in extraction.paragraphs]
        return (_render_lines_svg(lines, title=f"{self.document_format.value.upper()} archive"),)


class _ArchiveEntry:
    def __init__(self, *, name: str, text: str, editable: bool) -> None:
        self.name = name
        self.text = text
        self.editable = editable

    @property
    def target_path(self) -> str:
        if self.name == "gzip-payload":
            return _GZIP_BODY_TARGET
        return f"/archive/{self.name}/body"

    @property
    def preview(self) -> str:
        if self.text:
            return f"{self.name}: {self.text}"
        return self.name


def _read_entries(path: Path, *, document_format: DocumentFormat) -> list[_ArchiveEntry]:
    if document_format in {DocumentFormat.zip, DocumentFormat.epub}:
        return _read_zip_entries(path)
    if document_format is DocumentFormat.seven_z:
        return _read_7z_entries(path)
    if document_format is DocumentFormat.tar:
        return _read_tar_entries(path)
    if document_format is DocumentFormat.gz:
        return [_ArchiveEntry(name="gzip-payload", text=_read_gzip_text(path), editable=True)]
    raise DocumentMutationBlockedError(
        BlockedReason.unsupported_format,
        f"Unsupported archive format: {document_format.value}",
    )


def _read_zip_entries(path: Path) -> list[_ArchiveEntry]:
    entries: list[_ArchiveEntry] = []
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir() or not _safe_member_name(info.filename):
                    continue
                text = _read_zip_member_text(archive, info)
                entries.append(_ArchiveEntry(name=info.filename, text=text, editable=bool(text)))
    except zipfile.BadZipFile as exc:
        raise DocumentMutationBlockedError(BlockedReason.corrupt, "Invalid ZIP container.") from exc
    return entries


def _read_tar_entries(path: Path) -> list[_ArchiveEntry]:
    entries: list[_ArchiveEntry] = []
    try:
        with tarfile.open(path, mode="r:*") as archive:
            for member in archive.getmembers():
                if not member.isfile() or not _safe_member_name(member.name):
                    continue
                payload = archive.extractfile(member)
                if payload is None:
                    continue
                text = _decode_inline_text(payload.read(_MAX_INLINE_TEXT_BYTES))
                entries.append(_ArchiveEntry(name=member.name, text=text, editable=bool(text)))
    except tarfile.TarError as exc:
        raise DocumentMutationBlockedError(BlockedReason.corrupt, "Invalid TAR container.") from exc
    return entries


def _read_7z_entries(path: Path) -> list[_ArchiveEntry]:
    with tempfile.TemporaryDirectory(prefix="ummaya-7z-read-") as temp_root:
        root = Path(temp_root)
        member_names = _extract_7z_archive(path, root)
        entries: list[_ArchiveEntry] = []
        for member_name in member_names:
            member_path = _safe_extracted_member_path(root, member_name)
            if member_path is None or not member_path.is_file() or member_path.is_symlink():
                continue
            payload = member_path.read_bytes()[:_MAX_INLINE_TEXT_BYTES]
            text = _decode_inline_text(payload)
            entries.append(_ArchiveEntry(name=member_name, text=text, editable=bool(text)))
        return entries


def _read_zip_member_text(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    if info.file_size > _MAX_INLINE_TEXT_BYTES:
        return ""
    try:
        return _decode_inline_text(archive.read(info.filename))
    except (KeyError, RuntimeError, NotImplementedError, zipfile.BadZipFile):
        return ""


def _read_gzip_text(path: Path) -> str:
    try:
        with gzip.open(path, "rb") as archive:
            return _decode_inline_text(archive.read(_MAX_INLINE_TEXT_BYTES))
    except OSError as exc:
        raise DocumentMutationBlockedError(BlockedReason.corrupt, "Invalid GZIP payload.") from exc


def _decode_inline_text(payload: bytes) -> str:
    if b"\x00" in payload:
        return ""
    try:
        return payload.decode("utf-8").strip()
    except UnicodeDecodeError:
        return ""


def _operation_target_name(operation: DocumentPatchOperation) -> str:
    if operation.operation_type not in {OperationType.replace_text, OperationType.set_field_value}:
        _raise_unsupported_operation(operation)
    return operation.target_path


def _operation_replacement(operation: DocumentPatchOperation) -> bytes:
    if operation.value is None:
        _raise_unsupported_operation(operation)
    return str(operation.value).encode("utf-8")


def _member_name_from_target(target_path: str) -> str:
    match = _ARCHIVE_BODY_RE.fullmatch(target_path)
    if match is None:
        raise DocumentMutationBlockedError(
            BlockedReason.unsupported_operation,
            f"Archive target must match /archive/<member>/body: {target_path}",
        )
    member_name = match.group("member")
    if not _safe_member_name(member_name):
        raise DocumentMutationBlockedError(
            BlockedReason.path_traversal_detected,
            f"Archive member target is unsafe: {member_name}",
        )
    return member_name


def _replace_zip_members(
    path: Path,
    replacements: dict[str, bytes],
    *,
    preserve_epub_mimetype: bool,
) -> bytes:
    buffer = io.BytesIO()
    found: set[str] = set()
    with (
        zipfile.ZipFile(path) as source,
        zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as target,
    ):
        if preserve_epub_mimetype and "mimetype" in source.namelist():
            target.writestr(
                "mimetype",
                source.read("mimetype"),
                compress_type=zipfile.ZIP_STORED,
            )
        for info in source.infolist():
            if info.is_dir():
                continue
            if preserve_epub_mimetype and info.filename == "mimetype":
                continue
            if not _safe_member_name(info.filename):
                raise DocumentMutationBlockedError(
                    BlockedReason.path_traversal_detected,
                    f"Archive member path is unsafe: {info.filename}",
                )
            payload = replacements.get(info.filename)
            if payload is None:
                payload = source.read(info.filename)
            else:
                found.add(info.filename)
            target.writestr(info.filename, payload)
    _ensure_all_replacements_found(replacements, found)
    return buffer.getvalue()


def _replace_tar_members(path: Path, replacements: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    found: set[str] = set()
    with tarfile.open(path, mode="r:*") as source, tarfile.open(fileobj=buffer, mode="w") as target:
        for member in source.getmembers():
            if not _safe_member_name(member.name):
                raise DocumentMutationBlockedError(
                    BlockedReason.path_traversal_detected,
                    f"Archive member path is unsafe: {member.name}",
                )
            if not member.isfile():
                target.addfile(member)
                continue
            payload = replacements.get(member.name)
            if payload is None:
                source_payload = source.extractfile(member)
                payload = b"" if source_payload is None else source_payload.read()
            else:
                found.add(member.name)
            info = tarfile.TarInfo(member.name)
            info.size = len(payload)
            info.mode = member.mode
            info.mtime = member.mtime
            target.addfile(info, io.BytesIO(payload))
    _ensure_all_replacements_found(replacements, found)
    return buffer.getvalue()


def _replace_7z_members(path: Path, replacements: dict[str, bytes]) -> bytes:
    with tempfile.TemporaryDirectory(prefix="ummaya-7z-write-") as temp_root:
        root = Path(temp_root) / "src"
        root.mkdir()
        member_names = _extract_7z_archive(path, root)
        found: set[str] = set()
        for member_name, payload in replacements.items():
            member_path = _safe_extracted_member_path(root, member_name)
            if member_path is None or not member_path.is_file() or member_path.is_symlink():
                continue
            member_path.write_bytes(payload)
            found.add(member_name)
        _ensure_all_replacements_found(replacements, found)

        output_path = Path(temp_root) / "updated.7z"
        _run_bsdtar(
            [
                "-cf",
                str(output_path),
                "--format=7zip",
                "-C",
                str(root),
                *member_names,
            ]
        )
        return output_path.read_bytes()


def _write_gzip_payload(payload: bytes) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb") as archive:
        archive.write(payload)
    return buffer.getvalue()


def _ensure_all_replacements_found(replacements: dict[str, bytes], found: set[str]) -> None:
    missing = sorted(set(replacements) - found)
    if missing:
        raise DocumentMutationBlockedError(
            BlockedReason.validation_failed,
            f"Archive member does not exist: {missing[0]}",
        )


def _safe_member_name(name: str) -> bool:
    if not name or "\x00" in name or "\\" in name:
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and not any(part in {"", ".", ".."} for part in path.parts)


def _extract_7z_archive(path: Path, destination: Path) -> list[str]:
    member_names = _list_7z_member_names(path)
    _run_bsdtar(
        [
            "-xf",
            str(path),
            "-C",
            str(destination),
            "--no-same-owner",
            "--no-same-permissions",
        ]
    )
    _validate_extracted_7z_tree(destination, member_names)
    return member_names


def _list_7z_member_names(path: Path) -> list[str]:
    result = _run_bsdtar(["-tf", str(path)], capture_output=True)
    names = [line.strip() for line in result.stdout.decode("utf-8").splitlines() if line.strip()]
    unsafe = [name for name in names if not _safe_member_name(name)]
    if unsafe:
        raise DocumentMutationBlockedError(
            BlockedReason.path_traversal_detected,
            f"7z archive member path is unsafe: {unsafe[0]}",
        )
    return names


def _validate_extracted_7z_tree(root: Path, member_names: list[str]) -> None:
    expected = {_normalize_member_name(name) for name in member_names}
    actual: set[str] = set()
    for item in root.rglob("*"):
        relative = item.relative_to(root).as_posix()
        if item.is_symlink():
            raise DocumentMutationBlockedError(
                BlockedReason.unsupported_operation,
                f"7z archive symlink entries are not promoted: {relative}",
            )
        if item.is_file():
            actual.add(relative)
    unexpected = sorted(actual - expected)
    if unexpected:
        raise DocumentMutationBlockedError(
            BlockedReason.path_traversal_detected,
            f"7z archive extracted an unexpected member: {unexpected[0]}",
        )


def _safe_extracted_member_path(root: Path, member_name: str) -> Path | None:
    normalized = _normalize_member_name(member_name)
    if not _safe_member_name(normalized):
        return None
    candidate = root.joinpath(*PurePosixPath(normalized).parts)
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _normalize_member_name(member_name: str) -> str:
    return member_name.rstrip("/")


def _run_bsdtar(
    args: list[str],
    *,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    executable = shutil.which("bsdtar")
    if executable is None:
        raise DocumentMutationBlockedError(
            BlockedReason.unsupported_operation,
            "7z archive handling requires a local bsdtar/libarchive runtime.",
        )
    try:
        return subprocess.run(  # noqa: S603 - static executable lookup plus static argv.
            [executable, *args],
            check=True,
            capture_output=capture_output,
            timeout=_BSDTAR_TIMEOUT_SECONDS,
        )
    except subprocess.CalledProcessError as exc:
        raise DocumentMutationBlockedError(
            BlockedReason.corrupt,
            f"7z archive operation failed through bsdtar: {exc.stderr.decode('utf-8', 'replace')}",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise DocumentMutationBlockedError(
            BlockedReason.oversized_expanded_bytes,
            "7z archive operation exceeded the local timeout budget.",
        ) from exc


def _metadata(
    path: Path,
    *,
    document_format: DocumentFormat,
    entry_count: int,
) -> dict[str, MetadataValue]:
    return {
        "adapter_id": f"archive-container-{document_format.value}-adapter",
        "engine_id": f"archive-container-{document_format.value}",
        "format": document_format.value,
        "source_name": path.name,
        "entry_count": entry_count,
        "mutation_policy": "archive_child_derivative_write_render_save",
        "render_oracle": "archive-container-structural-svg",
    }


def _render_lines_svg(lines: list[str], *, title: str) -> bytes:
    escaped_title = html.escape(title)
    safe_lines = [html.escape(line) for line in lines if line]
    height = max(160, 72 + len(safe_lines) * 28)
    text_nodes = [
        f'<text x="32" y="{84 + index * 28}" font-size="15" font-family="monospace">{line}</text>'
        for index, line in enumerate(safe_lines[:80])
    ]
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="{height}" '
        f'viewBox="0 0 1040 {height}">'
        '<rect width="100%" height="100%" fill="#ffffff"/>'
        f'<text x="32" y="40" font-size="22" font-family="sans-serif" '
        f'font-weight="700">{escaped_title}</text>' + "".join(text_nodes) + "</svg>"
    )
    return svg.encode("utf-8")


def _raise_unsupported_operation(operation: DocumentPatchOperation) -> NoReturn:
    raise DocumentMutationBlockedError(
        BlockedReason.unsupported_operation,
        f"Archive operation is not supported: "
        f"{operation.operation_type.value} {operation.target_path}",
    )
