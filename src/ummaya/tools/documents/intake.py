# SPDX-License-Identifier: Apache-2.0
"""Fail-closed document intake for local Public AX artifacts."""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict, Field

from ummaya.tools.documents.models import (
    BlockedReason,
    DocumentFormat,
    DocumentIntakeResult,
    DocumentSecurityFinding,
    SecurityFindingSeverity,
    SecurityState,
    ToolResultStatus,
)


class DocumentIntakePolicy(BaseModel):
    """Fail-closed pre-parse limits for user supplied document artifacts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed_formats: frozenset[str] = Field(
        default_factory=lambda: frozenset(_EXTENSION_TO_FORMAT.values())
    )
    max_raw_bytes: int = 50 * 1024 * 1024
    max_expanded_bytes: int = 200 * 1024 * 1024
    max_entries: int = 5_000
    max_depth: int = 1
    allow_external_links: bool = False
    allow_macros: bool = False
    allow_embedded_active_content: bool = False


_EXTENSION_TO_FORMAT: dict[str, str] = {
    ".hwpx": "hwpx",
    ".hwp": "hwp",
    ".docx": "docx",
    ".pdf": "pdf",
    ".xlsx": "xlsx",
    ".pptx": "pptx",
}

_MIME_BY_FORMAT: dict[str, frozenset[str]] = {
    "hwpx": frozenset(
        {
            "application/haansofthwpx",
            "application/vnd.hancom.hwpx",
            "application/x-hwpx",
            "application/zip",
        }
    ),
    "hwp": frozenset(
        {
            "application/haansofthwp",
            "application/vnd.hancom.hwp",
            "application/x-hwp",
            "application/octet-stream",
        }
    ),
    "docx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
        }
    ),
    "pdf": frozenset({"application/pdf"}),
    "xlsx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/zip",
        }
    ),
    "pptx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/zip",
        }
    ),
}

_DETECTED_MIME_BY_FORMAT: dict[str, str] = {
    "hwpx": "application/vnd.hancom.hwpx",
    "hwp": "application/vnd.hancom.hwp",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

_ZIP_FORMAT_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("docx", ("word/document.xml",)),
    ("xlsx", ("xl/workbook.xml",)),
    ("pptx", ("ppt/presentation.xml",)),
    (
        "hwpx",
        (
            "Contents/section0.xml",
            "Contents/header.xml",
            "version.xml",
            "META-INF/manifest.xml",
        ),
    ),
)

_OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_PDF_SIGNATURE = b"%PDF-"
_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")

_MACRO_MARKERS = (
    "vbaproject.bin",
    "/vba",
    "macrosheets/",
    "xl4macrosheets/",
)

_ACTIVE_CONTENT_MARKERS = (
    "/activex/",
    "/embeddings/",
    "oleobject",
    "flash",
    "javascript",
)

_RELATIONSHIP_SUFFIX = ".rels"

_BLOCKED_REASON_BY_INTERNAL: dict[str, str] = {
    "unsupported_input": "unsupported_format",
    "unsupported_extension": "unsupported_format",
    "unsupported_compression": "unsupported_format",
    "nested_package": "unsupported_format",
    "raw_size_limit": "oversized_raw_bytes",
    "corrupt_package": "corrupt",
    "encrypted_package": "encrypted",
    "zip_expansion_limit": "oversized_expanded_bytes",
    "zip_entry_limit": "package_entry_limit_exceeded",
    "zip_path_traversal": "path_traversal_detected",
    "active_content": "macro_detected",
    "external_link": "external_link_detected",
}

DEFAULT_INTAKE_POLICY = DocumentIntakePolicy()


def inspect_document_intake(
    source_path: str | Path,
    *,
    expected_format: str | object | None = None,
    declared_mime_type: str | None = None,
    policy: DocumentIntakePolicy | None = None,
) -> DocumentIntakeResult:
    """Validate document bytes before format-specific parsing can run."""

    active_policy = policy or DEFAULT_INTAKE_POLICY
    path = Path(source_path)
    expected = _format_value(expected_format)
    declared_mime = _normalize_mime(declared_mime_type)

    if not path.exists() or not path.is_file():
        return _blocked_result(
            path=path,
            expected_format=expected,
            declared_mime_type=declared_mime,
            reason="unsupported_input",
            message="Document intake requires an existing local file.",
        )

    extension_format = _EXTENSION_TO_FORMAT.get(path.suffix.lower())
    if extension_format is None or extension_format not in active_policy.allowed_formats:
        return _blocked_result(
            path=path,
            expected_format=expected,
            declared_mime_type=declared_mime,
            reason="unsupported_extension",
            message="Document extension is not on the supported allowlist.",
        )

    raw_size = path.stat().st_size
    if raw_size > active_policy.max_raw_bytes:
        return _blocked_result(
            path=path,
            expected_format=expected,
            declared_mime_type=declared_mime,
            reason="raw_size_limit",
            message="Document raw byte size exceeds the intake policy.",
            byte_size=raw_size,
        )

    payload = path.read_bytes()
    sha256 = hashlib.sha256(payload).hexdigest()

    detected_format, expanded_byte_size, package_reason = _detect_format(payload, active_policy)
    if package_reason is not None:
        return _blocked_result(
            path=path,
            expected_format=expected,
            declared_mime_type=declared_mime,
            reason=package_reason,
            message=_reason_message(package_reason),
            byte_size=raw_size,
            sha256=sha256,
        )

    if detected_format is None:
        return _blocked_result(
            path=path,
            expected_format=expected,
            declared_mime_type=declared_mime,
            reason="signature_mismatch",
            message="Document signature or package structure is not supported.",
            byte_size=raw_size,
            sha256=sha256,
        )

    if expected is not None and expected != detected_format:
        return _blocked_result(
            path=path,
            detected_format=detected_format,
            expected_format=expected,
            declared_mime_type=declared_mime,
            reason="signature_mismatch",
            message="Expected document format does not match detected content.",
            byte_size=raw_size,
            expanded_byte_size=expanded_byte_size,
            sha256=sha256,
        )

    if extension_format != detected_format:
        return _blocked_result(
            path=path,
            detected_format=detected_format,
            expected_format=expected,
            declared_mime_type=declared_mime,
            reason="signature_mismatch",
            message="Filename extension does not match detected content.",
            byte_size=raw_size,
            expanded_byte_size=expanded_byte_size,
            sha256=sha256,
        )

    if declared_mime is not None and declared_mime not in _MIME_BY_FORMAT[detected_format]:
        return _blocked_result(
            path=path,
            detected_format=detected_format,
            expected_format=expected,
            declared_mime_type=declared_mime,
            reason="mime_mismatch",
            message="Declared MIME type does not match detected document format.",
            byte_size=raw_size,
            expanded_byte_size=expanded_byte_size,
            sha256=sha256,
        )

    return _result(
        status="ok",
        path=path,
        detected_format=_document_format(detected_format),
        expected_format=_document_format(expected),
        declared_mime_type=declared_mime,
        mime_type=_DETECTED_MIME_BY_FORMAT[detected_format],
        byte_size=raw_size,
        expanded_byte_size=expanded_byte_size,
        sha256=sha256,
        blocked_reason=None,
        findings=(),
    )


def _detect_format(
    payload: bytes, policy: DocumentIntakePolicy
) -> tuple[str | None, int, str | None]:
    if payload.startswith(_PDF_SIGNATURE):
        return "pdf", 0, None

    if payload.startswith(_OLE_SIGNATURE):
        return "hwp", 0, None

    if not payload.startswith(_ZIP_SIGNATURES):
        return None, 0, None

    try:
        with zipfile.ZipFile(PathBytes(payload)) as package:
            package_entries = package.infolist()
            package_reason = _inspect_zip_package(package, package_entries, policy)
            if package_reason is not None:
                return None, 0, package_reason

            names = frozenset(info.filename for info in package_entries)
            detected = _detect_zip_format(names)
            expanded_size = sum(info.file_size for info in package_entries)
            return detected, expanded_size, None
    except zipfile.BadZipFile:
        return None, 0, "corrupt_package"
    except NotImplementedError:
        return None, 0, "unsupported_compression"


def _inspect_zip_package(
    package: zipfile.ZipFile,
    entries: list[zipfile.ZipInfo],
    policy: DocumentIntakePolicy,
) -> str | None:
    if len(entries) > policy.max_entries:
        return "zip_entry_limit"

    expanded_size = 0
    for entry in entries:
        if entry.flag_bits & 0x1:
            return "encrypted_package"
        if _is_unsafe_package_name(entry.filename):
            return "zip_path_traversal"
        expanded_size += entry.file_size
        if expanded_size > policy.max_expanded_bytes:
            return "zip_expansion_limit"
        if _is_nested_package(entry.filename, policy):
            return "nested_package"
        if _is_macro_entry(entry.filename) and not policy.allow_macros:
            return "active_content"
        if _is_active_content_entry(entry.filename) and not policy.allow_embedded_active_content:
            return "active_content"

    if not policy.allow_external_links and _has_external_relationship(package, entries):
        return "external_link"

    return None


def _detect_zip_format(names: frozenset[str]) -> str | None:
    for document_format, markers in _ZIP_FORMAT_MARKERS:
        if any(marker in names for marker in markers):
            return document_format
    return None


def _is_unsafe_package_name(name: str) -> bool:
    if not name or "\x00" in name or "\\" in name:
        return True
    if name.startswith(("/", "~")):
        return True
    path = PurePosixPath(name)
    return path.is_absolute() or ".." in path.parts


def _is_nested_package(name: str, policy: DocumentIntakePolicy) -> bool:
    if policy.max_depth > 1:
        return False
    return name.lower().endswith((".zip", ".hwpx", ".docx", ".xlsx", ".pptx", ".jar"))


def _is_macro_entry(name: str) -> bool:
    normalized = f"/{name.lower()}"
    return any(marker in normalized for marker in _MACRO_MARKERS)


def _is_active_content_entry(name: str) -> bool:
    normalized = f"/{name.lower()}"
    return any(marker in normalized for marker in _ACTIVE_CONTENT_MARKERS)


def _has_external_relationship(package: zipfile.ZipFile, entries: list[zipfile.ZipInfo]) -> bool:
    for entry in entries:
        if not entry.filename.lower().endswith(_RELATIONSHIP_SUFFIX):
            continue
        with package.open(entry) as relationship_file:
            contents = relationship_file.read(1024 * 1024).lower()
        if b'targetmode="external"' in contents:
            return True
        if b"target='http://" in contents or b'target="http://' in contents:
            return True
        if b"target='https://" in contents or b'target="https://' in contents:
            return True
    return False


def _blocked_result(
    *,
    path: Path,
    reason: str,
    message: str,
    detected_format: str | None = None,
    expected_format: str | None = None,
    declared_mime_type: str | None = None,
    byte_size: int = 0,
    expanded_byte_size: int = 0,
    sha256: str | None = None,
) -> DocumentIntakeResult:
    blocked_reason = _blocked_reason(reason)
    finding = _finding(code=blocked_reason, severity="blocked", message=message)
    return _result(
        status="blocked",
        path=path,
        detected_format=_document_format(detected_format),
        expected_format=_document_format(expected_format),
        declared_mime_type=declared_mime_type,
        mime_type=(
            _DETECTED_MIME_BY_FORMAT[detected_format] if detected_format is not None else None
        ),
        byte_size=byte_size,
        expanded_byte_size=expanded_byte_size,
        sha256=sha256,
        blocked_reason=blocked_reason,
        findings=(finding,),
    )


def _result(
    *,
    status: str,
    path: Path,
    detected_format: DocumentFormat | None,
    expected_format: DocumentFormat | None,
    declared_mime_type: str | None,
    mime_type: str | None,
    byte_size: int,
    expanded_byte_size: int,
    sha256: str | None,
    blocked_reason: BlockedReason | None,
    findings: tuple[DocumentSecurityFinding, ...],
) -> DocumentIntakeResult:
    return DocumentIntakeResult(
        tool_id="document_inspect",
        correlation_id=_correlation_id(sha256),
        status=ToolResultStatus(status),
        artifact_refs=[f"sha256:{sha256}"] if sha256 is not None else [],
        source_path=path,
        display_name=path.name,
        detected_format=detected_format,
        expected_format=expected_format,
        declared_mime_type=declared_mime_type,
        mime_type=mime_type,
        byte_size=byte_size,
        expanded_byte_size=expanded_byte_size,
        sha256=sha256,
        security_state=SecurityState.accepted if status == "ok" else SecurityState.blocked,
        blocked_reason=blocked_reason,
        findings=list(findings),
        text_summary=_text_summary(
            status=status,
            detected_format=detected_format.value if detected_format is not None else None,
            blocked_reason=blocked_reason.value if blocked_reason is not None else None,
            byte_size=byte_size,
            expanded_byte_size=expanded_byte_size,
        ),
    )


def _finding(
    *,
    code: BlockedReason,
    severity: SecurityFindingSeverity,
    message: str,
) -> DocumentSecurityFinding:
    return DocumentSecurityFinding(
        finding_id=f"security-{code.value}",
        code=code,
        severity=severity,
        message=message,
    )


def _document_format(value: str | None) -> DocumentFormat | None:
    if value is None:
        return None
    return DocumentFormat(value)


def _format_value(value: str | object | None) -> str | None:
    if value is None:
        return None
    candidate = getattr(value, "value", value)
    return str(candidate).lower()


def _normalize_mime(value: str | None) -> str | None:
    if value is None:
        return None
    return value.split(";", maxsplit=1)[0].strip().lower()


def _blocked_reason(reason: str) -> BlockedReason:
    return BlockedReason(_BLOCKED_REASON_BY_INTERNAL.get(reason, reason))


def _correlation_id(sha256: str | None) -> str:
    suffix = sha256[:12] if sha256 is not None else "unavailable"
    return f"document-intake-{suffix}"


def _text_summary(
    *,
    status: str,
    detected_format: str | None,
    blocked_reason: str | None,
    byte_size: int,
    expanded_byte_size: int,
) -> str:
    if status == "ok":
        return (
            f"Document intake accepted {detected_format} artifact "
            f"({byte_size} raw bytes, {expanded_byte_size} expanded bytes)."
        )
    return f"Document intake blocked: {blocked_reason}."


def _reason_message(reason: str) -> str:
    return {
        "corrupt_package": "Document package is corrupt or unreadable.",
        "unsupported_compression": "Document package uses unsupported compression.",
        "encrypted_package": "Encrypted document package members are blocked.",
        "zip_path_traversal": "Document package contains unsafe member paths.",
        "zip_expansion_limit": "Document package expands beyond the intake policy.",
        "zip_entry_limit": "Document package contains too many entries.",
        "nested_package": "Nested document packages are blocked at intake.",
        "active_content": "Document package contains macros or active content.",
        "external_link": "Document package contains external relationship targets.",
    }.get(reason, "Document failed intake security validation.")


class PathBytes(io.BytesIO):
    """BytesIO subclass with a stable name for ZipFile diagnostics."""

    name = "<document-intake-bytes>"
