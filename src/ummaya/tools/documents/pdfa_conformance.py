# SPDX-License-Identifier: Apache-2.0
"""Optional local PDF/A export and conformance validation bridge."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Protocol

PDFA_EXPORTER_ID = "ghostscript-pdfa2b-pdfwrite-exporter"
PDFA_VALIDATOR_ID = "verapdf-pdfa-conformance-validator"
PDFA_FLAVOUR = "2b"
PDFA_TIMEOUT_SECONDS = 120


class PdfaConformanceBridgeError(ValueError):
    """Raised when PDF/A export or validation fails closed."""


@dataclass(frozen=True)
class PdfaConformanceReport:
    """Local post-write PDF/A conformance result."""

    exporter_id: str
    validator_id: str
    pdfa_flavour: str
    sha256: str
    byte_size: int
    summary: str


@dataclass(frozen=True)
class PdfaExportResult:
    """PDF/A payload plus the conformance report that approved it."""

    payload: bytes
    report: PdfaConformanceReport


class PdfaConformanceBridge(Protocol):
    """Bridge that turns a PDF payload into a validated PDF/A payload."""

    bridge_id: str

    def export_pdfa(self, payload: bytes) -> PdfaExportResult:
        """Return validated PDF/A bytes or fail closed."""


class LocalPdfaConformanceBridge:
    """Ghostscript PDF/A export plus veraPDF post-write validation."""

    bridge_id = "ghostscript-verapdf-pdfa2b-bridge"

    def __init__(
        self,
        *,
        ghostscript_executable: Path,
        verapdf_executable: Path,
        pdfa_def_path: Path,
        srgb_icc_path: Path,
        timeout_seconds: int = PDFA_TIMEOUT_SECONDS,
    ) -> None:
        self.ghostscript_executable = _validated_executable(
            ghostscript_executable,
            label="ghostscript_executable",
        )
        self.verapdf_executable = _validated_executable(
            verapdf_executable,
            label="verapdf_executable",
        )
        self.pdfa_def_path = _validated_file(pdfa_def_path, label="pdfa_def_path")
        self.srgb_icc_path = _validated_file(srgb_icc_path, label="srgb_icc_path")
        if timeout_seconds < 1 or timeout_seconds > 300:
            raise ValueError("PDF/A bridge timeout_seconds must be between 1 and 300")
        self.timeout_seconds = timeout_seconds

    def export_pdfa(self, payload: bytes) -> PdfaExportResult:
        """Export PDF bytes to PDF/A-2b and validate the output with veraPDF."""
        if not payload.startswith(b"%PDF-"):
            raise PdfaConformanceBridgeError("PDF/A export requires a PDF payload")
        with tempfile.TemporaryDirectory(prefix="ummaya-pdfa-") as temp_root:
            temp_dir = Path(temp_root)
            input_path = temp_dir / "input.pdf"
            output_path = temp_dir / "output.pdf"
            pdfa_def_path = temp_dir / "PDFA_def.ps"
            srgb_icc_path = temp_dir / "srgb.icc"
            input_path.write_bytes(payload)
            shutil.copy2(self.pdfa_def_path, pdfa_def_path)
            shutil.copy2(self.srgb_icc_path, srgb_icc_path)
            self._run_ghostscript(
                input_path=input_path,
                output_path=output_path,
                cwd=temp_dir,
            )
            output_payload = output_path.read_bytes()
            if not output_payload.startswith(b"%PDF-"):
                raise PdfaConformanceBridgeError("PDF/A exporter did not produce a PDF payload")
            report = self._validate_with_verapdf(output_path, output_payload)
            return PdfaExportResult(payload=output_payload, report=report)

    def _run_ghostscript(
        self,
        *,
        input_path: Path,
        output_path: Path,
        cwd: Path,
    ) -> None:
        command = [
            str(self.ghostscript_executable),
            "--permit-file-read=srgb.icc",
            "-dPDFA=2",
            "-dBATCH",
            "-dNOPAUSE",
            "-dNOOUTERSAVE",
            "-sColorConversionStrategy=RGB",
            "-sDEVICE=pdfwrite",
            "-dPDFACompatibilityPolicy=1",
            f"-sOutputFile={output_path}",
            "PDFA_def.ps",
            str(input_path),
        ]
        completed = _run_local_command(
            command,
            cwd=cwd,
            timeout_seconds=self.timeout_seconds,
        )
        if completed.returncode != 0:
            raise PdfaConformanceBridgeError(
                "Ghostscript PDF/A export failed: " + _process_output_summary(completed)
            )
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise PdfaConformanceBridgeError("Ghostscript PDF/A export produced no output")

    def _validate_with_verapdf(
        self,
        output_path: Path,
        output_payload: bytes,
    ) -> PdfaConformanceReport:
        command = [
            str(self.verapdf_executable),
            "--format",
            "text",
            "--flavour",
            PDFA_FLAVOUR,
            str(output_path),
        ]
        completed = _run_local_command(
            command,
            cwd=output_path.parent,
            timeout_seconds=self.timeout_seconds,
        )
        summary = _process_output_summary(completed)
        if completed.returncode != 0 or not completed.stdout.decode(
            "utf-8",
            errors="replace",
        ).lstrip().startswith("PASS "):
            raise PdfaConformanceBridgeError(
                "veraPDF PDF/A conformance validation failed: " + summary
            )
        return PdfaConformanceReport(
            exporter_id=PDFA_EXPORTER_ID,
            validator_id=PDFA_VALIDATOR_ID,
            pdfa_flavour=PDFA_FLAVOUR,
            sha256=hashlib.sha256(output_payload).hexdigest(),
            byte_size=len(output_payload),
            summary=summary,
        )


def build_default_pdfa_conformance_bridge(
    *,
    env: Mapping[str, str] | None = None,
) -> PdfaConformanceBridge | None:
    """Build the local PDF/A bridge when Ghostscript and veraPDF are available."""
    active_env = os.environ if env is None else env
    ghostscript = _find_executable("gs", active_env=active_env)
    verapdf = _find_executable("verapdf", active_env=active_env)
    if ghostscript is None or verapdf is None:
        return None
    assets = discover_ghostscript_pdfa_assets(ghostscript)
    if assets is None:
        return None
    pdfa_def_path, srgb_icc_path = assets
    return LocalPdfaConformanceBridge(
        ghostscript_executable=ghostscript,
        verapdf_executable=verapdf,
        pdfa_def_path=pdfa_def_path,
        srgb_icc_path=srgb_icc_path,
    )


def discover_ghostscript_pdfa_assets(
    ghostscript_executable: Path,
) -> tuple[Path, Path] | None:
    """Return Ghostscript's PDF/A prefix and sRGB ICC profile paths if present."""
    executable = ghostscript_executable.expanduser().resolve(strict=False)
    for parent in executable.parents:
        pdfa_def_path = parent / "share" / "ghostscript" / "lib" / "PDFA_def.ps"
        srgb_icc_path = parent / "share" / "ghostscript" / "iccprofiles" / "srgb.icc"
        if pdfa_def_path.is_file() and srgb_icc_path.is_file():
            return pdfa_def_path.resolve(strict=False), srgb_icc_path.resolve(strict=False)
    return None


def _find_executable(
    executable_name: str,
    *,
    active_env: Mapping[str, str],
) -> Path | None:
    path_env = active_env.get("PATH")
    if not path_env:
        return None
    found = which(executable_name, path=path_env)
    if found is None:
        return None
    candidate = Path(found).expanduser().resolve(strict=False)
    if not candidate.exists() or not candidate.is_file() or not os.access(candidate, os.X_OK):
        return None
    return candidate


def _validated_executable(path: Path, *, label: str) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    if not resolved.is_absolute():
        raise ValueError(f"{label} must be absolute")
    if not resolved.exists() or not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise ValueError(f"{label} must be an executable file: {resolved}")
    return resolved


def _validated_file(path: Path, *, label: str) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    if not resolved.is_absolute():
        raise ValueError(f"{label} must be absolute")
    if not resolved.is_file():
        raise ValueError(f"{label} must be an existing file: {resolved}")
    return resolved


def _run_local_command(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(  # noqa: S603 - executables are absolute and prevalidated.
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PdfaConformanceBridgeError(
            f"PDF/A bridge command timed out after {timeout_seconds}s"
        ) from exc


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
