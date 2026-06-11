# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import os
import zipfile
from decimal import Decimal
from pathlib import Path

import pytest

from ummaya.tools.documents import registry as document_registry
from ummaya.tools.documents.baselines import (
    BaselineField,
    BaselineTableGeometry,
    BaselineTextAnchor,
    ConformanceBaseline,
    ConformanceBaselineCatalog,
)
from ummaya.tools.documents.engines import DocumentEngineRegistry
from ummaya.tools.documents.models import (
    DocumentExtraction,
    DocumentFormat,
    DocumentPatch,
    FormField,
    ParagraphBlock,
    ToolResultStatus,
)
from ummaya.tools.documents.registry import DocumentToolRuntime
from ummaya.tools.documents.tool_defs import (
    DocumentApplyFillRequest,
    DocumentCopyForEditRequest,
    DocumentFieldPatch,
    DocumentInspectRequest,
    DocumentLocator,
    DocumentSaveRequest,
)


class LocalExportDocxEngine:
    document_format = DocumentFormat.docx
    engine_id = "local-export-docx-engine"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=[
                ParagraphBlock(
                    block_id="paragraph-001",
                    text=f"Application extracted from {path.name}",
                    source_path="/word/document.xml/p[1]",
                )
            ],
            fields=[
                FormField(
                    field_id="applicant_name",
                    label="Applicant name",
                    path="/word/document.xml/field[applicant_name]",
                    field_type="text",
                    required=True,
                    current_value="Hong Gil-dong",
                    source_confidence=Decimal("1"),
                )
            ],
        )

    def apply_patch(self, path: Path, patch: DocumentPatch) -> bytes:
        marker = "|".join(operation.operation_id for operation in patch.operations)
        return path.read_bytes() + f"\npatched:{marker}".encode()

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        return (f"render:{artifact_id}:{path.name}".encode(),)


def test_document_save_blocks_source_path_destination_without_overwrite(
    tmp_path: Path,
) -> None:
    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)
    source_sha256_before = source.read_bytes()
    runtime, derivative_artifact_id = _prepared_derivative(source, tmp_path, "source-path")

    save_result = runtime.save(
        DocumentSaveRequest(
            correlation_id="source-path-export-save",
            document=DocumentLocator(artifact_id=derivative_artifact_id),
            destination_display_name=source.name,
            destination_path=str(source),
        )
    )

    assert save_result.status is ToolResultStatus.blocked
    assert save_result.blocked_reason == "validation_failed"
    assert source.read_bytes() == source_sha256_before
    assert not save_result.saved_exports
    assert not any(ref.startswith("export-") for ref in save_result.artifact_refs)
    assert not any(path.name.startswith("export-") for path in (tmp_path / "artifacts").rglob("*"))


def test_document_save_blocks_destination_created_after_validation_without_overwrite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)
    runtime, derivative_artifact_id = _prepared_derivative(source, tmp_path, "race")
    destination = tmp_path / "exports" / "citizen-final.docx"
    citizen_bytes = b"citizen draft created during local export race"
    write_tempfile = document_registry._write_tempfile_for_local_export

    def write_tempfile_then_create_destination(
        destination_path: Path,
        payload: bytes,
        parent_fd: int,
    ) -> Path:
        temp_path = write_tempfile(destination_path, payload, parent_fd)
        destination_path.write_bytes(citizen_bytes)
        return temp_path

    monkeypatch.setattr(
        document_registry,
        "_write_tempfile_for_local_export",
        write_tempfile_then_create_destination,
    )

    save_result = runtime.save(
        DocumentSaveRequest(
            correlation_id="race-export-save",
            document=DocumentLocator(artifact_id=derivative_artifact_id),
            destination_display_name=destination.name,
            destination_path=str(destination),
        )
    )

    assert save_result.status is ToolResultStatus.blocked
    assert save_result.blocked_reason == "validation_failed"
    assert destination.read_bytes() == citizen_bytes
    assert not save_result.saved_exports
    assert not any(ref.startswith("export-") for ref in save_result.artifact_refs)
    assert not any(path.name.startswith("export-") for path in (tmp_path / "artifacts").rglob("*"))


@pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlink unavailable")
def test_document_save_blocks_preexisting_parent_symlink(
    tmp_path: Path,
) -> None:
    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)
    runtime, derivative_artifact_id = _prepared_derivative(source, tmp_path, "raw-parent-symlink")
    attacker_parent = tmp_path / "attacker-exports"
    attacker_parent.mkdir()
    destination_parent = tmp_path / "exports"
    destination_parent.symlink_to(attacker_parent, target_is_directory=True)
    destination = destination_parent / "citizen-final.docx"

    save_result = runtime.save(
        DocumentSaveRequest(
            correlation_id="raw-parent-symlink-export-save",
            document=DocumentLocator(artifact_id=derivative_artifact_id),
            destination_display_name=destination.name,
            destination_path=str(destination),
        )
    )

    assert save_result.status is ToolResultStatus.blocked
    assert save_result.blocked_reason == "validation_failed"
    assert not (attacker_parent / destination.name).exists()
    assert not save_result.saved_exports
    assert not any(ref.startswith("export-") for ref in save_result.artifact_refs)
    assert not any(path.name.startswith("export-") for path in (tmp_path / "artifacts").rglob("*"))


@pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlink unavailable")
def test_document_save_blocks_parent_symlink_created_after_validation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)
    runtime, derivative_artifact_id = _prepared_derivative(source, tmp_path, "parent-symlink")
    destination = tmp_path / "exports" / "citizen-final.docx"
    hidden_target = tmp_path / ".hidden-target"
    hidden_target.mkdir()
    write_tempfile = document_registry._write_tempfile_for_local_export

    def replace_parent_with_symlink_then_write(
        destination_path: Path,
        payload: bytes,
        parent_fd: int,
    ) -> Path:
        destination_path.parent.rmdir()
        destination_path.parent.symlink_to(hidden_target, target_is_directory=True)
        return write_tempfile(destination_path, payload, parent_fd)

    monkeypatch.setattr(
        document_registry,
        "_write_tempfile_for_local_export",
        replace_parent_with_symlink_then_write,
    )

    save_result = runtime.save(
        DocumentSaveRequest(
            correlation_id="parent-symlink-export-save",
            document=DocumentLocator(artifact_id=derivative_artifact_id),
            destination_display_name=destination.name,
            destination_path=str(destination),
        )
    )

    assert save_result.status is ToolResultStatus.blocked
    assert save_result.blocked_reason == "validation_failed"
    assert not (hidden_target / destination.name).exists()
    assert not save_result.saved_exports
    assert not any(ref.startswith("export-") for ref in save_result.artifact_refs)
    assert not any(path.name.startswith("export-") for path in (tmp_path / "artifacts").rglob("*"))


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlink unavailable")
def test_document_save_blocks_parent_symlink_swapped_during_publish(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)
    runtime, derivative_artifact_id = _prepared_derivative(source, tmp_path, "publish-window")
    destination = tmp_path / "exports" / "citizen-final.docx"
    hidden_target = tmp_path / ".hidden-target"
    hidden_target.mkdir()
    original_link = document_registry.os.link
    attack_triggered = False

    def swap_parent_after_final_check_then_link(
        source_path: Path | str,
        destination_path: Path | str,
        *args: object,
        **kwargs: object,
    ) -> None:
        nonlocal attack_triggered
        if not attack_triggered and Path(destination_path).name == destination.name:
            attack_triggered = True
            temp_path = Path(source_path)
            temp_bytes = temp_path.read_bytes() if temp_path.is_file() else b""
            original_parent = tmp_path / "exports-original"
            destination.parent.rename(original_parent)
            destination.parent.symlink_to(hidden_target, target_is_directory=True)
            if temp_bytes:
                (hidden_target / temp_path.name).write_bytes(temp_bytes)
        original_link(source_path, destination_path, *args, **kwargs)

    monkeypatch.setattr(document_registry.os, "link", swap_parent_after_final_check_then_link)

    save_result = runtime.save(
        DocumentSaveRequest(
            correlation_id="publish-window-export-save",
            document=DocumentLocator(artifact_id=derivative_artifact_id),
            destination_display_name=destination.name,
            destination_path=str(destination),
        )
    )

    assert attack_triggered is True
    assert save_result.status is ToolResultStatus.blocked
    assert save_result.blocked_reason == "validation_failed"
    assert not (hidden_target / destination.name).exists()
    assert not save_result.saved_exports
    assert not any(ref.startswith("export-") for ref in save_result.artifact_refs)
    assert not any(path.name.startswith("export-") for path in (tmp_path / "artifacts").rglob("*"))


def test_document_save_blocks_parent_directory_swapped_during_publish(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)
    runtime, derivative_artifact_id = _prepared_derivative(source, tmp_path, "parent-dir-swap")
    destination = tmp_path / "exports" / "citizen-final.docx"
    attacker_parent = tmp_path / "attacker-exports"
    original_parent = tmp_path / "exports-original"
    attacker_parent.mkdir()
    write_tempfile = document_registry._write_tempfile_for_local_export

    def write_tempfile_then_swap_parent_directory(
        destination_path: Path,
        payload: bytes,
        parent_fd: int,
    ) -> Path:
        temp_path = write_tempfile(destination_path, payload, parent_fd)
        destination_path.parent.rename(original_parent)
        attacker_parent.rename(destination_path.parent)
        (destination_path.parent / temp_path.name).write_bytes(b"attacker replacement bytes")
        return temp_path

    monkeypatch.setattr(
        document_registry,
        "_write_tempfile_for_local_export",
        write_tempfile_then_swap_parent_directory,
    )

    save_result = runtime.save(
        DocumentSaveRequest(
            correlation_id="parent-dir-swap-export-save",
            document=DocumentLocator(artifact_id=derivative_artifact_id),
            destination_display_name=destination.name,
            destination_path=str(destination),
        )
    )

    assert save_result.status is ToolResultStatus.blocked
    assert save_result.blocked_reason == "validation_failed"
    assert not destination.exists()
    assert list(original_parent.iterdir()) == []
    assert not save_result.saved_exports
    assert not any(ref.startswith("export-") for ref in save_result.artifact_refs)
    assert not any(path.name.startswith("export-") for path in (tmp_path / "artifacts").rglob("*"))


def test_document_save_does_not_write_payload_when_parent_swaps_before_temp_creation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)
    runtime, derivative_artifact_id = _prepared_derivative(source, tmp_path, "pre-temp-swap")
    destination = tmp_path / "exports" / "citizen-final.docx"
    attacker_parent = tmp_path / "attacker-exports"
    original_parent = tmp_path / "exports-original"
    attacker_parent.mkdir()
    original_parent_changed = document_registry._raise_if_local_export_parent_changed
    original_publish = document_registry._publish_tempfile_without_clobber
    attack_triggered = False
    leaked_before_cleanup = False

    def check_parent_then_swap(parent_fd: int, destination_path: Path) -> None:
        nonlocal attack_triggered
        original_parent_changed(parent_fd, destination_path)
        if not attack_triggered:
            attack_triggered = True
            destination_path.parent.rename(original_parent)
            attacker_parent.rename(destination_path.parent)

    def observe_temp_before_blocked_publish(
        temp_file, destination_path: Path, parent_fd: int
    ) -> None:
        nonlocal leaked_before_cleanup
        if temp_file.path.exists():
            leaked_before_cleanup = b"patched:" in temp_file.path.read_bytes()
        original_publish(temp_file, destination_path, parent_fd)

    monkeypatch.setattr(
        document_registry,
        "_raise_if_local_export_parent_changed",
        check_parent_then_swap,
    )
    monkeypatch.setattr(
        document_registry,
        "_publish_tempfile_without_clobber",
        observe_temp_before_blocked_publish,
    )

    save_result = runtime.save(
        DocumentSaveRequest(
            correlation_id="pre-temp-swap-export-save",
            document=DocumentLocator(artifact_id=derivative_artifact_id),
            destination_display_name=destination.name,
            destination_path=str(destination),
        )
    )

    assert attack_triggered is True
    assert save_result.status is ToolResultStatus.blocked
    assert save_result.blocked_reason == "validation_failed"
    assert leaked_before_cleanup is False
    assert not destination.exists()
    assert list(original_parent.iterdir()) == []
    assert not save_result.saved_exports
    assert not any(ref.startswith("export-") for ref in save_result.artifact_refs)
    assert not any(path.name.startswith("export-") for path in (tmp_path / "artifacts").rglob("*"))


def test_document_save_blocks_same_parent_temp_entry_substitution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)
    runtime, derivative_artifact_id = _prepared_derivative(source, tmp_path, "temp-substitution")
    destination = tmp_path / "exports" / "citizen-final.docx"
    original_link = document_registry.os.link
    attack_triggered = False

    def replace_temp_entry_then_link(
        source_path: Path | str,
        destination_path: Path | str,
        *args: object,
        **kwargs: object,
    ) -> None:
        nonlocal attack_triggered
        if not attack_triggered and Path(destination_path).name == destination.name:
            attack_triggered = True
            parent_fd = kwargs["src_dir_fd"]
            assert isinstance(parent_fd, int)
            source_name = Path(source_path).name
            document_registry.os.unlink(source_name, dir_fd=parent_fd)
            attacker_fd = document_registry.os.open(
                source_name,
                document_registry.os.O_WRONLY
                | document_registry.os.O_CREAT
                | document_registry.os.O_EXCL,
                0o600,
                dir_fd=parent_fd,
            )
            try:
                document_registry.os.write(attacker_fd, b"attacker replacement document bytes")
                document_registry.os.fsync(attacker_fd)
            finally:
                document_registry.os.close(attacker_fd)
        original_link(source_path, destination_path, *args, **kwargs)

    monkeypatch.setattr(document_registry.os, "link", replace_temp_entry_then_link)

    save_result = runtime.save(
        DocumentSaveRequest(
            correlation_id="temp-substitution-export-save",
            document=DocumentLocator(artifact_id=derivative_artifact_id),
            destination_display_name=destination.name,
            destination_path=str(destination),
        )
    )

    assert attack_triggered is True
    assert save_result.status is ToolResultStatus.blocked
    assert save_result.blocked_reason == "validation_failed"
    assert not destination.exists()
    assert not save_result.saved_exports
    assert not any(ref.startswith("export-") for ref in save_result.artifact_refs)
    assert not any(path.name.startswith("export-") for path in (tmp_path / "artifacts").rglob("*"))


def test_document_save_removes_destination_hardlink_to_temp_when_publish_blocks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)
    runtime, derivative_artifact_id = _prepared_derivative(source, tmp_path, "dest-hardlink")
    destination = tmp_path / "exports" / "citizen-final.docx"
    original_link = document_registry.os.link
    attack_triggered = False

    def precreate_destination_hardlink_then_link(
        source_path: Path | str,
        destination_path: Path | str,
        *args: object,
        **kwargs: object,
    ) -> None:
        nonlocal attack_triggered
        if not attack_triggered and Path(destination_path).name == destination.name:
            attack_triggered = True
            original_link(source_path, destination_path, *args, **kwargs)
        original_link(source_path, destination_path, *args, **kwargs)

    monkeypatch.setattr(document_registry.os, "link", precreate_destination_hardlink_then_link)

    save_result = runtime.save(
        DocumentSaveRequest(
            correlation_id="dest-hardlink-export-save",
            document=DocumentLocator(artifact_id=derivative_artifact_id),
            destination_display_name=destination.name,
            destination_path=str(destination),
        )
    )

    assert attack_triggered is True
    assert save_result.status is ToolResultStatus.blocked
    assert save_result.blocked_reason == "validation_failed"
    assert not destination.exists()
    assert not save_result.saved_exports
    assert not any(ref.startswith("export-") for ref in save_result.artifact_refs)
    assert not any(path.name.startswith("export-") for path in (tmp_path / "artifacts").rglob("*"))


def test_document_save_blocks_temp_entry_replaced_by_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)
    runtime, derivative_artifact_id = _prepared_derivative(source, tmp_path, "temp-directory")
    destination = tmp_path / "exports" / "citizen-final.docx"
    original_link = document_registry.os.link
    attack_triggered = False

    def replace_temp_with_directory_then_link(
        source_path: Path | str,
        destination_path: Path | str,
        *args: object,
        **kwargs: object,
    ) -> None:
        nonlocal attack_triggered
        if not attack_triggered and Path(destination_path).name == destination.name:
            attack_triggered = True
            parent_fd = kwargs["src_dir_fd"]
            assert isinstance(parent_fd, int)
            source_name = Path(source_path).name
            document_registry.os.unlink(source_name, dir_fd=parent_fd)
            document_registry.os.mkdir(source_name, 0o700, dir_fd=parent_fd)
        original_link(source_path, destination_path, *args, **kwargs)

    monkeypatch.setattr(document_registry.os, "link", replace_temp_with_directory_then_link)

    save_result = runtime.save(
        DocumentSaveRequest(
            correlation_id="temp-directory-export-save",
            document=DocumentLocator(artifact_id=derivative_artifact_id),
            destination_display_name=destination.name,
            destination_path=str(destination),
        )
    )

    assert attack_triggered is True
    assert save_result.status is ToolResultStatus.blocked
    assert save_result.blocked_reason == "validation_failed"
    assert not destination.exists()
    assert not save_result.saved_exports
    assert not any(ref.startswith("export-") for ref in save_result.artifact_refs)
    assert not any(path.name.startswith("export-") for path in (tmp_path / "artifacts").rglob("*"))


def test_document_save_blocks_temp_entry_directory_before_publish_precheck(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)
    runtime, derivative_artifact_id = _prepared_derivative(source, tmp_path, "temp-precheck")
    destination = tmp_path / "exports" / "citizen-final.docx"
    original_entry_matches = document_registry._local_export_entry_matches_open_file
    attack_triggered = False

    def replace_temp_before_precheck(
        parent_fd: int,
        entry_name: str,
        file_fd: int,
    ) -> bool:
        nonlocal attack_triggered
        if not attack_triggered and entry_name.startswith(f".{destination.name}."):
            attack_triggered = True
            document_registry.os.unlink(entry_name, dir_fd=parent_fd)
            document_registry.os.mkdir(entry_name, 0o700, dir_fd=parent_fd)
        return original_entry_matches(parent_fd, entry_name, file_fd)

    monkeypatch.setattr(
        document_registry,
        "_local_export_entry_matches_open_file",
        replace_temp_before_precheck,
    )

    save_result = runtime.save(
        DocumentSaveRequest(
            correlation_id="temp-precheck-export-save",
            document=DocumentLocator(artifact_id=derivative_artifact_id),
            destination_display_name=destination.name,
            destination_path=str(destination),
        )
    )

    assert attack_triggered is True
    assert save_result.status is ToolResultStatus.blocked
    assert save_result.blocked_reason == "validation_failed"
    assert not destination.exists()
    assert not save_result.saved_exports
    assert not any(ref.startswith("export-") for ref in save_result.artifact_refs)
    assert not any(path.name.startswith("export-") for path in (tmp_path / "artifacts").rglob("*"))


def _prepared_derivative(
    source: Path,
    tmp_path: Path,
    correlation_prefix: str,
) -> tuple[DocumentToolRuntime, str]:
    runtime = _runtime(tmp_path)
    inspect_result = runtime.inspect(
        DocumentInspectRequest(
            correlation_id=f"{correlation_prefix}-export-inspect",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
        )
    )
    assert inspect_result.status is ToolResultStatus.ok
    source_artifact_id = next(
        ref for ref in inspect_result.artifact_refs if ref.startswith("source-")
    )
    copy_result = runtime.copy_for_edit(
        DocumentCopyForEditRequest(
            correlation_id=f"{correlation_prefix}-export-copy",
            document=DocumentLocator(artifact_id=source_artifact_id),
        )
    )
    assert copy_result.status is ToolResultStatus.ok
    working_artifact_id = next(
        ref for ref in copy_result.artifact_refs if ref.startswith("working-")
    )
    fill_result = runtime.apply_fill(
        DocumentApplyFillRequest(
            correlation_id=f"{correlation_prefix}-export-fill",
            document=DocumentLocator(artifact_id=working_artifact_id),
            patches=(
                DocumentFieldPatch(
                    target_path="/word/document.xml/field[applicant_name]",
                    value="Kim",
                ),
            ),
        )
    )
    assert fill_result.status is ToolResultStatus.ok
    derivative_artifact_id = next(
        ref for ref in fill_result.artifact_refs if ref.startswith("derivative-")
    )
    return runtime, derivative_artifact_id


def _runtime(tmp_path: Path) -> DocumentToolRuntime:
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(LocalExportDocxEngine())
    return DocumentToolRuntime(
        session_id="session-doc-local-export-source-path",
        artifact_root=tmp_path / "artifacts",
        engine_registry=engine_registry,
        baseline_catalog=_baseline_catalog(),
    )


def _write_minimal_docx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as package:
        package.writestr("[Content_Types].xml", "<Types/>")
        package.writestr("word/document.xml", "<w:document/>")


def _baseline_catalog() -> ConformanceBaselineCatalog:
    return ConformanceBaselineCatalog(
        version=1,
        catalog_id="document-local-export-safety",
        source_policy="offline_fixtures_only",
        live_network_allowed=False,
        baselines=(
            ConformanceBaseline(
                template_id="civil-form-docx",
                schema_id="civil-form-docx-local-export-v1",
                format=DocumentFormat.docx,
                authoritative_standard="ECMA-376 Office Open XML",
                authority_refs=("tests/tools/documents/test_document_local_export_safety.py",),
                supports_conformance=True,
                required_fields=(
                    BaselineField(
                        field_id="applicant_name",
                        label="Applicant name",
                        path="/word/document.xml/field[applicant_name]",
                    ),
                ),
                protected_text=(
                    BaselineTextAnchor(
                        text="Application extracted from derivative-source-path-export-fill.docx",
                        anchor="/word/document.xml/p[1]",
                    ),
                ),
                table_geometries=(
                    BaselineTableGeometry(
                        table_id="table-001",
                        anchor="/word/document.xml/tbl[1]",
                        rows=1,
                        columns=1,
                    ),
                ),
            ),
        ),
    )
