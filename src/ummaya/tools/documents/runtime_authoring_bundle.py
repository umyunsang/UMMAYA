# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING

from ummaya.tools.documents.authoring import hash_authoring_text

if TYPE_CHECKING:
    from ummaya.tools.documents.tool_defs import DocumentFieldPatch


@dataclass(frozen=True, slots=True)
class IssuedAuthoringDraft:
    draft_id: str
    target_path: str
    draft_sha256: str
    target_paths: tuple[str, ...] = ()


def issued_authoring_draft_id(*, target_path: str, draft_sha256: str) -> str:
    token = sha256(f"{target_path}\0{draft_sha256}".encode()).hexdigest()[:24]
    return f"draft-{token}"


def approved_patch_bundle_matches_issued_draft(
    patches: tuple[DocumentFieldPatch, ...],
    *,
    approved_draft_id: str | None,
    approved_draft_sha256: str | None,
    issued_drafts: tuple[IssuedAuthoringDraft, ...],
) -> bool:
    if len(patches) < 2 or approved_draft_id is None or approved_draft_sha256 is None:
        return False
    draft_sha256 = _authoring_bundle_sha256(patches)
    if draft_sha256 != approved_draft_sha256:
        return False
    target_paths = tuple(patch.target_path for patch in patches)
    return any(
        draft.draft_id == approved_draft_id
        and draft.draft_sha256 == approved_draft_sha256
        and draft.target_paths == target_paths
        for draft in issued_drafts
    )


def issued_authoring_bundle(
    patches: tuple[DocumentFieldPatch, ...],
) -> IssuedAuthoringDraft:
    target_paths = tuple(patch.target_path for patch in patches)
    draft_sha256 = _authoring_bundle_sha256(patches)
    bundle_target = _authoring_bundle_target_path(target_paths)
    return IssuedAuthoringDraft(
        draft_id=issued_authoring_draft_id(
            target_path=bundle_target,
            draft_sha256=draft_sha256,
        ),
        target_path=bundle_target,
        draft_sha256=draft_sha256,
        target_paths=target_paths,
    )


def _authoring_bundle_sha256(patches: tuple[DocumentFieldPatch, ...]) -> str:
    return hash_authoring_text(
        "\0".join(
            f"{patch.target_path}\0{hash_authoring_text(str(patch.value))}" for patch in patches
        )
    )


def _authoring_bundle_target_path(target_paths: tuple[str, ...]) -> str:
    token = sha256("\0".join(target_paths).encode()).hexdigest()[:24]
    return f"bundle:{token}"
