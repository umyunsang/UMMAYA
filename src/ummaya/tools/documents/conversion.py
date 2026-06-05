# SPDX-License-Identifier: Apache-2.0
"""Format conversion engine registry for document editable derivatives."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from shutil import which
from typing import Protocol

from ummaya.tools.documents.models import DocumentArtifact, DocumentFormat

_HWP_TO_HWPX_CONVERTER_ENV = "UMMAYA_HWP_TO_HWPX_CONVERTER"
_HWP_TO_HWPX_CONVERTER_ARGS_ENV = "UMMAYA_HWP_TO_HWPX_CONVERTER_ARGS_JSON"
_HWP_TO_HWPX_CONVERTER_ENGINE_ID_ENV = "UMMAYA_HWP_TO_HWPX_CONVERTER_ENGINE_ID"
_HWP_TO_HWPX_CONVERTER_TIMEOUT_ENV = "UMMAYA_HWP_TO_HWPX_CONVERTER_TIMEOUT_SECONDS"
_HWPXJS_ENGINE_ID = "hwpxjs-cli-convert-hwp"
_HWPXJS_HWP_TO_HWPX_ARGS = ("convert:hwp", "{source}", "{output}")
_HWP_CONVERTER_DEFAULT_TIMEOUT_SECONDS = 120
_LEGACY_OFFICE_ENGINE_ID = "libreoffice-legacy-office-to-ooxml-bridge"
_TEXTUTIL_DOC_ENGINE_ID = "macos-textutil-doc-to-docx-bridge"
_MICROSOFT_EXCEL_APP_ENV = "UMMAYA_MICROSOFT_EXCEL_APP"
_MICROSOFT_EXCEL_ENGINE_ID = "microsoft-excel-applescript-xls-to-xlsx-bridge"
_LEGACY_OFFICE_TIMEOUT_SECONDS = 120
_TEXTUTIL_TIMEOUT_SECONDS = 60
_MICROSOFT_EXCEL_TIMEOUT_SECONDS = 120
_LEGACY_OFFICE_CONVERSIONS: tuple[
    tuple[DocumentFormat, DocumentFormat, tuple[str, ...]],
    ...,
] = (
    (
        DocumentFormat.doc,
        DocumentFormat.docx,
        (
            "--headless",
            "--convert-to",
            "docx:MS Word 2007 XML",
            "--outdir",
            "{outdir}",
            "{source}",
        ),
    ),
    (
        DocumentFormat.xls,
        DocumentFormat.xlsx,
        (
            "--headless",
            "--convert-to",
            "xlsx:Calc MS Excel 2007 XML",
            "--outdir",
            "{outdir}",
            "{source}",
        ),
    ),
    (
        DocumentFormat.ppt,
        DocumentFormat.pptx,
        (
            "--headless",
            "--convert-to",
            "pptx:Impress MS PowerPoint 2007 XML",
            "--outdir",
            "{outdir}",
            "{source}",
        ),
    ),
)
_TEXTUTIL_DOC_TO_DOCX_ARGS = ("-convert", "docx", "-output", "{output}", "{source}")
_MICROSOFT_EXCEL_XLS_TO_XLSX_ARGS = (
    "-e",
    "on run argv",
    "-e",
    "set sourcePath to POSIX file (item 1 of argv)",
    "-e",
    "set outputPath to POSIX file (item 2 of argv)",
    "-e",
    'tell application "Microsoft Excel"',
    "-e",
    "set display alerts to false",
    "-e",
    "open workbook workbook file name sourcePath",
    "-e",
    "save workbook as active workbook filename outputPath file format workbook default",
    "-e",
    "close active workbook saving no",
    "-e",
    "end tell",
    "-e",
    "end run",
    "{source}",
    "{output}",
)


class DocumentConversionEngine(Protocol):
    """Promoted engine that converts one source format into one output format."""

    source_format: DocumentFormat
    output_format: DocumentFormat
    engine_id: str

    def convert_for_edit(self, source: DocumentArtifact) -> bytes:
        """Return editable derivative bytes without mutating the source artifact."""


class UnsupportedDocumentConversionError(LookupError):
    """Raised when no promoted conversion engine is registered for a format pair."""

    def __init__(self, source_format: DocumentFormat, output_format: DocumentFormat) -> None:
        super().__init__(
            "No promoted document conversion registered for "
            f"{source_format.value} -> {output_format.value}"
        )
        self.source_format = source_format
        self.output_format = output_format


class DocumentConversionEngineError(ValueError):
    """Raised when a promoted conversion engine fails its execution contract."""


class LocalCliDocumentConversionEngine:
    """Fail-closed conversion bridge for pinned local CLI candidates."""

    def __init__(
        self,
        *,
        source_format: DocumentFormat,
        output_format: DocumentFormat,
        engine_id: str,
        executable: Path,
        args: Sequence[str],
        timeout_seconds: int = 30,
    ) -> None:
        executable_path = executable.expanduser()
        if not executable_path.is_absolute():
            raise ValueError("document conversion executable must be an absolute path")
        resolved_executable = executable_path.resolve(strict=False)
        if not resolved_executable.exists():
            raise ValueError(
                f"document conversion executable does not exist: {resolved_executable}"
            )
        if not resolved_executable.is_file():
            raise ValueError(f"document conversion executable is not a file: {resolved_executable}")
        if not os.access(resolved_executable, os.X_OK):
            raise ValueError(
                f"document conversion executable is not executable: {resolved_executable}"
            )
        if not engine_id:
            raise ValueError("document conversion engine_id is required")
        if timeout_seconds < 1 or timeout_seconds > 300:
            raise ValueError("document conversion timeout_seconds must be between 1 and 300")
        if not args:
            raise ValueError("document conversion CLI args are required")
        if not any("{source}" in arg for arg in args):
            raise ValueError("document conversion CLI args must include {source}")
        if not any("{output}" in arg for arg in args) and not any(
            "{outdir}" in arg for arg in args
        ):
            raise ValueError("document conversion CLI args must include {output} or {outdir}")

        self.source_format = source_format
        self.output_format = output_format
        self.engine_id = engine_id
        self.executable = resolved_executable
        self.args = tuple(args)
        self.timeout_seconds = timeout_seconds

    def convert_for_edit(self, source: DocumentArtifact) -> bytes:
        """Run the pinned CLI and return validated editable derivative bytes."""
        if source.format is not self.source_format:
            raise DocumentConversionEngineError(
                "document conversion source format mismatch: "
                f"expected {self.source_format.value}, got {source.format.value}"
            )
        source_path = source.source_path.expanduser().resolve()
        if not source_path.exists() or not source_path.is_file():
            raise DocumentConversionEngineError(
                f"document conversion source file does not exist: {source_path}"
            )
        source_hash_before = _file_sha256(source_path)

        with tempfile.TemporaryDirectory(prefix="ummaya-document-conversion-") as temp_root:
            temp_source_path = Path(temp_root) / source_path.name
            shutil.copy2(source_path, temp_source_path)
            output_path = Path(temp_root) / f"output.{self.output_format.value}"
            command = [str(self.executable), *self._expanded_args(temp_source_path, output_path)]
            try:
                completed = subprocess.run(  # noqa: S603 - executable is absolute and prevalidated.
                    command,
                    cwd=temp_root,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise DocumentConversionEngineError(
                    f"document conversion CLI timed out after {self.timeout_seconds}s"
                ) from exc
            if completed.returncode != 0:
                raise DocumentConversionEngineError(
                    "document conversion CLI exited non-zero "
                    f"({completed.returncode}): {_process_output_summary(completed)}"
                )
            source_hash_after = _file_sha256(source_path)
            if source_hash_after != source_hash_before:
                raise DocumentConversionEngineError(
                    "document conversion CLI modified the source artifact"
                )
            if not output_path.exists():
                legacy_output = output_path.with_name(
                    f"{temp_source_path.stem}.{self.output_format.value}"
                )
                if legacy_output.exists():
                    output_path = legacy_output
            if not output_path.is_file():
                raise DocumentConversionEngineError(
                    "document conversion CLI did not create the declared output artifact"
                )
            payload = output_path.read_bytes()
            if not payload:
                raise DocumentConversionEngineError(
                    "document conversion CLI produced an empty output artifact"
                )
            _validate_output_payload(payload, self.output_format)
            return payload

    def _expanded_args(self, source_path: Path, output_path: Path) -> tuple[str, ...]:
        return tuple(
            arg.replace("{source}", str(source_path))
            .replace("{output}", str(output_path))
            .replace("{outdir}", str(output_path.parent))
            for arg in self.args
        )


class DocumentConversionRegistry:
    """Session-local registry of promoted document conversion engines."""

    def __init__(self) -> None:
        self._engines: dict[tuple[DocumentFormat, DocumentFormat], DocumentConversionEngine] = {}

    def register(self, engine: DocumentConversionEngine) -> None:
        """Register one promoted engine for one source/output format pair."""
        key = (engine.source_format, engine.output_format)
        if key in self._engines:
            raise ValueError(
                "document conversion engine already registered for "
                f"{engine.source_format.value} -> {engine.output_format.value}"
            )
        self._engines[key] = engine

    def get(
        self,
        source_format: DocumentFormat,
        output_format: DocumentFormat,
    ) -> DocumentConversionEngine | None:
        """Return the promoted conversion engine for a format pair, if present."""
        return self._engines.get((source_format, output_format))

    def require(
        self,
        source_format: DocumentFormat,
        output_format: DocumentFormat,
    ) -> DocumentConversionEngine:
        """Return the promoted conversion engine or fail closed."""
        engine = self.get(source_format, output_format)
        if engine is None:
            raise UnsupportedDocumentConversionError(source_format, output_format)
        return engine


def build_default_document_conversion_registry(
    *,
    env: Mapping[str, str] | None = None,
) -> DocumentConversionRegistry:
    """Build promoted local conversion engines from explicit UMMAYA env config."""
    active_env = os.environ if env is None else env
    registry = DocumentConversionRegistry()
    executable = active_env.get(_HWP_TO_HWPX_CONVERTER_ENV)
    if not executable:
        hwpxjs_executable = _find_default_hwpxjs_executable(active_env)
        if hwpxjs_executable is not None:
            registry.register(
                LocalCliDocumentConversionEngine(
                    source_format=DocumentFormat.hwp,
                    output_format=DocumentFormat.hwpx,
                    engine_id=_HWPXJS_ENGINE_ID,
                    executable=hwpxjs_executable,
                    args=_HWPXJS_HWP_TO_HWPX_ARGS,
                    timeout_seconds=_HWP_CONVERTER_DEFAULT_TIMEOUT_SECONDS,
                )
            )
        legacy_office_executable = _find_default_libreoffice_executable(active_env)
        if legacy_office_executable is not None:
            for source_format, output_format, args in _LEGACY_OFFICE_CONVERSIONS:
                registry.register(
                    LocalCliDocumentConversionEngine(
                        source_format=source_format,
                        output_format=output_format,
                        engine_id=_LEGACY_OFFICE_ENGINE_ID,
                        executable=legacy_office_executable,
                        args=args,
                        timeout_seconds=_LEGACY_OFFICE_TIMEOUT_SECONDS,
                    )
                )
        elif (textutil_executable := _find_default_textutil_executable(active_env)) is not None:
            registry.register(
                LocalCliDocumentConversionEngine(
                    source_format=DocumentFormat.doc,
                    output_format=DocumentFormat.docx,
                    engine_id=_TEXTUTIL_DOC_ENGINE_ID,
                    executable=textutil_executable,
                    args=_TEXTUTIL_DOC_TO_DOCX_ARGS,
                    timeout_seconds=_TEXTUTIL_TIMEOUT_SECONDS,
                )
            )
        if legacy_office_executable is None:
            excel_executable = _find_default_excel_osascript_executable(active_env)
            if excel_executable is not None:
                registry.register(
                    LocalCliDocumentConversionEngine(
                        source_format=DocumentFormat.xls,
                        output_format=DocumentFormat.xlsx,
                        engine_id=_MICROSOFT_EXCEL_ENGINE_ID,
                        executable=excel_executable,
                        args=_MICROSOFT_EXCEL_XLS_TO_XLSX_ARGS,
                        timeout_seconds=_MICROSOFT_EXCEL_TIMEOUT_SECONDS,
                    )
                )
        return registry

    args_raw = active_env.get(_HWP_TO_HWPX_CONVERTER_ARGS_ENV)
    if not args_raw:
        raise ValueError(
            f"{_HWP_TO_HWPX_CONVERTER_ARGS_ENV} is required when "
            f"{_HWP_TO_HWPX_CONVERTER_ENV} is set"
        )

    registry.register(
        LocalCliDocumentConversionEngine(
            source_format=DocumentFormat.hwp,
            output_format=DocumentFormat.hwpx,
            engine_id=active_env.get(
                _HWP_TO_HWPX_CONVERTER_ENGINE_ID_ENV,
                "local-hwp-to-hwpx",
            ),
            executable=Path(executable),
            args=_converter_args_from_json(args_raw),
            timeout_seconds=_converter_timeout_from_env(
                active_env.get(_HWP_TO_HWPX_CONVERTER_TIMEOUT_ENV)
            ),
        )
    )
    return registry


def _find_executable(name: str, *, active_env: Mapping[str, str]) -> Path | None:
    path_env = active_env.get("PATH")
    if not path_env:
        return None
    found = which(name, path=path_env)
    if found is None:
        return None
    candidate = Path(found).expanduser().resolve(strict=False)
    if not candidate.exists() or not candidate.is_file() or not os.access(candidate, os.X_OK):
        return None
    return candidate


def _find_default_hwpxjs_executable(active_env: Mapping[str, str]) -> Path | None:
    discovered = _find_executable("hwpxjs", active_env=active_env)
    if discovered is not None:
        return discovered
    if active_env is not os.environ:
        return None
    for root in (Path.cwd(), Path(__file__).resolve().parents[4]):
        candidate = root / "node_modules" / ".bin" / "hwpxjs"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve(strict=False)
    return None


def _find_default_libreoffice_executable(active_env: Mapping[str, str]) -> Path | None:
    for executable_name in ("soffice", "libreoffice"):
        discovered = _find_executable(executable_name, active_env=active_env)
        if discovered is not None:
            return discovered
    return None


def _find_default_textutil_executable(active_env: Mapping[str, str]) -> Path | None:
    return _find_executable("textutil", active_env=active_env)


def _find_default_excel_osascript_executable(active_env: Mapping[str, str]) -> Path | None:
    excel_app = _find_microsoft_excel_app(active_env)
    if excel_app is None:
        return None
    return _find_executable("osascript", active_env=active_env)


def _find_microsoft_excel_app(active_env: Mapping[str, str]) -> Path | None:
    configured = active_env.get(_MICROSOFT_EXCEL_APP_ENV)
    if configured:
        candidate = Path(configured).expanduser().resolve(strict=False)
        if candidate.exists() and candidate.is_dir():
            return candidate
        return None
    if active_env is not os.environ:
        return None
    candidate = Path("/Applications/Microsoft Excel.app")
    if candidate.exists() and candidate.is_dir():
        return candidate
    return None


def _converter_args_from_json(raw: str) -> tuple[str, ...]:
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{_HWP_TO_HWPX_CONVERTER_ARGS_ENV} must be a JSON string list") from exc
    if not isinstance(decoded, list) or not decoded:
        raise ValueError(f"{_HWP_TO_HWPX_CONVERTER_ARGS_ENV} must be a non-empty JSON list")
    if not all(isinstance(item, str) and item for item in decoded):
        raise ValueError(f"{_HWP_TO_HWPX_CONVERTER_ARGS_ENV} entries must be non-empty strings")
    return tuple(decoded)


def _converter_timeout_from_env(raw: str | None) -> int:
    if raw is None or raw == "":
        return 30
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{_HWP_TO_HWPX_CONVERTER_TIMEOUT_ENV} must be an integer") from exc


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _process_output_summary(completed: subprocess.CompletedProcess[bytes]) -> str:
    stdout = _truncate_process_bytes(completed.stdout)
    stderr = _truncate_process_bytes(completed.stderr)
    if stdout and stderr:
        return f"stdout={stdout!r}; stderr={stderr!r}"
    if stdout:
        return f"stdout={stdout!r}"
    if stderr:
        return f"stderr={stderr!r}"
    return "no process output"


def _truncate_process_bytes(payload: bytes, limit: int = 500) -> str:
    text = payload.decode("utf-8", errors="replace").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _validate_output_payload(payload: bytes, output_format: DocumentFormat) -> None:
    if output_format is DocumentFormat.hwpx:
        _validate_hwpx_payload(payload)
        return
    if output_format in {DocumentFormat.docx, DocumentFormat.xlsx, DocumentFormat.pptx}:
        _validate_ooxml_payload(payload, output_format)


def _validate_hwpx_payload(payload: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = set(archive.namelist())
            if "mimetype" not in members:
                raise DocumentConversionEngineError("CLI output is not a valid HWPX package")
            mimetype = archive.read("mimetype").decode("utf-8", errors="replace").strip()
            if mimetype != "application/owpml":
                raise DocumentConversionEngineError("CLI output is not a valid HWPX package")
            if "Contents/header.xml" not in members:
                raise DocumentConversionEngineError("CLI output is not a valid HWPX package")
            has_section = any(
                member.startswith("Contents/section") and member.endswith(".xml")
                for member in members
            )
            if not has_section:
                raise DocumentConversionEngineError("CLI output is not a valid HWPX package")
    except zipfile.BadZipFile as exc:
        raise DocumentConversionEngineError("CLI output is not a valid HWPX package") from exc


def _validate_ooxml_payload(payload: bytes, output_format: DocumentFormat) -> None:
    marker_by_format = {
        DocumentFormat.docx: "word/document.xml",
        DocumentFormat.xlsx: "xl/workbook.xml",
        DocumentFormat.pptx: "ppt/presentation.xml",
    }
    marker = marker_by_format[output_format]
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = set(archive.namelist())
            if "[Content_Types].xml" not in members or marker not in members:
                raise DocumentConversionEngineError(
                    f"CLI output is not a valid {output_format.value.upper()} package"
                )
    except zipfile.BadZipFile as exc:
        raise DocumentConversionEngineError(
            f"CLI output is not a valid {output_format.value.upper()} package"
        ) from exc
