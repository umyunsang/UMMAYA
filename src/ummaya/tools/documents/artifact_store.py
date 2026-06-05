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
    DocumentDiff,
    DocumentFormat,
    SecurityState,
)

DEFAULT_ARTIFACT_ROOT = Path.home() / ".ummaya" / "document_artifacts"
_SAFE_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_LEGACY_ARTIFACT_DIRECTORIES = (
    ("sources", ArtifactLineage.source),
    (ArtifactLineage.working_copy.value, ArtifactLineage.working_copy),
    (ArtifactLineage.render.value, ArtifactLineage.render),
    ("renders", ArtifactLineage.render),
    (ArtifactLineage.validation_report.value, ArtifactLineage.validation_report),
    (ArtifactLineage.export.value, ArtifactLineage.export),
)
_MIME_BY_FORMAT = {
    DocumentFormat.hwpx: "application/owpml",
    DocumentFormat.owpml: "application/owpml",
    DocumentFormat.hwp: "application/x-hwp",
    DocumentFormat.docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    DocumentFormat.pdf: "application/pdf",
    DocumentFormat.xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    DocumentFormat.pptx: (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    ),
    DocumentFormat.odt: "application/vnd.oasis.opendocument.text",
    DocumentFormat.ods: "application/vnd.oasis.opendocument.spreadsheet",
    DocumentFormat.odp: "application/vnd.oasis.opendocument.presentation",
    DocumentFormat.html: "text/html",
    DocumentFormat.htm: "text/html",
    DocumentFormat.txt: "text/plain",
    DocumentFormat.rtf: "application/rtf",
    DocumentFormat.md: "text/markdown",
    DocumentFormat.epub: "application/epub+zip",
    DocumentFormat.csv: "text/csv",
    DocumentFormat.tsv: "text/tab-separated-values",
    DocumentFormat.xml: "application/xml",
    DocumentFormat.rdf: "application/rdf+xml",
    DocumentFormat.ttl: "text/turtle",
    DocumentFormat.lod: "text/plain",
    DocumentFormat.json: "application/json",
    DocumentFormat.jsonl: "application/x-ndjson",
    DocumentFormat.yaml: "application/yaml",
    DocumentFormat.yml: "application/yaml",
    DocumentFormat.geojson: "application/geo+json",
    DocumentFormat.gpx: "application/gpx+xml",
    DocumentFormat.kml: "application/vnd.google-earth.kml+xml",
    DocumentFormat.fasta: "text/plain",
    DocumentFormat.sgml: "text/sgml",
    DocumentFormat.dtd: "application/xml-dtd",
    DocumentFormat.hml: "application/xml",
    DocumentFormat.zip: "application/zip",
    DocumentFormat.tar: "application/x-tar",
    DocumentFormat.gz: "application/gzip",
    DocumentFormat.etc: "text/plain",
}


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

    def load_artifact(self, artifact_id: str) -> DocumentArtifact | None:
        """Load one exact artifact from the current session store."""

        artifact_component = _validate_component(artifact_id, label="artifact_id")
        metadata_path = self._artifact_metadata_path(artifact_component)
        if metadata_path.is_file():
            artifact = DocumentArtifact.model_validate_json(metadata_path.read_bytes())
            if artifact.artifact_id != artifact_component:
                raise ArtifactStoreSecurityError(
                    f"artifact metadata id mismatch: {artifact.artifact_id}"
                )
            if artifact.session_id != self.session_id:
                raise ArtifactStoreSecurityError(
                    f"artifact session mismatch: {artifact.session_id}"
                )
            self._verify_artifact_payload(artifact)
            return artifact
        return self._load_legacy_artifact(artifact_component)

    def store_diff(self, diff: DocumentDiff) -> None:
        """Persist the structured diff for a derivative artifact."""

        _validate_component(diff.source_artifact_id, label="source_artifact_id")
        derivative_artifact_id = _validate_component(
            diff.derivative_artifact_id,
            label="derivative_artifact_id",
        )
        diff_path = self._diff_metadata_path(derivative_artifact_id)
        _write_replace(
            diff_path,
            diff.model_dump_json(indent=2).encode("utf-8"),
        )

    def load_diff(self, derivative_artifact_id: str) -> DocumentDiff | None:
        """Load a structured diff by exact derivative artifact id."""

        artifact_component = _validate_component(
            derivative_artifact_id,
            label="derivative_artifact_id",
        )
        diff_path = self._diff_metadata_path(artifact_component)
        if not diff_path.is_file():
            return None
        diff = DocumentDiff.model_validate_json(diff_path.read_bytes())
        if diff.derivative_artifact_id != artifact_component:
            raise ArtifactStoreSecurityError(
                f"diff derivative mismatch: {diff.derivative_artifact_id}"
            )
        _validate_component(diff.source_artifact_id, label="source_artifact_id")
        return diff

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
        artifact = DocumentArtifact(
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
        self._write_artifact_metadata(artifact)
        return artifact

    def _artifact_metadata_path(self, artifact_id: str) -> Path:
        artifact_component = _validate_component(artifact_id, label="artifact_id")
        return _safe_join(
            self.session_root,
            ".metadata",
            "artifacts",
            f"{artifact_component}.json",
        )

    def _diff_metadata_path(self, derivative_artifact_id: str) -> Path:
        artifact_component = _validate_component(
            derivative_artifact_id,
            label="derivative_artifact_id",
        )
        return _safe_join(
            self.session_root,
            ".metadata",
            "diffs",
            f"{artifact_component}.json",
        )

    def _write_artifact_metadata(self, artifact: DocumentArtifact) -> None:
        metadata_path = self._artifact_metadata_path(artifact.artifact_id)
        _write_immutable(
            metadata_path,
            artifact.model_dump_json(indent=2).encode("utf-8"),
        )

    def _verify_artifact_payload(self, artifact: DocumentArtifact) -> None:
        artifact_path = Path(artifact.source_path).expanduser().resolve()
        _require_inside(artifact_path, self.session_root)
        if not artifact_path.is_file():
            raise ArtifactStoreError(f"artifact payload is missing: {artifact.artifact_id}")
        payload = artifact_path.read_bytes()
        payload_sha256 = hashlib.sha256(payload).hexdigest()
        if payload_sha256 != artifact.sha256:
            raise ArtifactStoreError(f"artifact checksum mismatch: {artifact.artifact_id}")
        if len(payload) != artifact.byte_size:
            raise ArtifactStoreError(f"artifact byte size mismatch: {artifact.artifact_id}")

    def _load_legacy_artifact(self, artifact_id: str) -> DocumentArtifact | None:
        for directory_name, lineage in _LEGACY_ARTIFACT_DIRECTORIES:
            artifact_dir = _safe_join(self.session_root, directory_name, artifact_id)
            if not artifact_dir.is_dir():
                continue
            files = sorted(
                candidate
                for candidate in artifact_dir.iterdir()
                if candidate.is_file() and not candidate.name.startswith(".")
            )
            if len(files) != 1:
                raise ArtifactStoreError(f"ambiguous legacy artifact payload: {artifact_id}")
            artifact_path = files[0].resolve()
            document_format = _format_from_path(artifact_path)
            if document_format is None:
                return None
            parent_artifact_id = self._legacy_parent_artifact_id(artifact_id, lineage)
            if lineage is not ArtifactLineage.source and parent_artifact_id is None:
                return None
            payload = artifact_path.read_bytes()
            return DocumentArtifact(
                artifact_id=artifact_id,
                session_id=self.session_id,
                source_path=artifact_path,
                display_name=artifact_path.name,
                format=document_format,
                mime_type=_mime_for_format(document_format),
                sha256=hashlib.sha256(payload).hexdigest(),
                byte_size=len(payload),
                expanded_byte_size=len(payload),
                page_count=None,
                sheet_count=None,
                slide_count=None,
                section_count=None,
                created_at=datetime.fromtimestamp(artifact_path.stat().st_mtime, UTC),
                lineage=lineage,
                parent_artifact_id=parent_artifact_id,
                security_state=SecurityState.accepted,
                blocked_reason=None,
            )
        return None

    def _legacy_parent_artifact_id(
        self,
        artifact_id: str,
        lineage: ArtifactLineage,
    ) -> str | None:
        if lineage is ArtifactLineage.source:
            return None
        if artifact_id.startswith("derivative-"):
            candidate = f"working-{artifact_id.removeprefix('derivative-')}"
            if self._legacy_artifact_directory_exists(candidate, ArtifactLineage.working_copy):
                return candidate
        if artifact_id.startswith("working-"):
            source_artifact_ids = self._legacy_artifact_ids("sources")
            if len(source_artifact_ids) == 1:
                return source_artifact_ids[0]
        return None

    def _legacy_artifact_directory_exists(
        self,
        artifact_id: str,
        lineage: ArtifactLineage,
    ) -> bool:
        for directory_name, directory_lineage in _LEGACY_ARTIFACT_DIRECTORIES:
            if directory_lineage is not lineage:
                continue
            artifact_dir = _safe_join(self.session_root, directory_name, artifact_id)
            if artifact_dir.is_dir():
                return True
        return False

    def _legacy_artifact_ids(self, directory_name: str) -> list[str]:
        directory = _safe_join(self.session_root, directory_name)
        if not directory.is_dir():
            return []
        artifact_ids: list[str] = []
        for candidate in sorted(directory.iterdir()):
            if not candidate.is_dir():
                continue
            try:
                artifact_ids.append(_validate_component(candidate.name, label="artifact_id"))
            except ArtifactStoreSecurityError:
                continue
        return artifact_ids


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


def _write_replace(destination: Path, payload: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f"{destination.name}.tmp")
    temporary.write_bytes(payload)
    temporary.replace(destination)


def _format_from_path(path: Path) -> DocumentFormat | None:
    suffix = path.suffix.lower().lstrip(".")
    try:
        return DocumentFormat(suffix)
    except ValueError:
        return None


def _mime_for_format(document_format: DocumentFormat) -> str:
    return _MIME_BY_FORMAT.get(document_format, "application/octet-stream")


def _raw_value(value: object) -> str:
    return str(getattr(value, "value", value))
