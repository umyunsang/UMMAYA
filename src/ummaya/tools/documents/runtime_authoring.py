# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from ummaya.tools.documents.adapter_registry import (
    DocumentAdapterRegistry,
    UnsupportedDocumentAdapterError,
)
from ummaya.tools.documents.authoring import hash_authoring_text
from ummaya.tools.documents.conversion import (
    DocumentConversionRegistry,
    UnsupportedDocumentConversionError,
)
from ummaya.tools.documents.models import (
    BlockedReason,
    DocumentArtifact,
    DocumentExtraction,
    DocumentFormat,
    DocumentToolResult,
)
from ummaya.tools.documents.runtime_authoring_bundle import (
    IssuedAuthoringDraft,
    approved_patch_bundle_matches_issued_draft,
    issued_authoring_bundle,
    issued_authoring_draft_id,
)
from ummaya.tools.documents.tool_defs import unsupported_document_tool_result

if TYPE_CHECKING:
    from ummaya.tools.documents.tool_defs import DocumentFieldPatch

_NARRATIVE_TERMS: Final[tuple[str, ...]] = (
    "자기소개",
    "지원동기",
    "성장과정",
    "사업계획",
    "계획",
    "경험",
    "수상",
    "문항",
    "motivation",
    "selfintro",
    "businessplan",
)


@dataclass(frozen=True, slots=True)
class EditableDerivativePreview:
    document_format: DocumentFormat
    extraction: DocumentExtraction


def preview_editable_derivative(
    source: DocumentArtifact,
    *,
    correlation_id: str,
    derivative_format: DocumentFormat,
    conversion_registry: DocumentConversionRegistry,
    adapter_registry: DocumentAdapterRegistry,
) -> EditableDerivativePreview | DocumentToolResult:
    try:
        engine = conversion_registry.require(source.format, derivative_format)
    except UnsupportedDocumentConversionError:
        return unsupported_document_tool_result(
            tool_id="document",
            correlation_id=correlation_id,
            artifact_refs=(source.artifact_id,),
            message=_missing_conversion_message(source.format, derivative_format),
        )
    try:
        payload = engine.convert_for_edit(source)
    except ValueError as exc:
        return unsupported_document_tool_result(
            tool_id="document",
            correlation_id=correlation_id,
            artifact_refs=(source.artifact_id,),
            message=f"Document conversion failed before authoring planning: {exc}",
            reason=BlockedReason.validation_failed,
        )
    try:
        adapter = adapter_registry.require_promoted(derivative_format)
    except UnsupportedDocumentAdapterError:
        return unsupported_document_tool_result(
            tool_id="document",
            correlation_id=correlation_id,
            artifact_refs=(source.artifact_id,),
            message=(
                f"No promoted {derivative_format.value} adapter is registered for "
                "authoring planning."
            ),
        )
    with tempfile.TemporaryDirectory(prefix="ummaya-authoring-preview-") as temp_root:
        preview_path = Path(temp_root) / f"preview.{derivative_format.value}"
        preview_path.write_bytes(payload)
        extraction = adapter.inspect(preview_path, artifact_id=correlation_id)
    return EditableDerivativePreview(document_format=derivative_format, extraction=extraction)


def unapproved_narrative_patch_targets(
    patches: tuple[DocumentFieldPatch, ...],
    *,
    extraction: DocumentExtraction | None,
    approved_draft_id: str | None,
    approved_draft_sha256: str | None,
    issued_drafts: tuple[IssuedAuthoringDraft, ...],
) -> tuple[str, ...]:
    narrative_patches = _string_narrative_patches(patches, extraction=extraction)
    if approved_patch_bundle_matches_issued_draft(
        narrative_patches,
        approved_draft_id=approved_draft_id,
        approved_draft_sha256=approved_draft_sha256,
        issued_drafts=issued_drafts,
    ):
        return ()
    blocked_targets: list[str] = []
    for patch in patches:
        if not _patch_targets_narrative_content(patch, extraction=extraction):
            continue
        if _approved_patch_matches_issued_draft(
            patch,
            approved_draft_id=approved_draft_id,
            approved_draft_sha256=approved_draft_sha256,
            issued_drafts=issued_drafts,
        ):
            continue
        blocked_targets.append(patch.target_path)
    return tuple(blocked_targets)


def issue_authoring_drafts_for_unapproved_patches(
    patches: tuple[DocumentFieldPatch, ...],
    *,
    extraction: DocumentExtraction | None,
) -> tuple[IssuedAuthoringDraft, ...]:
    drafts: list[IssuedAuthoringDraft] = []
    narrative_patches: list[DocumentFieldPatch] = []
    for patch in patches:
        if not isinstance(patch.value, str):
            continue
        if not _patch_targets_narrative_content(patch, extraction=extraction):
            continue
        narrative_patches.append(patch)
        draft_sha256 = hash_authoring_text(patch.value)
        drafts.append(
            IssuedAuthoringDraft(
                draft_id=issued_authoring_draft_id(
                    target_path=patch.target_path,
                    draft_sha256=draft_sha256,
                ),
                target_path=patch.target_path,
                draft_sha256=draft_sha256,
                target_paths=(patch.target_path,),
            )
        )
    if len(narrative_patches) > 1:
        return (issued_authoring_bundle(tuple(narrative_patches)), *drafts)
    return tuple(drafts)


def _approved_patch_matches_issued_draft(
    patch: DocumentFieldPatch,
    *,
    approved_draft_id: str | None,
    approved_draft_sha256: str | None,
    issued_drafts: tuple[IssuedAuthoringDraft, ...],
) -> bool:
    if not isinstance(patch.value, str):
        return False
    if approved_draft_id is None or approved_draft_sha256 is None:
        return False
    if hash_authoring_text(patch.value) != approved_draft_sha256:
        return False
    for draft in issued_drafts:
        if (
            draft.draft_id == approved_draft_id
            and draft.target_path == patch.target_path
            and draft.draft_sha256 == approved_draft_sha256
        ):
            return True
    return False


def _string_narrative_patches(
    patches: tuple[DocumentFieldPatch, ...],
    *,
    extraction: DocumentExtraction | None,
) -> tuple[DocumentFieldPatch, ...]:
    return tuple(
        patch
        for patch in patches
        if isinstance(patch.value, str)
        and _patch_targets_narrative_content(patch, extraction=extraction)
    )


def _patch_targets_narrative_content(
    patch: DocumentFieldPatch,
    *,
    extraction: DocumentExtraction | None,
) -> bool:
    patch_key = _normalize_authoring_key(patch.target_path)
    if extraction is None:
        return _has_narrative_term(patch_key)
    for field in extraction.fields:
        field_keys = {
            _normalize_authoring_key(field.field_id),
            _normalize_authoring_key(field.label),
            _normalize_authoring_key(field.path),
        }
        if patch_key not in field_keys:
            continue
        return any(_has_narrative_term(field_key) for field_key in field_keys)
    return _has_narrative_term(patch_key)


def _has_narrative_term(value: str) -> bool:
    return any(term in value for term in _NARRATIVE_TERMS)


def _normalize_authoring_key(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _missing_conversion_message(
    source_format: DocumentFormat,
    derivative_format: DocumentFormat,
) -> str:
    if source_format is DocumentFormat.hwp:
        return (
            "HWP binary direct writing is blocked. HWP to HWPX conversion is "
            "required before editing legacy HWP files. Direct HWP binary working "
            "copies remain blocked. Use a HWPX or DOCX editable template, or "
            "register a vetted local HWP to HWPX conversion engine."
        )
    return (
        f"Document conversion is required before planning edits for "
        f"{source_format.value} files, but no promoted "
        f"{source_format.value}->{derivative_format.value} conversion engine is registered."
    )
