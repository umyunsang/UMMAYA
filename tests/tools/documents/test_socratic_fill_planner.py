# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from decimal import Decimal

from ummaya.tools.documents.models import (
    DocumentExtraction,
    DocumentFormat,
    DocumentIR,
    FormSlot,
    SourceAnchor,
)
from ummaya.tools.documents.planner import plan_autonomous_fill


def test_broad_form_fill_without_user_evidence_returns_questions() -> None:
    document_ir = DocumentIR(
        artifact_id="artifact-public-application",
        document_format=DocumentFormat.hwpx,
        extraction=DocumentExtraction(artifact_id="artifact-public-application"),
        form_slots=(
            _slot("business_name", label="상호(단체명)", format_path="/form/table[1]/r1c2"),
            _slot("business_plan", label="사업계획", format_path="/form/table[1]/r2c2"),
        ),
    )

    plan = plan_autonomous_fill(
        document_ir,
        instruction="문서 내용을 파악하고 내용에 맞게 알아서 채워줘.",
    )

    assert plan.requires_human_review is True
    assert {slot.slot_id for slot in plan.slots} == {"business_name", "business_plan"}
    assert set(plan.blocked_slot_ids) == {"business_name", "business_plan"}
    assert {slot.candidate_value for slot in plan.slots} == {None}
    assert all(slot.evidence_text is not None for slot in plan.slots)
    assert all(slot.evidence_text.startswith("needs_input:") for slot in plan.slots)


def test_plausible_write_request_without_evidence_is_blocked() -> None:
    document_ir = DocumentIR(
        artifact_id="artifact-self-intro",
        document_format=DocumentFormat.docx,
        extraction=DocumentExtraction(artifact_id="artifact-self-intro"),
        form_slots=(_slot("award_history", label="수상 경력", format_path="/word/paragraphs/3"),),
    )

    plan = plan_autonomous_fill(
        document_ir,
        instruction="대충 그럴듯하게 써줘.",
    )

    assert plan.requires_human_review is True
    assert plan.blocked_slot_ids == ("award_history",)
    assert plan.slots[0].candidate_value is None
    assert plan.slots[0].evidence_text is not None
    assert plan.slots[0].evidence_text.startswith("blocked_missing_evidence:")


def test_narrative_section_requires_user_answers_before_draft() -> None:
    document_ir = DocumentIR(
        artifact_id="artifact-self-intro-question",
        document_format=DocumentFormat.docx,
        extraction=DocumentExtraction(artifact_id="artifact-self-intro-question"),
        form_slots=(
            _slot(
                "self_intro_motivation",
                label="자기소개서 지원동기 문항",
                format_path="/word/paragraphs/5",
            ),
        ),
    )

    plan = plan_autonomous_fill(
        document_ir,
        instruction="자기소개서 문항을 작성해줘.",
    )

    assert plan.requires_human_review is True
    assert plan.blocked_slot_ids == ("self_intro_motivation",)
    assert plan.slots[0].candidate_value is None
    assert plan.slots[0].evidence_text is not None
    assert plan.slots[0].evidence_text.startswith("needs_input:")


def test_narrative_section_requires_draft_approval_before_patch() -> None:
    document_ir = DocumentIR(
        artifact_id="artifact-business-plan",
        document_format=DocumentFormat.docx,
        extraction=DocumentExtraction(artifact_id="artifact-business-plan"),
        form_slots=(
            _slot(
                "business_plan_market",
                label="사업계획 시장 진입 계획",
                format_path="/word/paragraphs/9",
            ),
        ),
    )

    plan = plan_autonomous_fill(
        document_ir,
        instruction="사업계획서 항목을 작성해줘.",
        session_context={
            "사업계획 시장 진입 계획": "공공데이터 민원 자동화 경험을 바탕으로 작성합니다."
        },
    )

    assert plan.requires_human_review is True
    assert plan.blocked_slot_ids == ("business_plan_market",)
    assert plan.slots[0].candidate_value is None
    assert plan.slots[0].evidence_text is not None
    assert plan.slots[0].evidence_text.startswith("draft_requires_approval:")


def _slot(slot_id: str, *, label: str, format_path: str) -> FormSlot:
    return FormSlot(
        slot_id=slot_id,
        label=label,
        field_type="text",
        required=True,
        protected=False,
        source_anchor=SourceAnchor(
            format_path=format_path,
            confidence=Decimal("0.95"),
            engine_id="test-ir-engine",
        ),
        current_value=None,
        confidence=Decimal("0.95"),
    )
