# SPDX-License-Identifier: Apache-2.0
"""Known-only passive adapters for non-promoted public-document families."""

from __future__ import annotations

import json
import tarfile
import zipfile
from pathlib import Path

import yaml

from ummaya.tools.documents.adapter_registry import build_default_document_adapter_registry
from ummaya.tools.documents.formats.code_file import PythonSourceDocumentAdapter
from ummaya.tools.documents.formats.data_file import (
    DataFileDocumentAdapter as PromotedDataFileDocumentAdapter,
)
from ummaya.tools.documents.formats.odf import OdfdoDocumentAdapter
from ummaya.tools.documents.formats.passive import (
    ArchiveDocumentSetAdapter,
    CodeFileDocumentAdapter,
    GeospatialDocumentAdapter,
    ImageScanDocumentAdapter,
    LegacyOfficeDocumentAdapter,
    MediaAssetDocumentAdapter,
    OdfDocumentAdapter,
    TextWebExportAdapter,
)
from ummaya.tools.documents.formats.passive import (
    DataFileDocumentAdapter as PassiveDataFileDocumentAdapter,
)
from ummaya.tools.documents.formats.text_web import TextWebDocumentAdapter
from ummaya.tools.documents.intake import inspect_document_intake
from ummaya.tools.documents.models import (
    BlockedReason,
    DocumentFormat,
    DocumentFormatFamily,
    KnownDocumentFormat,
    ToolResultStatus,
)
from ummaya.tools.documents.registry import DocumentToolRuntime
from ummaya.tools.documents.tool_defs import (
    DocumentFieldPatch,
    DocumentLocator,
    DocumentPrimitiveRequest,
)


def test_default_registry_exposes_known_only_passive_family_adapters() -> None:
    registry = build_default_document_adapter_registry()

    assert isinstance(registry.require_known(KnownDocumentFormat.odt), OdfdoDocumentAdapter)
    assert isinstance(registry.require_known(KnownDocumentFormat.ods), OdfdoDocumentAdapter)
    assert isinstance(registry.require_known(KnownDocumentFormat.odp), OdfdoDocumentAdapter)
    assert isinstance(registry.require_known(KnownDocumentFormat.html), TextWebDocumentAdapter)
    assert isinstance(registry.require_known(KnownDocumentFormat.htm), TextWebDocumentAdapter)
    assert isinstance(registry.require_known(KnownDocumentFormat.txt), TextWebDocumentAdapter)
    assert isinstance(registry.require_known(KnownDocumentFormat.rtf), TextWebDocumentAdapter)
    assert isinstance(registry.require_known(KnownDocumentFormat.md), TextWebDocumentAdapter)
    assert isinstance(registry.require_known(KnownDocumentFormat.doc), LegacyOfficeDocumentAdapter)
    assert isinstance(
        registry.require_known(KnownDocumentFormat.csv), PromotedDataFileDocumentAdapter
    )
    assert isinstance(
        registry.require_known(KnownDocumentFormat.ttl), PromotedDataFileDocumentAdapter
    )
    assert isinstance(
        registry.require_known(KnownDocumentFormat.geojson), PromotedDataFileDocumentAdapter
    )
    assert isinstance(
        registry.require_known(KnownDocumentFormat.python), PythonSourceDocumentAdapter
    )
    assert isinstance(registry.require_known(KnownDocumentFormat.png), ImageScanDocumentAdapter)
    assert isinstance(registry.require_known(KnownDocumentFormat.gif), ImageScanDocumentAdapter)
    assert isinstance(registry.require_known(KnownDocumentFormat.shp), GeospatialDocumentAdapter)
    assert isinstance(registry.require_known(KnownDocumentFormat.mp4), MediaAssetDocumentAdapter)
    assert registry.require_known(KnownDocumentFormat.zip).promoted_formats == (DocumentFormat.zip,)
    assert registry.require_known(KnownDocumentFormat.seven_z).promoted_formats == (
        DocumentFormat.seven_z,
    )
    assert registry.require_known(KnownDocumentFormat.epub).promoted_formats == (
        DocumentFormat.epub,
    )

    assert registry.require_known(KnownDocumentFormat.odt).promoted_formats == (
        DocumentFormat.odt,
        DocumentFormat.ods,
        DocumentFormat.odp,
    )
    assert registry.require_known(KnownDocumentFormat.html).promoted_formats == (
        DocumentFormat.html,
        DocumentFormat.htm,
        DocumentFormat.txt,
        DocumentFormat.rtf,
        DocumentFormat.md,
    )
    assert registry.require_known(KnownDocumentFormat.doc).promoted_formats == ()
    assert DocumentFormat.csv in registry.require_known(KnownDocumentFormat.csv).promoted_formats
    assert DocumentFormat.ttl in registry.require_known(KnownDocumentFormat.ttl).promoted_formats
    assert registry.require_known(KnownDocumentFormat.python).promoted_formats == (
        DocumentFormat.python,
    )
    assert registry.require_known(KnownDocumentFormat.shp).promoted_formats == ()
    assert registry.require_known(KnownDocumentFormat.mp4).promoted_formats == ()
    assert registry.require_known(KnownDocumentFormat.png).promoted_formats == ()
    assert registry.require_known(KnownDocumentFormat.tar).promoted_formats == (DocumentFormat.tar,)
    assert registry.require_known(KnownDocumentFormat.gz).promoted_formats == (DocumentFormat.gz,)


def test_data_adapter_extracts_csv_and_records_serializer_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "public-data.csv"
    path.write_text("기관,값\n행안부,공공문서\n", encoding="utf-8")
    adapter = PassiveDataFileDocumentAdapter()

    extraction = adapter.inspect(path, artifact_id="csv-artifact")

    assert extraction.tables[0].cells[0].text == "기관"
    assert extraction.tables[0].cells[3].text == "공공문서"
    assert extraction.metadata["known_format"] == "csv"
    assert extraction.metadata["round_trip_passed"] is True
    assert extraction.metadata["serializer"] == "csv"


def test_data_adapter_extracts_json_jsonl_yaml_and_xml_roundtrips(tmp_path: Path) -> None:
    fixtures = {
        "data.json": json.dumps({"기관": "행안부", "값": 3}, ensure_ascii=False),
        "data.geojson": json.dumps(
            {"type": "FeatureCollection", "features": []}, ensure_ascii=False
        ),
        "data.jsonl": "\n".join(
            [
                json.dumps({"row": 1, "value": "행안부"}, ensure_ascii=False),
                json.dumps({"row": 2, "value": "공공문서"}, ensure_ascii=False),
            ]
        )
        + "\n",
        "data.yaml": yaml.safe_dump({"기관": "행안부", "값": 3}, allow_unicode=True),
        "data.xml": "<root><agency>MOIS</agency><value>public</value></root>",
        "data.gpx": "<gpx><trk><name>trail</name></trk></gpx>",
    }
    adapter = PassiveDataFileDocumentAdapter()

    for filename, payload in fixtures.items():
        path = tmp_path / filename
        path.write_text(payload, encoding="utf-8")

        extraction = adapter.inspect(path, artifact_id=filename)

        assert extraction.metadata["round_trip_passed"] is True
        assert extraction.metadata["known_format"] == path.suffix.removeprefix(".")
        assert extraction.paragraphs


def test_data_adapter_extracts_public_data_text_family_without_mutation(tmp_path: Path) -> None:
    fixtures = {
        "graph.ttl": "@prefix ex: <https://example.test/> .\nex:a ex:b ex:c .\n",
        "culture.lod": '<https://example.test/a> <https://example.test/b> "c" .\n',
        "sequence.fasta": ">NIBR\nACTGACTG\n",
        "schema.dtd": "<!ELEMENT root (child*)>\n",
    }
    adapter = PassiveDataFileDocumentAdapter()

    for filename, payload in fixtures.items():
        path = tmp_path / filename
        path.write_text(payload, encoding="utf-8")
        original = path.read_bytes()

        extraction = adapter.inspect(path, artifact_id=filename)

        assert extraction.metadata["known_format"] == path.suffix.removeprefix(".")
        assert extraction.metadata["mutation_policy"] == "read_only_data_file"
        assert extraction.paragraphs
        assert path.read_bytes() == original


def test_metadata_only_adapters_classify_legacy_geospatial_and_media_assets(
    tmp_path: Path,
) -> None:
    fixtures = (
        (LegacyOfficeDocumentAdapter(), "legacy.doc", b"\xd0\xcf\x11\xe0legacy", "doc"),
        (GeospatialDocumentAdapter(), "boundary.shp", b"\x00" * 16, "shp"),
        (
            GeospatialDocumentAdapter(),
            "model.stl",
            b"solid public\nendsolid public\n",
            "stl",
        ),
        (MediaAssetDocumentAdapter(), "audio.mp3", b"ID3\x04\x00\x00", "mp3"),
    )

    for adapter, filename, payload, expected_format in fixtures:
        path = tmp_path / filename
        path.write_bytes(payload)
        original = path.read_bytes()

        extraction = adapter.inspect(path, artifact_id=filename)

        assert extraction.metadata["known_format"] == expected_format
        assert "metadata" in str(extraction.metadata["mutation_policy"]) or (
            extraction.metadata["mutation_policy"] == "conversion_required_legacy_office"
        )
        assert extraction.warnings
        assert path.read_bytes() == original


def test_code_adapter_extracts_context_but_never_promotes_document_mutation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "script.py"
    path.write_text("print('공공데이터')\n", encoding="utf-8")
    adapter = CodeFileDocumentAdapter()

    extraction = adapter.inspect(path, artifact_id="code-artifact")

    assert extraction.paragraphs[0].text == "print('공공데이터')"
    assert extraction.metadata["known_format"] == "py"
    assert extraction.metadata["mutation_policy"] == "read_only_code_file"


def test_text_web_export_adapter_extracts_text_without_mutation(tmp_path: Path) -> None:
    path = tmp_path / "notice.html"
    path.write_text(
        "<html><body><h1>공고문</h1><p>제출 서류 안내</p></body></html>", encoding="utf-8"
    )
    original = path.read_bytes()
    adapter = TextWebExportAdapter()

    extraction = adapter.inspect(path, artifact_id="html-artifact")

    assert [paragraph.text for paragraph in extraction.paragraphs] == ["공고문", "제출 서류 안내"]
    assert extraction.metadata["mutation_policy"] == "read_only_text_export"
    assert path.read_bytes() == original
    assert not hasattr(adapter, "apply_patch")


def test_image_scan_adapter_extracts_reference_and_never_mutates_original(tmp_path: Path) -> None:
    path = tmp_path / "scan.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    original = path.read_bytes()
    adapter = ImageScanDocumentAdapter()

    extraction = adapter.inspect(path, artifact_id="scan-artifact")

    assert extraction.images[0].content_type == "image/png"
    assert extraction.metadata["mutation_policy"] == "extraction_only"
    assert path.read_bytes() == original
    assert not hasattr(adapter, "apply_patch")


def test_document_primitive_saves_image_attachment_as_markdown_derivative(
    tmp_path: Path,
) -> None:
    source = tmp_path / "scan.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    original = source.read_bytes()
    destination = tmp_path / "scan-context.md"
    runtime = DocumentToolRuntime(session_id="image-attachment-derivative", artifact_root=tmp_path)

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="image-attachment-derivative",
            document=DocumentLocator(path=str(source)),
            operation="save",
            instruction=(
                "이 이미지 첨부 파일의 내용을 문서 작업 근거로 파악하고 "
                "제출 검토용 설명 문서로 저장해."
            ),
            destination_path=str(destination),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert destination.is_file()
    payload = destination.read_text(encoding="utf-8")
    assert "Attachment Context Derivative" in payload
    assert "scan.png" in payload
    assert "known_format: png" in payload
    assert "OCR text: not available" in payload
    assert result.render_artifacts
    assert result.render_artifacts[0].render_mime_type == "image/svg+xml"
    assert result.saved_exports
    assert result.saved_exports[0].local_path == destination.resolve()
    assert source.read_bytes() == original


def test_document_primitive_saves_non_document_attachment_context_families(
    tmp_path: Path,
) -> None:
    fixtures = (
        ("boundary.prj", b'GEOGCS["WGS 84"]\n', "known_format: prj"),
        ("recording.mp3", b"ID3\x04\x00\x00", "known_format: mp3"),
    )

    for filename, payload, expected_marker in fixtures:
        source = tmp_path / filename
        source.write_bytes(payload)
        original = source.read_bytes()
        destination = tmp_path / f"{source.stem}-context.md"
        runtime = DocumentToolRuntime(
            session_id=f"attachment-{source.suffix.removeprefix('.')}",
            artifact_root=tmp_path,
        )

        result = runtime.document(
            DocumentPrimitiveRequest(
                correlation_id=f"attachment-{source.suffix.removeprefix('.')}",
                document=DocumentLocator(path=str(source)),
                operation="save",
                instruction="첨부 파일의 내용을 파악하고 제출 검토용 설명 문서로 저장해.",
                destination_path=str(destination),
            )
        )

        assert result.status is ToolResultStatus.ok
        assert destination.is_file()
        assert expected_marker in destination.read_text(encoding="utf-8")
        assert result.render_artifacts
        assert result.saved_exports
        assert source.read_bytes() == original


def test_archive_adapter_enumerates_children_without_in_place_mutation(tmp_path: Path) -> None:
    path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("forms/application.csv", "name,value\n")
    original = path.read_bytes()
    adapter = ArchiveDocumentSetAdapter()

    extraction = adapter.inspect(path, artifact_id="archive-artifact")

    assert extraction.paragraphs[0].text == "forms/application.csv"
    assert extraction.metadata["child_mutation_policy"] == "route_children_as_derivatives"
    assert path.read_bytes() == original
    assert not hasattr(adapter, "apply_patch")


def test_archive_adapter_supports_tar_listing_without_child_mutation(tmp_path: Path) -> None:
    payload = tmp_path / "application.txt"
    payload.write_text("form", encoding="utf-8")
    path = tmp_path / "bundle.tar"
    with tarfile.open(path, "w") as archive:
        archive.add(payload, arcname="application.txt")
    adapter = ArchiveDocumentSetAdapter()

    extraction = adapter.inspect(path, artifact_id="tar-artifact")

    assert extraction.paragraphs[0].text == "application.txt"
    assert extraction.metadata["known_format"] == "tar"
    assert extraction.metadata["child_mutation_policy"] == "route_children_as_derivatives"


def test_odf_adapter_extracts_content_xml_text_as_read_only_candidate(tmp_path: Path) -> None:
    path = tmp_path / "form.odt"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        archive.writestr(
            "content.xml",
            (
                '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:'
                'xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:'
                'xmlns:text:1.0"><office:body><office:text><text:p>공공 양식</text:p>'
                "</office:text></office:body></office:document-content>"
            ),
        )
    adapter = OdfDocumentAdapter()

    extraction = adapter.inspect(path, artifact_id="odf-artifact")

    assert extraction.paragraphs[0].text == "공공 양식"
    assert extraction.metadata["known_format"] == "odt"
    assert extraction.metadata["mutation_policy"] == "read_only_odf_candidate"


def test_known_passive_families_classify_and_block_runtime_write(tmp_path: Path) -> None:
    fixtures = {
        "scan.png": (b"\x89PNG\r\n\x1a\n" + b"\x00" * 8, DocumentFormatFamily.image_scan),
        "scan.gif": (b"GIF89a", DocumentFormatFamily.image_scan),
        "boundary.shp": (b"\x00" * 16, DocumentFormatFamily.geospatial_data),
        "audio.mp3": (b"ID3\x04\x00\x00", DocumentFormatFamily.media_asset),
    }

    for filename, (payload, expected_family) in fixtures.items():
        path = tmp_path / filename
        path.write_bytes(payload)

        result = inspect_document_intake(path)

        assert result.status is ToolResultStatus.blocked
        assert result.blocked_reason is BlockedReason.unsupported_operation
        assert result.format_family is expected_family
        assert result.known_format is not None


def test_document_primitive_routes_attachment_known_formats_to_markdown_derivative(
    tmp_path: Path,
) -> None:
    fixtures = {
        "scan.png": _write_runtime_png_fixture,
        "scan.gif": _write_runtime_gif_fixture,
        "boundary.shp": _write_runtime_shp_fixture,
        "audio.mp3": _write_runtime_mp3_fixture,
    }

    for filename, writer in fixtures.items():
        source = writer(tmp_path / filename)
        original = source.read_bytes()
        runtime = DocumentToolRuntime(
            session_id=f"passive-{source.suffix.removeprefix('.')}",
            artifact_root=tmp_path / f"store-{source.suffix.removeprefix('.')}",
        )

        inspect_result = runtime.document(
            DocumentPrimitiveRequest(
                correlation_id=f"inspect-{source.suffix.removeprefix('.')}",
                document=DocumentLocator(path=str(source)),
                operation="inspect",
                instruction="문서 내용을 파악해.",
            )
        )

        assert inspect_result.status is ToolResultStatus.ok
        assert inspect_result.extraction is not None
        assert inspect_result.artifact_refs == []
        assert "known-only" in inspect_result.text_summary

        fill_result = runtime.document(
            DocumentPrimitiveRequest(
                correlation_id=f"fill-{source.suffix.removeprefix('.')}",
                document=DocumentLocator(path=str(source)),
                operation="fill",
                instruction="문서 내용을 파악하고 테스트 값으로 수정해.",
                patches=(DocumentFieldPatch(target_path="/unsupported/edit", value="변경값"),),
            )
        )

        assert fill_result.status is ToolResultStatus.ok
        assert fill_result.render_artifacts
        assert fill_result.saved_exports == ()
        assert "Attachment context derivative" in fill_result.text_summary
        assert any(ref.startswith("working-") for ref in fill_result.artifact_refs)
        assert source.read_bytes() == original


def _write_runtime_odf_fixture(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        archive.writestr(
            "content.xml",
            (
                '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:'
                'xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:'
                'xmlns:text:1.0"><office:body><office:text><text:p>공공 양식</text:p>'
                "</office:text></office:body></office:document-content>"
            ),
        )
    return path


def _write_runtime_csv_fixture(path: Path) -> Path:
    path.write_text("기관,값\n행안부,공공문서\n", encoding="utf-8")
    return path


def _write_runtime_ttl_fixture(path: Path) -> Path:
    path.write_text("@prefix ex: <https://example.test/> .\nex:a ex:b ex:c .\n", encoding="utf-8")
    return path


def _write_runtime_geojson_fixture(path: Path) -> Path:
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _write_runtime_html_fixture(path: Path) -> Path:
    path.write_text(
        "<html><body><h1>공고문</h1><p>제출 서류 안내</p></body></html>",
        encoding="utf-8",
    )
    return path


def _write_runtime_png_fixture(path: Path) -> Path:
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    return path


def _write_runtime_gif_fixture(path: Path) -> Path:
    path.write_bytes(b"GIF89a")
    return path


def _write_runtime_shp_fixture(path: Path) -> Path:
    path.write_bytes(b"\x00" * 16)
    return path


def _write_runtime_mp3_fixture(path: Path) -> Path:
    path.write_bytes(b"ID3\x04\x00\x00")
    return path


def _write_runtime_zip_fixture(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("forms/application.csv", "name,value\n")
    return path


def _write_runtime_epub_fixture(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("OPS/content.xhtml", "<html><body><p>공공 전자책</p></body></html>")
    return path
