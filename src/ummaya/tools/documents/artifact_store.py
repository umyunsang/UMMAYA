# SPDX-License-Identifier: Apache-2.0
"""Session-scoped artifact storage for public document harness files."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath

from ummaya.tools.documents.models import (
    ArtifactLineage,
    DocumentArtifact,
    DocumentFormat,
    SecurityState,
)

DEFAULT_ARTIFACT_ROOT = Path.home() / ".ummaya" / "document_artifacts"
_SAFE_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class ArtifactStoreError(ValueError):
    """Base error for document artifact store failures."""


class ArtifactStoreSecurityError(ArtifactStoreError):
    """Raised when a requested artifact path would cross a storage boundary."""


class ArtifactStoreConflictError(ArtifactStoreError):
    """Raised when immutable artifact storage would overwrite existing bytes."""


class DocumentArtifactStore:
    """Store immutable sources and derivatives below one session root."""

    def __init__(self, *, session_id: str, root: str | Path | None = None) -> None:
        self.session_id = _validate_component(session_id, label="session_id")
        base_root = DEFAULT_ARTIFACT_ROOT if root is None else Path(root)
        self.root = base_root.expanduser().resolve()
        self.session_root = _safe_join(self.root, self.session_id)
        self.session_root.mkdir(parents=True, exist_ok=True)

    def store_source(
        self,
        source_path: str | Path,
        *,
        artifact_id: str,
        document_format: DocumentFormat,
        mime_type: str,
        display_name: str | None = None,
        expanded_byte_size: int | None = None,
    ) -> DocumentArtifact:
        """Copy user-provided source bytes into immutable session storage."""

        artifact_component = _validate_component(artifact_id, label="artifact_id")
        source = Path(source_path).expanduser().resolve()
        if not source.is_file():
            raise ArtifactStoreSecurityError(f"source file does not exist: {source}")

        safe_name = _validate_filename(display_name or source.name, label="display_name")
        payload = source.read_bytes()
        stored_path = _safe_join(self.session_root, "sources", artifact_component, safe_name)
        _write_immutable(stored_path, payload)

        return self._build_artifact(
            artifact_id=artifact_id,
            path=stored_path,
            document_format=document_format,
            mime_type=mime_type,
            payload=payload,
            expanded_byte_size=expanded_byte_size,
            lineage=ArtifactLineage.source,
            parent_artifact_id=None,
        )

    def write_derivative(
        self,
        parent: DocumentArtifact,
        *,
        artifact_id: str,
        lineage: ArtifactLineage,
        destination_name: str,
        payload: bytes,
        document_format: DocumentFormat | None = None,
        mime_type: str | None = None,
        expanded_byte_size: int | None = None,
    ) -> DocumentArtifact:
        """Write a derivative artifact without mutating the parent artifact."""

        artifact_component = _validate_component(artifact_id, label="artifact_id")
        lineage_value = _raw_value(lineage)
        if lineage_value == "source":
            raise ArtifactStoreSecurityError("derivative lineage cannot be source")

        parent_path = Path(parent.source_path).expanduser().resolve()
        _require_inside(parent_path, self.session_root)
        safe_name = _validate_filename(destination_name, label="destination_name")
        lineage_component = _validate_component(lineage_value, label="lineage")
        derivative_path = _safe_join(
            self.session_root,
            lineage_component,
            artifact_component,
            safe_name,
        )
        _write_immutable(derivative_path, payload)

        return self._build_artifact(
            artifact_id=artifact_id,
            path=derivative_path,
            document_format=document_format or parent.format,
            mime_type=mime_type or parent.mime_type,
            payload=payload,
            expanded_byte_size=expanded_byte_size,
            lineage=lineage,
            parent_artifact_id=parent.artifact_id,
        )

    def _build_artifact(
        self,
        *,
        artifact_id: str,
        path: Path,
        document_format: DocumentFormat,
        mime_type: str,
        payload: bytes,
        expanded_byte_size: int | None,
        lineage: ArtifactLineage,
        parent_artifact_id: str | None,
    ) -> DocumentArtifact:
        byte_size = len(payload)
        return DocumentArtifact(
            artifact_id=artifact_id,
            session_id=self.session_id,
            source_path=path,
            display_name=path.name,
            format=document_format,
            mime_type=mime_type,
            sha256=hashlib.sha256(payload).hexdigest(),
            byte_size=byte_size,
            expanded_byte_size=expanded_byte_size if expanded_byte_size is not None else byte_size,
            page_count=None,
            sheet_count=None,
            slide_count=None,
            section_count=None,
            created_at=datetime.now(UTC),
            lineage=lineage,
            parent_artifact_id=parent_artifact_id,
            security_state=SecurityState.accepted,
            blocked_reason=None,
        )


def _validate_component(value: str, *, label: str) -> str:
    if not value or value in {".", ".."}:
        raise ArtifactStoreSecurityError(f"unsafe {label}: {value!r}")
    if value.startswith((".", "~")):
        raise ArtifactStoreSecurityError(f"unsafe {label}: {value!r}")
    if "/" in value or "\\" in value:
        raise ArtifactStoreSecurityError(f"unsafe {label}: {value!r}")
    if not _SAFE_COMPONENT_RE.fullmatch(value):
        raise ArtifactStoreSecurityError(f"unsafe {label}: {value!r}")
    return value


def _validate_filename(value: str, *, label: str) -> str:
    if not value or value in {".", ".."}:
        raise ArtifactStoreSecurityError(f"unsafe {label}: {value!r}")
    if value.startswith((".", "~")):
        raise ArtifactStoreSecurityError(f"unsafe {label}: {value!r}")
    path = Path(value)
    windows_path = PureWindowsPath(value)
    if path.is_absolute() or windows_path.is_absolute():
        raise ArtifactStoreSecurityError(f"unsafe {label}: {value!r}")
    if path.name != value or windows_path.name != value:
        raise ArtifactStoreSecurityError(f"unsafe {label}: {value!r}")
    if any(part in {"", ".", ".."} for part in path.parts + windows_path.parts):
        raise ArtifactStoreSecurityError(f"unsafe {label}: {value!r}")
    return value


def _safe_join(root: Path, *parts: str) -> Path:
    base = root.resolve()
    candidate = base.joinpath(*parts).resolve()
    _require_inside(candidate, base)
    return candidate


def _require_inside(candidate: Path, root: Path) -> None:
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    if resolved_candidate != resolved_root and resolved_root not in resolved_candidate.parents:
        raise ArtifactStoreSecurityError(f"path escapes artifact root: {resolved_candidate}")


def _write_immutable(destination: Path, payload: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("xb") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise ArtifactStoreConflictError(f"artifact already exists: {destination}") from exc


def _raw_value(value: object) -> str:
    return str(getattr(value, "value", value))
