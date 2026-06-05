# SPDX-License-Identifier: Apache-2.0
"""Fail-closed document intake for local Public AX artifacts."""

from __future__ import annotations

import ast
import gzip
import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

import yaml
from defusedxml import ElementTree  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field

from ummaya.tools.documents.models import (
    KNOWN_DOCUMENT_FORMAT_FAMILIES,
    PROMOTED_RUNTIME_DOCUMENT_FORMATS,
    BlockedReason,
    DocumentFormat,
    DocumentFormatFamily,
    DocumentIntakeResult,
    DocumentSecurityFinding,
    KnownDocumentFormat,
    SecurityFindingSeverity,
    SecurityState,
    ToolResultStatus,
)


class DocumentIntakePolicy(BaseModel):
    """Fail-closed pre-parse limits for user supplied document artifacts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed_formats: frozenset[str] = Field(
        default_factory=lambda: frozenset(format_.value for format_ in KnownDocumentFormat)
    )
    max_raw_bytes: int = 50 * 1024 * 1024
    max_expanded_bytes: int = 200 * 1024 * 1024
    max_entries: int = 5_000
    max_depth: int = 1
    allow_external_links: bool = False
    allow_macros: bool = False
    allow_embedded_active_content: bool = False


_EXTENSION_TO_KNOWN_FORMAT: dict[str, str] = {
    ".hwpx": "hwpx",
    ".hwp": "hwp",
    ".hml": "hml",
    ".owpml": "owpml",
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".pptx": "pptx",
    ".doc": "doc",
    ".xls": "xls",
    ".ppt": "ppt",
    ".pdf": "pdf",
    ".pdfa": "pdfa",
    ".odt": "odt",
    ".ods": "ods",
    ".odp": "odp",
    ".html": "html",
    ".htm": "htm",
    ".txt": "txt",
    ".rtf": "rtf",
    ".md": "md",
    ".epub": "epub",
    ".csv": "csv",
    ".tsv": "tsv",
    ".xml": "xml",
    ".rdf": "rdf",
    ".ttl": "ttl",
    ".lod": "lod",
    ".json": "json",
    ".jsonl": "jsonl",
    ".yaml": "yaml",
    ".yml": "yml",
    ".geojson": "geojson",
    ".gpx": "gpx",
    ".kml": "kml",
    ".fasta": "fasta",
    ".sgml": "sgml",
    ".dtd": "dtd",
    ".py": "py",
    ".png": "png",
    ".jpg": "jpg",
    ".jpeg": "jpeg",
    ".gif": "gif",
    ".tif": "tif",
    ".tiff": "tiff",
    ".bmp": "bmp",
    ".webp": "webp",
    ".shp": "shp",
    ".shx": "shx",
    ".dbf": "dbf",
    ".prj": "prj",
    ".stl": "stl",
    ".wav": "wav",
    ".mp3": "mp3",
    ".mp4": "mp4",
    ".zip": "zip",
    ".7z": "7z",
    ".tar": "tar",
    ".gz": "gz",
    ".etc": "etc",
}

_PROMOTED_FORMAT_VALUES = frozenset(format_.value for format_ in PROMOTED_RUNTIME_DOCUMENT_FORMATS)
_KNOWN_FORMAT_RUNTIME_ALIASES: dict[str, str] = {
    "pdfa": "pdf",
}


def _runtime_format_for_known_format(known_format: str) -> str | None:
    if known_format in _PROMOTED_FORMAT_VALUES:
        return known_format
    return _KNOWN_FORMAT_RUNTIME_ALIASES.get(known_format)


_EXTENSION_TO_FORMAT: dict[str, str] = {
    extension: known_format
    for extension, known_format in _EXTENSION_TO_KNOWN_FORMAT.items()
    if _runtime_format_for_known_format(known_format) is not None
}

_MIME_BY_FORMAT: dict[str, frozenset[str]] = {
    "hwpx": frozenset(
        {
            "application/haansofthwpx",
            "application/vnd.hancom.hwpx",
            "application/x-hwpx",
            "application/owpml",
            "application/zip",
        }
    ),
    "owpml": frozenset(
        {
            "application/owpml",
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
    "odt": frozenset(
        {
            "application/vnd.oasis.opendocument.text",
            "application/zip",
        }
    ),
    "ods": frozenset(
        {
            "application/vnd.oasis.opendocument.spreadsheet",
            "application/zip",
        }
    ),
    "odp": frozenset(
        {
            "application/vnd.oasis.opendocument.presentation",
            "application/zip",
        }
    ),
    "html": frozenset({"text/html", "application/xhtml+xml"}),
    "htm": frozenset({"text/html", "application/xhtml+xml"}),
    "txt": frozenset({"text/plain"}),
    "rtf": frozenset({"application/rtf", "text/rtf"}),
    "md": frozenset({"text/markdown", "text/plain"}),
    "epub": frozenset({"application/epub+zip", "application/zip"}),
    "csv": frozenset({"text/csv", "text/plain"}),
    "tsv": frozenset({"text/tab-separated-values", "text/plain"}),
    "xml": frozenset({"application/xml", "text/xml"}),
    "rdf": frozenset({"application/rdf+xml", "application/xml", "text/xml"}),
    "ttl": frozenset({"text/turtle", "text/plain"}),
    "lod": frozenset({"text/plain"}),
    "json": frozenset({"application/json", "text/plain"}),
    "jsonl": frozenset({"application/x-ndjson", "application/json", "text/plain"}),
    "yaml": frozenset({"application/yaml", "text/yaml", "text/plain"}),
    "yml": frozenset({"application/yaml", "text/yaml", "text/plain"}),
    "geojson": frozenset({"application/geo+json", "application/json", "text/plain"}),
    "gpx": frozenset({"application/gpx+xml", "application/xml", "text/xml"}),
    "kml": frozenset({"application/vnd.google-earth.kml+xml", "application/xml", "text/xml"}),
    "fasta": frozenset({"text/plain"}),
    "sgml": frozenset({"text/sgml", "text/plain"}),
    "dtd": frozenset({"application/xml-dtd", "text/plain"}),
    "py": frozenset({"text/x-python", "text/plain"}),
    "hml": frozenset({"application/xml", "text/xml"}),
    "zip": frozenset({"application/zip"}),
    "7z": frozenset({"application/x-7z-compressed", "application/7z"}),
    "tar": frozenset({"application/x-tar", "application/tar"}),
    "gz": frozenset({"application/gzip", "application/x-gzip"}),
    "etc": frozenset({"text/plain"}),
}

_DETECTED_MIME_BY_FORMAT: dict[str, str] = {
    "hwpx": "application/vnd.hancom.hwpx",
    "owpml": "application/owpml",
    "hwp": "application/vnd.hancom.hwp",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "odt": "application/vnd.oasis.opendocument.text",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
    "odp": "application/vnd.oasis.opendocument.presentation",
    "html": "text/html",
    "htm": "text/html",
    "txt": "text/plain",
    "rtf": "application/rtf",
    "md": "text/markdown",
    "epub": "application/epub+zip",
    "csv": "text/csv",
    "tsv": "text/tab-separated-values",
    "xml": "application/xml",
    "rdf": "application/rdf+xml",
    "ttl": "text/turtle",
    "lod": "text/plain",
    "json": "application/json",
    "jsonl": "application/x-ndjson",
    "yaml": "application/yaml",
    "yml": "application/yaml",
    "geojson": "application/geo+json",
    "gpx": "application/gpx+xml",
    "kml": "application/vnd.google-earth.kml+xml",
    "fasta": "text/plain",
    "sgml": "text/sgml",
    "dtd": "application/xml-dtd",
    "py": "text/x-python",
    "hml": "application/xml",
    "zip": "application/zip",
    "7z": "application/x-7z-compressed",
    "tar": "application/x-tar",
    "gz": "application/gzip",
    "etc": "text/plain",
}

_ODF_MIMETYPE_FORMATS: dict[bytes, str] = {
    b"application/vnd.oasis.opendocument.text": "odt",
    b"application/vnd.oasis.opendocument.spreadsheet": "ods",
    b"application/vnd.oasis.opendocument.presentation": "odp",
}

_TEXT_WEB_FORMAT_VALUES = frozenset({"html", "htm", "txt", "rtf", "md"})
_DATA_FORMAT_VALUES = frozenset(
    {
        "csv",
        "tsv",
        "xml",
        "rdf",
        "ttl",
        "lod",
        "json",
        "jsonl",
        "yaml",
        "yml",
        "geojson",
        "gpx",
        "kml",
        "fasta",
        "sgml",
        "dtd",
        "hml",
        "etc",
    }
)
_CODE_FORMAT_VALUES = frozenset({"py"})

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
_SEVEN_Z_SIGNATURE = b"7z\xbc\xaf\x27\x1c"

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
    "known_unsupported_format": "unsupported_operation",
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

    known_format = _EXTENSION_TO_KNOWN_FORMAT.get(path.suffix.lower())
    if known_format is None or known_format not in active_policy.allowed_formats:
        return _blocked_result(
            path=path,
            expected_format=expected,
            declared_mime_type=declared_mime,
            reason="unsupported_extension",
            message="Document extension is not on the supported allowlist.",
            known_format=known_format,
            next_safe_actions=(
                _next_safe_actions_for_known_format(known_format)
                if known_format is not None
                else ()
            ),
        )

    raw_size = path.stat().st_size
    if raw_size > active_policy.max_raw_bytes:
        return _blocked_result(
            path=path,
            expected_format=expected,
            declared_mime_type=declared_mime,
            reason="raw_size_limit",
            message="Document raw byte size exceeds the intake policy.",
            known_format=known_format,
            byte_size=raw_size,
        )

    payload = path.read_bytes()
    sha256 = hashlib.sha256(payload).hexdigest()

    runtime_format = _runtime_format_for_known_format(known_format)
    if runtime_format is None:
        return _blocked_result(
            path=path,
            expected_format=expected,
            declared_mime_type=declared_mime,
            reason="known_unsupported_format",
            message=(
                "Document format is recognized, but no promoted runtime adapter "
                "can safely process this operation yet."
            ),
            known_format=known_format,
            byte_size=raw_size,
            sha256=sha256,
            next_safe_actions=_next_safe_actions_for_known_format(known_format),
        )

    detected_format, expanded_byte_size, package_reason = _detect_format(
        payload,
        active_policy,
        known_format=known_format,
    )
    if package_reason is not None:
        return _blocked_result(
            path=path,
            expected_format=expected,
            declared_mime_type=declared_mime,
            reason=package_reason,
            message=_reason_message(package_reason),
            known_format=known_format,
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
            known_format=known_format,
            byte_size=raw_size,
            sha256=sha256,
        )

    if expected is not None and not _expected_format_matches(
        expected=expected,
        detected_format=detected_format,
        known_format=known_format,
    ):
        return _blocked_result(
            path=path,
            detected_format=detected_format,
            known_format=known_format,
            expected_format=expected,
            declared_mime_type=declared_mime,
            reason="signature_mismatch",
            message="Expected document format does not match detected content.",
            byte_size=raw_size,
            expanded_byte_size=expanded_byte_size,
            sha256=sha256,
        )

    if not _known_format_matches_detected(
        known_format=known_format,
        detected_format=detected_format,
    ):
        return _blocked_result(
            path=path,
            detected_format=detected_format,
            known_format=known_format,
            expected_format=expected,
            declared_mime_type=declared_mime,
            reason="signature_mismatch",
            message="Filename extension does not match detected content.",
            byte_size=raw_size,
            expanded_byte_size=expanded_byte_size,
            sha256=sha256,
        )

    if declared_mime is not None and not _declared_mime_matches_formats(
        declared_mime=declared_mime,
        known_format=known_format,
        detected_format=detected_format,
    ):
        return _blocked_result(
            path=path,
            detected_format=detected_format,
            known_format=known_format,
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
        known_format=_known_document_format(known_format),
        format_family=_format_family(known_format),
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
    payload: bytes, policy: DocumentIntakePolicy, *, known_format: str
) -> tuple[str | None, int, str | None]:
    binary_result = _detect_binary_container_format(
        payload,
        policy,
        known_format=known_format,
    )
    if binary_result is not None:
        return binary_result

    if not payload.startswith(_ZIP_SIGNATURES):
        if _is_text_web_payload(payload, known_format=known_format):
            return known_format, 0, None
        if _is_data_payload(payload, known_format=known_format):
            return known_format, 0, None
        if _is_code_payload(payload, known_format=known_format):
            return known_format, 0, None
        return None, 0, None

    try:
        with zipfile.ZipFile(PathBytes(payload)) as package:
            package_entries = package.infolist()
            package_reason = _inspect_zip_package(package, package_entries, policy)
            if package_reason is not None:
                return None, 0, package_reason

            names = frozenset(info.filename for info in package_entries)
            detected = _detect_zip_format(package, names)
            if detected == "hwpx" and known_format == "owpml":
                detected = "owpml"
            expanded_size = sum(info.file_size for info in package_entries)
            return detected, expanded_size, None
    except zipfile.BadZipFile:
        return None, 0, "corrupt_package"
    except NotImplementedError:
        return None, 0, "unsupported_compression"


def _detect_binary_container_format(
    payload: bytes,
    policy: DocumentIntakePolicy,
    *,
    known_format: str,
) -> tuple[str | None, int, str | None] | None:
    if payload.startswith(_PDF_SIGNATURE):
        return "pdf", 0, None
    if payload.startswith(_OLE_SIGNATURE):
        return "hwp", 0, None
    if known_format == "7z" and payload.startswith(_SEVEN_Z_SIGNATURE):
        return "7z", 0, None
    if known_format == "gz" and payload.startswith(b"\x1f\x8b"):
        return _detect_gzip_format(payload, policy)
    if known_format != "tar":
        return None
    tar_detected, tar_expanded_size, tar_reason = _detect_tar_format(payload, policy)
    if tar_detected is not None or tar_reason is not None:
        return tar_detected, tar_expanded_size, tar_reason
    return None


def _is_text_web_payload(payload: bytes, *, known_format: str) -> bool:
    if known_format not in _TEXT_WEB_FORMAT_VALUES:
        return False
    if b"\x00" in payload:
        return False
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError:
        return False
    if known_format in {"html", "htm"}:
        lowered = decoded[:4096].lower()
        return "<html" in lowered or "<body" in lowered or "<p" in lowered
    if known_format == "rtf":
        return decoded.lstrip().startswith("{\\rtf")
    return True


def _is_data_payload(payload: bytes, *, known_format: str) -> bool:
    if known_format not in _DATA_FORMAT_VALUES:
        return False
    if b"\x00" in payload:
        return False
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError:
        return False
    if known_format in {"json", "geojson"}:
        return _loads_json(decoded)
    if known_format == "jsonl":
        return all(_loads_json(line) for line in decoded.splitlines() if line.strip())
    if known_format in {"yaml", "yml"}:
        return _loads_yaml(decoded)
    if known_format in {"xml", "rdf", "gpx", "kml", "hml"}:
        return _loads_xml(decoded)
    if known_format in {"csv", "tsv"}:
        return bool(decoded.strip())
    return bool(decoded.strip())


def _is_code_payload(payload: bytes, *, known_format: str) -> bool:
    if known_format not in _CODE_FORMAT_VALUES:
        return False
    if b"\x00" in payload:
        return False
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError:
        return False
    if not decoded.strip():
        return False
    try:
        ast.parse(decoded)
    except SyntaxError:
        return False
    return True


def _expected_format_matches(
    *,
    expected: str,
    detected_format: str,
    known_format: str,
) -> bool:
    return expected in {detected_format, known_format} or (
        _runtime_format_for_known_format(expected) == detected_format
    )


def _known_format_matches_detected(
    *,
    known_format: str,
    detected_format: str,
) -> bool:
    if known_format == "hwp" and detected_format in {"hwpx", "owpml"}:
        return True
    return known_format == detected_format or (
        _runtime_format_for_known_format(known_format) == detected_format
    )


def _declared_mime_matches_formats(
    *,
    declared_mime: str,
    known_format: str,
    detected_format: str,
) -> bool:
    allowed_mimes = set(_MIME_BY_FORMAT[detected_format])
    if _known_format_matches_detected(
        known_format=known_format,
        detected_format=detected_format,
    ):
        allowed_mimes.update(_MIME_BY_FORMAT.get(known_format, frozenset()))
    return declared_mime in allowed_mimes


def _loads_json(payload: str) -> bool:
    try:
        json.loads(payload)
    except json.JSONDecodeError:
        return False
    return True


def _loads_yaml(payload: str) -> bool:
    try:
        yaml.safe_load(payload)
    except yaml.YAMLError:
        return False
    return True


def _loads_xml(payload: str) -> bool:
    try:
        ElementTree.fromstring(payload.encode("utf-8"))
    except ElementTree.ParseError:
        return False
    return True


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


def _detect_zip_format(package: zipfile.ZipFile, names: frozenset[str]) -> str | None:
    odf_format = _detect_odf_format(package, names)
    if odf_format is not None:
        return odf_format
    if _detect_epub_format(package, names):
        return "epub"
    for document_format, markers in _ZIP_FORMAT_MARKERS:
        if any(marker in names for marker in markers):
            return document_format
    if _is_generic_zip_candidate(names):
        return "zip"
    return None


def _detect_epub_format(package: zipfile.ZipFile, names: frozenset[str]) -> bool:
    if "mimetype" not in names:
        return False
    try:
        with package.open("mimetype") as mimetype_file:
            mimetype = mimetype_file.read(256).strip()
    except KeyError:
        return False
    return mimetype == b"application/epub+zip"


def _is_generic_zip_candidate(names: frozenset[str]) -> bool:
    return bool(names) and "mimetype" not in names


def _detect_tar_format(
    payload: bytes,
    policy: DocumentIntakePolicy,
) -> tuple[str | None, int, str | None]:
    try:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as package:
            expanded_size = 0
            member_count = 0
            for member in package.getmembers():
                member_count += 1
                if member_count > policy.max_entries:
                    return None, 0, "zip_entry_limit"
                if _is_unsafe_package_name(member.name):
                    return None, 0, "zip_path_traversal"
                if member.islnk() or member.issym() or member.isdev():
                    return None, 0, "active_content"
                expanded_size += max(member.size, 0)
                if expanded_size > policy.max_expanded_bytes:
                    return None, 0, "zip_expansion_limit"
            return ("tar", expanded_size, None) if member_count else (None, 0, "corrupt_package")
    except tarfile.TarError:
        return None, 0, None


def _detect_gzip_format(
    payload: bytes,
    policy: DocumentIntakePolicy,
) -> tuple[str | None, int, str | None]:
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(payload)) as package:
            expanded = package.read(policy.max_expanded_bytes + 1)
    except (OSError, EOFError):
        return None, 0, "corrupt_package"
    if len(expanded) > policy.max_expanded_bytes:
        return None, 0, "zip_expansion_limit"
    return "gz", len(expanded), None


def _detect_odf_format(package: zipfile.ZipFile, names: frozenset[str]) -> str | None:
    if (
        "mimetype" not in names
        or "META-INF/manifest.xml" not in names
        or "content.xml" not in names
    ):
        return None
    try:
        with package.open("mimetype") as mimetype_file:
            mimetype = mimetype_file.read(256).strip()
    except KeyError:
        return None
    return _ODF_MIMETYPE_FORMATS.get(mimetype)


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
    return name.lower().endswith((".zip", ".hwpx", ".owpml", ".docx", ".xlsx", ".pptx", ".jar"))


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
    known_format: str | None = None,
    expected_format: str | None = None,
    declared_mime_type: str | None = None,
    byte_size: int = 0,
    expanded_byte_size: int = 0,
    sha256: str | None = None,
    next_safe_actions: tuple[str, ...] = (),
) -> DocumentIntakeResult:
    blocked_reason = _blocked_reason(reason)
    finding = _finding(code=blocked_reason, severity="blocked", message=message)
    return _result(
        status="blocked",
        path=path,
        detected_format=_document_format(detected_format),
        known_format=_known_document_format(known_format or detected_format),
        format_family=_format_family(known_format or detected_format),
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
        next_safe_actions=next_safe_actions,
    )


def _result(
    *,
    status: str,
    path: Path,
    detected_format: DocumentFormat | None,
    known_format: KnownDocumentFormat | None,
    format_family: DocumentFormatFamily | None,
    expected_format: DocumentFormat | None,
    declared_mime_type: str | None,
    mime_type: str | None,
    byte_size: int,
    expanded_byte_size: int,
    sha256: str | None,
    blocked_reason: BlockedReason | None,
    findings: tuple[DocumentSecurityFinding, ...],
    next_safe_actions: tuple[str, ...] = (),
) -> DocumentIntakeResult:
    return DocumentIntakeResult(
        tool_id="document_inspect",
        correlation_id=_correlation_id(sha256),
        status=ToolResultStatus(status),
        artifact_refs=[f"sha256:{sha256}"] if sha256 is not None else [],
        source_path=path,
        display_name=path.name,
        detected_format=detected_format,
        known_format=known_format,
        format_family=format_family,
        expected_format=expected_format,
        declared_mime_type=declared_mime_type,
        mime_type=mime_type,
        byte_size=byte_size,
        expanded_byte_size=expanded_byte_size,
        sha256=sha256,
        security_state=SecurityState.accepted if status == "ok" else SecurityState.blocked,
        blocked_reason=blocked_reason,
        findings=list(findings),
        next_safe_actions=list(next_safe_actions),
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
    try:
        return DocumentFormat(value)
    except ValueError:
        return None


def _known_document_format(value: str | None) -> KnownDocumentFormat | None:
    if value is None:
        return None
    try:
        return KnownDocumentFormat(value)
    except ValueError:
        return None


def _format_family(value: str | None) -> DocumentFormatFamily | None:
    known_format = _known_document_format(value)
    if known_format is None:
        return None
    return KNOWN_DOCUMENT_FORMAT_FAMILIES[known_format]


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


def _next_safe_actions_for_known_format(known_format: str) -> tuple[str, ...]:
    family = _format_family(known_format)
    if family is DocumentFormatFamily.odf:
        return (
            "Use read-only extraction after an ODF adapter passes promotion gates.",
            "Convert to a promoted editable derivative only with explicit user approval.",
        )
    if family is DocumentFormatFamily.data_file:
        return (
            "Use schema or text inspection through the data-file adapter.",
            "Do not reinterpret the file as an editable public form.",
        )
    if family is DocumentFormatFamily.image_scan:
        return (
            "Use OCR or visual extraction only after an image-scan adapter is promoted.",
            "Create a separate editable derivative instead of mutating the raster source.",
        )
    if family is DocumentFormatFamily.archive:
        return (
            "Enumerate archive members only after secure archive routing is promoted.",
            "Do not mutate archive children in place.",
        )
    if family is DocumentFormatFamily.legacy_office:
        return (
            "Use metadata-only inspection unless an explicit conversion bridge is approved.",
            "Create an editable derivative instead of mutating the legacy binary source.",
        )
    if family is DocumentFormatFamily.geospatial_data:
        return (
            "Use geospatial metadata inspection or route packaged sidecars as derivatives.",
            "Do not reinterpret GIS or 3D geometry files as editable public forms.",
        )
    if family is DocumentFormatFamily.media_asset:
        return (
            "Use media metadata or transcription extraction only after a local adapter "
            "is approved.",
            "Create a separate document derivative for written content.",
        )
    if family is DocumentFormatFamily.code_file:
        return (
            "Use read-only source inspection for context.",
            "Do not mutate code artifacts through the public-document writer.",
        )
    return ("Use a promoted format adapter or request explicit conversion to a derivative.",)


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
