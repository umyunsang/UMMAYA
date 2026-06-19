# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from ummaya.ipc.stdio import _normalize_document_root_call_for_user_intent


def test_question_first_authoring_keeps_extract_read_only(tmp_path: Path) -> None:
    source = tmp_path / "form.docx"
    source.write_bytes(b"fixture")
    query = (
        "이 사업계획서 양식의 빈칸과 문항을 먼저 확인하고 제출할 수 있게 작성해줘. "
        f"근거가 부족하면 먼저 질문해. 파일: {source}"
    )
    args = {
        "tool_id": "document",
        "params": {
            "document": {"path": str(source)},
            "operation": "extract",
            "instruction": "사업계획서 양식의 모든 빈칸, 문항, 서식을 구조적으로 추출하세요.",
        },
    }

    normalized = _normalize_document_root_call_for_user_intent("document", args, query)

    assert normalized == args


def test_draft_without_writing_keeps_extract_read_only(tmp_path: Path) -> None:
    source = tmp_path / "form.docx"
    source.write_bytes(b"fixture")
    query = (
        "근거는 다음과 같아. 기업 및 브랜드명은 UMMAYA 공공문서 자동작성 고도화야. "
        "이 근거만 사용해서 초안을 먼저 보여줘. 아직 문서에는 쓰지 마."
    )
    args = {
        "tool_id": "document",
        "params": {
            "document": {"path": str(source)},
            "operation": "extract",
            "instruction": "근거를 확인하고 초안 작성 가능 여부를 파악하세요.",
        },
    }

    normalized = _normalize_document_root_call_for_user_intent("document", args, query)

    assert normalized == args


def test_d1_read_only_inspect_negated_write_terms_force_inspect_from_fill(
    tmp_path: Path,
) -> None:
    source = tmp_path / "readonly-inspect.docx"
    source.write_bytes(b"fixture")
    query = f"{source} 문서의 구조와 빈칸만 확인해줘. 절대 수정하거나 저장하지 마."
    args = {
        "tool_id": "document",
        "params": {
            "correlation_id": "d1-readonly",
            "document": {"path": str(source), "expected_format": "docx"},
            "operation": "fill",
            "instruction": "문서 빈칸을 채우세요.",
            "patches": [{"path": "/body/0", "value": "mutating value"}],
            "destination_path": str(tmp_path / "mutated.docx"),
        },
    }

    normalized = _normalize_document_root_call_for_user_intent("document", args, query)

    assert normalized is not args
    params = normalized["params"]
    assert params["operation"] == "inspect"
    assert params["instruction"] == query
    assert params["document"]["path"] == str(source)
    assert "patches" not in params
    assert "destination_path" not in params
