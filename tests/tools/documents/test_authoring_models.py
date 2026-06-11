# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_document_authoring_models_require_evidence_and_approval_hashes() -> None:
    from ummaya.tools.documents.authoring import (
        ApprovalDecision,
        ApprovalDecisionKind,
        AuthoringClosureVerdict,
        AuthoringEvidenceItem,
        AuthoringState,
        DraftCandidate,
        DraftClaim,
        EvidenceSourceKind,
        SocraticQuestion,
        hash_authoring_text,
    )

    evidence = AuthoringEvidenceItem(
        evidence_id="evidence-user-001",
        source_kind=EvidenceSourceKind.user_provided,
        summary="사용자가 창업 경험을 제공했다.",
        source_ref="turn-4.answer-1",
    )
    question = SocraticQuestion(
        question_id="question-plan-001",
        target_id="business_plan.market",
        prompt="시장 규모 근거를 알려주세요.",
        required=True,
    )
    claim = DraftClaim(
        claim_id="claim-market-001",
        text="사용자가 제공한 창업 경험을 바탕으로 시장 진입 계획을 설명한다.",
        evidence_refs=("evidence-user-001",),
    )
    draft_text = "창업 경험을 바탕으로 시장 진입 계획을 작성합니다."
    draft = DraftCandidate(
        draft_id="draft-business-plan-001",
        target_id="business_plan.market",
        draft_text=draft_text,
        draft_sha256=hash_authoring_text(draft_text),
        claims=(claim,),
    )
    approval = ApprovalDecision(
        approval_id="approval-business-plan-001",
        draft_id=draft.draft_id,
        decision=ApprovalDecisionKind.approved,
        draft_sha256=draft.draft_sha256,
        approved_text_sha256=draft.draft_sha256,
    )

    verdict = AuthoringClosureVerdict(
        state=AuthoringState.approved_for_mutation,
        target_id=draft.target_id,
        evidence_items=(evidence,),
        questions=(question,),
        draft=draft,
        approval=approval,
    )

    assert verdict.state is AuthoringState.approved_for_mutation
    assert verdict.approval is approval
    assert verdict.draft is draft

    with pytest.raises(ValidationError, match="approved_for_mutation requires approval"):
        AuthoringClosureVerdict(
            state=AuthoringState.approved_for_mutation,
            target_id=draft.target_id,
            evidence_items=(evidence,),
            questions=(question,),
            draft=draft,
        )


def test_document_authoring_models_reject_approved_claim_without_evidence() -> None:
    from ummaya.tools.documents.authoring import (
        AuthoringEvidenceItem,
        DraftCandidate,
        DraftClaim,
        EvidenceSourceKind,
        hash_authoring_text,
    )

    evidence = AuthoringEvidenceItem(
        evidence_id="evidence-user-001",
        source_kind=EvidenceSourceKind.user_provided,
        summary="사용자가 프로젝트 경험을 제공했다.",
        source_ref="turn-2.answer-1",
    )
    unsupported_claim = DraftClaim(
        claim_id="claim-unsupported-001",
        text="지원자는 전국 대회에서 수상했다.",
        evidence_refs=("missing-evidence",),
    )
    draft_text = "전국 대회 수상 경험을 설명합니다."

    with pytest.raises(ValidationError, match="unknown evidence reference"):
        DraftCandidate(
            draft_id="draft-self-intro-001",
            target_id="self_intro.awards",
            draft_text=draft_text,
            draft_sha256=hash_authoring_text(draft_text),
            claims=(unsupported_claim,),
            evidence_items=(evidence,),
        )


def test_document_authoring_models_reject_approved_mutation_with_cancel_decision() -> None:
    from ummaya.tools.documents.authoring import (
        ApprovalDecision,
        ApprovalDecisionKind,
        AuthoringClosureVerdict,
        AuthoringEvidenceItem,
        AuthoringState,
        DraftCandidate,
        DraftClaim,
        EvidenceSourceKind,
        SocraticQuestion,
        hash_authoring_text,
    )

    evidence = AuthoringEvidenceItem(
        evidence_id="evidence-user-approval",
        source_kind=EvidenceSourceKind.user_provided,
        summary="사용자가 프로젝트 경험을 제공했다.",
    )
    claim = DraftClaim(
        claim_id="claim-project-approval",
        text="사용자 제공 경험만 설명한다.",
        evidence_refs=(evidence.evidence_id,),
    )
    draft_text = "사용자 제공 경험만 바탕으로 초안을 작성합니다."
    draft = DraftCandidate(
        draft_id="draft-project-approval",
        target_id="self_intro.project",
        draft_text=draft_text,
        draft_sha256=hash_authoring_text(draft_text),
        claims=(claim,),
    )
    question = SocraticQuestion(
        question_id="question-project-approval",
        target_id=draft.target_id,
        prompt="프로젝트 경험 근거를 알려주세요.",
        required=True,
    )
    cancel_decision = ApprovalDecision(
        approval_id="approval-project-cancel",
        draft_id=draft.draft_id,
        decision=ApprovalDecisionKind.cancel,
        draft_sha256=draft.draft_sha256,
    )

    with pytest.raises(ValidationError, match="approved_for_mutation requires an approval"):
        AuthoringClosureVerdict(
            state=AuthoringState.approved_for_mutation,
            target_id=draft.target_id,
            evidence_items=(evidence,),
            questions=(question,),
            draft=draft,
            approval=cancel_decision,
        )


def test_document_authoring_models_require_approved_text_hash_for_approval() -> None:
    from ummaya.tools.documents.authoring import (
        ApprovalDecision,
        ApprovalDecisionKind,
        hash_authoring_text,
    )

    draft_sha256 = hash_authoring_text("사용자 제공 근거만 반영한 초안입니다.")

    with pytest.raises(ValidationError, match="approved decisions require approved_text_sha256"):
        ApprovalDecision(
            approval_id="approval-missing-approved-hash",
            draft_id="draft-missing-approved-hash",
            decision=ApprovalDecisionKind.approved,
            draft_sha256=draft_sha256,
        )


def test_document_authoring_models_reject_blank_decision_with_approved_hash() -> None:
    from ummaya.tools.documents.authoring import (
        ApprovalDecision,
        ApprovalDecisionKind,
        hash_authoring_text,
    )

    draft_sha256 = hash_authoring_text("빈칸으로 두기로 한 초안입니다.")

    with pytest.raises(
        ValidationError,
        match="blank or cancel decisions cannot carry approved_text_sha256",
    ):
        ApprovalDecision(
            approval_id="approval-blank-with-approved-hash",
            draft_id="draft-blank-with-approved-hash",
            decision=ApprovalDecisionKind.leave_blank,
            draft_sha256=draft_sha256,
            approved_text_sha256=draft_sha256,
        )


def test_document_authoring_models_reject_waiting_state_with_draft() -> None:
    from ummaya.tools.documents.authoring import (
        AuthoringClosureVerdict,
        AuthoringEvidenceItem,
        AuthoringState,
        DraftCandidate,
        DraftClaim,
        EvidenceSourceKind,
        SocraticQuestion,
        hash_authoring_text,
    )

    evidence = AuthoringEvidenceItem(
        evidence_id="evidence-waiting-001",
        source_kind=EvidenceSourceKind.user_provided,
        summary="사용자가 일부 근거만 제공했다.",
    )
    claim = DraftClaim(
        claim_id="claim-waiting-001",
        text="아직 승인되지 않은 초안이다.",
        evidence_refs=(evidence.evidence_id,),
    )
    draft_text = "질문 대기 상태에서는 이 초안을 들고 있으면 안 됩니다."
    draft = DraftCandidate(
        draft_id="draft-waiting-001",
        target_id="business_plan.market",
        draft_text=draft_text,
        draft_sha256=hash_authoring_text(draft_text),
        claims=(claim,),
    )
    question = SocraticQuestion(
        question_id="question-waiting-001",
        target_id=draft.target_id,
        prompt="시장 규모 근거를 알려주세요.",
        required=True,
    )

    with pytest.raises(ValidationError, match="cannot carry draft"):
        AuthoringClosureVerdict(
            state=AuthoringState.blocked_missing_evidence,
            target_id=draft.target_id,
            evidence_items=(evidence,),
            questions=(question,),
            draft=draft,
        )


def test_document_authoring_result_payload_exposes_machine_readable_states() -> None:
    from ummaya.tools.documents.authoring import (
        AuthoringClosureVerdict,
        AuthoringState,
        DocumentAuthoringResult,
        SocraticQuestion,
    )
    from ummaya.tools.documents.models import ToolResultStatus

    question = SocraticQuestion(
        question_id="question-result-state",
        target_id="self_intro.motivation",
        prompt="지원 동기 근거를 알려주세요.",
        required=True,
    )
    verdict = AuthoringClosureVerdict(
        state=AuthoringState.needs_input,
        target_id="self_intro.motivation",
        questions=(question,),
    )

    result = DocumentAuthoringResult(
        tool_id="document",
        correlation_id="corr-authoring-state",
        status=ToolResultStatus.needs_input,
        text_summary="Authoring needs user evidence.",
        authoring=verdict,
    )
    encoded = result.model_dump(mode="json")

    assert encoded["status"] == "needs_input"
    assert encoded["authoring"]["state"] == "needs_input"
    assert encoded["authoring"]["questions"][0]["question_id"] == "question-result-state"

    with pytest.raises(ValidationError, match="needs_input authoring results require status"):
        DocumentAuthoringResult(
            tool_id="document",
            correlation_id="corr-authoring-state-stale",
            status=ToolResultStatus.ok,
            text_summary="Stale success status must not mask a question.",
            authoring=verdict,
        )
