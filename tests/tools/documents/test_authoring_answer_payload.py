# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_authoring_verdict_serializes_collected_user_answers() -> None:
    from ummaya.tools.documents.authoring import (
        AuthoringClosureVerdict,
        AuthoringEvidenceItem,
        AuthoringState,
        EvidenceSourceKind,
        SocraticQuestion,
        UserAnswer,
    )

    evidence = AuthoringEvidenceItem(
        evidence_id="evidence-team-leadership",
        source_kind=EvidenceSourceKind.user_provided,
        summary="공모전에서 팀 리더로 일정과 역할을 조율했습니다.",
    )
    question = SocraticQuestion(
        question_id="question-team-leadership",
        target_id="self_intro.motivation",
        prompt="지원동기를 뒷받침할 구체적인 경험은 무엇인가요?",
        required=True,
    )
    answer = UserAnswer(
        answer_id="answer-team-leadership",
        question_id=question.question_id,
        response_summary=evidence.summary,
        evidence_refs=(evidence.evidence_id,),
    )

    verdict = AuthoringClosureVerdict(
        state=AuthoringState.needs_input,
        target_id=question.target_id,
        evidence_items=(evidence,),
        questions=(question,),
        answers=(answer,),
    )

    encoded = verdict.model_dump(mode="json")

    assert encoded["answers"][0]["response_summary"] == evidence.summary


def test_authoring_verdict_rejects_answer_for_unknown_question() -> None:
    from ummaya.tools.documents.authoring import (
        AuthoringClosureVerdict,
        AuthoringEvidenceItem,
        AuthoringState,
        EvidenceSourceKind,
        SocraticQuestion,
        UserAnswer,
    )

    evidence = AuthoringEvidenceItem(
        evidence_id="evidence-business-plan",
        source_kind=EvidenceSourceKind.user_provided,
        summary="초기 고객 인터뷰 3건을 진행했습니다.",
    )
    question = SocraticQuestion(
        question_id="question-market",
        target_id="business_plan.market",
        prompt="시장 검증 근거를 알려주세요.",
        required=True,
    )
    answer = UserAnswer(
        answer_id="answer-unknown",
        question_id="question-missing",
        response_summary=evidence.summary,
        evidence_refs=(evidence.evidence_id,),
    )

    with pytest.raises(ValidationError, match="answers must reference known questions"):
        AuthoringClosureVerdict(
            state=AuthoringState.needs_input,
            target_id=question.target_id,
            evidence_items=(evidence,),
            questions=(question,),
            answers=(answer,),
        )
