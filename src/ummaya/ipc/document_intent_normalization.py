# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

_DOCUMENT_WRITE_REQUEST_RE: Final = re.compile(
    r"(작성|수정|편집|채우|채워|입력|변경|저장|write|edit|fill|apply|save)",
    re.IGNORECASE,
)
_DOCUMENT_SAVE_REQUEST_RE: Final = re.compile(
    r"(저장|내보내|export|save)",
    re.IGNORECASE,
)
_QUESTION_FIRST_AUTHORING_RE: Final = re.compile(
    r"(근거가\s*부족하면\s*먼저\s*질문|먼저\s*(?:확인|파악|검토|질문|물어)|"
    r"초안을?\s*먼저|아직.{0,40}(?:쓰지\s*마|작성하지\s*마|저장하지\s*마|"
    r"반영하지\s*마)|문서에는\s*쓰지\s*마)",
    re.IGNORECASE,
)
_DOCUMENT_INTERNAL_USER_QUERY_KEY: Final = "__ummaya_user_query"
_DOCUMENT_EXPLICIT_LOCAL_PATH_RE: Final = re.compile(
    r"(?P<path>(?:~|/)[^\s\"'<>]+?\."
    r"(?:hwpx|hwp|docx|pdf|xlsx|pptx|odt|ods|odp|doc|xls|ppt|csv|txt|md|json|xml|html))",
    re.IGNORECASE,
)


def _normalize_document_root_call_for_user_intent(
    fname: str,
    args_obj: dict[str, object],
    latest_user_utt: str,
) -> dict[str, object]:
    if fname != "document" or args_obj.get("tool_id") != "document":
        return args_obj
    params_obj = args_obj.get("params")
    if not isinstance(params_obj, dict):
        return args_obj
    normalized_params = dict(params_obj)
    internal_user_query = normalized_params.pop(_DOCUMENT_INTERNAL_USER_QUERY_KEY, None)
    intent_text = latest_user_utt
    if isinstance(internal_user_query, str) and internal_user_query.strip():
        intent_text = internal_user_query.strip()
    _normalize_document_path_from_user_query(normalized_params, intent_text)
    operation = str(params_obj.get("operation") or "").casefold()
    changed = normalized_params != params_obj
    if (
        operation in {"fill", "save"}
        and intent_text
        and _DOCUMENT_WRITE_REQUEST_RE.search(intent_text)
    ):
        if _DOCUMENT_SAVE_REQUEST_RE.search(intent_text):
            normalized_params["operation"] = "save"
        normalized_params["instruction"] = intent_text
        return {**args_obj, "params": normalized_params}
    if operation not in {"inspect", "extract"}:
        return {**args_obj, "params": normalized_params} if changed else args_obj
    if _should_keep_read_only_for_question_first_authoring(intent_text):
        return {**args_obj, "params": normalized_params} if changed else args_obj
    if not intent_text or not _DOCUMENT_WRITE_REQUEST_RE.search(intent_text):
        return {**args_obj, "params": normalized_params} if changed else args_obj

    normalized_params["operation"] = (
        "save" if _DOCUMENT_SAVE_REQUEST_RE.search(intent_text) else "fill"
    )
    normalized_params["instruction"] = intent_text
    return {**args_obj, "params": normalized_params}


def _normalize_document_path_from_user_query(
    normalized_params: dict[str, object],
    intent_text: str,
) -> None:
    if not intent_text:
        return
    document_obj = normalized_params.get("document")
    if not isinstance(document_obj, dict):
        return
    current_path = document_obj.get("path")
    if isinstance(current_path, str) and Path(current_path).expanduser().exists():
        return
    expected_format = document_obj.get("expected_format")
    expected_suffix = f".{expected_format}".lower() if isinstance(expected_format, str) else None
    explicit_paths: list[Path] = []
    for match in _DOCUMENT_EXPLICIT_LOCAL_PATH_RE.finditer(intent_text):
        candidate = Path(match.group("path").rstrip(".,;:)]}）")).expanduser()
        if expected_suffix is not None and candidate.suffix.lower() != expected_suffix:
            continue
        if candidate.exists():
            explicit_paths.append(candidate.resolve())
    if not explicit_paths:
        return
    normalized_params["document"] = {
        **document_obj,
        "path": str(explicit_paths[0]),
    }


def _should_keep_read_only_for_question_first_authoring(intent_text: str) -> bool:
    return bool(intent_text and _QUESTION_FIRST_AUTHORING_RE.search(intent_text))
