# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import io
import re
import zipfile
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ummaya.tools.documents.authoring import hash_authoring_text
from ummaya.tools.documents.conversion import DocumentConversionRegistry
from ummaya.tools.documents.engines import DocumentEngineRegistry, DocumentInspectionEngine
from ummaya.tools.documents.models import (
    DocumentArtifact,
    DocumentExtraction,
    DocumentFormat,
    DocumentPatch,
    FormField,
    ToolResultStatus,
)
from ummaya.tools.documents.registry import DocumentToolRuntime
from ummaya.tools.documents.tool_defs import (
    DocumentFieldPatch,
    DocumentLocator,
    DocumentPrimitiveRequest,
)


class NarrativeDocxEngine:
    document_format = DocumentFormat.docx
    engine_id = "narrative-docx-engine"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        return DocumentExtraction(
            artifact_id=artifact_id,
            fields=[
                FormField(
                    field_id="self_intro_motivation",
                    label="자기소개서 지원동기 문항",
                    path="/word/document.xml/field[self_intro_motivation]",
                    field_type="text",
                    required=True,
                    current_value=None,
                    source_confidence=Decimal("1"),
                ),
            ],
            metadata={"engine_id": self.engine_id},
        )

    def apply_patch(self, path: Path, patch: DocumentPatch) -> bytes:
        return path.read_bytes() + f"\npatched:{len(patch.operations)}".encode()

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        return (f"render:{artifact_id}:{path.name}".encode(),)


class NeutralPathNarrativeDocxEngine:
    document_format = DocumentFormat.docx
    engine_id = "neutral-path-narrative-docx-engine"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        return DocumentExtraction(
            artifact_id=artifact_id,
            fields=[
                FormField(
                    field_id="field_0",
                    label="자기소개서 지원동기 문항",
                    path="/word/document.xml/field[0]",
                    field_type="text",
                    required=True,
                    current_value=None,
                    source_confidence=Decimal("1"),
                ),
            ],
            metadata={"engine_id": self.engine_id},
        )

    def apply_patch(self, path: Path, patch: DocumentPatch) -> bytes:
        return path.read_bytes() + f"\npatched:{len(patch.operations)}".encode()

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        return (f"render:{artifact_id}:{path.name}".encode(),)


class LegacyDocToDocxConversion:
    source_format = DocumentFormat.doc
    output_format = DocumentFormat.docx
    engine_id = "legacy-doc-to-docx-test-conversion"

    def convert_for_edit(self, source: DocumentArtifact) -> bytes:
        _ = source
        return _minimal_docx_bytes()


def test_document_runtime_returns_needs_input_before_derivative_for_unsupported_broad_fill(
    tmp_path: Path,
) -> None:
    source = tmp_path / "self-intro.doc"
    source.write_bytes(b"legacy-doc")
    runtime = _runtime(tmp_path)

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="corr-authoring-needs-input",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.doc),
            operation="fill",
            instruction="이 자기소개서 양식을 문서 내용에 맞게 알아서 작성해줘.",
        )
    )

    assert result.status is ToolResultStatus.needs_input
    assert result.artifact_refs == ["source-corr-authoring-needs-input"]
    assert "self_intro_motivation" in result.text_summary
    assert not any(artifact_id.startswith("working-") for artifact_id in runtime._artifacts)
    assert not any(artifact_id.startswith("derivative-") for artifact_id in runtime._artifacts)
    assert not (tmp_path / "artifacts" / "session-authoring-runtime" / "working_copy").exists()


def test_document_runtime_does_not_apply_unapproved_narrative_answer(
    tmp_path: Path,
) -> None:
    source = tmp_path / "business-plan.doc"
    source.write_bytes(b"legacy-doc")
    runtime = _runtime(tmp_path)

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="corr-authoring-no-approval",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.doc),
            operation="fill",
            instruction="자기소개서 지원동기 문항을 작성해줘.",
        )
    )

    assert result.status is ToolResultStatus.needs_input
    assert result.saved_exports == ()
    assert result.diff is None
    assert not any(artifact_id.startswith("derivative-") for artifact_id in runtime._artifacts)


def test_document_runtime_blocks_unapproved_legacy_narrative_patch_after_preview(
    tmp_path: Path,
) -> None:
    source = tmp_path / "legacy-self-intro.doc"
    source.write_bytes(b"legacy-doc")
    runtime = _runtime(tmp_path, engine=NeutralPathNarrativeDocxEngine())

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="corr-authoring-legacy-explicit-unapproved",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.doc),
            operation="fill",
            instruction="자기소개서 지원동기 문항 초안을 반영해줘.",
            patches=(
                DocumentFieldPatch(
                    target_path="/word/document.xml/field[0]",
                    value="승인되지 않은 지원 동기 초안입니다.",
                ),
            ),
        )
    )

    assert result.status is ToolResultStatus.needs_input
    assert not any(artifact_id.startswith("working-") for artifact_id in runtime._artifacts)
    assert not any(artifact_id.startswith("derivative-") for artifact_id in runtime._artifacts)


def test_document_request_rejects_partial_authoring_approval_metadata(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError, match="approved draft id and sha256"):
        DocumentPrimitiveRequest(
            correlation_id="corr-authoring-partial-approval",
            document=DocumentLocator(
                path=str(tmp_path / "self-intro.docx"),
                expected_format=DocumentFormat.docx,
            ),
            operation="fill",
            instruction="승인한 자기소개서 초안을 반영해줘.",
            approved_draft_id="draft-self-intro-motivation",
        )


def test_document_runtime_rejects_matching_hash_without_issued_draft_id(
    tmp_path: Path,
) -> None:
    source = tmp_path / "self-intro-bypass.docx"
    _write_minimal_docx(source)
    draft_text = "사용자가 승인하지 않았지만 해시만 맞춘 지원 동기 초안입니다."
    target_path = "/word/document.xml/field[self_intro_motivation]"
    runtime = _runtime(tmp_path)

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="corr-authoring-approval-bypass",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
            operation="fill",
            instruction="승인한 자기소개서 지원동기 문항 초안을 반영해줘.",
            patches=(DocumentFieldPatch(target_path=target_path, value=draft_text),),
            approved_draft_id="never-issued-by-runtime",
            approved_draft_sha256=hash_authoring_text(draft_text),
        )
    )

    assert result.status is ToolResultStatus.needs_input
    assert "approved draft" in result.text_summary
    assert not any(artifact_id.startswith("derivative-") for artifact_id in runtime._artifacts)


def test_document_runtime_applies_approved_draft_to_derivative_only_after_approval(
    tmp_path: Path,
) -> None:
    source = tmp_path / "self-intro-approved.docx"
    _write_minimal_docx(source)
    draft_text = "사용자가 승인한 지원 동기 초안입니다."
    target_path = "/word/document.xml/field[self_intro_motivation]"

    unapproved_runtime = _runtime(tmp_path / "unapproved")
    unapproved = unapproved_runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="corr-authoring-unapproved-draft",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
            operation="fill",
            instruction="자기소개서 지원동기 문항 초안을 반영해줘.",
            patches=(DocumentFieldPatch(target_path=target_path, value=draft_text),),
        )
    )

    assert unapproved.status is ToolResultStatus.needs_input
    assert not any(
        artifact_id.startswith("derivative-") for artifact_id in unapproved_runtime._artifacts
    )

    approval_token = re.search(r"approved_draft_id=([A-Za-z0-9_.-]+)", unapproved.text_summary)
    assert approval_token is not None
    approved = unapproved_runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="corr-authoring-approved-draft",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.docx),
            operation="fill",
            instruction="승인한 자기소개서 지원동기 문항 초안을 반영해줘.",
            patches=(DocumentFieldPatch(target_path=target_path, value=draft_text),),
            approved_draft_id=approval_token.group(1),
            approved_draft_sha256=hash_authoring_text(draft_text),
        )
    )

    assert approved.status is ToolResultStatus.ok
    assert any(
        artifact_id.startswith("derivative-") for artifact_id in unapproved_runtime._artifacts
    )
    assert approved.diff is not None
    assert approved.diff.changes[0].after_value == draft_text


def _runtime(
    tmp_path: Path,
    *,
    engine: DocumentInspectionEngine | None = None,
) -> DocumentToolRuntime:
    engine_registry = DocumentEngineRegistry()
    engine_registry.register(engine or NarrativeDocxEngine())
    conversion_registry = DocumentConversionRegistry()
    conversion_registry.register(LegacyDocToDocxConversion())
    return DocumentToolRuntime(
        session_id="session-authoring-runtime",
        artifact_root=tmp_path / "artifacts",
        engine_registry=engine_registry,
        conversion_registry=conversion_registry,
        enable_default_pdfa_conformance_bridge=False,
    )


def _write_minimal_docx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as package:
        package.writestr("[Content_Types].xml", "<Types/>")
        package.writestr("word/document.xml", "<w:document/>")


def _minimal_docx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as package:
        package.writestr("[Content_Types].xml", "<Types/>")
        package.writestr("word/document.xml", "<w:document/>")
    return buffer.getvalue()
