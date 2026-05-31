from __future__ import annotations

import io
import struct
import zipfile
from collections.abc import Mapping
from pathlib import Path

from ummaya.tools.documents.intake import (
    DEFAULT_INTAKE_POLICY,
    inspect_document_intake,
)


def _value(value: object) -> object:
    return getattr(value, "value", value)


def _policy_with(**updates: object) -> object:
    if hasattr(DEFAULT_INTAKE_POLICY, "model_copy"):
        return DEFAULT_INTAKE_POLICY.model_copy(update=updates)
    return DEFAULT_INTAKE_POLICY.__class__(**(DEFAULT_INTAKE_POLICY.__dict__ | updates))


def _zip_bytes(entries: Mapping[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for name, payload in entries.items():
            package.writestr(name, payload)
    return buffer.getvalue()


def _encrypted_zip_bytes(entries: Mapping[str, bytes]) -> bytes:
    data = bytearray(_zip_bytes(entries))
    position = 0
    while True:
        offset = data.find(b"PK\x03\x04", position)
        if offset == -1:
            break
        flags = struct.unpack_from("<H", data, offset + 6)[0]
        struct.pack_into("<H", data, offset + 6, flags | 0x1)
        position = offset + 4

    position = 0
    while True:
        offset = data.find(b"PK\x01\x02", position)
        if offset == -1:
            break
        flags = struct.unpack_from("<H", data, offset + 8)[0]
        struct.pack_into("<H", data, offset + 8, flags | 0x1)
        position = offset + 4
    return bytes(data)


def _content_types() -> bytes:
    return (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        b'<Override PartName="/word/document.xml" '
        b'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        b"</Types>"
    )


def _docx_bytes(*, extra_entries: Mapping[str, bytes] | None = None) -> bytes:
    entries: dict[str, bytes] = {
        "[Content_Types].xml": _content_types(),
        "word/document.xml": b"<w:document/>",
    }
    if extra_entries:
        entries.update(extra_entries)
    return _zip_bytes(entries)


def _write(path: Path, payload: bytes) -> Path:
    path.write_bytes(payload)
    return path


def _assert_blocked(result: object, reason: str) -> None:
    assert _value(result.status) == "blocked"
    assert _value(result.blocked_reason) == reason
    assert any(_value(finding.code) == reason for finding in result.findings)
    assert all(_value(finding.severity) == "blocked" for finding in result.findings)


def test_accepts_valid_docx_package_when_extension_signature_and_mime_match(
    tmp_path: Path,
) -> None:
    source = _write(tmp_path / "form.docx", _docx_bytes())

    result = inspect_document_intake(
        source,
        expected_format="docx",
        declared_mime_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )

    assert _value(result.status) == "ok"
    assert result.blocked_reason is None
    assert result.findings == []
    assert "docx" in result.text_summary
    assert result.artifact_refs


def test_blocks_unsupported_extension_before_content_parsing(tmp_path: Path) -> None:
    source = _write(tmp_path / "payload.exe", b"MZ")

    result = inspect_document_intake(source, declared_mime_type="application/octet-stream")

    _assert_blocked(result, "unsupported_format")


def test_blocks_extension_and_signature_mismatch(tmp_path: Path) -> None:
    source = _write(tmp_path / "form.docx", b"%PDF-1.7\n%%EOF\n")

    result = inspect_document_intake(
        source,
        expected_format="docx",
        declared_mime_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )

    _assert_blocked(result, "signature_mismatch")


def test_blocks_declared_mime_mismatch_instead_of_trusting_it(tmp_path: Path) -> None:
    source = _write(tmp_path / "form.pdf", b"%PDF-1.7\n%%EOF\n")

    result = inspect_document_intake(
        source,
        expected_format="pdf",
        declared_mime_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )

    _assert_blocked(result, "mime_mismatch")


def test_blocks_corrupt_zip_package(tmp_path: Path) -> None:
    source = _write(tmp_path / "form.docx", b"PK\x03\x04not-a-valid-zip-package")

    result = inspect_document_intake(source, expected_format="docx")

    _assert_blocked(result, "corrupt")


def test_blocks_encrypted_zip_members(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "form.docx",
        _encrypted_zip_bytes(
            {
                "[Content_Types].xml": _content_types(),
                "word/document.xml": b"<w:document/>",
            }
        ),
    )

    result = inspect_document_intake(source, expected_format="docx")

    _assert_blocked(result, "encrypted")


def test_blocks_zip_expansion_over_policy_limit(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "form.docx",
        _docx_bytes(extra_entries={"word/large.xml": b"A" * 256}),
    )
    policy = _policy_with(max_expanded_bytes=64)

    result = inspect_document_intake(source, expected_format="docx", policy=policy)

    _assert_blocked(result, "oversized_expanded_bytes")


def test_blocks_zip_path_traversal_members(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "form.docx",
        _docx_bytes(extra_entries={"../evil.xml": b"owned"}),
    )

    result = inspect_document_intake(source, expected_format="docx")

    _assert_blocked(result, "path_traversal_detected")


def test_blocks_ooxml_macros_and_active_content(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "form.docx",
        _docx_bytes(extra_entries={"word/vbaProject.bin": b"macro"}),
    )

    result = inspect_document_intake(source, expected_format="docx")

    _assert_blocked(result, "macro_detected")


def test_blocks_external_relationship_targets(tmp_path: Path) -> None:
    relationships = (
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Id="rId1" '
        b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
        b'Target="https://example.invalid/form" TargetMode="External"/>'
        b"</Relationships>"
    )
    source = _write(
        tmp_path / "form.docx",
        _docx_bytes(extra_entries={"word/_rels/document.xml.rels": relationships}),
    )

    result = inspect_document_intake(source, expected_format="docx")

    _assert_blocked(result, "external_link_detected")
