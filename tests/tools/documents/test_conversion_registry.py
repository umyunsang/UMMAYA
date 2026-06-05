# SPDX-License-Identifier: Apache-2.0
"""Tests for document format conversion engine registration."""

from __future__ import annotations

import hashlib
import io
import os
import stat
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ummaya.tools.documents.conversion import (
    DocumentConversionEngineError,
    DocumentConversionRegistry,
    LocalCliDocumentConversionEngine,
    UnsupportedDocumentConversionError,
    build_default_document_conversion_registry,
)
from ummaya.tools.documents.models import (
    ArtifactLineage,
    DocumentArtifact,
    DocumentFormat,
    SecurityState,
)


class MinimalConversionEngine:
    """Minimal conversion engine test double."""

    source_format = DocumentFormat.hwp
    output_format = DocumentFormat.hwpx
    engine_id = "fake-hwp-to-hwpx"

    def convert_for_edit(self, source: DocumentArtifact) -> bytes:
        assert source.format is DocumentFormat.hwp
        return b"converted-hwpx"


def test_conversion_registry_returns_registered_engine_by_source_and_output_format() -> None:
    engine = MinimalConversionEngine()
    registry = DocumentConversionRegistry()

    registry.register(engine)

    assert registry.require(DocumentFormat.hwp, DocumentFormat.hwpx) is engine


def test_conversion_registry_rejects_duplicate_source_output_registration() -> None:
    registry = DocumentConversionRegistry()
    registry.register(MinimalConversionEngine())

    with pytest.raises(ValueError, match="already registered"):
        registry.register(MinimalConversionEngine())


def test_conversion_registry_fails_closed_for_unpromoted_conversion() -> None:
    registry = DocumentConversionRegistry()

    with pytest.raises(UnsupportedDocumentConversionError):
        registry.require(DocumentFormat.hwp, DocumentFormat.hwpx)


def test_default_conversion_registry_is_empty_without_explicit_hwp_bridge_env() -> None:
    registry = build_default_document_conversion_registry(env={})

    with pytest.raises(UnsupportedDocumentConversionError):
        registry.require(DocumentFormat.hwp, DocumentFormat.hwpx)


def test_default_conversion_registry_registers_explicit_local_hwp_bridge(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "legacy.hwp"
    source_path.write_bytes(b"legacy-hwp")
    payload = _minimal_hwpx_payload("로컬 변환")
    executable = _write_cli_converter(tmp_path / "convert.py", payload=payload)
    registry = build_default_document_conversion_registry(
        env={
            "UMMAYA_HWP_TO_HWPX_CONVERTER": str(executable),
            "UMMAYA_HWP_TO_HWPX_CONVERTER_ARGS_JSON": '["{source}", "{output}"]',
            "UMMAYA_HWP_TO_HWPX_CONVERTER_ENGINE_ID": "local-test-hwp-to-hwpx",
        }
    )

    engine = registry.require(DocumentFormat.hwp, DocumentFormat.hwpx)

    assert engine.engine_id == "local-test-hwp-to-hwpx"
    assert engine.convert_for_edit(_document_artifact(source_path)) == payload
    assert source_path.read_bytes() == b"legacy-hwp"


def test_local_cli_conversion_uses_temporary_input_copy_to_preserve_source(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "legacy.hwp"
    source_path.write_bytes(b"legacy-hwp")
    payload = _minimal_hwpx_payload("복사본 변환")
    executable = _write_cli_converter(
        tmp_path / "convert-mutating.py",
        payload=payload,
        mutate_source=True,
    )
    engine = LocalCliDocumentConversionEngine(
        source_format=DocumentFormat.hwp,
        output_format=DocumentFormat.hwpx,
        engine_id="mutating-local-cli",
        executable=executable,
        args=("{source}", "{output}"),
    )

    assert engine.convert_for_edit(_document_artifact(source_path)) == payload
    assert source_path.read_bytes() == b"legacy-hwp"


def test_default_conversion_registry_registers_discovered_hwpxjs_bridge(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "legacy.hwp"
    source_path.write_bytes(b"legacy-hwp")
    payload = _minimal_hwpx_payload("hwpxjs 변환")
    _write_cli_converter(
        tmp_path / "hwpxjs",
        payload=payload,
        expected_args=("convert:hwp",),
    )
    registry = build_default_document_conversion_registry(
        env={"PATH": str(tmp_path)},
    )

    engine = registry.require(DocumentFormat.hwp, DocumentFormat.hwpx)

    assert engine.engine_id == "hwpxjs-cli-convert-hwp"
    assert engine.convert_for_edit(_document_artifact(source_path)) == payload
    assert source_path.read_bytes() == b"legacy-hwp"


def test_default_conversion_registry_registers_discovered_libreoffice_legacy_bridge(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "legacy.doc"
    source_path.write_bytes(b"legacy-doc")
    payload = _minimal_ooxml_payload("word/document.xml")
    _write_libreoffice_converter(
        tmp_path / "libreoffice",
        output_suffix=".docx",
        payload=payload,
        expected_args=(
            "--headless",
            "--convert-to",
            "docx:MS Word 2007 XML",
            "--outdir",
        ),
    )
    registry = build_default_document_conversion_registry(env={"PATH": str(tmp_path)})

    engine = registry.require(DocumentFormat.doc, DocumentFormat.docx)

    assert engine.engine_id == "libreoffice-legacy-office-to-ooxml-bridge"
    assert (
        engine.convert_for_edit(_document_artifact(source_path, document_format=DocumentFormat.doc))
        == payload
    )
    assert source_path.read_bytes() == b"legacy-doc"


def test_default_conversion_registry_registers_discovered_textutil_doc_bridge(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "legacy.doc"
    source_path.write_bytes(b"legacy-doc")
    payload = _minimal_ooxml_payload("word/document.xml")
    _write_textutil_converter(
        tmp_path / "textutil",
        payload=payload,
        expected_args=("-convert", "docx", "-output"),
    )
    registry = build_default_document_conversion_registry(env={"PATH": str(tmp_path)})

    engine = registry.require(DocumentFormat.doc, DocumentFormat.docx)

    assert engine.engine_id == "macos-textutil-doc-to-docx-bridge"
    assert (
        engine.convert_for_edit(_document_artifact(source_path, document_format=DocumentFormat.doc))
        == payload
    )
    assert source_path.read_bytes() == b"legacy-doc"


def test_default_conversion_registry_registers_discovered_excel_xls_bridge(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "legacy.xls"
    source_path.write_bytes(b"legacy-xls")
    payload = _minimal_ooxml_payload("xl/workbook.xml")
    _write_osascript_converter(tmp_path / "osascript", payload=payload)
    excel_app = tmp_path / "Microsoft Excel.app"
    excel_app.mkdir()
    registry = build_default_document_conversion_registry(
        env={
            "PATH": str(tmp_path),
            "UMMAYA_MICROSOFT_EXCEL_APP": str(excel_app),
        }
    )

    engine = registry.require(DocumentFormat.xls, DocumentFormat.xlsx)

    assert engine.engine_id == "microsoft-excel-applescript-xls-to-xlsx-bridge"
    assert (
        engine.convert_for_edit(_document_artifact(source_path, document_format=DocumentFormat.xls))
        == payload
    )
    assert source_path.read_bytes() == b"legacy-xls"


def test_default_conversion_registry_rejects_env_bridge_without_explicit_args(
    tmp_path: Path,
) -> None:
    executable = _write_cli_converter(
        tmp_path / "convert.py",
        payload=_minimal_hwpx_payload("ignored"),
    )

    with pytest.raises(ValueError, match="ARGS_JSON"):
        build_default_document_conversion_registry(
            env={"UMMAYA_HWP_TO_HWPX_CONVERTER": str(executable)}
        )


def test_conversion_engine_contract_keeps_original_hwp_immutable(tmp_path: Path) -> None:
    source_path = tmp_path / "legacy.hwp"
    source_path.write_bytes(b"legacy-hwp")
    source = DocumentArtifact(
        artifact_id="source-hwp",
        session_id="conversion-test",
        format=DocumentFormat.hwp,
        source_path=source_path,
        display_name="legacy.hwp",
        mime_type="application/x-hwp",
        byte_size=source_path.stat().st_size,
        expanded_byte_size=source_path.stat().st_size,
        sha256="8eb2d6efea34a5c14d470dd5b737c96b882bf4328d9be32bc6e733d6db38a7de",
        created_at=datetime(2026, 6, 3, tzinfo=UTC),
        lineage=ArtifactLineage.source,
        security_state=SecurityState.accepted,
    )
    engine = MinimalConversionEngine()

    converted = engine.convert_for_edit(source)

    assert converted == b"converted-hwpx"
    assert source_path.read_bytes() == b"legacy-hwp"


def test_local_cli_conversion_engine_requires_pinned_absolute_executable(tmp_path: Path) -> None:
    executable = tmp_path / "missing-converter"

    with pytest.raises(ValueError, match="absolute"):
        LocalCliDocumentConversionEngine(
            source_format=DocumentFormat.hwp,
            output_format=DocumentFormat.hwpx,
            engine_id="relative-cli",
            executable=Path("relative-converter"),
            args=("{source}", "{output}"),
        )
    with pytest.raises(ValueError, match="does not exist"):
        LocalCliDocumentConversionEngine(
            source_format=DocumentFormat.hwp,
            output_format=DocumentFormat.hwpx,
            engine_id="missing-cli",
            executable=executable,
            args=("{source}", "{output}"),
        )


def test_local_cli_conversion_engine_runs_cli_and_preserves_hwp_source(tmp_path: Path) -> None:
    source_path = tmp_path / "legacy.hwp"
    source_path.write_bytes(b"legacy-hwp")
    payload = _minimal_hwpx_payload("홍길동")
    executable = _write_cli_converter(tmp_path / "convert.py", payload=payload)
    source = _document_artifact(source_path)
    engine = LocalCliDocumentConversionEngine(
        source_format=DocumentFormat.hwp,
        output_format=DocumentFormat.hwpx,
        engine_id="local-hwpforge-dry-run",
        executable=executable,
        args=("{source}", "{output}"),
    )

    converted = engine.convert_for_edit(source)

    assert converted == payload
    assert source_path.read_bytes() == b"legacy-hwp"


def test_local_cli_conversion_engine_fails_closed_for_invalid_hwpx_output(tmp_path: Path) -> None:
    source_path = tmp_path / "legacy.hwp"
    source_path.write_bytes(b"legacy-hwp")
    executable = _write_cli_converter(tmp_path / "convert.py", payload=b"not-a-hwpx-package")
    engine = LocalCliDocumentConversionEngine(
        source_format=DocumentFormat.hwp,
        output_format=DocumentFormat.hwpx,
        engine_id="invalid-output-cli",
        executable=executable,
        args=("{source}", "{output}"),
    )

    with pytest.raises(DocumentConversionEngineError, match="valid HWPX package"):
        engine.convert_for_edit(_document_artifact(source_path))


def test_local_cli_conversion_engine_isolates_source_mutation_to_temp_copy(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "legacy.hwp"
    source_path.write_bytes(b"legacy-hwp")
    payload = _minimal_hwpx_payload("변환")
    executable = _write_cli_converter(
        tmp_path / "convert.py",
        payload=payload,
        mutate_source=True,
    )
    engine = LocalCliDocumentConversionEngine(
        source_format=DocumentFormat.hwp,
        output_format=DocumentFormat.hwpx,
        engine_id="mutating-cli",
        executable=executable,
        args=("{source}", "{output}"),
    )

    assert engine.convert_for_edit(_document_artifact(source_path)) == payload
    assert source_path.read_bytes() == b"legacy-hwp"


def _document_artifact(
    path: Path,
    *,
    document_format: DocumentFormat = DocumentFormat.hwp,
) -> DocumentArtifact:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return DocumentArtifact(
        artifact_id="source-hwp",
        session_id="conversion-test",
        format=document_format,
        source_path=path,
        display_name=path.name,
        mime_type="application/octet-stream",
        byte_size=path.stat().st_size,
        expanded_byte_size=path.stat().st_size,
        sha256=digest,
        created_at=datetime(2026, 6, 3, tzinfo=UTC),
        lineage=ArtifactLineage.source,
        security_state=SecurityState.accepted,
    )


def _minimal_hwpx_payload(text: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/owpml")
        archive.writestr("Contents/header.xml", "<header />")
        archive.writestr(
            "Contents/section0.xml",
            (
                "<?xml version='1.0' encoding='UTF-8'?>"
                "<section xmlns:hp='http://www.hancom.co.kr/hwpml/2011/paragraph'>"
                f"<hp:t>{text}</hp:t>"
                "</section>"
            ),
        )
    return output.getvalue()


def _minimal_ooxml_payload(marker: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr(marker, "<xml/>")
    return output.getvalue()


def _write_cli_converter(
    executable: Path,
    *,
    payload: bytes,
    mutate_source: bool = False,
    expected_args: tuple[str, ...] = (),
) -> Path:
    payload_path = executable.with_suffix(".payload")
    payload_path.write_bytes(payload)
    mutation = "source.write_bytes(source.read_bytes() + b'-mutated')" if mutate_source else "pass"
    executable.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from pathlib import Path",
                "import sys",
                f"expected = {expected_args!r}",
                "if expected:",
                "    assert tuple(sys.argv[1:1 + len(expected)]) == expected",
                "source = Path(sys.argv[-2])",
                "output = Path(sys.argv[-1])",
                f"{mutation}",
                f"output.write_bytes(Path({str(payload_path)!r}).read_bytes())",
                "",
            ]
        ),
        encoding="utf-8",
    )
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    assert os.access(executable, os.X_OK)
    return executable


def _write_libreoffice_converter(
    executable: Path,
    *,
    output_suffix: str,
    payload: bytes,
    expected_args: tuple[str, ...],
) -> Path:
    payload_path = executable.with_suffix(".payload")
    payload_path.write_bytes(payload)
    executable.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from pathlib import Path",
                "import sys",
                f"expected = {expected_args!r}",
                "assert tuple(sys.argv[1:1 + len(expected)]) == expected",
                "outdir = Path(sys.argv[1 + len(expected)])",
                "source = Path(sys.argv[-1])",
                f"target = outdir / (source.stem + {output_suffix!r})",
                f"target.write_bytes(Path({str(payload_path)!r}).read_bytes())",
                "",
            ]
        ),
        encoding="utf-8",
    )
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    assert os.access(executable, os.X_OK)
    return executable


def _write_textutil_converter(
    executable: Path,
    *,
    payload: bytes,
    expected_args: tuple[str, ...],
) -> Path:
    payload_path = executable.with_suffix(".payload")
    payload_path.write_bytes(payload)
    executable.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from pathlib import Path",
                "import sys",
                f"expected = {expected_args!r}",
                "assert tuple(sys.argv[1:1 + len(expected)]) == expected",
                "output = Path(sys.argv[1 + len(expected)])",
                "source = Path(sys.argv[-1])",
                "assert source.suffix == '.doc'",
                f"output.write_bytes(Path({str(payload_path)!r}).read_bytes())",
                "",
            ]
        ),
        encoding="utf-8",
    )
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    assert os.access(executable, os.X_OK)
    return executable


def _write_osascript_converter(executable: Path, *, payload: bytes) -> Path:
    payload_path = executable.with_suffix(".payload")
    payload_path.write_bytes(payload)
    executable.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from pathlib import Path",
                "import sys",
                "source = Path(sys.argv[-2])",
                "output = Path(sys.argv[-1])",
                "assert source.suffix == '.xls'",
                "assert output.suffix == '.xlsx'",
                "assert 'Microsoft Excel' in ' '.join(sys.argv)",
                f"output.write_bytes(Path({str(payload_path)!r}).read_bytes())",
                "",
            ]
        ),
        encoding="utf-8",
    )
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    assert os.access(executable, os.X_OK)
    return executable
