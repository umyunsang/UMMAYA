# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
import uuid
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
_DOCUMENT_READ_ONLY_INSPECT_RE: Final = re.compile(
    r"(구조.{0,30}빈칸.{0,30}확인|빈칸.{0,30}확인|구조.{0,30}확인|"
    r"확인해\s*줘|검토만|inspect|read[- ]?only)",
    re.IGNORECASE,
)
_DOCUMENT_MUTATION_PROHIBITION_RE: Final = re.compile(
    r"(절대.{0,40}(?:수정|저장|작성|채우|입력|변경).{0,40}"
    r"(?:하지\s*마|하지\s*말|금지)|"
    r"(?:수정|저장|작성|채우|입력|변경).{0,30}(?:하지\s*마|하지\s*말)|"
    r"(?:do not|don't).{0,40}(?:modify|save|write|edit|fill))",
    re.IGNORECASE,
)
_QUESTION_FIRST_AUTHORING_RE: Final = re.compile(
    r"(근거가\s*부족하면\s*먼저\s*질문|먼저\s*(?:확인|파악|검토|질문|물어)|"
    r"초안을?\s*먼저|아직.{0,40}(?:쓰지\s*마|작성하지\s*마|저장하지\s*마|"
    r"반영하지\s*마)|문서에는\s*쓰지\s*마)",
    re.IGNORECASE,
)
_DOCUMENT_MUTATION_PARAM_KEYS: Final[frozenset[str]] = frozenset(
    {
        "approved_draft_id",
        "destination_display_name",
        "destination_path",
        "dry_run",
        "patches",
        "styles",
        "template_id",
    }
)
_DOCUMENT_INTERNAL_USER_QUERY_KEY: Final = "__ummaya_user_query"
_DOCUMENT_ROOT_SYNTHESIS_KEYS: Final[frozenset[str]] = frozenset(
    {_DOCUMENT_INTERNAL_USER_QUERY_KEY}
)
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

    intent_text = _document_intent_text(params_obj, latest_user_utt)
    synthesized_params = _synthesize_document_read_params(params_obj, intent_text)
    if synthesized_params is not None:
        return {**args_obj, "params": synthesized_params}

    normalized_params = dict(params_obj)
    normalized_params.pop(_DOCUMENT_INTERNAL_USER_QUERY_KEY, None)
    _normalize_document_path_from_user_query(normalized_params, intent_text)
    if _is_explicit_read_only_inspect_intent(intent_text):
        read_only_params = _strip_mutation_params(normalized_params)
        read_only_params["operation"] = "inspect"
        read_only_params["instruction"] = intent_text
        return {**args_obj, "params": read_only_params}

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


def _document_intent_text(params_obj: dict[str, object], latest_user_utt: str) -> str:
    internal_user_query = params_obj.get(_DOCUMENT_INTERNAL_USER_QUERY_KEY)
    if isinstance(internal_user_query, str) and internal_user_query.strip():
        return internal_user_query.strip()
    return latest_user_utt


def _synthesize_document_read_params(
    params_obj: dict[str, object],
    intent_text: str,
) -> dict[str, object] | None:
    if (
        not intent_text
        or isinstance(params_obj.get("document"), dict)
        or set(params_obj) - _DOCUMENT_ROOT_SYNTHESIS_KEYS
    ):
        return None
    local_path = _first_existing_document_path(intent_text, None)
    if local_path is None:
        return None
    document_format = local_path.suffix.removeprefix(".").lower()
    return {
        "correlation_id": f"document-intent-{uuid.uuid4().hex}",
        "document": {"path": str(local_path), "expected_format": document_format},
        "operation": "inspect",
        "instruction": intent_text,
    }


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
    explicit_path = _first_existing_document_path(intent_text, expected_suffix)
    if explicit_path is None:
        return
    normalized_params["document"] = {
        **document_obj,
        "path": str(explicit_path),
    }


def _first_existing_document_path(intent_text: str, expected_suffix: str | None) -> Path | None:
    for match in _DOCUMENT_EXPLICIT_LOCAL_PATH_RE.finditer(intent_text):
        candidate = Path(match.group("path").rstrip(".,;:)]}）")).expanduser()
        if expected_suffix is not None and candidate.suffix.lower() != expected_suffix:
            continue
        if candidate.exists():
            return candidate.resolve()
    return None


def _should_keep_read_only_for_question_first_authoring(intent_text: str) -> bool:
    return bool(intent_text and _QUESTION_FIRST_AUTHORING_RE.search(intent_text))


def _is_explicit_read_only_inspect_intent(intent_text: str) -> bool:
    return bool(
        intent_text
        and _DOCUMENT_READ_ONLY_INSPECT_RE.search(intent_text)
        and _DOCUMENT_MUTATION_PROHIBITION_RE.search(intent_text)
    )


def _strip_mutation_params(params_obj: dict[str, object]) -> dict[str, object]:
    return {
        key: value for key, value in params_obj.items() if key not in _DOCUMENT_MUTATION_PARAM_KEYS
    }
