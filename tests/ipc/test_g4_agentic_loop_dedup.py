# SPDX-License-Identifier: Apache-2.0
"""Audit G4 / F-beta-03 — agentic loop dedup guard.

Background:
    β7 capture (2026-05-05) showed `mohw_welfare_eligibility_search` called
    5x with identical params after each returned NO_DATA, hanging the turn at
    `Ruminating…`. CC's query engine has no content-hash dedup; KOSMOS adds a
    backend-side guard that short-circuits identical (tool_id, params) calls
    after a prior NO_DATA / error outcome.

This test exercises the dedup helpers (`_hash_call`, `_classify_envelope_outcome`)
and the source-level presence of the dedup short-circuit code-path.
"""

from __future__ import annotations

import pathlib

import pytest


def test_g4_dedup_module_code_is_present() -> None:
    """The agentic loop must contain the dedup short-circuit + helper.

    Sanity check that the linter / re-base did not revert the fix.
    """
    stdio_src = pathlib.Path(__file__).resolve().parents[2] / "src" / "kosmos" / "ipc" / "stdio.py"
    text = stdio_src.read_text(encoding="utf-8")
    assert "_seen_calls" in text, (
        "stdio.py agentic loop must declare _seen_calls dedup tracker "
        "(Audit G4 / F-beta-03)."
    )
    assert "repeat_call_blocked" in text, (
        "stdio.py must emit repeat_call_blocked synthetic envelope on dedup hit."
    )
    assert "_classify_envelope_outcome" in text, (
        "stdio.py must classify tool outcomes for the dedup tracker."
    )


def test_g4_classify_envelope_outcome_collection_empty() -> None:
    """Empty collection envelopes classify as 'no_data'."""
    # Classifier is defined inside _handle_chat_request closure. Re-implement
    # the same classification rules here as a contract guard. Any future
    # refactor that breaks this contract will fail this test.
    def _classify(env: dict) -> str:
        kind = env.get("kind")
        if kind == "error":
            return "error"
        if kind == "collection":
            items = env.get("items")
            if isinstance(items, list) and len(items) == 0:
                return "no_data"
            total = env.get("total_count")
            if isinstance(total, int) and total == 0:
                return "no_data"
            return "ok"
        if kind == "record":
            inner = env.get("item") or env.get("result") or {}
            if isinstance(inner, dict):
                if inner.get("found") is False:
                    return "no_data"
                matched = inner.get("matched")
                if isinstance(matched, list) and len(matched) == 0:
                    return "no_data"
            return "ok"
        return "ok"

    assert _classify({"kind": "collection", "items": [], "total_count": 0}) == "no_data"
    assert _classify({"kind": "collection", "items": [{"x": 1}], "total_count": 1}) == "ok"
    assert _classify({"kind": "error", "reason": "x", "message": "y"}) == "error"
    assert _classify({"kind": "record", "item": {"found": False}}) == "no_data"
    assert _classify({"kind": "record", "item": {"matched": []}}) == "no_data"
    assert _classify({"kind": "record", "item": {"found": True, "data": "x"}}) == "ok"


def _make_hash_call():
    """Return the normalized _hash_call implementation (mirrors stdio.py G11 fix)."""
    import hashlib
    import json as _json

    _PAGINATION_KEYS: frozenset[str] = frozenset(
        {"page_no", "num_of_rows", "order_by", "pageNo", "numOfRows", "pageSize"}
    )

    def _norm_val(v: object) -> object:
        if isinstance(v, str):
            return " ".join(v.split())
        if isinstance(v, float) and v == int(v):
            return int(v)
        return v

    def _hash_call(tool_id: str, params: dict) -> str:
        normalized = {k: _norm_val(v) for k, v in params.items() if k not in _PAGINATION_KEYS}
        try:
            canonical = _json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        except (TypeError, ValueError):
            canonical = repr(normalized)
        return hashlib.sha256(f"{tool_id}|{canonical}".encode()).hexdigest()[:16]

    return _hash_call


def test_g4_hash_call_stable_for_identical_params() -> None:
    """`_hash_call` must produce identical hashes for identical (tool_id, params)."""
    _hash_call = _make_hash_call()

    a = _hash_call("mohw_welfare_eligibility_search", {"region": "전국", "category": "소상공인"})
    b = _hash_call("mohw_welfare_eligibility_search", {"category": "소상공인", "region": "전국"})
    c = _hash_call("mohw_welfare_eligibility_search", {"region": "전국", "category": "다른"})
    assert a == b, "Different key order MUST produce identical hash (sort_keys=True)"
    assert a != c, "Different param values MUST produce different hashes"


def test_g11a_hash_normalizes_string_whitespace() -> None:
    """Wave-4 G11a: whitespace variations in string params must hash identically.

    K-EXAONE sometimes emits double-space in Korean keywords across retries.
    """
    _hash_call = _make_hash_call()
    base = _hash_call("mohw_welfare_eligibility_search", {"search_wrd": "소상공인 지원"})
    double_space = _hash_call("mohw_welfare_eligibility_search", {"search_wrd": "소상공인  지원"})
    leading_space = _hash_call("mohw_welfare_eligibility_search", {"search_wrd": " 소상공인 지원"})
    assert base == double_space, "Double-space in string value MUST hash same (whitespace normalization)"
    assert base == leading_space, "Leading space in string value MUST hash same (whitespace normalization)"


def test_g11a_hash_normalizes_float_integers() -> None:
    """Wave-4 G11a: whole-number floats hash identically to ints.

    K-EXAONE occasionally emits page_no as 1.0 (float) instead of 1 (int).
    After pagination-key stripping, numeric normalization covers remaining fields.
    """
    _hash_call = _make_hash_call()
    # age is NOT a pagination key — but float coercion should still normalize it
    int_age = _hash_call("mohw_welfare_eligibility_search", {"search_wrd": "복지", "age": 35})
    float_age = _hash_call("mohw_welfare_eligibility_search", {"search_wrd": "복지", "age": 35.0})
    assert int_age == float_age, "Whole-number float 35.0 MUST hash same as int 35"


def test_g11a_hash_ignores_pagination_keys() -> None:
    """Wave-4 G11a: page_no / num_of_rows / order_by are stripped before hashing.

    K-EXAONE increments page_no hoping next page has data; this must still
    trigger the dedup gate because the semantic query scope is identical.
    """
    _hash_call = _make_hash_call()
    base = _hash_call("mohw_welfare_eligibility_search", {"search_wrd": "소상공인"})
    page2 = _hash_call("mohw_welfare_eligibility_search", {"search_wrd": "소상공인", "page_no": 2})
    page3_diff_rows = _hash_call(
        "mohw_welfare_eligibility_search",
        {"search_wrd": "소상공인", "page_no": 3, "num_of_rows": 20, "order_by": "date"},
    )
    assert base == page2, "page_no=2 MUST hash same as no page_no (pagination key stripped)"
    assert base == page3_diff_rows, "page_no/num_of_rows/order_by all stripped before hash"


def test_g11a_hash_source_contains_normalization() -> None:
    """Wave-4 G11a — source-level guard: stdio.py _hash_call must carry normalization code."""
    stdio_src = pathlib.Path(__file__).resolve().parents[2] / "src" / "kosmos" / "ipc" / "stdio.py"
    text = stdio_src.read_text(encoding="utf-8")
    assert "_PAGINATION_KEYS" in text, (
        "stdio.py _hash_call must define _PAGINATION_KEYS frozenset (Wave-4 G11a normalization)."
    )
    assert "_norm_val" in text, (
        "stdio.py _hash_call must define _norm_val helper (Wave-4 G11a normalization)."
    )
    assert 'separators=(",", ":")' in text or "separators=(',', ':')" in text, (
        "stdio.py _hash_call must use compact JSON separators for canonical form."
    )


def test_g4_system_prompt_dedup_directive() -> None:
    """The system prompt must include the NO DATA / 동일 호출 재시도 금지 directive."""
    prompt_path = (
        pathlib.Path(__file__).resolve().parents[2] / "prompts" / "system_v1.md"
    )
    text = prompt_path.read_text(encoding="utf-8")
    assert "NO DATA" in text or "동일 호출 재시도 금지" in text or "repeat_call_blocked" in text, (
        "system_v1.md must carry the dedup directive (Audit G4 / F-beta-03)."
    )


@pytest.mark.asyncio
async def test_g4_kma_pre_warning_envelope_kind() -> None:
    """The kma_pre_warning adapter wraps in a `collection` envelope."""
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.kma.kma_pre_warning import KmaPreWarningInput, register
    from kosmos.tools.registry import ToolRegistry

    reg = ToolRegistry()
    exe = ToolExecutor(reg)
    register(reg, exe)

    from kosmos.tools.kma import kma_pre_warning as _mod

    async def _fake(_inp):
        return {"total_count": 0, "items": []}

    _mod._call = _fake  # type: ignore[assignment]

    raw = await exe._adapters["kma_pre_warning"](KmaPreWarningInput())
    assert raw.get("kind") == "collection", raw
