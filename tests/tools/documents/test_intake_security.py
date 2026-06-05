from __future__ import annotations

import gzip
import io
import shutil
import struct
import subprocess
import tarfile
import zipfile
from collections.abc import Mapping
from pathlib import Path

import pytest

from ummaya.tools.documents.intake import (
    DEFAULT_INTAKE_POLICY,
    inspect_document_intake,
)
from ummaya.tools.documents.models import PROMOTED_RUNTIME_DOCUMENT_FORMATS, KnownDocumentFormat

_ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)


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
            info = zipfile.ZipInfo(name, _ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            package.writestr(info, payload)
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


def _hwpx_bytes() -> bytes:
    return _zip_bytes(
        {
            "Contents/section0.xml": b"<section/>",
            "version.xml": b"<version/>",
        }
    )


def _owpml_hwp_bytes() -> bytes:
    return _zip_bytes(
        {
            "mimetype": b"application/owpml",
            "Contents/section0.xml": b"<section/>",
            "Contents/header.xml": b"<header/>",
            "version.xml": b"<version/>",
            "META-INF/manifest.xml": b"<manifest/>",
        }
    )


def _xlsx_bytes() -> bytes:
    return _zip_bytes({"xl/workbook.xml": b"<workbook/>"})


def _pptx_bytes() -> bytes:
    return _zip_bytes({"ppt/presentation.xml": b"<presentation/>"})


def _odf_bytes(mime_type: str) -> bytes:
    return _zip_bytes(
        {
            "mimetype": mime_type.encode("ascii"),
            "META-INF/manifest.xml": b"<manifest:manifest/>",
            "content.xml": b"<office:document-content/>",
        }
    )


def _epub_bytes() -> bytes:
    return _zip_bytes(
        {
            "mimetype": b"application/epub+zip",
            "OPS/content.xhtml": b"<html><body><p>public</p></body></html>",
        }
    )


def _tar_bytes() -> bytes:
    buffer = io.BytesIO()
    payload = b"public"
    info = tarfile.TarInfo("forms/application.txt")
    info.size = len(payload)
    with tarfile.open(fileobj=buffer, mode="w") as package:
        package.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def _gzip_bytes() -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as package:
        package.write(b"public")
    return buffer.getvalue()


def _seven_z_bytes(tmp_path: Path) -> bytes:
    executable = shutil.which("bsdtar")
    if executable is None:
        return b"7z\xbc\xaf\x27\x1c\x00\x04\x00\x00\x00\x00\x00\x00"
    source_root = tmp_path / "seven-z-src"
    member = source_root / "forms" / "application.txt"
    member.parent.mkdir(parents=True, exist_ok=True)
    member.write_text("public", encoding="utf-8")
    output = tmp_path / "bundle-source.7z"
    subprocess.run(  # noqa: S603 - test-only static argv.
        [
            executable,
            "-cf",
            str(output),
            "--format=7zip",
            "-C",
            str(source_root),
            "forms/application.txt",
        ],
        check=True,
        timeout=15,
    )
    return output.read_bytes()


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


@pytest.mark.parametrize(
    ("filename", "payload", "expected_format", "format_family"),
    (
        ("form.hwpx", _hwpx_bytes(), "hwpx", "hwp"),
        ("legacy.hwp", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"hwp", "hwp", "hwp"),
        ("form.owpml", _hwpx_bytes(), "owpml", "hwp"),
        ("form.docx", _docx_bytes(), "docx", "ooxml"),
        ("sheet.xlsx", _xlsx_bytes(), "xlsx", "ooxml"),
        ("deck.pptx", _pptx_bytes(), "pptx", "ooxml"),
        ("form.pdf", b"%PDF-1.7\n%%EOF\n", "pdf", "pdf"),
        (
            "form.odt",
            _odf_bytes("application/vnd.oasis.opendocument.text"),
            "odt",
            "odf",
        ),
        (
            "sheet.ods",
            _odf_bytes("application/vnd.oasis.opendocument.spreadsheet"),
            "ods",
            "odf",
        ),
        (
            "deck.odp",
            _odf_bytes("application/vnd.oasis.opendocument.presentation"),
            "odp",
            "odf",
        ),
        ("notice.html", b"<html><body><p>notice</p></body></html>", "html", "text_web_export"),
        ("notice.htm", b"<html><body><p>notice</p></body></html>", "htm", "text_web_export"),
        ("notice.txt", b"notice\n", "txt", "text_web_export"),
        ("notice.md", b"# notice\n", "md", "text_web_export"),
        ("notice.rtf", b"{\\rtf1\\ansi notice}", "rtf", "text_web_export"),
        ("ebook.epub", _epub_bytes(), "epub", "archive"),
        ("data.csv", b"name,value\nagency,MOIS\n", "csv", "data_file"),
        ("data.tsv", b"name\tvalue\nagency\tMOIS\n", "tsv", "data_file"),
        ("data.json", b'{"agency":"MOIS"}\n', "json", "data_file"),
        ("data.jsonl", b'{"agency":"MOIS"}\n', "jsonl", "data_file"),
        ("data.yaml", b"agency: MOIS\n", "yaml", "data_file"),
        ("data.yml", b"agency: MOIS\n", "yml", "data_file"),
        ("data.xml", b"<root><agency>MOIS</agency></root>", "xml", "data_file"),
        ("graph.rdf", b"<rdf><agency>MOIS</agency></rdf>", "rdf", "data_file"),
        ("graph.ttl", b"@prefix ex: <https://example.test/> .\n", "ttl", "data_file"),
        ("graph.lod", b'<s> <p> "o" .\n', "lod", "data_file"),
        ("map.geojson", b'{"type":"FeatureCollection","features":[]}', "geojson", "data_file"),
        ("route.gpx", b"<gpx><trk><name>trail</name></trk></gpx>", "gpx", "data_file"),
        ("route.kml", b"<kml><name>trail</name></kml>", "kml", "data_file"),
        ("sequence.fasta", b">NIBR\nACTG\n", "fasta", "data_file"),
        ("schema.sgml", b"<doc><p>public</p></doc>\n", "sgml", "data_file"),
        ("schema.dtd", b"<!ELEMENT week (#PCDATA)>\n", "dtd", "data_file"),
        ("script.py", b"def main():\n    return 'public data'\n", "py", "code_file"),
        ("legacy.hml", b"<hml><p>public</p></hml>", "hml", "data_file"),
        ("bundle.zip", _zip_bytes({"forms/application.txt": b"public"}), "zip", "archive"),
        ("bundle.7z", None, "7z", "archive"),
        ("bundle.tar", _tar_bytes(), "tar", "archive"),
        ("bundle.gz", _gzip_bytes(), "gz", "archive"),
        ("payload.etc", b"key=value\n", "etc", "data_file"),
    ),
)
def test_promoted_runtime_formats_emit_known_format_and_family_metadata(
    tmp_path: Path,
    filename: str,
    payload: bytes,
    expected_format: str,
    format_family: str,
) -> None:
    source_payload = _seven_z_bytes(tmp_path) if payload is None else payload
    source = _write(tmp_path / filename, source_payload)

    result = inspect_document_intake(source, expected_format=expected_format)

    assert _value(result.status) == "ok"
    assert _value(result.detected_format) == expected_format
    assert _value(result.known_format) == expected_format
    assert _value(result.format_family) == format_family


def test_pdfa_extension_is_accepted_as_pdf_runtime_with_pdfa_lineage(
    tmp_path: Path,
) -> None:
    source = _write(tmp_path / "archive-form.pdfa", b"%PDF-1.7\n%%EOF\n")

    result = inspect_document_intake(
        source,
        expected_format="pdfa",
        declared_mime_type="application/pdf",
    )

    assert _value(result.status) == "ok"
    assert _value(result.detected_format) == "pdf"
    assert _value(result.known_format) == "pdfa"
    assert _value(result.format_family) == "pdf"
    assert result.mime_type == "application/pdf"


def test_blocks_unsupported_extension_before_content_parsing(tmp_path: Path) -> None:
    source = _write(tmp_path / "payload.exe", b"MZ")

    result = inspect_document_intake(source, declared_mime_type="application/octet-stream")

    _assert_blocked(result, "unsupported_format")


@pytest.mark.parametrize(
    ("filename", "payload", "known_format", "format_family"),
    (
        ("scan.png", b"\x89PNG\r\n\x1a\n", "png", "image_scan"),
        ("scan.gif", b"GIF89a", "gif", "image_scan"),
        ("boundary.shp", b"\x00" * 16, "shp", "geospatial_data"),
        ("model.stl", b"solid public\nendsolid public\n", "stl", "geospatial_data"),
        ("audio.mp3", b"ID3\x04\x00\x00", "mp3", "media_asset"),
        ("legacy.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1legacy-doc", "doc", "legacy_office"),
        ("legacy.xls", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1legacy-xls", "xls", "legacy_office"),
        ("legacy.ppt", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1legacy-ppt", "ppt", "legacy_office"),
    ),
)
def test_known_but_unpromoted_formats_fail_closed_with_family_and_next_actions(
    tmp_path: Path,
    filename: str,
    payload: bytes,
    known_format: str,
    format_family: str,
) -> None:
    source = _write(tmp_path / filename, payload)

    result = inspect_document_intake(source)

    _assert_blocked(result, "unsupported_operation")
    assert _value(result.detected_format) is None
    assert _value(result.known_format) == known_format
    assert _value(result.format_family) == format_family
    assert result.next_safe_actions


@pytest.mark.parametrize(
    "known_format",
    tuple(
        known_format
        for known_format in KnownDocumentFormat
        if known_format.value
        not in {
            *(document_format.value for document_format in PROMOTED_RUNTIME_DOCUMENT_FORMATS),
            "pdfa",
        }
    ),
)
def test_all_known_unpromoted_extensions_are_classified_before_runtime_parse(
    tmp_path: Path,
    known_format: KnownDocumentFormat,
) -> None:
    source = _write(tmp_path / f"sample.{known_format.value}", b"placeholder")

    result = inspect_document_intake(source)

    _assert_blocked(result, "unsupported_operation")
    assert _value(result.known_format) == known_format.value
    assert result.format_family is not None
    assert result.next_safe_actions


def test_policy_denied_known_format_preserves_classification_metadata(tmp_path: Path) -> None:
    source = _write(tmp_path / "form.odt", b"placeholder")
    policy = _policy_with(allowed_formats=frozenset({"docx"}))

    result = inspect_document_intake(source, policy=policy)

    _assert_blocked(result, "unsupported_format")
    assert _value(result.known_format) == "odt"
    assert _value(result.format_family) == "odf"


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
    assert _value(result.known_format) == "docx"
    assert _value(result.format_family) == "ooxml"


def test_accepts_official_hwp_extension_when_payload_is_hwpx_package(
    tmp_path: Path,
) -> None:
    source = _write(tmp_path / "official-form.hwp", _owpml_hwp_bytes())

    result = inspect_document_intake(source, expected_format="hwp")

    assert _value(result.status) == "ok"
    assert _value(result.known_format) == "hwp"
    assert _value(result.detected_format) == "hwpx"
    assert _value(result.format_family) == "hwp"
    assert result.blocked_reason is None


def test_accepts_hwp_mime_when_hwp_extension_wraps_hwpx_package(
    tmp_path: Path,
) -> None:
    source = _write(tmp_path / "official-form.hwp", _owpml_hwp_bytes())

    result = inspect_document_intake(
        source,
        expected_format="hwp",
        declared_mime_type="application/x-hwp",
    )

    assert _value(result.status) == "ok"
    assert _value(result.known_format) == "hwp"
    assert _value(result.detected_format) == "hwpx"
    assert result.blocked_reason is None


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
