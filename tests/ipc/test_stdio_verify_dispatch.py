# SPDX-License-Identifier: Apache-2.0
"""Regression test for stdio.py:_dispatch_primitive verify branch.

Bug (Spec 2521 / Spec 2297 / Issue #C1, citizen smoke 2026-05-04):
    Snapshots S2..S8 of the verify-cascade smoke captured every K-EXAONE
    ``verify({tool_id: "mock_verify_module_modid", params: {...}})`` call
    surfacing as ``VerifyMismatchError(message="No verify adapter
    registered for family ''")`` — the IPC stdio dispatcher read
    ``family_hint`` directly from the args dict and never translated
    ``tool_id`` → ``family_hint``. The mvp_surface
    ``_VerifyInputForLLM.translate_tool_id_shape`` validator only fires
    when the LLM call enters Pydantic schema validation; the IPC stdio
    direct path bypassed that validator.

Fix:
    ``stdio.py`` verify branch now calls
    ``kosmos.tools.verify_canonical_map.resolve_family(tool_id)`` first,
    falling back to ``args_obj["family_hint"]`` / ``args_obj["family"]``
    when the tool_id lookup misses (legacy compatibility).

This test asserts:
1. All 10 canonical ``mock_verify_*`` ↔ family_hint pairs resolve
   correctly via the canonical map (single source-of-truth derived from
   ``prompts/system_v1.md`` ``<verify_families>``).
2. The full IPC dispatch path translates ``tool_id`` → ``family_hint``
   and finds the registered adapter (no VerifyMismatchError).
3. Legacy ``family_hint`` (no tool_id) keeps working — backward
   compatibility for tools-bridge callers.
4. Empty legacy selectors still surface the expected ``VerifyMismatchError``;
   unknown citizen-shape ``tool_id`` values fail before adapter dispatch.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import os
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest

# Importing the mock package registers all 10 mock_verify_* adapters via
# register_verify_adapter() at module-import time (side effect).
import kosmos.tools.mock  # noqa: F401
from kosmos.ipc.frame_schema import (
    ChatMessage as IPCChatMessage,
)
from kosmos.ipc.frame_schema import ChatRequestFrame
from kosmos.ipc.stdio import (
    _build_forced_lookup_args,
    _build_forced_submit_args,
    _build_grounded_safety_answer,
    _build_policy_forced_verify_args,
    _build_tool_result_completion_answer,
    _check_final_answer_grounding,
    _check_pending_submit_before_non_submit,
    _check_privileged_chain_terminated_early,
    _check_public_subscribe_terminated_early,
    _check_submit_prerequisite,
    _check_tool_call_after_completed_submit,
    _check_tool_call_after_completed_submit_subscribe,
    _coerce_adapter_params_from_schema,
    _delegation_plan_from_candidates,
    _enrich_lookup_args_from_resolve_result,
    _gov24_direct_followup_flow_completed,
    _gov24_minwon_types_from_query,
    _gov24_movein_sequence_completed,
    _latest_delegation_context,
    _latest_kma_forecast_base,
    _mock_delegation_context_for_tool,
    _next_gov24_movein_submit_args,
    _normalise_resolve_location_args,
    _query_implies_followup_lookup,
    _query_prefers_resolve_location_before_verify,
    _retrieval_policy_requires_initial_verify,
    _submit_args_compatible_with_latest_auth,
    _tool_payload_succeeded,
)
from kosmos.llm.models import StreamEvent
from kosmos.tools.verify_canonical_map import (
    get_canonical_map,
    resolve_family,
)

_RUNNER_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# 1. Pure-function tests for the canonical map
# ---------------------------------------------------------------------------


# Source-of-truth: prompts/system_v1.md <verify_families> block.
# Mirrored here so any drift between prompt and code blows up the test.
_EXPECTED_PAIRS: dict[str, str] = {
    "mock_verify_gongdong_injeungseo": "gongdong_injeungseo",
    "mock_verify_geumyung_injeungseo": "geumyung_injeungseo",
    "mock_verify_ganpyeon_injeung": "ganpyeon_injeung",
    "mock_verify_mobile_id": "mobile_id",
    "mock_verify_mydata": "mydata",
    "mock_verify_module_simple_auth": "simple_auth_module",
    "mock_verify_module_modid": "modid",
    "mock_verify_module_kec": "kec",
    "mock_verify_module_geumyung": "geumyung_module",
    "mock_verify_module_any_id_sso": "any_id_sso",
}


@pytest.mark.parametrize(
    ("tool_id", "expected_family"),
    list(_EXPECTED_PAIRS.items()),
)
def test_resolve_family_covers_all_10_canonical_pairs(tool_id: str, expected_family: str) -> None:
    """All 10 canonical mock_verify_* tool_ids resolve to the right family_hint.

    This is the SOT-mirror assertion: prompt-side
    ``<verify_families>`` and code-side mapping must agree.
    """
    assert resolve_family(tool_id) == expected_family, (
        f"resolve_family({tool_id!r}) returned {resolve_family(tool_id)!r}, "
        f"expected {expected_family!r}"
    )


def test_canonical_map_has_exactly_ten_entries() -> None:
    """FR-008b: the verify_families block must enumerate ≥10 entries."""
    canonical = get_canonical_map()
    assert len(canonical) >= 10, (
        f"Expected at least 10 verify families, got {len(canonical)}: {dict(canonical)!r}"
    )


def test_resolve_family_unknown_tool_id_returns_none() -> None:
    """Unknown tool_ids must surface as None so the dispatcher can fall
    through to the legacy ``family_hint`` arg (backward compatibility)."""
    assert resolve_family("some_unknown_verify_tool") is None
    assert resolve_family("") is None
    assert resolve_family("submit_something_else") is None


# ---------------------------------------------------------------------------
# 2. IPC dispatcher integration — minimal harness
# ---------------------------------------------------------------------------


def _ts() -> str:
    now = datetime.now(tz=UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _make_chat_request(prompt: str) -> ChatRequestFrame:
    return ChatRequestFrame(
        session_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        role="tui",
        ts=_ts(),
        kind="chat_request",
        messages=[IPCChatMessage(role="user", content=prompt)],
        tools=[],
        system=None,
    )


class _CaptureBuf:
    def __init__(self) -> None:
        self._buf = io.BytesIO()

    def write(self, data: bytes) -> None:
        self._buf.write(data)

    def flush(self) -> None:
        pass

    def as_frames(self) -> list[dict[str, Any]]:
        self._buf.seek(0)
        frames: list[dict[str, Any]] = []
        for line in self._buf:
            stripped = line.strip()
            if stripped:
                with contextlib.suppress(json.JSONDecodeError):
                    frames.append(json.loads(stripped))
        return frames


class _FakeStdout:
    def __init__(self) -> None:
        self.buffer = _CaptureBuf()

    def write(self, data: str) -> None:
        """Direct write path used by emit_manifest (str → bytes)."""
        self.buffer.write(data.encode())

    def flush(self) -> None:
        pass


class _VerifyOnceLLMClient:
    """Fake LLM that emits exactly one ``verify`` tool_call and then
    finishes the conversation on turn 2.

    The exact tool-call args are pulled from class-level ``_args_json``
    set by the test harness immediately before invoking ``run``.
    """

    _class_turn: int = 0
    _args_json: str = "{}"
    _call_id_prefix: str = "verify"

    def __init__(self, config: Any) -> None:  # noqa: D401
        pass

    async def stream(  # noqa: PLR0913
        self,
        messages: list[Any],
        *,
        tools: list[Any] | None = None,
        tool_choice: Any = None,
        temperature: float = 1.0,
        top_p: float = 0.95,
        presence_penalty: float = 0.0,
        max_tokens: int = 1024,
        stop: Any = None,
    ) -> AsyncIterator[StreamEvent]:
        type(self)._class_turn += 1
        turn = type(self)._class_turn

        if turn == 1:
            call_id = f"call-{type(self)._call_id_prefix}-{uuid.uuid4().hex[:8]}"
            yield StreamEvent(
                type="tool_call_delta",
                tool_call_index=0,
                tool_call_id=call_id,
                function_name="verify",
                function_args_delta=type(self)._args_json,
            )
            yield StreamEvent(type="done")
        else:
            yield StreamEvent(type="content_delta", content="검증 완료.")
            yield StreamEvent(type="done")


async def _run_verify_dispatch(
    frame: ChatRequestFrame,
    args_obj: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> _CaptureBuf:
    """Run a single chat_request through the IPC harness with a fake LLM
    that emits one ``verify(args_obj)`` tool_call.

    Returns the captured NDJSON frame buffer.
    """
    from kosmos.ipc import stdio as stdio_mod
    from kosmos.ipc.frame_schema import SessionEventFrame

    monkeypatch.setattr(stdio_mod, "_stdout_lock", None)

    # Gap B fix: verify is now gated (GATED_PRIMITIVES includes "verify").
    # These tests only exercise the tool_id → family_hint translation path,
    # NOT the permission gating logic. Bypass the gate by patching
    # GATED_PRIMITIVES to the pre-Gap-B set (submit/subscribe only) so
    # verify auto-allows and the IPC loop doesn't wait 60 s for citizen input.
    import kosmos.primitives as _prims_mod

    monkeypatch.setattr(
        _prims_mod,
        "GATED_PRIMITIVES",
        frozenset({"submit", "subscribe"}),
    )

    fake_stdout = _FakeStdout()
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    _VerifyOnceLLMClient._class_turn = 0
    _VerifyOnceLLMClient._args_json = json.dumps(args_obj, ensure_ascii=False)

    class _FakeLLMConfig:
        pass

    import kosmos.llm.client as llm_client_mod
    import kosmos.llm.config as llm_config_mod

    monkeypatch.setattr(llm_client_mod, "LLMClient", _VerifyOnceLLMClient)
    monkeypatch.setattr(llm_config_mod, "LLMClientConfig", _FakeLLMConfig)

    # Stub the prompt loader so the test doesn't hit the manifest on disk.
    try:
        import kosmos.context.prompt_loader as pl_mod

        class _FPL:
            def __init__(self, *, manifest_path: Any) -> None:
                pass

            def load(self, name: str) -> str:
                return f"System prompt ({name})"

        monkeypatch.setattr(pl_mod, "PromptLoader", _FPL)
    except ImportError:
        pass

    session_id = frame.session_id
    exit_frame = SessionEventFrame(
        session_id=session_id,
        correlation_id=str(uuid.uuid4()),
        role="tui",
        ts=_ts(),
        kind="session_event",
        event="exit",
        payload={},
    )
    payload = (frame.model_dump_json() + "\n").encode() + (
        exit_frame.model_dump_json() + "\n"
    ).encode()

    r_fd, w_fd = os.pipe()
    os.write(w_fd, payload)
    os.close(w_fd)
    r_file = os.fdopen(r_fd, "rb")

    class _FakeStdinWrapper:
        buffer = r_file

    monkeypatch.setattr(sys, "stdin", _FakeStdinWrapper())

    import logging as _logging

    from kosmos.ipc.stdio import run as ipc_run

    try:
        await asyncio.wait_for(ipc_run(session_id=session_id), timeout=_RUNNER_TIMEOUT)
    except (TimeoutError, Exception) as exc:  # noqa: BLE001
        _logging.getLogger(__name__).debug("_run_verify_dispatch: IPC loop exited early: %s", exc)
    finally:
        if not r_file.closed:
            r_file.close()

    return fake_stdout.buffer


def _extract_verify_envelope(frames: list[dict[str, Any]]) -> dict[str, Any]:
    """Pull the inner ``envelope.result`` payload from the first verify
    tool_result frame in ``frames``."""
    tool_results = [f for f in frames if f.get("kind") == "tool_result"]
    assert tool_results, (
        f"No tool_result frames emitted; got kinds={[f.get('kind') for f in frames]}"
    )
    envelope = tool_results[0].get("envelope", {})
    inner = envelope.get("result")
    assert isinstance(inner, dict), f"envelope.result must be a dict, got {type(inner)}"
    return {"envelope": envelope, "inner": inner}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_id", "expected_family"),
    list(_EXPECTED_PAIRS.items()),
)
async def test_dispatch_verify_translates_tool_id_to_family_hint(
    tool_id: str,
    expected_family: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM-emitted ``verify({tool_id: "mock_verify_*"})`` must dispatch
    via the canonical map and reach the registered adapter.

    Pre-fix: every call surfaced as ``VerifyMismatchError`` because the
    stdio dispatcher read ``args["family_hint"]`` (always missing) and
    sent an empty string to ``verify()``.

    Post-fix: ``resolve_family(tool_id)`` runs first and produces the
    correct family_hint so the registered adapter is invoked.
    """
    args_obj: dict[str, Any] = {
        "tool_id": tool_id,
        "params": {
            "scope_list": ["lookup:test.read"],
            "purpose_ko": "테스트",
            "purpose_en": "test",
        },
    }
    frame = _make_chat_request(f"verify {tool_id}")
    buf = await _run_verify_dispatch(frame, args_obj, monkeypatch)

    frames = buf.as_frames()
    parts = _extract_verify_envelope(frames)
    envelope = parts["envelope"]
    inner = parts["inner"]

    assert envelope.get("kind") == "verify", (
        f"Expected envelope.kind=='verify', got {envelope.get('kind')!r}"
    )
    # The envelope's outer ``family`` mirror is set from the resolved
    # family_hint; must equal the expected mapping.
    assert envelope.get("family") == expected_family, (
        f"Expected envelope.family=={expected_family!r}, got {envelope.get('family')!r}"
    )
    # The adapter result MUST NOT be a VerifyMismatchError surfaced as
    # ``family == 'mismatch_error'`` — that was the pre-fix symptom.
    assert inner.get("family") != "mismatch_error", (
        f"verify({tool_id!r}) returned VerifyMismatchError post-fix; inner={inner!r}"
    )
    assert inner.get("family") == expected_family, (
        f"Expected adapter to return family={expected_family!r}, got "
        f"family={inner.get('family')!r}; inner={inner!r}"
    )


@pytest.mark.asyncio
async def test_dispatch_verify_legacy_family_hint_still_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy callers that still pass ``family_hint`` directly (no
    ``tool_id`` field) must keep working — the canonical-map lookup
    misses, then the dispatcher falls back to the legacy field."""
    args_obj: dict[str, Any] = {
        "family_hint": "modid",
        "session_context": {
            "scope_list": ["lookup:hometax.simplified"],
            "session_id": "test-legacy",
        },
    }
    frame = _make_chat_request("legacy verify modid")
    buf = await _run_verify_dispatch(frame, args_obj, monkeypatch)

    frames = buf.as_frames()
    parts = _extract_verify_envelope(frames)
    envelope = parts["envelope"]
    inner = parts["inner"]

    assert envelope.get("family") == "modid"
    assert inner.get("family") == "modid", (
        f"legacy family_hint='modid' must still dispatch; inner={inner!r}"
    )


@pytest.mark.asyncio
async def test_dispatch_verify_packs_citizen_params_into_session_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Citizen-shape verify params must reach the adapter as session_context.

    The stdio dispatcher bypasses _VerifyInputForLLM's Pydantic pre-validator,
    so it must explicitly merge args.params into session_context before calling
    verify(). Otherwise the DelegationToken is minted with the adapter default
    scope and downstream lookup/submit calls fail scope validation.
    """
    scopes = ["lookup:hometax.simplified", "submit:hometax.tax-return"]
    args_obj: dict[str, Any] = {
        "tool_id": "mock_verify_module_modid",
        "params": {
            "scope_list": scopes,
            "purpose_ko": "부가세 신고와 납부",
            "purpose_en": "VAT filing and payment",
        },
    }
    frame = _make_chat_request("verify modid with scopes")
    buf = await _run_verify_dispatch(frame, args_obj, monkeypatch)

    frames = buf.as_frames()
    parts = _extract_verify_envelope(frames)
    inner = parts["inner"]
    delegation = inner.get("delegation_context")
    assert isinstance(delegation, dict), f"missing delegation_context: {inner!r}"
    token = delegation.get("token")
    assert isinstance(token, dict), f"missing delegation token: {delegation!r}"
    assert token.get("scope") == ",".join(scopes)
    assert delegation.get("purpose_ko") == "부가세 신고와 납부"
    assert delegation.get("purpose_en") == "VAT filing and payment"


@pytest.mark.asyncio
async def test_dispatch_verify_enriches_empty_citizen_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Citizen-shape verify recovers omitted scopes/purpose from registry policy."""
    args_obj: dict[str, Any] = {
        "tool_id": "mock_verify_module_modid",
        "params": {},
    }
    frame = _make_chat_request("verify modid without scopes")
    buf = await _run_verify_dispatch(frame, args_obj, monkeypatch)

    frames = buf.as_frames()
    parts = _extract_verify_envelope(frames)
    inner = parts["inner"]
    delegation = inner.get("delegation_context")
    assert isinstance(delegation, dict), f"missing delegation_context: {inner!r}"
    token = delegation.get("token")
    assert isinstance(token, dict), f"missing delegation token: {delegation!r}"
    assert token.get("scope") == "verify:modid.identity"
    assert delegation.get("purpose_ko") == "verify modid without scopes"
    assert (
        delegation.get("purpose_en")
        == "Citizen-requested delegated government service workflow."
    )


def test_latest_delegation_context_reads_nested_verify_envelope() -> None:
    """Agent-loop helper must unwrap ToolResultEnvelope.result.result."""
    delegation_context = {
        "token": {
            "vp_jwt": "mock.jwt",
            "delegation_token": "del_test",
            "scope": "lookup:hometax.simplified,submit:hometax.tax-return",
            "issuer_did": "did:web:mobileid.go.kr",
            "issued_at": "2026-05-06T00:00:00Z",
            "expires_at": "2026-05-07T00:00:00Z",
        },
        "citizen_did": "did:web:mobileid.go.kr:test",
        "purpose_ko": "부가세 신고와 납부",
        "purpose_en": "VAT filing and payment",
    }
    messages = [
        {
            "role": "tool",
            "name": "verify",
            "content": json.dumps(
                {
                    "kind": "verify",
                    "result": {
                        "family": "modid",
                        "result": {
                            "family": "modid",
                            "published_tier": "modid_aal3",
                            "nist_aal_hint": "AAL3",
                            "delegation_context": delegation_context,
                        },
                    },
                }
            ),
        }
    ]

    assert _latest_delegation_context(messages) == delegation_context


def _registry_with_all_tools() -> Any:
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.register_all import register_all_tools
    from kosmos.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry=registry)
    register_all_tools(registry, executor)
    return registry


def test_mock_delegation_context_appends_session_bound_issuance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Synthetic MyData delegation must be visible to validate_delegation()."""
    from kosmos.memdir import consent_ledger

    captured: list[Any] = []

    def fake_append(event: Any, *, ledger_root: object | None = None) -> object:
        captured.append(event)
        return object()

    monkeypatch.setattr(consent_ledger, "append_delegation_issued", fake_append)

    ctx = _mock_delegation_context_for_tool(
        "mock_submit_module_public_mydata_action",
        session_id="session-dat-001",
        user_query="정부기관들이 내 정보를 어디에 쓰고 있는지 확인하고 고쳐줘.",
        registry=_registry_with_all_tools(),
    )

    assert ctx is not None
    token = ctx["token"]
    assert isinstance(token, dict)
    assert token["scope"] == "submit:public_mydata.action"
    assert captured
    event = captured[0]
    assert event.session_id == "session-dat-001"
    assert event.delegation_token == token["delegation_token"]
    assert event.scope == token["scope"]


def test_policy_forced_verify_args_use_registry_delegation_source() -> None:
    """Empty tool_choice=verify turns recover through registry-derived args.

    The CIV-001 real-use path can return no structured tool_call even though
    the backend sent explicit tool_choice=verify.  The recovery must build the
    same verify call from adapter metadata, not from query keyword routing.
    """
    args = _build_policy_forced_verify_args(
        (
            "현재 위치는 부산 사하구 다대1동입니다. 이사했어요. "
            "전입신고하고 자동차 주소, 건강보험, 학교 관련 주소 변경까지 같이 처리해줘."
        ),
        _registry_with_all_tools(),
    )

    assert args is not None
    assert args["tool_id"] == "mock_verify_ganpyeon_injeung"
    params = args["params"]
    assert isinstance(params, dict)
    assert "lookup:gov24.movein" in params["scope_list"]
    assert "submit:gov24.minwon" in params["scope_list"]
    assert params["purpose_ko"]
    assert params["purpose_en"]


def test_policy_forced_verify_prefers_coherent_submit_source_bundle() -> None:
    """Mixed submit candidates must not force a cross-family tier failure later."""
    args = _build_policy_forced_verify_args(
        "퇴사했는데 실업급여 받을 수 있는지 확인하고 워크넷 등록이랑 고용센터 예약까지 해줘.",
        _registry_with_all_tools(),
    )

    assert args is not None
    assert args["tool_id"] == "mock_verify_ganpyeon_injeung"
    params = args["params"]
    assert isinstance(params, dict)
    assert "submit:gov24.minwon" in params["scope_list"]
    assert "submit:welfare.application" not in params["scope_list"]


def test_policy_forced_verify_prefers_scoped_gov24_death_bundle() -> None:
    """A close-scored scoped Gov24 submit should not be shadowed by a generic tier submit."""
    registry = _registry_with_all_tools()
    query = (
        "아버지가 돌아가셨어. 사망신고, 장례 지원, 국민연금 유족급여, "
        "재산 관련 절차를 순서대로 알려줘."
    )

    assert _gov24_minwon_types_from_query(query, registry) == ["사망신고", "국민연금유족급여"]

    args = _build_policy_forced_verify_args(query, registry)

    assert args is not None
    assert args["tool_id"] == "mock_verify_ganpyeon_injeung"
    params = args["params"]
    assert isinstance(params, dict)
    assert params["scope_list"] == ["submit:gov24.minwon"]


def test_policy_forced_verify_uses_hometax_scope_bundle_for_refund_account() -> None:
    args = _build_policy_forced_verify_args(
        "작년 종합소득세 신고하고 환급받을 수 있으면 환급 계좌까지 등록해줘.",
        _registry_with_all_tools(),
    )

    assert args is not None
    assert args["tool_id"] == "mock_verify_module_modid"
    params = args["params"]
    assert isinstance(params, dict)
    assert "lookup:hometax.simplified" in params["scope_list"]
    assert "submit:hometax.tax-return" in params["scope_list"]
    assert "submit:gov24.minwon" not in params["scope_list"]


def test_policy_forced_verify_uses_gov24_for_flood_damage_bundle() -> None:
    registry = _registry_with_all_tools()
    query = (
        "현재 위치는 부산 사하구 다대1동입니다. 집이 침수됐어. "
        "피해 신고, 재난지원금, 임시주거, 전기·가스 안전 점검까지 바로 도와줘."
    )

    assert _gov24_minwon_types_from_query(query, registry) == ["피해신고", "재난지원금"]

    args = _build_policy_forced_verify_args(query, registry)

    assert args is not None
    assert args["tool_id"] == "mock_verify_ganpyeon_injeung"
    params = args["params"]
    assert isinstance(params, dict)
    assert params["scope_list"] == ["submit:gov24.minwon"]


def test_gov24_minwon_types_match_business_certificate_and_license() -> None:
    registry = _registry_with_all_tools()
    query = "사업자등록하고 영업신고까지 처리하고 진행상태 알림도 받아줘."

    assert _gov24_minwon_types_from_query(query, registry) == [
        "사업자등록증명",
        "영업신고",
    ]


def test_business_bundle_forces_subscribe_after_two_gov24_submits() -> None:
    registry = _registry_with_all_tools()
    query = (
        "카페 창업하려고 해. 사업자등록, 영업신고, 위생교육, 카드가맹, "
        "세금 준비까지 순서대로 처리해줘."
    )
    messages = [_verified_ganpyeon_tier_tool_message(), _lookup_tool_message()]
    for index, minwon_type in enumerate(["사업자등록증명", "영업신고"], start=1):
        call_id = f"submit-business-{index}"
        messages.append(
            _assistant_tool_call_message(
                call_id,
                "submit",
                {
                    "tool_id": "mock_submit_module_gov24_minwon",
                    "params": {"minwon_type": minwon_type},
                },
            )
        )
        messages.append(
            {
                **_submit_tool_message(
                    result_status="succeeded",
                    receipt_status="접수완료",
                    receipt_extra={"minwon_type": minwon_type},
                ),
                "tool_call_id": call_id,
            }
        )

    followup = _check_privileged_chain_terminated_early(
        messages,
        query,
        registry=registry,
    )

    assert followup is not None
    assert followup[0] == "subscribe"


def test_gov24_minwon_types_match_immigration_extension_and_reservation() -> None:
    registry = _registry_with_all_tools()
    query = "외국인등록증 체류기간 연장해야 해. 예약이나 전자민원 가능한 부분 처리해줘."

    assert _gov24_minwon_types_from_query(query, registry) == [
        "체류기간연장",
        "방문예약",
    ]


def test_initial_verify_policy_uses_gated_shortlist_not_only_top_candidate() -> None:
    from kosmos.tools.search import search

    registry = _registry_with_all_tools()
    query = (
        "이번 달 재산세랑 자동차세, 과태료 밀린 거 있는지 확인하고 "
        "납부 가능한 건 한 번에 처리해줘."
    )
    candidates = search(
        query=query,
        bm25_index=registry.bm25_index,
        registry=registry,
        top_k=8,
    )

    assert candidates[0].tool_id == "mock_lookup_module_national_ax_bundle"
    assert candidates[0].citizen_facing_gate == "read-only"
    assert _retrieval_policy_requires_initial_verify(candidates) is True


def test_initial_verify_policy_keeps_public_location_flow_location_first() -> None:
    from kosmos.tools.search import search

    registry = _registry_with_all_tools()
    query = (
        "아이가 밤에 열이 높아. 지금 갈 수 있는 응급실이나 "
        "야간진료 병원 찾고 보험 적용되는지도 알려줘."
    )
    candidates = search(
        query=query,
        bm25_index=registry.bm25_index,
        registry=registry,
        top_k=8,
    )

    assert candidates[0].primitive == "subscribe"
    assert _retrieval_policy_requires_initial_verify(candidates) is False


def test_initial_verify_policy_prefers_location_anchor_for_flood_bundle() -> None:
    from kosmos.tools.search import search

    registry = _registry_with_all_tools()
    query = (
        "현재 위치는 부산 사하구 다대1동입니다. 집이 침수됐어. "
        "피해 신고, 재난지원금, 임시주거, 전기·가스 안전 점검까지 바로 도와줘."
    )
    candidates = search(
        query=query,
        bm25_index=registry.bm25_index,
        registry=registry,
        top_k=8,
    )

    assert candidates[0].tool_id == "mock_submit_module_gov24_minwon"
    assert _retrieval_policy_requires_initial_verify(candidates) is True
    assert _query_prefers_resolve_location_before_verify(query, candidates) is True


def test_initial_verify_policy_keeps_login_lookup_before_location_anchor() -> None:
    from kosmos.tools.search import search

    registry = _registry_with_all_tools()
    query = (
        "현재 위치는 부산 사하구 다대1동입니다. 이사 때문에 아이 학교 전학이 "
        "필요해. 전입신고랑 전학 절차, 돌봄 신청까지 같이 해줘."
    )
    candidates = search(
        query=query,
        bm25_index=registry.bm25_index,
        registry=registry,
        top_k=8,
    )

    assert candidates[0].tool_id == "mock_submit_module_gov24_minwon"
    assert _retrieval_policy_requires_initial_verify(candidates) is True
    assert _query_prefers_resolve_location_before_verify(query, candidates) is False


def test_delegation_plan_prefers_submit_source_over_login_lookup_source() -> None:
    from kosmos.tools.search import search

    registry = _registry_with_all_tools()
    query = (
        "가족관계증명서랑 주민등록등본이 필요한데 법원 제출용으로 "
        "발급하고 제출 가능한지 확인해줘."
    )
    candidates = search(
        query=query,
        bm25_index=registry.bm25_index,
        registry=registry,
        top_k=8,
    )

    verify_tool_id, scopes = _delegation_plan_from_candidates(candidates, registry)

    assert candidates[0].tool_id == "mock_lookup_module_gov24_certificate"
    assert verify_tool_id == "mock_verify_ganpyeon_injeung"
    assert "lookup:gov24.certificate" in scopes
    assert "submit:gov24.minwon" in scopes


def test_delegation_plan_grants_same_namespace_lookup_and_submit_scopes() -> None:
    registry = _registry_with_all_tools()
    args = _build_policy_forced_verify_args(
        "가족관계증명서 발급하고 사망신고랑 국민연금 유족급여 신청까지 도와줘.",
        registry,
    )

    assert args is not None
    params = args["params"]
    assert isinstance(params, dict)
    assert "lookup:gov24.certificate" in params["scope_list"]
    assert "submit:gov24.minwon" in params["scope_list"]


def test_subscribe_top_query_can_still_require_location_followup_lookup() -> None:
    registry = _registry_with_all_tools()
    query = (
        "부모님 지역에 폭염, 미세먼지, 정전, 단수 알림을 묶어서 받아보고 "
        "위험하면 내가 대신 확인할 수 있게 해줘."
    )

    assert _query_implies_followup_lookup(
        query,
        registry=registry,
    )


def test_subscribe_top_verify_intent_does_not_move_location_before_verify() -> None:
    from kosmos.tools.search import search

    registry = _registry_with_all_tools()
    query = (
        "부모님 지역에 폭염, 미세먼지, 정전, 단수 알림을 묶어서 받아보고 "
        "위험하면 내가 대신 확인할 수 있게 해줘."
    )
    candidates = search(
        query=query,
        bm25_index=registry.bm25_index,
        registry=registry,
        top_k=8,
    )

    assert candidates[0].primitive == "subscribe"
    assert _retrieval_policy_requires_initial_verify(candidates) is True
    assert _query_prefers_resolve_location_before_verify(query, candidates) is False


def test_public_lookup_chain_forces_registry_subscribe_before_final() -> None:
    registry = _registry_with_all_tools()
    messages = [
        {
            "role": "tool",
            "name": "lookup",
            "content": json.dumps(
                {
                    "result": {
                        "kind": "collection",
                        "items": [{"name": "mock hospital"}],
                        "total_count": 1,
                    }
                },
                ensure_ascii=False,
            ),
        }
    ]

    followup = _check_public_subscribe_terminated_early(
        messages,
        (
            "아이가 밤에 열이 높아. 지금 갈 수 있는 응급실이나 "
            "야간진료 병원 찾고 보험 적용되는지도 알려줘."
        ),
        registry=registry,
    )

    assert followup is not None
    assert followup[0] == "subscribe"


def test_mydata_verified_chain_forces_welfare_submit_without_delegation_context() -> None:
    registry = _registry_with_all_tools()
    query = (
        "생활비가 부족해. 내가 받을 수 있는 기초생활, 주거급여, "
        "긴급복지 지원을 찾아서 신청 가능한 것부터 진행해줘."
    )
    messages = [
        {
            "role": "tool",
            "name": "verify",
            "content": json.dumps(
                {
                    "result": {
                        "result": {
                            "family": "mydata",
                            "published_tier": "mydata_individual_aal2",
                            "nist_aal_hint": "AAL2",
                        }
                    }
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "tool",
            "name": "lookup",
            "content": json.dumps(
                {"result": {"kind": "collection", "items": [{"servNm": "주거급여"}]}},
                ensure_ascii=False,
            ),
        },
    ]

    followup = _check_privileged_chain_terminated_early(
        messages,
        query,
        registry=registry,
    )

    assert followup is not None
    assert followup[0] == "submit"
    assert _build_forced_submit_args(
        query,
        messages,
        registry,
    )["tool_id"] == "mock_welfare_application_submit_v1"


def test_pending_submit_blocks_early_subscribe() -> None:
    registry = _registry_with_all_tools()
    messages = [
        {
            "role": "tool",
            "name": "verify",
            "content": json.dumps(
                {
                    "result": {
                        "result": {
                            "published_tier": "ganpyeon_injeung_kakao_aal2",
                            "nist_aal_hint": "AAL2",
                            "delegation_context": {
                                "token": {
                                    "delegation_token": "del-test",
                                    "scope": "submit:gov24.minwon",
                                }
                            },
                        }
                    }
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "tool",
            "name": "lookup",
            "content": json.dumps(
                {"result": {"kind": "record", "item": {"found": True}}},
                ensure_ascii=False,
            ),
        },
    ]

    followup = _check_pending_submit_before_non_submit(
        "subscribe",
        messages,
        "모바일 신분증 발급하고 정부24랑 홈택스에서 쓸 수 있게 인증 수단도 연결해줘.",
        registry=registry,
    )

    assert followup is not None
    assert followup[0] == "submit"


def test_submit_args_reject_peer_aal_adapter_after_mydata_verify() -> None:
    registry = _registry_with_all_tools()
    messages = [
        {
            "role": "tool",
            "name": "verify",
            "content": json.dumps(
                {
                    "result": {
                        "result": {
                            "family": "mydata",
                            "published_tier": "mydata_individual_aal2",
                            "nist_aal_hint": "AAL2",
                        }
                    }
                },
                ensure_ascii=False,
            ),
        }
    ]

    assert not _submit_args_compatible_with_latest_auth(
        {"tool_id": "mock_submit_module_gov24_minwon", "params": {}},
        messages,
        registry,
    )
    assert _submit_args_compatible_with_latest_auth(
        {"tool_id": "mock_welfare_application_submit_v1", "params": {}},
        messages,
        registry,
    )


def test_submit_args_reject_ungranted_scope_even_when_tier_matches() -> None:
    registry = _registry_with_all_tools()
    messages = [
        {
            "role": "tool",
            "name": "verify",
            "content": json.dumps(
                {
                    "result": {
                        "result": {
                            "published_tier": "modid_aal3",
                            "delegation_context": {
                                "token": {
                                    "delegation_token": "del-hometax",
                                    "scope": (
                                        "lookup:hometax.simplified,"
                                        "submit:hometax.tax-return"
                                    ),
                                }
                            },
                        }
                    }
                },
                ensure_ascii=False,
            ),
        }
    ]

    assert not _submit_args_compatible_with_latest_auth(
        {"tool_id": "mock_submit_module_gov24_minwon", "params": {}},
        messages,
        registry,
    )
    assert _submit_args_compatible_with_latest_auth(
        {"tool_id": "mock_submit_module_hometax_taxreturn", "params": {}},
        messages,
        registry,
    )


def test_completed_submit_subscribe_blocks_extra_lookup() -> None:
    registry = _registry_with_all_tools()
    messages = [
        {
            "role": "tool",
            "name": "verify",
            "content": json.dumps(
                {
                    "result": {
                        "result": {
                            "family": "mydata",
                            "published_tier": "mydata_individual_aal2",
                            "nist_aal_hint": "AAL2",
                        }
                    }
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "tool",
            "name": "lookup",
            "content": json.dumps(
                {"result": {"kind": "collection", "items": [{"servNm": "임신출산"}]}},
                ensure_ascii=False,
            ),
        },
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call-submit-welfare",
                    "type": "function",
                    "function": {
                        "name": "submit",
                        "arguments": json.dumps(
                            {
                                "tool_id": "mock_welfare_application_submit_v1",
                                "params": {},
                            }
                        ),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "name": "submit",
            "tool_call_id": "call-submit-welfare",
            "content": json.dumps(
                {
                    "result": {
                        "status": "succeeded",
                        "adapter_receipt": {"status": "succeeded"},
                    }
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "tool",
            "name": "subscribe",
            "content": json.dumps(
                {
                    "kind": "subscribe",
                    "status": "opened",
                    "subscription_id": "sub-test",
                    "handle_id": "sub-test",
                },
                ensure_ascii=False,
            ),
        },
    ]

    followup = _check_tool_call_after_completed_submit_subscribe(
        "lookup",
        messages,
        (
            "임신했는데 받을 수 있는 지원금, 진료비 바우처, "
            "출산휴가 관련 신청을 한 번에 정리하고 신청해줘."
        ),
        registry=registry,
    )

    assert followup is not None
    assert followup[0] == "final"


def test_completed_submit_subscribe_allows_remaining_gov24_submit() -> None:
    registry = _registry_with_all_tools()
    messages = [
        {
            "role": "tool",
            "name": "verify",
            "content": json.dumps(
                {
                    "result": {
                        "result": {
                            "published_tier": "ganpyeon_injeung_kakao_aal2",
                            "nist_aal_hint": "AAL2",
                            "delegation_context": {
                                "token": {
                                    "delegation_token": "del-test",
                                    "scope": "submit:gov24.minwon",
                                }
                            },
                        }
                    }
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call-submit-gov24",
                    "type": "function",
                    "function": {
                        "name": "submit",
                        "arguments": json.dumps(
                            {
                                "tool_id": "mock_submit_module_gov24_minwon",
                                "params": {"minwon_type": "주민등록등본"},
                            }
                        ),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "name": "submit",
            "tool_call_id": "call-submit-gov24",
            "content": json.dumps(
                {
                    "result": {
                        "status": "succeeded",
                        "adapter_receipt": {
                            "status": "접수완료",
                            "minwon_type": "주민등록등본",
                        },
                    }
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "tool",
            "name": "subscribe",
            "content": json.dumps(
                {
                    "kind": "subscribe",
                    "status": "opened",
                    "subscription_id": "sub-test",
                    "handle_id": "sub-test",
                },
                ensure_ascii=False,
            ),
        },
    ]

    followup = _check_tool_call_after_completed_submit_subscribe(
        "submit",
        messages,
        "가족관계증명서랑 주민등록등본이 필요한데 법원 제출용으로 발급하고 제출 가능한지 확인해줘.",
        registry=registry,
    )

    assert followup is None


def test_completed_submit_blocks_low_confidence_lookup_drift() -> None:
    registry = _registry_with_all_tools()
    messages = [
        {
            "role": "tool",
            "name": "verify",
            "content": json.dumps(
                {
                    "result": {
                        "result": {
                            "family": "mydata",
                            "published_tier": "mydata_individual_aal2",
                            "nist_aal_hint": "AAL2",
                        }
                    }
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "tool",
            "name": "lookup",
            "content": json.dumps(
                {"result": {"kind": "record", "item": {"matched": ["medical_cost"]}}},
                ensure_ascii=False,
            ),
        },
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call-submit-medical",
                    "type": "function",
                    "function": {
                        "name": "submit",
                        "arguments": json.dumps(
                            {
                                "tool_id": "mock_welfare_application_submit_v1",
                                "params": {},
                            }
                        ),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "name": "submit",
            "tool_call_id": "call-submit-medical",
            "content": json.dumps(
                {
                    "result": {
                        "status": "succeeded",
                        "adapter_receipt": {"status": "succeeded"},
                    }
                },
                ensure_ascii=False,
            ),
        },
    ]

    followup = _check_tool_call_after_completed_submit(
        "lookup",
        messages,
        (
            "최근 병원비가 많이 나왔는데 실손 말고 국가에서 받을 수 있는 "
            "의료비 지원이나 본인부담상한제 대상인지 확인해줘."
        ),
        registry=registry,
    )

    assert followup is not None
    assert followup[0] == "final"


def test_completed_submit_forces_strong_subscribe_before_lookup() -> None:
    registry = _registry_with_all_tools()
    messages = [
        {
            "role": "tool",
            "name": "verify",
            "content": json.dumps(
                {
                    "result": {
                        "result": {
                            "family": "mydata",
                            "published_tier": "mydata_individual_aal2",
                            "nist_aal_hint": "AAL2",
                        }
                    }
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call-submit-welfare",
                    "type": "function",
                    "function": {
                        "name": "submit",
                        "arguments": json.dumps(
                            {
                                "tool_id": "mock_welfare_application_submit_v1",
                                "params": {},
                            }
                        ),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "name": "submit",
            "tool_call_id": "call-submit-welfare",
            "content": json.dumps(
                {
                    "result": {
                        "status": "succeeded",
                        "adapter_receipt": {"status": "succeeded"},
                    }
                },
                ensure_ascii=False,
            ),
        },
    ]

    followup = _check_tool_call_after_completed_submit(
        "lookup",
        messages,
        (
            "생활비가 부족해. 내가 받을 수 있는 기초생활, 주거급여, "
            "긴급복지 지원을 찾아서 신청 가능한 것부터 진행해줘."
        ),
        registry=registry,
    )

    assert followup is not None
    assert followup[0] == "subscribe"


def test_forced_submit_stops_after_completed_gov24_labor_bundle() -> None:
    registry = _registry_with_all_tools()
    messages = [
        {
            "role": "tool",
            "name": "verify",
            "content": json.dumps(
                {
                    "result": {
                        "result": {
                            "family": "ganpyeon_injeung",
                            "published_tier": "ganpyeon_injeung_kakao_aal2",
                            "nist_aal_hint": "AAL2",
                        }
                    }
                },
                ensure_ascii=False,
            ),
        },
        _assistant_tool_call_message(
            "submit-worknet",
            "submit",
            {
                "tool_id": "mock_submit_module_gov24_minwon",
                "params": {"minwon_type": "워크넷등록"},
            },
        ),
        {
            **_submit_tool_message(
                result_status="succeeded",
                receipt_status="접수완료",
                receipt_extra={"minwon_type": "워크넷등록"},
            ),
            "tool_call_id": "submit-worknet",
        },
        _assistant_tool_call_message(
            "submit-jobcenter",
            "submit",
            {
                "tool_id": "mock_submit_module_gov24_minwon",
                "params": {"minwon_type": "고용센터예약"},
            },
        ),
        {
            **_submit_tool_message(
                result_status="succeeded",
                receipt_status="접수완료",
                receipt_extra={"minwon_type": "고용센터예약"},
            ),
            "tool_call_id": "submit-jobcenter",
        },
    ]

    followup = _build_forced_submit_args(
        "퇴사했는데 실업급여 받을 수 있는지 확인하고 워크넷 등록이랑 고용센터 예약까지 해줘.",
        messages,
        registry,
    )

    assert followup is None


def test_welfare_lookup_schema_filters_pregnancy_birth_query() -> None:
    registry = _registry_with_all_tools()

    coerced = _coerce_adapter_params_from_schema(
        {"tool_id": "mohw_welfare_eligibility_search", "params": {}},
        user_query=(
            "임신했는데 받을 수 있는 지원금, 진료비 바우처, "
            "출산휴가 관련 신청을 한 번에 정리하고 신청해줘."
        ),
        registry=registry,
    )

    params = coerced["params"]
    assert isinstance(params, dict)
    assert params["life_array"] == "007"
    assert params["intrs_thema_array"] == "080"
    assert params["search_wrd"] == "출산"


def test_privileged_chain_prioritizes_subscribe_after_submit_receipt() -> None:
    registry = _registry_with_all_tools()
    messages = [
        {
            "role": "tool",
            "name": "verify",
            "content": json.dumps(
                {
                    "result": {
                        "result": {
                            "published_tier": "modid_aal3",
                            "delegation_context": {
                                "token": {
                                    "delegation_token": "del-test",
                                    "scope": "submit:hometax.tax-return",
                                }
                            },
                        }
                    }
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "tool",
            "name": "lookup",
            "content": json.dumps(
                {"result": {"kind": "record", "item": {"found": True}}},
                ensure_ascii=False,
            ),
        },
        {
            "role": "tool",
            "name": "submit",
            "content": json.dumps(
                {
                    "result": {
                        "status": "succeeded",
                        "adapter_receipt": {"status": "succeeded"},
                    }
                },
                ensure_ascii=False,
            ),
        },
    ]

    followup = _check_privileged_chain_terminated_early(
        messages,
        (
            "이번 달 재산세랑 자동차세, 과태료 밀린 거 있는지 확인하고 "
            "납부 가능한 건 한 번에 처리해줘."
        ),
        registry=registry,
    )

    assert followup is not None
    assert followup[0] == "subscribe"


def test_hometax_refund_query_forces_refund_account_second_submit() -> None:
    registry = _registry_with_all_tools()
    submit_call_id = "submit-hometax-file-return"
    messages = [
        _verified_tool_message(),
        _lookup_tool_message(),
        _assistant_tool_call_message(
            submit_call_id,
            "submit",
            {
                "tool_id": "mock_submit_module_hometax_taxreturn",
                "params": {"action_type": "file_return"},
            },
        ),
        {
            **_submit_tool_message(
                result_status="succeeded",
                receipt_status="신고완료",
                receipt_extra={
                    "action_type": "file_return",
                    "preflight_validation": {
                        "payment": "separate_submit_required_before_payment"
                    },
                },
            ),
            "tool_call_id": submit_call_id,
        },
    ]

    user_query = "작년 종합소득세 신고하고 환급받을 수 있으면 환급 계좌까지 등록해줘."
    followup = _check_privileged_chain_terminated_early(
        messages,
        user_query,
        registry=registry,
    )
    forced_submit = _build_forced_submit_args(user_query, messages, registry)

    assert followup is not None
    assert followup[0] == "submit"
    assert forced_submit is not None
    params = forced_submit["params"]
    assert isinstance(params, dict)
    assert params["action_type"] == "register_refund_account"


def test_gov24_multi_certificate_request_forces_second_submit() -> None:
    registry = _registry_with_all_tools()
    messages = [
        {
            "role": "tool",
            "name": "verify",
            "content": json.dumps(
                {
                    "result": {
                        "result": {
                            "published_tier": "ganpyeon_injeung_kakao_aal2",
                            "delegation_context": {
                                "token": {
                                    "delegation_token": "del-test",
                                    "scope": "submit:gov24.minwon",
                                }
                            },
                        }
                    }
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "tool",
            "name": "lookup",
            "content": json.dumps(
                {"result": {"kind": "record", "item": {"certificate_type": "resident"}}},
                ensure_ascii=False,
            ),
        },
        {
            "role": "tool",
            "name": "submit",
            "content": json.dumps(
                {
                    "result": {
                        "status": "succeeded",
                        "adapter_receipt": {
                            "status": "접수완료",
                            "minwon_type": "주민등록등본",
                        },
                    }
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "tool",
            "name": "lookup",
            "content": json.dumps(
                {"result": {"kind": "record", "item": {"certificate_type": "family"}}},
                ensure_ascii=False,
            ),
        },
    ]

    followup = _check_privileged_chain_terminated_early(
        messages,
        "가족관계증명서랑 주민등록등본이 필요한데 법원 제출용으로 발급하고 제출 가능한지 확인해줘.",
        registry=registry,
    )

    assert followup is not None
    assert followup[0] == "submit"


def test_subscribe_top_privileged_chain_subscribes_before_lookup_after_location() -> None:
    registry = _registry_with_all_tools()
    messages = [
        {
            "role": "tool",
            "name": "verify",
            "content": json.dumps(
                {
                    "result": {
                        "result": {
                            "published_tier": "ganpyeon_injeung_kakao_aal2",
                            "delegation_context": {
                                "token": {
                                    "delegation_token": "del-test",
                                    "scope": "verify:ganpyeon.identity",
                                }
                            },
                        }
                    }
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "tool",
            "name": "resolve_location",
            "content": json.dumps(
                {
                    "result": {
                        "kind": "resolve_location",
                        "lat": 35.059152,
                        "lon": 128.971316,
                        "b_code": "2638010100",
                        "address_name": "부산 사하구 다대1동",
                    }
                },
                ensure_ascii=False,
            ),
        },
    ]

    followup = _check_privileged_chain_terminated_early(
        messages,
        (
            "부모님 지역에 폭염, 미세먼지, 정전, 단수 알림을 묶어서 받아보고 "
            "위험하면 내가 대신 확인할 수 있게 해줘."
        ),
        registry=registry,
    )

    assert followup is not None
    assert followup[0] == "subscribe"


def test_normalise_resolve_location_admcd_to_bundle_request() -> None:
    args = _normalise_resolve_location_args(
        {"query": "부산 사하구 다대1동", "want": "adm_cd"}
    )

    assert args["want"] == "coords_and_admcd"


def test_coerce_nmc_emergency_search_fills_integer_limit() -> None:
    coerced = _coerce_adapter_params_from_schema(
        {"tool_id": "nmc_emergency_search", "params": {"lat": 35.1, "lon": 129.0}},
        user_query="현재 위치 근처 응급실 찾아줘.",
        registry=_registry_with_all_tools(),
    )

    params = coerced["params"]
    assert isinstance(params, dict)
    assert params["limit"] == 5


def test_coerce_kma_alert_status_fills_station_id_from_schema_description() -> None:
    coerced = _coerce_adapter_params_from_schema(
        {"tool_id": "kma_weather_alert_status", "params": {}},
        user_query="부산 부모님 지역의 폭염 특보 상태를 확인해줘.",
        registry=_registry_with_all_tools(),
    )

    params = coerced["params"]
    assert isinstance(params, dict)
    assert params["stn_id"] == "159"


def test_latest_kma_forecast_base_uses_publication_anchor() -> None:
    kst = ZoneInfo("Asia/Seoul")

    assert _latest_kma_forecast_base(datetime(2026, 5, 6, 10, 5, tzinfo=kst)) == (
        "20260506",
        "0800",
    )
    assert _latest_kma_forecast_base(datetime(2026, 5, 6, 2, 5, tzinfo=kst)) == (
        "20260505",
        "2300",
    )


def test_coerce_kma_forecast_overrides_target_date_with_publication_base() -> None:
    coerced = _coerce_adapter_params_from_schema(
        {
            "tool_id": "kma_forecast_fetch",
            "params": {
                "lat": 35.059152,
                "lon": 128.971316,
                "base_date": "20990101",
                "base_time": "0200",
            },
        },
        user_query="내일 부산에서 서울 가는데 날씨 확인해줘.",
        registry=_registry_with_all_tools(),
    )

    params = coerced["params"]
    assert isinstance(params, dict)
    assert params["base_date"] != "20990101"
    assert params["base_time"] in {"0200", "0500", "0800", "1100", "1400", "1700", "2000", "2300"}


def test_subscribe_direct_envelope_counts_as_success() -> None:
    assert _tool_payload_succeeded(
        {
            "kind": "subscribe",
            "subscription_id": "sub-test",
            "handle_id": "sub-test",
            "status": "opened",
        },
        "subscribe",
    )
    assert not _tool_payload_succeeded(
        {
            "kind": "subscribe",
            "tool_id": "mock_rest_pull_tick_v1",
            "error": "missing adapter",
        },
        "subscribe",
    )


def _verified_tool_message() -> dict[str, Any]:
    return {
        "role": "tool",
        "name": "verify",
        "content": json.dumps(
            {
                "kind": "verify",
                "result": {
                    "status": "verified",
                    "delegation_context": {
                        "token": {
                            "delegation_token": "del_test",
                            "scope_list": [
                                "lookup:hometax.simplified",
                                "submit:hometax.tax-return",
                            ],
                            "expires_at": "2026-05-07T00:00:00Z",
                        },
                        "purpose_ko": "양도소득세 신고",
                        "purpose_en": "Capital-gains tax filing",
                    },
                },
            },
            ensure_ascii=False,
        ),
    }


def _verified_ganpyeon_tier_tool_message() -> dict[str, Any]:
    return {
        "role": "tool",
        "name": "verify",
        "content": json.dumps(
            {
                "result": {
                    "result": {
                        "published_tier": "ganpyeon_injeung_kakao_aal2",
                        "nist_aal_hint": "AAL2",
                        "delegation_context": {
                            "token": {
                                "delegation_token": "del-test-gov24",
                                "scope": "submit:gov24.minwon",
                            }
                        },
                    }
                }
            },
            ensure_ascii=False,
        ),
    }


def _lookup_tool_message() -> dict[str, Any]:
    return {
        "role": "tool",
        "name": "lookup",
        "content": json.dumps(
            {
                "kind": "lookup",
                "result": {
                    "kind": "record",
                    "tool_id": "mock_lookup_module_hometax_simplified",
                    "data": {"taxpayer_type": "individual"},
                },
            },
            ensure_ascii=False,
        ),
    }


def _gov24_movein_lookup_tool_message() -> dict[str, Any]:
    return {
        "role": "tool",
        "name": "lookup",
        "content": json.dumps(
            {
                "kind": "lookup",
                "result": {
                    "kind": "record",
                    "item": {
                        "workflow_kind": "gov24_movein_dependent_sequence",
                        "required_sequence": [
                            {
                                "step": 1,
                                "primitive": "submit",
                                "tool_id": "mock_submit_module_gov24_minwon",
                                "minwon_type": "전입신고",
                            },
                            {
                                "step": 2,
                                "primitive": "submit",
                                "tool_id": "mock_submit_module_gov24_minwon",
                                "minwon_type": "주소변경",
                            },
                        ],
                        "suggested_submit_params": {
                            "first_submit": {
                                "tool_id": "mock_submit_module_gov24_minwon",
                                "params": {
                                    "minwon_type": "전입신고",
                                    "delivery_method": "online",
                                },
                            },
                            "linked_address_update": {
                                "tool_id": "mock_submit_module_gov24_minwon",
                                "params": {
                                    "minwon_type": "주소변경",
                                    "delivery_method": "online",
                                },
                            },
                        },
                    },
                },
            },
            ensure_ascii=False,
        ),
    }


def _national_ax_bundle_lookup_tool_message() -> dict[str, Any]:
    return {
        "role": "tool",
        "name": "lookup",
        "content": json.dumps(
            {
                "kind": "lookup",
                "result": {
                    "kind": "record",
                    "item": {
                        "workflow_kind": "national_ax_bundle_discovery",
                        "lookup_ref": "mock-national-ax-bundle-20260505-001",
                    },
                },
            },
            ensure_ascii=False,
        ),
    }


def _resolve_location_tool_message() -> dict[str, Any]:
    return {
        "role": "tool",
        "name": "resolve_location",
        "content": json.dumps(
            {
                "kind": "resolve_location",
                "result": {
                    "kind": "bundle",
                    "source": "bundle",
                    "coords": {
                        "kind": "coords",
                        "lat": 35.059152,
                        "lon": 128.971316,
                        "confidence": "high",
                        "source": "kakao",
                    },
                    "adm_cd": {
                        "kind": "adm_cd",
                        "code": "2638010600",
                        "name": "부산광역시 사하구 다대동",
                        "level": "eupmyeondong",
                        "source": "kakao",
                    },
                },
            },
            ensure_ascii=False,
        ),
    }


def _resolve_location_v4_tool_message() -> dict[str, Any]:
    return {
        "role": "tool",
        "name": "resolve_location",
        "content": json.dumps(
            {
                "kind": "resolve_location",
                "result": {
                    "lat": 35.059152,
                    "lon": 128.971316,
                    "b_code": "2638010600",
                    "address_name": "부산광역시 사하구 다대동",
                    "confidence": "high",
                    "source": "kakao",
                },
            },
            ensure_ascii=False,
        ),
    }


def _assistant_tool_call_message(
    call_id: str,
    name: str,
    args_obj: dict[str, Any],
) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(args_obj, ensure_ascii=False),
                },
            }
        ],
    }


def _submit_tool_message(
    *,
    result_status: str,
    receipt_status: str,
    receipt_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    receipt = {
        "receipt_id": "hometax-test-RX-1",
        "status": receipt_status,
        "_mode": "mock",
    }
    if receipt_extra:
        receipt.update(receipt_extra)
    return {
        "role": "tool",
        "name": "submit",
        "content": json.dumps(
            {
                "kind": "submit",
                "result": {
                    "transaction_id": "urn:kosmos:submit:test",
                    "status": result_status,
                    "adapter_receipt": receipt,
                },
            },
            ensure_ascii=False,
        ),
    }


def test_tool_result_completion_answer_summarizes_lookup_and_submit() -> None:
    messages = [
        _assistant_tool_call_message(
            "lookup-1",
            "lookup",
            {"tool_id": "mock_lookup_module_hometax_simplified", "params": {}},
        ),
        {
            **_lookup_tool_message(),
            "tool_call_id": "lookup-1",
        },
        _assistant_tool_call_message(
            "submit-1",
            "submit",
            {"tool_id": "mock_submit_module_hometax_taxreturn", "params": {}},
        ),
        {
            **_submit_tool_message(
                result_status="succeeded",
                receipt_status="신고완료",
            ),
            "tool_call_id": "submit-1",
        },
    ]

    answer = _build_tool_result_completion_answer(messages)

    assert answer is not None
    assert "도구 결과 기준으로 처리 상태를 정리합니다" in answer
    assert "조회 `mock_lookup_module_hometax_simplified`: 1건" in answer
    assert "모의 제출: 접수" in answer
    assert "접수번호 hometax-test-RX-1" in answer


def test_tool_result_completion_answer_includes_timeseries_counts() -> None:
    messages = [
        _assistant_tool_call_message(
            "lookup-weather-1",
            "lookup",
            {"tool_id": "kma_forecast_fetch", "params": {}},
        ),
        {
            "role": "tool",
            "name": "lookup",
            "tool_call_id": "lookup-weather-1",
            "content": json.dumps(
                {
                    "kind": "timeseries",
                    "points": [{"timestamp_iso": "2026-05-06T09:00:00"}],
                    "interval": "hour",
                    "meta": {
                        "source": "kma_forecast_fetch",
                        "fetched_at": "2026-05-06T11:02:00+09:00",
                        "request_id": "req-weather",
                        "elapsed_ms": 1,
                    },
                },
                ensure_ascii=False,
            ),
        },
    ]

    answer = _build_tool_result_completion_answer(messages)

    assert answer is not None
    assert "조회 `kma_forecast_fetch`: 시계열 1건" in answer


def test_tool_result_completion_answer_returns_none_without_tool_results() -> None:
    assert _build_tool_result_completion_answer([{"role": "user", "content": "hi"}]) is None


def test_grounding_recovery_non_medical_chain_uses_completion_summary() -> None:
    messages = [
        _assistant_tool_call_message(
            "lookup-welfare-1",
            "lookup",
            {"tool_id": "mohw_welfare_eligibility_search", "params": {}},
        ),
        {
            "role": "tool",
            "name": "lookup",
            "tool_call_id": "lookup-welfare-1",
            "content": json.dumps(
                {"kind": "error", "reason": "completed_submit_subscribe_chain"},
                ensure_ascii=False,
            ),
        },
        _assistant_tool_call_message(
            "submit-welfare-1",
            "submit",
            {"tool_id": "mock_welfare_application_submit_v1", "params": {}},
        ),
        {
            **_submit_tool_message(
                result_status="succeeded",
                receipt_status="succeeded",
                receipt_extra={"benefit_code": "emergency_welfare"},
            ),
            "tool_call_id": "submit-welfare-1",
        },
    ]

    answer = _build_grounded_safety_answer(messages)

    assert answer is not None
    assert "도구 결과 기준으로 처리 상태를 정리합니다" in answer
    assert "completed_submit_subscribe_chain" not in answer
    assert "mohw_welfare_eligibility_search" not in answer
    assert "119" not in answer
    assert "E-Gen" not in answer


def test_final_answer_rejects_reasking_already_resolved_address() -> None:
    submit_call_id = "submit-gov24-1"
    messages = [
        _resolve_location_tool_message(),
        _assistant_tool_call_message(
            submit_call_id,
            "submit",
            {
                "tool_id": "mock_submit_module_gov24_minwon",
                "params": {"minwon_type": "전입신고"},
            },
        ),
        {
            **_submit_tool_message(
                result_status="succeeded",
                receipt_status="접수완료",
                receipt_extra={"minwon_type": "전입신고"},
            ),
            "tool_call_id": submit_call_id,
        },
    ]

    violation = _check_final_answer_grounding(
        "새 주소를 알려주시면 전학신청을 이어서 처리하겠습니다.",
        messages,
    )
    answer = _build_grounded_safety_answer(messages)

    assert violation is not None
    assert "address" in violation
    assert answer is not None
    assert "도구 결과 기준으로 처리 상태를 정리합니다" in answer


def test_final_answer_rejects_no_registered_tool_claim_after_submit_success() -> None:
    submit_call_id = "submit-koroad-1"
    messages = [
        _assistant_tool_call_message(
            submit_call_id,
            "submit",
            {
                "tool_id": "mock_koroad_driver_fitness_reservation_v1",
                "params": {"applicant_id": "mock-applicant"},
            },
        ),
        {
            **_submit_tool_message(
                result_status="succeeded",
                receipt_status="reserved",
                receipt_extra={
                    "receipt_id": "koroad-resv-test",
                    "reservation_type": "fitness_test",
                },
            ),
            "tool_call_id": submit_call_id,
        },
    ]

    violation = _check_final_answer_grounding(
        "현재 시스템은 예약·납부를 대리 처리하는 도구가 등록되어 있지 않습니다.",
        messages,
    )

    assert violation is not None
    assert "registered tool" in violation


def test_final_answer_rejects_external_handoff_after_submit_success() -> None:
    submit_call_id = "submit-koroad-1"
    messages = [
        _assistant_tool_call_message(
            submit_call_id,
            "submit",
            {
                "tool_id": "mock_koroad_driver_fitness_reservation_v1",
                "params": {"applicant_id": "mock-applicant"},
            },
        ),
        {
            **_submit_tool_message(
                result_status="succeeded",
                receipt_status="reserved",
                receipt_extra={
                    "receipt_id": "koroad-resv-test",
                    "reservation_type": "fitness_test",
                },
            ),
            "tool_call_id": submit_call_id,
        },
    ]

    violation = _check_final_answer_grounding(
        "적성검사 예약은 안전운전 통합민원 사이트에서 직접 진행하셔야 합니다.",
        messages,
    )

    assert violation is not None
    assert "external-site" in violation


def test_final_answer_rejects_official_service_direct_handoff_after_submit_success() -> None:
    submit_call_id = "submit-welfare-1"
    messages = [
        _assistant_tool_call_message(
            submit_call_id,
            "submit",
            {
                "tool_id": "mock_welfare_application_submit_v1",
                "params": {"benefit_code": "pregnancy_birth"},
            },
        ),
        {
            **_submit_tool_message(
                result_status="succeeded",
                receipt_status="succeeded",
                receipt_extra={"benefit_code": "pregnancy_birth"},
            ),
            "tool_call_id": submit_call_id,
        },
    ]

    violation = _check_final_answer_grounding(
        "실제 지원금 신청은 공식 서비스인 복지로를 통해 직접 진행해야 합니다.",
        messages,
    )

    assert violation is not None
    assert "external-site" in violation


def test_final_answer_rejects_dismissing_successful_subscribe() -> None:
    messages = [
        {
            "role": "tool",
            "name": "subscribe",
            "content": json.dumps(
                {
                    "kind": "subscribe",
                    "status": "opened",
                    "subscription_id": "sub-test",
                    "handle_id": "sub-test",
                },
                ensure_ascii=False,
            ),
        }
    ]

    violation = _check_final_answer_grounding(
        "실시간 알림 구독은 이 요청과 무관하므로 즉시 종료해야 합니다.",
        messages,
    )

    assert violation is not None
    assert "subscribe handle" in violation


def test_final_answer_rejects_ungrounded_procedure_details_after_submit() -> None:
    submit_call_id = "submit-gov24-death-1"
    messages = [
        _assistant_tool_call_message(
            submit_call_id,
            "submit",
            {
                "tool_id": "mock_submit_module_gov24_minwon",
                "params": {"minwon_type": "사망신고"},
            },
        ),
        {
            **_submit_tool_message(
                result_status="succeeded",
                receipt_status="접수완료",
                receipt_extra={"minwon_type": "사망신고"},
            ),
            "tool_call_id": submit_call_id,
        },
    ]

    violation = _check_final_answer_grounding(
        (
            "필요 서류는 사망진단서이고, 처리 기간은 2~4주입니다. "
            "정부24 콜센터 110과 국민연금공단 1355로 문의하세요."
        ),
        messages,
    )

    assert violation is not None
    assert "procedural" in violation

    violation = _check_final_answer_grounding(
        "가능한 지원금 유형과 자격요건, 신청방법, 세제혜택을 안내합니다.",
        messages,
    )

    assert violation is not None
    assert "procedural" in violation


def test_final_answer_rejects_cross_domain_alert_all_clear_without_status_payload() -> None:
    messages = [
        {
            "role": "tool",
            "name": "subscribe",
            "content": json.dumps(
                {
                    "kind": "subscribe",
                    "status": "opened",
                    "subscription_id": "sub-test",
                    "handle_id": "sub-test",
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "tool",
            "name": "lookup",
            "content": json.dumps(
                {
                    "kind": "collection",
                    "items": [],
                    "total_count": 0,
                    "meta": {
                        "source": "kma_weather_alert_status",
                        "fetched_at": "2026-05-06T10:54:00+09:00",
                        "request_id": "req-test",
                        "elapsed_ms": 1,
                    },
                },
                ensure_ascii=False,
            ),
        },
    ]

    violation = _check_final_answer_grounding(
        "미세먼지·정전·단수 관련 공식 경보는 발령되지 않은 상태입니다.",
        messages,
    )

    assert violation is not None
    assert "fine-dust" in violation


def test_final_answer_rejects_transit_recommendation_without_transit_payload() -> None:
    messages = [
        {
            "role": "tool",
            "name": "lookup",
            "content": json.dumps(
                {
                    "kind": "timeseries",
                    "points": [{"timestamp_iso": "2026-05-06T09:00:00"}],
                    "interval": "hour",
                    "meta": {
                        "source": "kma_forecast_fetch",
                        "fetched_at": "2026-05-06T10:54:00+09:00",
                        "request_id": "req-weather",
                        "elapsed_ms": 1,
                    },
                },
                ensure_ascii=False,
            ),
        },
        {
            "role": "tool",
            "name": "lookup",
            "content": json.dumps(
                {
                    "kind": "collection",
                    "items": [{"spot_nm": "부산 사하구 당리동"}],
                    "total_count": 1,
                    "meta": {
                        "source": "koroad_accident_hazard_search",
                        "fetched_at": "2026-05-06T10:54:00+09:00",
                        "request_id": "req-road",
                        "elapsed_ms": 1,
                    },
                },
                ensure_ascii=False,
            ),
        },
    ]

    violation = _check_final_answer_grounding(
        "KTX가 가장 안전하고 정시성이 높으며 부산역에서 서울역까지 약 2시간 30분 소요됩니다.",
        messages,
    )

    assert violation is not None
    assert "transit" in violation


def test_privileged_chain_rejected_submit_does_not_satisfy_submit_step() -> None:
    """A rejected submit result must not close the privileged chain gate.

    CIV-001/CIV-002 real-use captures showed the LLM calling Gov24 submit before
    prerequisites, receiving a rejected receipt, then moving on as if submit had
    succeeded. The terminal gate must force another submit attempt instead.
    """
    messages = [
        _verified_tool_message(),
        _lookup_tool_message(),
        _submit_tool_message(
            result_status="rejected",
            receipt_status="rejected",
            receipt_extra={"error": "scope_violation"},
        ),
    ]

    followup = _check_privileged_chain_terminated_early(
        messages,
        "아파트 팔았는데 양도소득세 얼마나 나오는지 계산하고 신고 절차까지 안내해줘.",
        registry=_registry_with_all_tools(),
    )

    assert followup is not None
    assert followup[0] == "submit"


def test_privileged_chain_successful_submit_satisfies_submit_step() -> None:
    messages = [
        _verified_tool_message(),
        _lookup_tool_message(),
        _submit_tool_message(result_status="succeeded", receipt_status="신고완료"),
    ]

    followup = _check_privileged_chain_terminated_early(
        messages,
        "아파트 팔았는데 양도소득세 얼마나 나오는지 계산하고 신고 절차까지 안내해줘.",
        registry=_registry_with_all_tools(),
    )

    assert followup is None


def test_submit_prerequisite_forces_lookup_before_tax_submit() -> None:
    prerequisite = _check_submit_prerequisite(
        "submit",
        [_verified_tool_message()],
        "아파트 팔았는데 양도소득세 얼마나 나오는지 계산하고 신고 절차까지 안내해줘.",
        registry=_registry_with_all_tools(),
    )

    assert prerequisite is not None
    assert prerequisite[0] == "lookup"


def test_submit_prerequisite_forces_resolve_location_before_address_submit() -> None:
    prerequisite = _check_submit_prerequisite(
        "submit",
        [_verified_tool_message()],
        "현재 위치는 부산 사하구 다대1동입니다. 이사했어. 전입신고하고 자동차, "
        "건강보험, 학교 관련 주소도 한 번에 바꿔줘.",
        registry=_registry_with_all_tools(),
    )

    assert prerequisite is not None
    assert prerequisite[0] == "resolve_location"


def test_submit_prerequisite_allows_submit_after_successful_lookup() -> None:
    prerequisite = _check_submit_prerequisite(
        "submit",
        [_verified_tool_message(), _lookup_tool_message()],
        "아파트 팔았는데 양도소득세 얼마나 나오는지 계산하고 신고 절차까지 안내해줘.",
        registry=_registry_with_all_tools(),
    )

    assert prerequisite is None


def test_lookup_enrichment_fills_admcd_from_resolve_result() -> None:
    args = {
        "tool_id": "mock_lookup_module_gov24_movein_sequence",
        "params": {},
    }

    enriched = _enrich_lookup_args_from_resolve_result(
        args,
        [_resolve_location_tool_message()],
        _registry_with_all_tools(),
    )

    params = enriched.get("params")
    assert isinstance(params, dict)
    assert params["adm_cd"] == "2638010600"
    assert params["address"] == "부산광역시 사하구 다대동"


def test_lookup_enrichment_accepts_flat_resolve_location_v4_result() -> None:
    args = {
        "tool_id": "mock_lookup_module_gov24_movein_sequence",
        "params": {},
    }

    enriched = _enrich_lookup_args_from_resolve_result(
        args,
        [_resolve_location_v4_tool_message()],
        _registry_with_all_tools(),
    )

    params = enriched.get("params")
    assert isinstance(params, dict)
    assert params["adm_cd"] == "2638010600"
    assert params["address"] == "부산광역시 사하구 다대동"


def test_gov24_movein_submit_sequence_advances_from_lookup_record() -> None:
    first = _next_gov24_movein_submit_args([_gov24_movein_lookup_tool_message()])

    assert first is not None
    assert first["tool_id"] == "mock_submit_module_gov24_minwon"
    first_params = first["params"]
    assert isinstance(first_params, dict)
    assert first_params["minwon_type"] == "전입신고"
    assert first_params["delivery_method"] == "online"
    assert first_params["applicant_name"] == "verified_citizen_mock"

    submit_call_id = "submit-gov24-1"
    second = _next_gov24_movein_submit_args(
        [
            _gov24_movein_lookup_tool_message(),
            _assistant_tool_call_message(
                submit_call_id,
                "submit",
                {
                    "tool_id": "mock_submit_module_gov24_minwon",
                    "params": {"minwon_type": "전입신고"},
                },
            ),
            {
                **_submit_tool_message(
                    result_status="succeeded",
                    receipt_status="접수완료",
                    receipt_extra={"minwon_type": "전입신고"},
                ),
                "tool_call_id": submit_call_id,
            },
        ]
    )

    assert second is not None
    second_params = second["params"]
    assert isinstance(second_params, dict)
    assert second_params["minwon_type"] == "주소변경"


def test_gov24_movein_submit_sequence_completes_after_required_steps() -> None:
    first_submit_call_id = "submit-gov24-1"
    second_submit_call_id = "submit-gov24-2"
    messages = [
        _gov24_movein_lookup_tool_message(),
        _assistant_tool_call_message(
            first_submit_call_id,
            "submit",
            {
                "tool_id": "mock_submit_module_gov24_minwon",
                "params": {"minwon_type": "전입신고"},
            },
        ),
        {
            **_submit_tool_message(
                result_status="succeeded",
                receipt_status="접수완료",
                receipt_extra={"minwon_type": "전입신고"},
            ),
            "tool_call_id": first_submit_call_id,
        },
        _assistant_tool_call_message(
            second_submit_call_id,
            "submit",
            {
                "tool_id": "mock_submit_module_gov24_minwon",
                "params": {"minwon_type": "주소변경"},
            },
        ),
        {
            **_submit_tool_message(
                result_status="succeeded",
                receipt_status="접수완료",
                receipt_extra={"minwon_type": "주소변경"},
            ),
            "tool_call_id": second_submit_call_id,
        },
    ]

    assert _next_gov24_movein_submit_args(messages) is None
    assert _gov24_movein_sequence_completed(messages)


def test_education_movein_chain_forces_initial_submit_before_lookup() -> None:
    user_query = (
        "현재 위치는 부산 사하구 다대1동입니다. 이사 때문에 아이 학교 전학이 "
        "필요해. 전입신고랑 전학 절차, 돌봄 신청까지 같이 해줘."
    )
    messages = [_verified_ganpyeon_tier_tool_message(), _resolve_location_tool_message()]

    followup = _check_privileged_chain_terminated_early(
        messages,
        user_query,
        registry=_registry_with_all_tools(),
    )
    forced_submit = _build_forced_submit_args(
        user_query,
        messages,
        _registry_with_all_tools(),
    )

    assert followup is not None
    assert followup[0] == "submit"
    assert forced_submit is not None
    assert forced_submit["tool_id"] == "mock_submit_module_gov24_minwon"
    params = forced_submit["params"]
    assert isinstance(params, dict)
    assert params["minwon_type"] == "전입신고"


def test_education_movein_chain_forces_resolve_before_initial_submit() -> None:
    user_query = (
        "현재 위치는 부산 사하구 다대1동입니다. 이사 때문에 아이 학교 전학이 "
        "필요해. 전입신고랑 전학 절차, 돌봄 신청까지 같이 해줘."
    )

    followup = _check_privileged_chain_terminated_early(
        [_verified_ganpyeon_tier_tool_message()],
        user_query,
        registry=_registry_with_all_tools(),
    )

    assert followup is not None
    assert followup[0] == "resolve_location"


def test_mobility_chain_forces_lookup_immediately_after_verify() -> None:
    """MOB-001 must not be allowed to re-open the same verify ceremony.

    Real-use capture target-state-mob001-after-koroad-submit-and-subscribe-heading
    showed verify completing, then the next model turn issuing the same verify
    call again. The harness-owned post-tool gate must force the registry-selected
    lookup as soon as DelegationContext exists.
    """
    user_query = (
        "운전면허 갱신해야 하는지 확인하고 적성검사 예약, 과태료, "
        "자동차세까지 같이 봐줘."
    )
    registry = _registry_with_all_tools()
    messages = [_verified_tool_message()]

    followup = _check_privileged_chain_terminated_early(
        messages,
        user_query,
        registry=registry,
    )
    forced_lookup = _build_forced_lookup_args(user_query, messages, registry)

    assert followup is not None
    assert followup[0] == "lookup"
    assert forced_lookup is not None
    assert forced_lookup["tool_id"] == "mock_lookup_module_national_ax_bundle"


def test_education_direct_gov24_submit_skips_lookup_prerequisite_after_resolve() -> None:
    user_query = (
        "현재 위치는 부산 사하구 다대1동입니다. 이사 때문에 아이 학교 전학이 "
        "필요해. 전입신고랑 전학 절차, 돌봄 신청까지 같이 해줘."
    )

    prerequisite = _check_submit_prerequisite(
        "submit",
        [_verified_ganpyeon_tier_tool_message(), _resolve_location_tool_message()],
        user_query,
        registry=_registry_with_all_tools(),
    )

    assert prerequisite is None


def test_flood_damage_location_first_submit_skips_lookup_prerequisite() -> None:
    user_query = (
        "현재 위치는 부산 사하구 다대1동입니다. 집이 침수됐어. "
        "피해 신고, 재난지원금, 임시주거, 전기·가스 안전 점검까지 바로 도와줘."
    )

    prerequisite = _check_submit_prerequisite(
        "submit",
        [_verified_ganpyeon_tier_tool_message(), _resolve_location_tool_message()],
        user_query,
        registry=_registry_with_all_tools(),
    )

    assert prerequisite is None


def test_education_movein_chain_prefers_bundle_lookup_after_initial_submit() -> None:
    user_query = (
        "현재 위치는 부산 사하구 다대1동입니다. 이사 때문에 아이 학교 전학이 "
        "필요해. 전입신고랑 전학 절차, 돌봄 신청까지 같이 해줘."
    )
    submit_call_id = "submit-gov24-edu-1"
    messages = [
        _verified_tool_message(),
        _resolve_location_tool_message(),
        _assistant_tool_call_message(
            submit_call_id,
            "submit",
            {
                "tool_id": "mock_submit_module_gov24_minwon",
                "params": {"minwon_type": "전입신고"},
            },
        ),
        {
            **_submit_tool_message(
                result_status="succeeded",
                receipt_status="접수완료",
                receipt_extra={"minwon_type": "전입신고"},
            ),
            "tool_call_id": submit_call_id,
        },
    ]

    forced_lookup = _build_forced_lookup_args(
        user_query,
        messages,
        _registry_with_all_tools(),
    )

    assert forced_lookup is not None
    assert forced_lookup["tool_id"] == "mock_lookup_module_national_ax_bundle"


def test_flood_damage_chain_blocks_lookup_until_requested_gov24_submits_complete() -> None:
    user_query = (
        "현재 위치는 부산 사하구 다대1동입니다. 집이 침수됐어. "
        "피해 신고, 재난지원금, 임시주거, 전기·가스 안전 점검까지 바로 도와줘."
    )
    registry = _registry_with_all_tools()
    messages = [_verified_ganpyeon_tier_tool_message(), _resolve_location_tool_message()]

    followup = _check_pending_submit_before_non_submit(
        "lookup",
        messages,
        user_query,
        registry=registry,
    )

    assert followup is not None
    assert followup[0] == "submit"


def test_education_chain_allows_bundle_lookup_after_initial_gov24_submit() -> None:
    user_query = (
        "현재 위치는 부산 사하구 다대1동입니다. 이사 때문에 아이 학교 전학이 "
        "필요해. 전입신고랑 전학 절차, 돌봄 신청까지 같이 해줘."
    )
    submit_call_id = "submit-gov24-edu-lookup-1"
    messages = [
        _verified_ganpyeon_tier_tool_message(),
        _resolve_location_tool_message(),
        _assistant_tool_call_message(
            submit_call_id,
            "submit",
            {
                "tool_id": "mock_submit_module_gov24_minwon",
                "params": {"minwon_type": "전입신고"},
            },
        ),
        {
            **_submit_tool_message(
                result_status="succeeded",
                receipt_status="접수완료",
                receipt_extra={"minwon_type": "전입신고"},
            ),
            "tool_call_id": submit_call_id,
        },
    ]

    followup = _check_pending_submit_before_non_submit(
        "lookup",
        messages,
        user_query,
        registry=_registry_with_all_tools(),
    )

    assert followup is None


def test_education_direct_followup_flow_completed_after_matched_minwon_receipts() -> None:
    user_query = (
        "현재 위치는 부산 사하구 다대1동입니다. 이사 때문에 아이 학교 전학이 "
        "필요해. 전입신고랑 전학 절차, 돌봄 신청까지 같이 해줘."
    )
    movein_call_id = "submit-gov24-edu-1"
    bundle_call_id = "lookup-national-bundle"
    transfer_call_id = "submit-gov24-edu-transfer"
    care_call_id = "submit-gov24-edu-2"
    messages = [
        _verified_tool_message(),
        _resolve_location_tool_message(),
        _assistant_tool_call_message(
            movein_call_id,
            "submit",
            {
                "tool_id": "mock_submit_module_gov24_minwon",
                "params": {"minwon_type": "전입신고"},
            },
        ),
        {
            **_submit_tool_message(
                result_status="succeeded",
                receipt_status="접수완료",
                receipt_extra={"minwon_type": "전입신고"},
            ),
            "tool_call_id": movein_call_id,
        },
        _assistant_tool_call_message(
            bundle_call_id,
            "lookup",
            {
                "tool_id": "mock_lookup_module_national_ax_bundle",
                "params": {},
            },
        ),
        {
            **_national_ax_bundle_lookup_tool_message(),
            "tool_call_id": bundle_call_id,
        },
        _assistant_tool_call_message(
            transfer_call_id,
            "submit",
            {
                "tool_id": "mock_submit_module_gov24_minwon",
                "params": {"minwon_type": "전학신청"},
            },
        ),
        {
            **_submit_tool_message(
                result_status="succeeded",
                receipt_status="접수완료",
                receipt_extra={"minwon_type": "전학신청"},
            ),
            "tool_call_id": transfer_call_id,
        },
        _assistant_tool_call_message(
            care_call_id,
            "submit",
            {
                "tool_id": "mock_submit_module_gov24_minwon",
                "params": {"minwon_type": "돌봄신청"},
            },
        ),
        {
            **_submit_tool_message(
                result_status="succeeded",
                receipt_status="접수완료",
                receipt_extra={"minwon_type": "돌봄신청"},
            ),
            "tool_call_id": care_call_id,
        },
    ]

    assert _gov24_direct_followup_flow_completed(
        user_query,
        messages,
        _registry_with_all_tools(),
    )


def test_privileged_chain_forces_second_gov24_movein_submit() -> None:
    submit_call_id = "submit-gov24-1"
    followup = _check_privileged_chain_terminated_early(
        [
            _verified_ganpyeon_tier_tool_message(),
            _gov24_movein_lookup_tool_message(),
            _assistant_tool_call_message(
                submit_call_id,
                "submit",
                {
                    "tool_id": "mock_submit_module_gov24_minwon",
                    "params": {"minwon_type": "전입신고"},
                },
            ),
            {
                **_submit_tool_message(
                    result_status="succeeded",
                    receipt_status="접수완료",
                    receipt_extra={"minwon_type": "전입신고"},
                ),
                "tool_call_id": submit_call_id,
            },
        ],
        "현재 위치는 부산 사하구 다대1동입니다. 이사했어. 전입신고하고 자동차, "
        "건강보험, 학교 관련 주소도 한 번에 바꿔줘.",
        registry=_registry_with_all_tools(),
    )

    assert followup is not None
    assert followup[0] == "submit"


@pytest.mark.asyncio
async def test_dispatch_verify_legacy_family_alias_still_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tools-bridge legacy alias ``family`` (instead of ``family_hint``)
    must keep working when ``tool_id`` is absent."""
    args_obj: dict[str, Any] = {
        "family": "mobile_id",
        "session_context": {"session_id": "test-legacy-alias"},
    }
    frame = _make_chat_request("legacy verify alias mobile_id")
    buf = await _run_verify_dispatch(frame, args_obj, monkeypatch)

    frames = buf.as_frames()
    parts = _extract_verify_envelope(frames)
    inner = parts["inner"]

    assert inner.get("family") == "mobile_id", (
        f"legacy family='mobile_id' alias must still dispatch; inner={inner!r}"
    )


@pytest.mark.asyncio
async def test_dispatch_verify_empty_tool_id_falls_back_to_mismatch_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When neither tool_id nor family_hint is provided, the dispatcher
    must surface a ``VerifyMismatchError`` (family='mismatch_error') —
    not crash, not silently succeed."""
    args_obj: dict[str, Any] = {
        "tool_id": "",
        "session_context": {},
    }
    frame = _make_chat_request("empty verify args")
    buf = await _run_verify_dispatch(frame, args_obj, monkeypatch)

    frames = buf.as_frames()
    parts = _extract_verify_envelope(frames)
    inner = parts["inner"]

    assert inner.get("family") == "mismatch_error", (
        f"empty verify args must surface VerifyMismatchError, got "
        f"family={inner.get('family')!r}; inner={inner!r}"
    )


@pytest.mark.asyncio
async def test_dispatch_verify_unknown_tool_id_fails_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown citizen-shape tool_ids must fail before adapter dispatch."""
    args_obj: dict[str, Any] = {
        "tool_id": "mock_verify_does_not_exist",
        "session_context": {},
    }
    frame = _make_chat_request("unknown verify tool_id")
    buf = await _run_verify_dispatch(frame, args_obj, monkeypatch)

    frames = buf.as_frames()
    tool_results = [f for f in frames if f.get("kind") == "tool_result"]
    assert tool_results, f"No tool_result frames emitted; got {frames!r}"
    envelope = tool_results[0].get("envelope", {})
    assert isinstance(envelope, dict)
    assert envelope.get("kind") == "verify"
    result = envelope.get("result", {})
    message = (
        result.get("message")
        if isinstance(result, dict)
        else envelope.get("error")
    )
    assert "unknown verify tool_id" in str(message)
