# SPDX-License-Identifier: Apache-2.0
"""Autonomous fill planner tests for public-document IR."""

from __future__ import annotations

from decimal import Decimal
from inspect import signature
from pathlib import Path
from typing import get_type_hints

from ummaya.tools.documents.formats.ooxml import PythonDocxDocumentEngine
from ummaya.tools.documents.models import (
    DocumentExtraction,
    DocumentFormat,
    DocumentIR,
    DocumentProtectedRange,
    FormField,
    FormSlot,
    ProtectedRangeCategory,
    SourceAnchor,
    TableBlock,
    TableCell,
)

_PUBLIC_FORM_FIXTURE_DIR = (
    Path(__file__).parents[2] / "fixtures" / "documents" / "public_forms" / "sources"
)
_SEOUL_CULTURE_DOCX = _PUBLIC_FORM_FIXTURE_DIR / "seoul-culture-application-plan.docx"
_SEOUL_DDP_DOCX = _PUBLIC_FORM_FIXTURE_DIR / "seoul-ddp-design-fair-application.docx"


def test_autonomous_fill_planner_consumes_ir_and_infers_next_week_values() -> None:
    from ummaya.tools.documents.planner import plan_autonomous_fill

    document_ir = DocumentIR(
        artifact_id="artifact-weekly-13",
        document_format=DocumentFormat.hwpx,
        extraction=_empty_extraction("artifact-weekly-13"),
        form_slots=(
            _slot(
                "week_label",
                label="주차",
                current_value="13주차",
                format_path="/body/section[1]/table[1]/cell[1,2]",
            ),
            _slot(
                "activity_period",
                label="활동기간",
                current_value="2026.06.01 ~ 2026.06.07",
                format_path="/body/section[1]/table[1]/cell[2,2]",
            ),
        ),
    )

    plan = plan_autonomous_fill(
        document_ir,
        instruction="문서 내용을 파악하고 알아서 다음 주차 활동일지로 작성해.",
    )

    assert plan.artifact_id == "artifact-weekly-13"
    assert plan.intent.operation == "fill"
    assert plan.requires_human_review is False
    slot_values = {slot.slot_id: slot.candidate_value for slot in plan.slots}
    assert slot_values == {
        "week_label": "14주차",
        "activity_period": "2026.06.08~2026.06.14",
    }
    assert plan.blocked_slot_ids == ()


def test_autonomous_fill_planner_blocks_protected_slots_and_accepts_only_ir() -> None:
    from ummaya.tools.documents.models import DocumentExtraction
    from ummaya.tools.documents.planner import plan_autonomous_fill

    planner_signature = signature(plan_autonomous_fill)
    type_hints = get_type_hints(plan_autonomous_fill)
    assert type_hints["document_ir"] is DocumentIR
    assert DocumentExtraction not in {
        parameter.annotation for parameter in planner_signature.parameters.values()
    }

    document_ir = DocumentIR(
        artifact_id="artifact-consent",
        document_format=DocumentFormat.hwpx,
        extraction=_empty_extraction("artifact-consent"),
        form_slots=(
            _slot(
                "consent_signature",
                label="서명",
                current_value=None,
                format_path="/body/section[1]/table[1]/cell[8,2]",
                field_type="signature",
                protected=True,
            ),
        ),
    )

    plan = plan_autonomous_fill(
        document_ir,
        instruction="개인정보 수집 이용 동의서를 내용 파악해서 서명까지 알아서 작성해.",
    )

    assert plan.requires_human_review is True
    assert plan.blocked_slot_ids == ("consent_signature",)
    assert plan.slots[0].candidate_value is None


def test_autonomous_fill_planner_strips_topic_particle_before_explicit_value() -> None:
    from ummaya.tools.documents.models import ParagraphBlock
    from ummaya.tools.documents.planner import plan_autonomous_fill

    extraction = DocumentExtraction(
        artifact_id="artifact-korean-particle",
        paragraphs=[
            ParagraphBlock(
                block_id="paragraph-applicant-name",
                text="신청인 성명",
                source_path="/body/section[1]/p[1]",
            ),
        ],
        fields=[
            FormField(
                field_id="applicant_name",
                label="신청인 성명",
                path="/body/section[1]/table[1]/cell[2,1]",
                field_type="text",
                required=True,
                current_value=None,
                source_confidence=Decimal("0.92"),
            ),
        ],
    )
    document_ir = DocumentIR.from_extraction(
        artifact_id="artifact-korean-particle",
        document_format=DocumentFormat.hwpx,
        extraction=extraction,
        engine_id="test-ir-engine",
    )

    plan = plan_autonomous_fill(
        document_ir,
        instruction="신청인 성명은 홍길동으로 입력해줘.",
    )

    assert plan.slots[0].candidate_value == "홍길동"


def test_autonomous_fill_planner_blocks_slots_matched_by_protected_ranges() -> None:
    from ummaya.tools.documents.planner import plan_autonomous_fill

    identity_anchor = SourceAnchor(
        format_path="/body/section[1]/table[1]/cell[5,2]",
        confidence=Decimal("0.98"),
        engine_id="test-ir-engine",
    )
    document_ir = DocumentIR(
        artifact_id="artifact-identity",
        document_format=DocumentFormat.hwpx,
        extraction=_empty_extraction("artifact-identity"),
        form_slots=(
            _slot(
                "resident_registration_number",
                label="주민등록번호",
                current_value=None,
                format_path=identity_anchor.format_path,
            ),
        ),
        protected_ranges=(
            DocumentProtectedRange(
                range_id="range-identity-number",
                category=ProtectedRangeCategory.identity_number,
                label="주민등록번호",
                source_anchor=identity_anchor,
                reason="Identity numbers require explicit review.",
            ),
        ),
    )

    plan = plan_autonomous_fill(
        document_ir,
        instruction="문서 내용을 파악해서 주민등록번호도 알아서 채워줘.",
    )

    assert plan.requires_human_review is True
    assert plan.blocked_slot_ids == ("resident_registration_number",)
    assert plan.slots[0].protected is True
    assert plan.slots[0].candidate_value is None


def test_document_ir_infers_blank_public_form_table_cells_as_slots() -> None:
    extraction = DocumentExtraction(
        artifact_id="artifact-public-table",
        fields=[
            FormField(
                field_id="label-business-name",
                label="상호(단체명)",
                path="/hwpx/text[21]",
                field_type="text",
                required=False,
                current_value="상호(단체명)",
                source_confidence=Decimal("1"),
            ),
            FormField(
                field_id="label-business-phone",
                label="사업장 전화번호",
                path="/hwpx/text[25]",
                field_type="text",
                required=False,
                current_value="(사업장 전화번호)",
                source_confidence=Decimal("1"),
            ),
        ],
        tables=[
            TableBlock(
                block_id="table-001",
                source_path="Contents/section0.xml#table[1]",
                cells=[
                    TableCell(
                        row_index=0,
                        column_index=0,
                        text="상호(단체명)",
                        source_path="Contents/section0.xml#table[1]/r1c1",
                        field_path="/hwpx/text[21]",
                    ),
                    TableCell(
                        row_index=0,
                        column_index=1,
                        text="",
                        source_path="Contents/section0.xml#table[1]/r1c2",
                    ),
                    TableCell(
                        row_index=0,
                        column_index=2,
                        text="(사업장 전화번호)",
                        source_path="Contents/section0.xml#table[1]/r1c3",
                        field_path="/hwpx/text[25]",
                    ),
                    TableCell(
                        row_index=0,
                        column_index=3,
                        text="",
                        source_path="Contents/section0.xml#table[1]/r1c4",
                    ),
                ],
            )
        ],
    )

    document_ir = DocumentIR.from_extraction(
        artifact_id="artifact-public-table",
        document_format=DocumentFormat.hwpx,
        extraction=extraction,
        engine_id="hwpx-package-text",
    )

    slots_by_path = {slot.source_anchor.format_path: slot for slot in document_ir.form_slots}
    assert slots_by_path["Contents/section0.xml#table[1]/r1c2"].label == "상호(단체명)"
    assert slots_by_path["Contents/section0.xml#table[1]/r1c2"].current_value == ""
    assert slots_by_path["Contents/section0.xml#table[1]/r1c4"].label == "사업장 전화번호"
    assert slots_by_path["Contents/section0.xml#table[1]/r1c4"].protected is True

    from ummaya.tools.documents.planner import plan_autonomous_fill

    plan = plan_autonomous_fill(
        document_ir,
        instruction="문서 내용을 파악하고 내용에 맞게 알아서 채워줘.",
    )

    planned_values = {slot.label: slot.candidate_value for slot in plan.slots}
    assert planned_values["상호(단체명)"] is None
    blocked_labels = {slot.label for slot in plan.slots if slot.slot_id in plan.blocked_slot_ids}
    assert "상호(단체명)" in blocked_labels
    assert "사업장 전화번호" in blocked_labels


def test_autonomous_fill_planner_ignores_unrequested_protected_ranges_for_explicit_field() -> None:
    from ummaya.tools.documents.planner import plan_autonomous_fill

    document_ir = DocumentIR(
        artifact_id="artifact-hwp-public-field",
        document_format=DocumentFormat.hwp,
        extraction=_empty_extraction("artifact-hwp-public-field"),
        form_slots=(
            _slot(
                "contest_name",
                label="대회명",
                current_value="기존 대회명",
                format_path="/hwp/table[1]/row[1]/cell[2]",
            ),
            _slot(
                "signature",
                label="서명",
                current_value="",
                format_path="/hwp/table[4]/row[5]/cell[2]",
            ),
        ),
        protected_ranges=(
            DocumentProtectedRange(
                range_id="range-signature",
                category=ProtectedRangeCategory.signature,
                label="서명",
                source_anchor=SourceAnchor(
                    format_path="/hwp/table[4]/row[5]/cell[2]",
                    confidence=Decimal("0.98"),
                    engine_id="test-ir-engine",
                ),
                reason="Signature requires explicit legal review.",
            ),
        ),
    )

    plan = plan_autonomous_fill(
        document_ir,
        instruction="대회명: 2026년 경기도 공공데이터·AI활용 창업경진대회 공공AX 테스트 로 갱신해.",
    )

    assert plan.requires_human_review is False
    assert plan.blocked_slot_ids == ()
    assert {slot.slot_id: slot.candidate_value for slot in plan.slots} == {
        "contest_name": "2026년 경기도 공공데이터·AI활용 창업경진대회 공공AX 테스트"
    }


def test_autonomous_fill_planner_deduplicates_noisy_hwpx_labels_for_explicit_field() -> None:
    from ummaya.tools.documents.planner import plan_autonomous_fill

    document_ir = DocumentIR(
        artifact_id="artifact-hwpx-noisy-labels",
        document_format=DocumentFormat.hwpx,
        extraction=_empty_extraction("artifact-hwpx-noisy-labels"),
        form_slots=(
            _slot(
                "hwpx-text-074",
                label="대회명",
                current_value="기존 대회명",
                format_path="/hwpx/text[74]",
            ),
            _slot(
                "hwpx-text-114",
                label="대회명",
                current_value="출품일자",
                format_path="/hwpx/text[114]",
            ),
            _slot(
                "hwpx-text-135",
                label="2",
                current_value="팀원",
                format_path="/hwpx/text[135]",
            ),
            _slot(
                "hwpx-text-227",
                label=":",
                current_value="엄윤상, 임재현",
                format_path="/hwpx/text[227]",
            ),
        ),
    )

    plan = plan_autonomous_fill(
        document_ir,
        instruction="대회명: 2026년 경기도 공공데이터·AI활용 창업경진대회 공공AX 테스트 로 갱신해.",
    )

    assert plan.requires_human_review is False
    assert [(slot.source_anchor.format_path, slot.candidate_value) for slot in plan.slots] == [
        ("/hwpx/text[74]", "2026년 경기도 공공데이터·AI활용 창업경진대회 공공AX 테스트")
    ]


def test_autonomous_fill_planner_disambiguates_repeated_protected_table_labels() -> None:
    from ummaya.tools.documents.planner import plan_autonomous_fill

    document_ir = DocumentIR(
        artifact_id="artifact-repeated-public-form-labels",
        document_format=DocumentFormat.hwpx,
        extraction=_empty_extraction("artifact-repeated-public-form-labels"),
        form_slots=(
            _slot(
                "신청인",
                label="신청인",
                current_value="",
                format_path="Contents/section0.xml#table[1]/r28c4",
                protected=True,
            ),
            _slot(
                "신청인",
                label="신청인",
                current_value="",
                format_path="Contents/section0.xml#table[2]/r2c2",
                protected=True,
            ),
        ),
    )

    plan = plan_autonomous_fill(
        document_ir,
        instruction="문서내용을 파악하고 전체 빈칸을 알아서 작성해.",
    )

    assert plan.requires_human_review is True
    assert len({slot.slot_id for slot in plan.slots}) == 2
    assert len(plan.blocked_slot_ids) == 2
    assert set(plan.blocked_slot_ids) == {slot.slot_id for slot in plan.slots}


def test_autonomous_fill_planner_keeps_adjacent_blank_cell_instruction_narrow() -> None:
    from ummaya.tools.documents.planner import plan_autonomous_fill

    document_ir = DocumentIR(
        artifact_id="artifact-official-application",
        document_format=DocumentFormat.hwpx,
        extraction=_empty_extraction("artifact-official-application"),
        form_slots=(
            _slot(
                "접수번호",
                label="접수번호",
                current_value="",
                format_path="Contents/section0.xml#table[1]/r4c2",
            ),
            _slot(
                "신청인",
                label="신청인",
                current_value="",
                format_path="Contents/section0.xml#table[1]/r28c4",
                protected=True,
            ),
            _slot(
                "신청인",
                label="신청인",
                current_value="",
                format_path="Contents/section0.xml#table[2]/r2c2",
                protected=True,
            ),
        ),
    )

    plan = plan_autonomous_fill(
        document_ir,
        instruction=(
            "공식 재난안전기업 지원 신청서 내용을 파악해서 "
            "접수번호 옆 빈칸에는 UMMAYA-2026-0002를 넣고, "
            "수정 후 변경된 부분만 바로 확인할 수 있게 보여줘."
        ),
    )

    assert plan.requires_human_review is False
    assert plan.blocked_slot_ids == ()
    assert [
        (slot.slot_id, slot.source_anchor.format_path, slot.candidate_value) for slot in plan.slots
    ] == [("접수번호", "Contents/section0.xml#table[1]/r4c2", "UMMAYA-2026-0002")]


def test_document_ir_extracts_table_sheet_slide_and_acroform_slots() -> None:
    xlsx_ir = DocumentIR.from_extraction(
        artifact_id="artifact-xlsx",
        document_format=DocumentFormat.xlsx,
        engine_id="openpyxl",
        extraction=DocumentExtraction(
            artifact_id="artifact-xlsx",
            tables=[
                TableBlock(
                    block_id="sheet-1",
                    source_path="/sheets/제출/cells",
                    cells=[
                        TableCell(
                            row_index=0,
                            column_index=0,
                            text="신청인",
                            source_path="/sheets/제출/cells/A1",
                        ),
                        TableCell(
                            row_index=0,
                            column_index=1,
                            text="",
                            source_path="/sheets/제출/cells/B1",
                            field_path="/sheets/제출/cells/B1",
                        ),
                    ],
                ),
            ],
        ),
    )
    pptx_ir = DocumentIR.from_extraction(
        artifact_id="artifact-pptx",
        document_format=DocumentFormat.pptx,
        engine_id="python-pptx",
        extraction=DocumentExtraction(
            artifact_id="artifact-pptx",
            paragraphs=[
                _paragraph(
                    block_id="slide-title",
                    text="기존 제목",
                    source_path="/slides/1/shapes/2/text",
                )
            ],
        ),
    )
    pdf_ir = DocumentIR.from_extraction(
        artifact_id="artifact-pdf",
        document_format=DocumentFormat.pdf,
        engine_id="pypdf-acroform",
        extraction=DocumentExtraction(
            artifact_id="artifact-pdf",
            fields=[
                FormField(
                    field_id="pdf-field-applicant-name",
                    label="applicant_name",
                    path="/acroform/fields/applicant_name",
                    field_type="text",
                    required=True,
                    current_value=None,
                    source_confidence=Decimal("1"),
                )
            ],
        ),
    )

    assert xlsx_ir.form_slots[0].label == "신청인"
    assert xlsx_ir.form_slots[0].source_anchor.format_path == "/sheets/제출/cells/B1"
    assert xlsx_ir.form_slots[0].source_anchor.sheet_index == 0
    assert pptx_ir.form_slots[0].label == "slide text"
    assert pptx_ir.form_slots[0].source_anchor.slide_index == 0
    assert pdf_ir.form_slots[0].source_anchor.format_path == "/acroform/fields/applicant_name"


def test_autonomous_fill_planner_value_precedence_and_missing_inputs() -> None:
    from ummaya.tools.documents.planner import plan_autonomous_fill

    document_ir = DocumentIR(
        artifact_id="artifact-proposal",
        document_format=DocumentFormat.docx,
        extraction=_empty_extraction("artifact-proposal"),
        form_slots=(
            _slot(
                "week_label", label="주차", current_value="13주차", format_path="/word/paragraphs/1"
            ),
            _slot(
                "project_name",
                label="프로젝트명",
                current_value=None,
                format_path="/word/paragraphs/2",
            ),
            _slot(
                "idea_summary",
                label="제안내용",
                current_value=None,
                format_path="/word/paragraphs/3",
            ),
            _slot(
                "applicant_name", label="성명", current_value=None, format_path="/word/paragraphs/4"
            ),
        ),
    )

    plan = plan_autonomous_fill(
        document_ir,
        instruction=(
            "문서내용을 파악하고 알아서 15주차 기획서로 작성해. "
            "제안내용은 공공데이터 기반 민원 자동화입니다."
        ),
        session_context={"프로젝트명": "GovOn"},
    )

    slot_values = {slot.slot_id: slot.candidate_value for slot in plan.slots}
    assert slot_values["week_label"] == "15주차"
    assert slot_values["project_name"] == "GovOn"
    assert slot_values["idea_summary"] == "공공데이터 기반 민원 자동화입니다."
    assert slot_values["applicant_name"] is None
    assert "applicant_name" in plan.blocked_slot_ids
    assert plan.requires_human_review is True


def test_autonomous_fill_planner_trims_update_and_save_clauses_from_keyed_values() -> None:
    from ummaya.tools.documents.planner import plan_autonomous_fill

    document_ir = DocumentIR(
        artifact_id="artifact-docx-date",
        document_format=DocumentFormat.docx,
        extraction=_empty_extraction("artifact-docx-date"),
        form_slots=(
            _slot(
                "created_date",
                label="작성일",
                current_value="2026-06-01",
                format_path="/word/tables/1/rows/1/cells/2",
            ),
        ),
    )

    plan = plan_autonomous_fill(
        document_ir,
        instruction=(
            "작성일: 2026-06-04 로 갱신하고, 저장은 "
            "/tmp/ummaya-tui-all-format-beta/tui-exports/civil-form-date-auto.docx 로 해줘."
        ),
    )

    assert plan.requires_human_review is False
    assert {slot.slot_id: slot.candidate_value for slot in plan.slots} == {
        "created_date": "2026-06-04"
    }


def test_autonomous_fill_planner_derives_docx_style_and_save_intent(tmp_path: Path) -> None:
    from ummaya.tools.documents.planner import plan_autonomous_fill

    destination_path = tmp_path / "form-output.docx"
    document_ir = DocumentIR(
        artifact_id="artifact-docx-style-save",
        document_format=DocumentFormat.docx,
        extraction=_empty_extraction("artifact-docx-style-save"),
        form_slots=(
            _slot(
                "receipt_number",
                label="접수번호",
                current_value=None,
                format_path="/word/tables/1/rows/1/cells/2",
            ),
        ),
    )

    plan = plan_autonomous_fill(
        document_ir,
        instruction=(
            "접수번호 옆 빈칸에는 UMMAYA-TUI-2026를 넣고, "
            "Malgun Gothic 12pt bold, 글자색 1F4E79, 배경색 FFF2CC, 가운데 정렬로 맞춰줘. "
            f"저장은 {destination_path} 로 해줘."
        ),
    )

    assert plan.requires_human_review is False
    assert [(slot.slot_id, slot.candidate_value) for slot in plan.slots] == [
        ("receipt_number", "UMMAYA-TUI-2026")
    ]
    assert len(plan.style_intents) == 1
    style_intent = plan.style_intents[0]
    assert style_intent.source_slot_id == "receipt_number"
    assert style_intent.target_path == "/word/tables/1/rows/1/cells/2"
    assert style_intent.style.target_path == "/word/tables/1/rows/1/cells/2"
    assert style_intent.style.font_family == "Malgun Gothic"
    assert style_intent.style.font_size_pt == Decimal("12")
    assert style_intent.style.bold is True
    assert style_intent.style.font_color_rgb == "1F4E79"
    assert style_intent.style.fill_color_rgb == "FFF2CC"
    assert style_intent.style.alignment == "center"
    assert plan.save_intent is not None
    assert plan.save_intent.destination_path == str(destination_path)
    assert plan.save_intent.destination_display_name == "form-output.docx"


def test_autonomous_fill_planner_blocks_unsafe_style_on_legal_signature_slot() -> None:
    from ummaya.tools.documents.planner import plan_autonomous_fill

    document_ir = DocumentIR(
        artifact_id="artifact-docx-signature-style",
        document_format=DocumentFormat.docx,
        extraction=_empty_extraction("artifact-docx-signature-style"),
        form_slots=(
            _slot(
                "signature",
                label="서명",
                current_value=None,
                format_path="/word/tables/4/rows/5/cells/2",
                field_type="signature",
                protected=True,
            ),
        ),
    )

    plan = plan_autonomous_fill(
        document_ir,
        instruction=(
            "문서 내용을 파악해서 서명 칸에는 홍길동을 넣고 Malgun Gothic 12pt bold로 맞춰줘."
        ),
    )

    assert plan.requires_human_review is True
    assert plan.blocked_slot_ids == ("signature",)
    assert plan.slots[0].candidate_value is None
    assert plan.style_intents == ()


def test_autonomous_fill_planner_targets_real_docx_public_form_slot(tmp_path: Path) -> None:
    from ummaya.tools.documents.planner import plan_autonomous_fill

    assert _SEOUL_CULTURE_DOCX.exists()
    engine = PythonDocxDocumentEngine()
    extraction = engine.inspect(_SEOUL_CULTURE_DOCX, artifact_id="seoul-culture-application-plan")
    document_ir = DocumentIR.from_extraction(
        artifact_id="seoul-culture-application-plan",
        document_format=DocumentFormat.docx,
        extraction=extraction,
        engine_id=engine.engine_id,
    )
    destination_path = tmp_path / "seoul-culture-filled.docx"

    plan = plan_autonomous_fill(
        document_ir,
        instruction=(
            "문서내용을 파악하고 팀명 옆 빈칸에는 GovOn Design AX를 넣어줘. "
            "Malgun Gothic 12pt bold로 맞추고 저장은 "
            f"{destination_path} 로 해줘."
        ),
    )

    assert plan.requires_human_review is False
    planned_slots = [
        (slot.label, slot.source_anchor.format_path, slot.candidate_value) for slot in plan.slots
    ]
    assert planned_slots == [
        (
            "팀명",
            "engine://python-docx/seoul-culture-application-plan.docx/table/1/r3c2",
            "GovOn Design AX",
        )
    ]
    assert len(plan.style_intents) == 1
    assert plan.style_intents[0].target_path == plan.slots[0].source_anchor.format_path
    assert plan.style_intents[0].style.font_family == "Malgun Gothic"
    assert plan.style_intents[0].style.font_size_pt == Decimal("12")
    assert plan.style_intents[0].style.bold is True
    assert plan.save_intent is not None
    assert plan.save_intent.destination_path == str(destination_path)


def test_docx_public_form_protected_address_slot_requires_review() -> None:
    from ummaya.tools.documents.planner import plan_autonomous_fill

    assert _SEOUL_DDP_DOCX.exists()
    engine = PythonDocxDocumentEngine()
    extraction = engine.inspect(_SEOUL_DDP_DOCX, artifact_id="seoul-ddp-design-fair-application")
    document_ir = DocumentIR.from_extraction(
        artifact_id="seoul-ddp-design-fair-application",
        document_format=DocumentFormat.docx,
        extraction=extraction,
        engine_id=engine.engine_id,
    )
    address_slot = _slot_by_label(document_ir, "사업장 주소")

    assert address_slot.current_value == ""
    assert address_slot.protected is True
    assert address_slot.source_anchor.format_path == (
        "engine://python-docx/seoul-ddp-design-fair-application.docx/table/1/r5c2"
    )

    plan = plan_autonomous_fill(
        document_ir,
        instruction="문서내용을 파악하고 모든 빈칸을 알아서 작성해.",
        session_context={"사업장 주소": "서울시 중구 을지로 281"},
    )
    planned_address = next(slot for slot in plan.slots if slot.slot_id == address_slot.slot_id)

    assert plan.requires_human_review is True
    assert address_slot.slot_id in plan.blocked_slot_ids
    assert planned_address.protected is True
    assert planned_address.candidate_value is None


def test_autonomous_fill_planner_suppresses_legal_and_identity_slots_across_formats() -> None:
    from ummaya.tools.documents.planner import plan_autonomous_fill

    protected_slots = (
        _slot(
            "docx_signature",
            label="서명",
            current_value=None,
            format_path="/word/tables/1/rows/1/cells/2",
        ),
        _slot(
            "xlsx_phone", label="전화번호", current_value=None, format_path="/sheets/신청/cells/B2"
        ),
        _slot(
            "pptx_consent",
            label="개인정보 동의",
            current_value=None,
            format_path="/slides/1/shapes/2/text",
        ),
        _slot(
            "pdf_rrn", label="주민등록번호", current_value=None, format_path="/acroform/fields/rrn"
        ),
    )
    document_ir = DocumentIR(
        artifact_id="artifact-legal",
        document_format=DocumentFormat.pdf,
        extraction=_empty_extraction("artifact-legal"),
        form_slots=protected_slots,
    )

    plan = plan_autonomous_fill(
        document_ir,
        instruction="문서내용을 파악하고 개인정보, 전화번호, 주민등록번호, 서명까지 알아서 작성해.",
        session_context={
            "전화번호": "010-0000-0000",
            "주민등록번호": "900101-1******",
            "서명": "홍길동",
        },
    )

    assert plan.requires_human_review is True
    assert set(plan.blocked_slot_ids) == {slot.slot_id for slot in protected_slots}
    assert all(slot.candidate_value is None for slot in plan.slots)


def test_autonomous_fill_planner_allows_user_provided_protected_person_value() -> None:
    from ummaya.tools.documents.planner import plan_autonomous_fill

    document_ir = DocumentIR(
        artifact_id="artifact-pdf-person",
        document_format=DocumentFormat.pdf,
        extraction=_empty_extraction("artifact-pdf-person"),
        form_slots=(
            _slot(
                "applicant_name",
                label="Applicant name",
                current_value="",
                format_path="/acroform/fields/applicant_name",
            ),
            _slot(
                "consent_signature",
                label="서명",
                current_value="",
                format_path="/acroform/fields/signature",
            ),
        ),
    )

    plan = plan_autonomous_fill(
        document_ir,
        instruction="Applicant name 필드를 테스트신청자 로 작성하고 서명 필드를 홍길동으로 작성해.",
    )

    slot_values = {slot.slot_id: slot.candidate_value for slot in plan.slots}
    assert slot_values["applicant_name"] == "테스트신청자"
    assert slot_values["consent_signature"] is None
    assert plan.blocked_slot_ids == ("consent_signature",)
    assert plan.requires_human_review is True


def test_autonomous_fill_planner_strips_topic_particle_from_explicit_korean_value() -> None:
    from ummaya.tools.documents.planner import plan_autonomous_fill

    document_ir = DocumentIR(
        artifact_id="artifact-korean-topic-particle",
        document_format=DocumentFormat.hwpx,
        extraction=_empty_extraction("artifact-korean-topic-particle"),
        form_slots=(
            _slot(
                "applicant_name",
                label="신청인 성명",
                current_value="",
                format_path="/body/section[1]/table[1]/cell[3,2]",
            ),
        ),
    )

    plan = plan_autonomous_fill(
        document_ir,
        instruction="신청인 성명은 홍길동으로 입력해줘.",
    )

    assert [(slot.slot_id, slot.candidate_value) for slot in plan.slots] == [
        ("applicant_name", "홍길동")
    ]
    assert plan.blocked_slot_ids == ()
    assert plan.requires_human_review is False


def test_public_document_writing_profile_matches_ai_friendly_guidance() -> None:
    from ummaya.tools.documents.planner import public_document_writing_profile

    profile = public_document_writing_profile()

    assert "clear_subject_predicate" in profile
    assert "plain_public_korean" in profile
    assert "standard_numbering_ladder" in profile
    assert "simple_tables_no_complex_merges" in profile
    assert "protected_legal_text_preserved" in profile


def _slot_by_label(document_ir: DocumentIR, label: str) -> FormSlot:
    for slot in document_ir.form_slots:
        if " ".join(slot.label.split()) == label:
            return slot
    raise KeyError(label)


def _slot(
    slot_id: str,
    *,
    label: str,
    current_value: str | None,
    format_path: str,
    field_type: str = "text",
    protected: bool = False,
) -> FormSlot:
    return FormSlot(
        slot_id=slot_id,
        label=label,
        field_type=field_type,
        required=True,
        protected=protected,
        source_anchor=SourceAnchor(
            format_path=format_path,
            confidence=Decimal("0.95"),
            engine_id="test-ir-engine",
        ),
        current_value=current_value,
        confidence=Decimal("0.95"),
    )


def _empty_extraction(artifact_id: str) -> object:
    return DocumentExtraction(artifact_id=artifact_id)


def _paragraph(block_id: str, *, text: str, source_path: str):
    from ummaya.tools.documents.models import ParagraphBlock

    return ParagraphBlock(block_id=block_id, text=text, source_path=source_path)
