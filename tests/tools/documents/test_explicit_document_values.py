# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from decimal import Decimal

from ummaya.tools.documents.explicit_values import explicit_keyed_value_for_label
from ummaya.tools.documents.models import (
    DocumentExtraction,
    DocumentFormat,
    DocumentIR,
    FormSlot,
    SourceAnchor,
)
from ummaya.tools.documents.planner import plan_autonomous_fill


def test_approval_sentence_with_quoted_korean_values_maps_each_label() -> None:
    document_ir = DocumentIR(
        artifact_id="artifact-business-plan",
        document_format=DocumentFormat.docx,
        extraction=DocumentExtraction(artifact_id="artifact-business-plan"),
        form_slots=(
            _slot("brand", "기업 및 브랜드명"),
            _slot("task", "디자인과제"),
            _slot("solution", "디자인 제안 및 해결 방안"),
            _slot("exhibit", "전시계획안"),
        ),
    )

    plan = plan_autonomous_fill(
        document_ir,
        instruction=(
            "초안을 승인해. 검토용 복사본을 /tmp/ummaya-task8-plan.docx 로 저장해줘. "
            '기업 및 브랜드명에는 "UMMAYA 공공문서 자동작성 고도화", '
            '디자인과제에는 "사용자가 제출 양식의 빈칸을 안전하게 채울 수 있게 '
            '돕는 문서 자동화 도구", '
            '디자인 제안 및 해결 방안에는 "문서 자동화 테스트, 증거 수집, '
            '렌더 비교 파이프라인을 통해 작성 근거와 결과를 검증하는 방식", '
            '전시계획안에는 "사용자가 원본과 검토용 복사본의 차이를 확인하고 '
            '승인할 수 있게 보여주는 흐름"만 넣어. '
            "원본은 건드리지 마."
        ),
    )

    assert {slot.label: slot.candidate_value for slot in plan.slots} == {
        "기업 및 브랜드명": "UMMAYA 공공문서 자동작성 고도화",
        "디자인과제": ("사용자가 제출 양식의 빈칸을 안전하게 채울 수 있게 돕는 문서 자동화 도구"),
        "디자인 제안 및 해결 방안": (
            "문서 자동화 테스트, 증거 수집, 렌더 비교 파이프라인을 통해 "
            "작성 근거와 결과를 검증하는 방식"
        ),
        "전시계획안": (
            "사용자가 원본과 검토용 복사본의 차이를 확인하고 승인할 수 있게 보여주는 흐름"
        ),
    }


def test_multiline_document_label_matches_spaced_user_label() -> None:
    instruction = (
        '디자인 제안 및 해결 방안에는 "문서 자동화 테스트, 증거 수집, '
        '렌더 비교 파이프라인을 통해 작성 근거와 결과를 검증하는 방식"만 넣어.'
    )

    value = explicit_keyed_value_for_label("디자인\n제안 및 \n해결 방안", instruction)

    assert value == (
        "문서 자동화 테스트, 증거 수집, 렌더 비교 파이프라인을 통해 "
        "작성 근거와 결과를 검증하는 방식"
    )


def test_quoted_korean_value_preserves_euro_command_like_phrase() -> None:
    instruction = (
        '디자인 제안 및 해결 방안은 "질문 루프, 증거 수집, 렌더 비교, '
        '재읽기 검증으로 작성 근거와 결과를 확인하는 방식"만 넣어.'
    )

    value = explicit_keyed_value_for_label("디자인\n제안 및 \n해결 방안", instruction)

    assert value == (
        "질문 루프, 증거 수집, 렌더 비교, 재읽기 검증으로 작성 근거와 결과를 확인하는 방식"
    )


def test_quoted_value_label_with_value_suffix_maps_to_label() -> None:
    instruction = '지원동기 값: "공공 문서 자동화 도구 개발 지원동기 초안입니다."'

    value = explicit_keyed_value_for_label("지원동기", instruction)

    assert value == "공공 문서 자동화 도구 개발 지원동기 초안입니다."


def test_unquoted_korean_value_drops_autonomous_command_tail() -> None:
    value = explicit_keyed_value_for_label(
        "팀명",
        "문서 내용을 파악하고 팀명은 GovOn-HWP로 알아서 작성해.",
    )

    assert value == "GovOn-HWP"


def _slot(slot_id: str, label: str) -> FormSlot:
    return FormSlot(
        slot_id=slot_id,
        label=label,
        field_type="text",
        required=False,
        current_value="",
        source_anchor=SourceAnchor(
            format_path=f"/{slot_id}",
            confidence=Decimal("1"),
            engine_id="test-ir-engine",
        ),
        confidence=Decimal("1"),
    )
