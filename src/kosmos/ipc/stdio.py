# SPDX-License-Identifier: Apache-2.0
"""Asyncio-based JSONL stdio reader/writer loop for the TUI ↔ backend IPC bridge.

Protocol
--------
* Every frame is a single line of JSON terminated by a newline (``\\n``).
* The backend reads frames from ``stdin`` and writes frames to ``stdout``.
* ``stderr`` is reserved for diagnostic / log output; TUI consumes it for crash notices.
* Graceful shutdown: ``SIGTERM`` / ``SIGINT`` → drain in-flight work → write
  ``session_event {event="exit"}`` → flush stdout → exit 0.
* ``stdout`` is flushed after every written frame (FR-005 ordering invariant).

Usage
-----
This module is invoked by the CLI when ``--ipc stdio`` is passed::

    uv run kosmos --ipc stdio

The ``run()`` coroutine is the public entry point; it blocks until the session
exits.  The ``write_frame()`` helper is available for code that needs to push
frames from outside this module.
"""

from __future__ import annotations

import asyncio
import contextlib
import json as _stdlib_json
import logging
import os
import re
import signal
import sys
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import FrameType, SimpleNamespace
from typing import TYPE_CHECKING, Any, Final, Literal, cast
from zoneinfo import ZoneInfo

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from pydantic import TypeAdapter, ValidationError

from kosmos.ipc.envelope import attach_envelope_span_attributes
from kosmos.ipc.frame_schema import (
    ErrorFrame,
    IPCFrame,
    SessionEventFrame,
)

if TYPE_CHECKING:
    from kosmos.session.manager import SessionManager

logger = logging.getLogger(__name__)

# Module-level tracer — follows the same pattern as kosmos.tools.executor and
# kosmos.engine.query (trace.get_tracer(__name__) at module load time).
_tracer = trace.get_tracer(__name__)

_CORE_PRIMITIVE_TOOL_IDS: set[str] = {
    "lookup",
    "resolve_location",
    "verify",
    "submit",
    "subscribe",
}
_DELEGATION_SCOPE_RE = re.compile(r"^(lookup|submit|verify|subscribe):[a-z0-9_]+\.[a-z0-9_-]+$")
_KMA_FORECAST_BASE_TIMES: Final[tuple[str, ...]] = (
    "0200",
    "0500",
    "0800",
    "1100",
    "1400",
    "1700",
    "2000",
    "2300",
)

# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

_frame_adapter: TypeAdapter[Any] = TypeAdapter(IPCFrame)


def _serialize_primitive_result(raw: object) -> dict[str, Any]:
    """Coerce a primitive return value to a JSON-serialisable dict.

    Pydantic models go through ``model_dump(mode="json")``; everything else
    falls back to ``{"raw": str(value)}`` so the envelope round-trip stays
    safe. Helper extracted from inline expressions to keep the dispatcher
    body under the line-length limit.
    """
    dump = getattr(raw, "model_dump", None)
    if callable(dump):
        result = dump(mode="json")
        if isinstance(result, dict):
            return result
        return {"raw": result}
    return {"raw": str(raw)}


# Module-level stdout lock — prevents interleaved JSON if multiple async tasks
# write simultaneously (guards the flush-after-every-frame invariant).
_stdout_lock: asyncio.Lock | None = None


# ---------------------------------------------------------------------------
# Spec spec-multi-turn-contamination — diagnostic instrumentation (DIAGNOSTIC
# ONLY, gated by KOSMOS_CHAT_REQUEST_DUMP=1; off by default — production
# behavior is unchanged when the env var is unset).
#
# Per-session turn counter; rebuilt at process boot, in-memory only.
# Increments at the entry of `_handle_chat_request` for every ChatRequestFrame
# whose session_id matches. Lets the diagnostic cross-correlate three layers
# (chat_messages_built / chat_request_dump / latest_user_utt / reasoning_preview)
# by `(session_id, turn_index)`.
# ---------------------------------------------------------------------------

_session_turn_counter: dict[str, int] = {}


def _diag_chat_request_enabled() -> bool:
    """Return True when KOSMOS_CHAT_REQUEST_DUMP env var is set to '1'.

    Helper exists so the env-var lookup is centralised and the call sites
    stay one-liners that are easy to grep / remove later.
    """
    return os.getenv("KOSMOS_CHAT_REQUEST_DUMP") == "1"


def _get_stdout_lock() -> asyncio.Lock:
    global _stdout_lock
    if _stdout_lock is None:
        _stdout_lock = asyncio.Lock()
    return _stdout_lock


# ---------------------------------------------------------------------------
# Frame I/O primitives
# ---------------------------------------------------------------------------


async def write_frame(
    frame: IPCFrame,
    *,
    _assembly_start_ns: int | None = None,
    tx_cache_state: Literal["miss", "hit", "stored"] | None = None,
) -> None:
    """Serialise *frame* to a single JSON line and write it to stdout.

    Flushes stdout immediately after every frame to preserve the FIFO ordering
    invariant required by the TUI (FR-005).

    Thread-safety: serialised by ``_stdout_lock`` so concurrent coroutines
    cannot interleave partial JSON.

    OTEL: emits a ``kosmos.ipc.frame`` child span (FR-053) with direction
    ``"outbound"``.  ``_assembly_start_ns`` is the ``time.monotonic_ns()``
    captured by the caller before building the frame payload; when absent,
    the span clock starts at the write call itself.  ``tx_cache_state`` is
    forwarded from the :class:`~kosmos.ipc.transaction_lru.TransactionLRU`
    path for irreversible-tool frames (Spec 032 T048 / FR-053).
    """
    t0_ns = _assembly_start_ns if _assembly_start_ns is not None else time.monotonic_ns()
    payload = frame.model_dump_json() + "\n"
    encoded = payload.encode("utf-8")
    lock = _get_stdout_lock()
    with _tracer.start_as_current_span("kosmos.ipc.frame") as span:
        try:
            async with lock:
                sys.stdout.buffer.write(encoded)
                sys.stdout.buffer.flush()
            latency_ms = (time.monotonic_ns() - t0_ns) / 1_000_000
            span.set_attribute("kosmos.session.id", frame.session_id)
            span.set_attribute("kosmos.frame.kind", frame.kind)
            span.set_attribute("kosmos.frame.direction", "outbound")
            span.set_attribute("kosmos.ipc.latency_ms", latency_ms)
            # Audit G4 — explicit arm-name + correlation_id span attribute so
            # cross-team triage (e.g. F-ε-02 silent plugin_op chase) can grep
            # OTLP for which arm + correlation went out the wire.
            if frame.correlation_id:
                span.set_attribute("kosmos.frame.correlation_id", frame.correlation_id)
            attach_envelope_span_attributes(frame, tx_cache_state=tx_cache_state)
        except Exception as exc:  # noqa: BLE001
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR))
            raise


def _write_frame_sync(frame: IPCFrame) -> None:
    """Synchronous variant used in signal handlers (no event loop available)."""
    payload = frame.model_dump_json() + "\n"
    sys.stdout.buffer.write(payload.encode("utf-8"))
    sys.stdout.buffer.flush()


# ---------------------------------------------------------------------------
# Reader loop
# ---------------------------------------------------------------------------


async def _reader_loop(
    stream: asyncio.StreamReader,
    on_frame: Callable[[IPCFrame], Any],
    session_id: str,
) -> None:
    """Read newline-delimited JSON frames from *stream* and dispatch them.

    Malformed lines are logged at ERROR and an ``error`` frame is sent back
    rather than crashing the loop (data-model.md § 1.4).
    """
    while True:
        try:
            line = await stream.readline()
        except (asyncio.IncompleteReadError, ConnectionResetError):
            logger.debug("stdin EOF or connection reset — stopping reader loop")
            break

        if not line:
            logger.debug("stdin EOF — stopping reader loop")
            break

        raw = line.decode("utf-8", errors="replace").strip()
        if not raw:
            continue  # skip blank lines

        try:
            frame = _frame_adapter.validate_json(raw)
        except (ValidationError, ValueError) as exc:
            logger.error("IPC decode error: %s | raw=%r", exc, raw[:200])
            # Emit an error frame back to the TUI (malformed input from TUI
            # should be surfaced, not silently dropped).
            err_frame = ErrorFrame(
                session_id=session_id,
                correlation_id=str(uuid.uuid4()),
                role="backend",
                ts=_utcnow(),
                kind="error",
                code="ipc_decode_error",
                message="Failed to decode IPC frame from TUI",
                details={"raw_preview": raw[:200]},
            )
            await write_frame(err_frame)
            continue

        logger.debug("IPC frame received: kind=%s session=%s", frame.kind, frame.session_id)
        _dispatch_start_ns = time.monotonic_ns()
        with _tracer.start_as_current_span("kosmos.ipc.frame") as span:
            try:
                result = on_frame(frame)
                if asyncio.iscoroutine(result):
                    await result
                latency_ms = (time.monotonic_ns() - _dispatch_start_ns) / 1_000_000
                span.set_attribute("kosmos.session.id", frame.session_id)
                span.set_attribute("kosmos.frame.kind", frame.kind)
                span.set_attribute("kosmos.frame.direction", "inbound")
                span.set_attribute("kosmos.ipc.latency_ms", latency_ms)
                attach_envelope_span_attributes(frame)
            except Exception as exc:  # noqa: BLE001
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                logger.exception("on_frame handler raised: %s", exc)


# ---------------------------------------------------------------------------
# Shutdown helpers
# ---------------------------------------------------------------------------


# Coordinate / admin-code field names that signal a downstream tool needs
# resolve_location to have run first (Epic #2766 chain prerequisite gate).
# The literal field set is intentionally broader than what any single
# adapter accepts so the gate catches every variant the LLM might pick.
_COORD_INPUT_FIELDS: frozenset[str] = frozenset(
    {
        "xPos",
        "yPos",
        "lat",
        "lon",
        "latitude",
        "longitude",
        "nx",
        "ny",
        "x",
        "y",
    }
)
_ADMCD_INPUT_FIELDS: frozenset[str] = frozenset(
    {
        "adm_cd",
        "siGunGuCd",
        "sgg_cd",
        "si_do",
        "gu_gun",
        "h_code",
        "b_code",
    }
)


def _check_chain_prerequisite(  # noqa: C901
    fname: str,
    args_obj: dict[str, object],
    llm_messages: list[Any],
    registry: Any = None,
) -> str | None:
    """Return chain-recovery error message when a prerequisite is missing.

    CC reference: ``Tool.validateInput?(input, context)`` in
    ``.references/claude-code-sourcemap/restored-src/src/Tool.ts:489``.
    The CC hook is tool-scoped; KOSMOS centralises the equivalent
    pre-dispatch check here because every coord-input adapter has the
    identical prerequisite (resolve_location must have been called in
    a prior turn of the same conversation). Adapter-scoped overrides can
    be added later by extending this function to dispatch on tool_id.

    Returns ``None`` when the call is allowed; returns a descriptive
    error message when the call should be rejected. The caller emits
    that message verbatim to the LLM via a tool_result envelope so the
    next agentic-loop turn can recover.
    """
    # Only the `lookup` primitive carries adapter calls (mode='fetch'
    # routes to a registered GovAPITool). All other primitives are
    # either coord-free (verify) or carry their own param schema
    # (submit, subscribe, resolve_location).
    if fname != "lookup":
        return None
    if not isinstance(args_obj, dict):
        return None
    # Accept both shapes the LLM emits: full {mode:'fetch', tool_id, params}
    # AND the abbreviated {tool_id, params} where mode is implicit. K-EXAONE
    # frequently omits mode when tool_id is set; treating those as fetch
    # closes the bypass that lets a tool_id=hira_* call slip past the gate
    # just because mode was unset.
    mode = args_obj.get("mode")
    tool_id = args_obj.get("tool_id")
    if mode not in (None, "fetch"):
        return None
    if not isinstance(tool_id, str) or not tool_id:
        return None
    params_obj = args_obj.get("params")
    params: dict[str, object] = params_obj if isinstance(params_obj, dict) else {}

    # Two ways to recognise a coord-input adapter call:
    # 1. The supplied params already carry coordinate/admcd fields — the
    #    LLM filled them in (possibly from prior knowledge). This is the
    #    primary failure mode the gate exists to catch.
    # 2. The supplied params are empty / coord-free, but the tool_id's
    #    registered input_schema declares coord/admcd fields. The LLM is
    #    about to hit invalid_params; getting here gives the chain hint
    #    one turn earlier and saves the round-trip.
    has_coord = any(k in params for k in _COORD_INPUT_FIELDS)
    has_admcd = any(k in params for k in _ADMCD_INPUT_FIELDS)
    schema_coord_fields: set[str] = set()
    schema_admcd_fields: set[str] = set()
    if not (has_coord or has_admcd):
        # Inspect the adapter's declared input schema to find out whether
        # this is a coord/admcd tool that simply has not been parameterised
        # yet. Best-effort — adapter lookup failures fall through as
        # "unknown shape, allow".
        if registry is None:
            return None
        try:
            tool = registry.lookup(tool_id)
            schema = tool.input_schema.model_json_schema()
            props = schema.get("properties", {})
            schema_coord_fields = set(props) & _COORD_INPUT_FIELDS
            schema_admcd_fields = set(props) & _ADMCD_INPUT_FIELDS
            if not (schema_coord_fields or schema_admcd_fields):
                return None
        except Exception:  # noqa: BLE001
            # Unknown tool / registry not booted — let the dispatcher
            # produce its own unknown_tool error instead of guessing.
            return None

    # Walk prior turns for a resolve_location invocation. Both function-
    # call envelopes (assistant.tool_calls[*].function.name) and the
    # textual <tool_call> markers (assistant.content) count — K-EXAONE
    # uses both. We accept either as evidence the citizen's location
    # was canonicalised through the registered resolver.
    for m in llm_messages:
        # LLMChatMessage instance OR dict — handle both.
        role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else None)
        if role != "assistant":
            continue
        tool_calls = getattr(m, "tool_calls", None) or (
            m.get("tool_calls") if isinstance(m, dict) else None
        )
        if tool_calls:
            for tc in tool_calls:
                call_fn = getattr(getattr(tc, "function", None), "name", None) or (
                    tc.get("function", {}).get("name") if isinstance(tc, dict) else None
                )
                if call_fn == "resolve_location":
                    return None
        content = getattr(m, "content", None) or (m.get("content") if isinstance(m, dict) else None)
        if isinstance(content, str) and "resolve_location" in content:
            # Textual <tool_call> marker fallback for K-EXAONE inline form.
            return None

    # Field naming: prefer the actually-supplied params (the LLM tipped its
    # hand on which fields it tried to fill), otherwise fall back to the
    # schema-introspected field set so the recovery message names something
    # the LLM can actually produce.
    missing_coord = (set(params.keys()) & _COORD_INPUT_FIELDS) or schema_coord_fields
    missing_admcd = (set(params.keys()) & _ADMCD_INPUT_FIELDS) or schema_admcd_fields
    missing_fields = sorted(missing_coord | missing_admcd)
    if has_coord or schema_coord_fields:
        field_kind = "coordinates"
    elif has_admcd or schema_admcd_fields:
        field_kind = "administrative code"
    else:
        field_kind = "location parameters"
    return (
        f"Chain prerequisite missing: this tool requires {field_kind} "
        f"({', '.join(missing_fields) if missing_fields else 'see input schema'}) "
        f"that MUST come from a prior resolve_location call in the same "
        f"conversation. No resolve_location turn precedes the current call — "
        f"that means the values would be guessed from prior knowledge instead "
        f"of being resolved against Kakao Local API. "
        f"RECOVERY: in the next turn call resolve_location(query='<지역명>', "
        f"want='coords') to obtain the canonical lat/lon for the citizen's "
        f"location, then re-invoke this tool with the returned values. Do NOT "
        f"guess coordinates."
    )


# ---------------------------------------------------------------------------
# Follow-up lookup gate (G-class fabrication countermeasure — 2026-05-04)
# ---------------------------------------------------------------------------
def _candidate_requires_resolved_location(candidate: object) -> bool:
    """Return True when a retrieved adapter declares location-derived inputs.

    The signal is the adapter's exported Pydantic input schema, not a query
    keyword list. This keeps the final-answer gate aligned with the live tool
    registry: if a future agency adapter stops requiring coordinates, this
    gate stops requiring a resolve → lookup chain without any router edit.
    """
    tool_id = getattr(candidate, "tool_id", "")
    primitive = getattr(candidate, "primitive", None)
    if tool_id == "resolve_location" or primitive != "lookup":
        return False
    schema = getattr(candidate, "input_schema_json", None)
    if not isinstance(schema, dict):
        return False
    props = schema.get("properties")
    if not isinstance(props, dict):
        return False
    field_names = set(props)
    return bool(field_names & (_COORD_INPUT_FIELDS | _ADMCD_INPUT_FIELDS))


def _query_implies_followup_lookup(
    user_query: str,
    *,
    registry: object | None = None,
    top_k: int = 12,
) -> bool:
    """Derive the resolve → lookup requirement from live adapter metadata.

    G-class chain enforcement: the integration-verification capture
    ``snap-001-01-kma-now`` showed K-EXAONE calling ``resolve_location`` twice
    and then producing a fabricated weather answer (16°C / 84% humidity vs
    raw KMA 20.7°C / 23%) without ever invoking a data adapter. The fix is
    no longer a keyword table. We run the same registry retrieval used for
    ``<available_adapters>`` and require a follow-up only when the top positive
    candidate is a lookup adapter whose schema declares coordinate or
    administrative-code inputs.
    """
    q = (user_query or "").strip()
    if not q or registry is None:
        return False
    try:
        from kosmos.tools.search import search  # noqa: PLC0415

        candidates = search(
            query=q,
            bm25_index=registry.bm25_index,  # type: ignore[attr-defined]
            registry=registry,  # type: ignore[arg-type]
            top_k=top_k,
        )
    except Exception:  # noqa: BLE001
        logger.exception("follow-up lookup policy retrieval failed for '%s'", q[:80])
        return False
    positive_candidates = _relevant_positive_candidates(candidates)
    if not positive_candidates:
        return False
    if _candidate_requires_resolved_location(positive_candidates[0]):
        return True
    top_tool_id = getattr(positive_candidates[0], "tool_id", None) or getattr(
        positive_candidates[0],
        "id",
        None,
    )
    if top_tool_id == "resolve_location":
        top_score = getattr(positive_candidates[0], "score", 0.0)
        return any(
            _candidate_requires_resolved_location(candidate)
            and getattr(candidate, "score", 0.0) >= top_score * 0.75
            for candidate in positive_candidates[1:]
            if getattr(candidate, "primitive", None) == "lookup"
        )
    if getattr(positive_candidates[0], "primitive", None) == "subscribe":
        return any(
            _candidate_requires_resolved_location(candidate)
            for candidate in positive_candidates[1:]
            if getattr(candidate, "primitive", None) == "lookup"
        )
    return False


def _conversation_has_verify(llm_messages: list[Any]) -> bool:
    for m in llm_messages:
        role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else None)
        if role == "tool":
            name = getattr(m, "name", None) or (m.get("name") if isinstance(m, dict) else None)
            if name == "verify":
                return True
            continue
        if role != "assistant":
            continue
        tool_calls = getattr(m, "tool_calls", None) or (
            m.get("tool_calls") if isinstance(m, dict) else None
        )
        if not tool_calls:
            continue
        for tc in tool_calls:
            call_fn = getattr(getattr(tc, "function", None), "name", None) or (
                tc.get("function", {}).get("name") if isinstance(tc, dict) else None
            )
            if call_fn == "verify":
                return True
    return False


def _conversation_has_primitive(llm_messages: list[Any], primitive_name: str) -> bool:
    for m in llm_messages:
        role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else None)
        if role == "tool":
            name = getattr(m, "name", None) or (m.get("name") if isinstance(m, dict) else None)
            if name == primitive_name:
                return True
            continue
        if role != "assistant":
            continue
        tool_calls = getattr(m, "tool_calls", None) or (
            m.get("tool_calls") if isinstance(m, dict) else None
        )
        if not tool_calls:
            continue
        for tc in tool_calls:
            call_fn = getattr(getattr(tc, "function", None), "name", None) or (
                tc.get("function", {}).get("name") if isinstance(tc, dict) else None
            )
            if call_fn == primitive_name:
                return True
    return False


def _tool_message_payload(message: Any, primitive_name: str) -> dict[str, object] | None:
    role = getattr(message, "role", None) or (
        message.get("role") if isinstance(message, dict) else None
    )
    name = getattr(message, "name", None) or (
        message.get("name") if isinstance(message, dict) else None
    )
    if role != "tool" or name != primitive_name:
        return None
    content = getattr(message, "content", None) or (
        message.get("content") if isinstance(message, dict) else None
    )
    if not isinstance(content, str) or not content:
        return None
    try:
        payload = _stdlib_json.loads(content)
    except (_stdlib_json.JSONDecodeError, TypeError):
        return None
    if isinstance(payload, dict):
        return cast("dict[str, object]", payload)
    return None


def _tool_payload_result(payload: dict[str, object]) -> dict[str, object] | None:
    result = payload.get("result")
    if isinstance(result, dict):
        nested_result = result.get("result")
        if isinstance(nested_result, dict):
            return cast("dict[str, object]", nested_result)
        return cast("dict[str, object]", result)
    return None


def _status_is_rejected_or_failed(status: object) -> bool:
    if not isinstance(status, str):
        return False
    return status.strip().lower() in {
        "rejected",
        "failed",
        "반려",
        "반려됨",
        "실패",
    }


def _tool_payload_succeeded(payload: dict[str, object], primitive_name: str) -> bool:
    if payload.get("kind") == "error":
        return False
    result = _tool_payload_result(payload)
    if result is None:
        if primitive_name == "subscribe" and payload.get("kind") == "subscribe":
            return payload.get("status") == "opened" and (
                isinstance(payload.get("subscription_id"), str)
                or isinstance(payload.get("handle_id"), str)
            )
        return False
    if result.get("kind") == "error":
        return False
    if _status_is_rejected_or_failed(result.get("status")):
        return False
    adapter_receipt = result.get("adapter_receipt")
    if isinstance(adapter_receipt, dict):
        if _status_is_rejected_or_failed(adapter_receipt.get("status")):
            return False
        if adapter_receipt.get("error") or adapter_receipt.get("reason"):
            return False
    if primitive_name == "submit":
        return result.get("status") in {"succeeded", "accepted"}
    return True


def _conversation_has_successful_primitive(
    llm_messages: list[Any],
    primitive_name: str,
) -> bool:
    for message in llm_messages:
        payload = _tool_message_payload(message, primitive_name)
        if payload is None:
            continue
        if _tool_payload_succeeded(payload, primitive_name):
            return True
    return False


def _latest_verify_result(llm_messages: list[Any]) -> dict[str, object] | None:
    """Return the latest verified AuthContext payload emitted by verify."""
    for m in reversed(llm_messages):
        role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else None)
        if role != "tool":
            continue
        name = getattr(m, "name", None) or (m.get("name") if isinstance(m, dict) else None)
        if name != "verify":
            continue
        content = getattr(m, "content", None) or (m.get("content") if isinstance(m, dict) else None)
        if not isinstance(content, str) or not content:
            continue
        try:
            payload = _stdlib_json.loads(content)
        except (_stdlib_json.JSONDecodeError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        result = payload.get("result")
        if isinstance(result, dict):
            nested_result = result.get("result")
            if isinstance(nested_result, dict):
                return cast("dict[str, object]", nested_result)
            return cast("dict[str, object]", result)
    return None


def _latest_delegation_context(llm_messages: list[Any]) -> dict[str, object] | None:
    """Return the latest DelegationContext emitted by a verify tool result."""
    result = _latest_verify_result(llm_messages)
    if result is not None:
        delegation_context = result.get("delegation_context")
        if isinstance(delegation_context, dict):
            return cast("dict[str, object]", delegation_context)
    return None


def _delegation_context_from_auth_context(auth_context: object | None) -> dict[str, object] | None:
    delegation_context = getattr(auth_context, "delegation_context", None)
    if delegation_context is None:
        return None
    dump = getattr(delegation_context, "model_dump", None)
    if callable(dump):
        dumped = dump(mode="json")
        if isinstance(dumped, dict):
            return cast("dict[str, object]", dumped)
    if isinstance(delegation_context, dict):
        return cast("dict[str, object]", delegation_context)
    return None


def _mock_delegation_context_for_tool(
    tool_id: str,
    *,
    session_id: str,
    user_query: str,
    registry: Any,
) -> dict[str, object] | None:
    """Build a scope-bound mock DelegationContext for mock-only MyData actions."""
    scope = _required_scope_for_registry_tool(registry, tool_id)
    if not isinstance(scope, str) or not _is_valid_delegation_scope(scope):
        return None
    issued_at = datetime.now(UTC)
    delegation_token = f"del_{uuid.uuid4().hex}"
    issuer_did = "did:web:kosmos.local:mock-mydata"
    expires_at = issued_at + timedelta(hours=1)
    try:
        from kosmos.memdir.consent_ledger import (  # noqa: PLC0415
            DelegationIssuedEvent,
            append_delegation_issued,
        )

        append_delegation_issued(
            DelegationIssuedEvent(
                ts=issued_at,
                session_id=session_id,
                delegation_token=delegation_token,
                scope=scope,
                expires_at=expires_at,
                issuer_did=issuer_did,
                verify_tool_id="mock_verify_mydata",
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "mock delegation issuance ledger append failed for tool_id=%s session=%s: %s",
            tool_id,
            session_id,
            exc,
        )
    return {
        "token": {
            "vp_jwt": "mock-header.mock-payload.mock-signature-not-cryptographic",
            "delegation_token": delegation_token,
            "scope": scope,
            "issuer_did": issuer_did,
            "issued_at": issued_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "_mode": "mock",
        },
        "citizen_did": "did:web:kosmos.local:citizen:mock",
        "purpose_ko": (user_query or "정부 서비스 위임 처리")[:200],
        "purpose_en": "Citizen-requested delegated government service workflow.",
    }


def _permission_visible_arguments(args_obj: dict[str, object]) -> dict[str, object]:
    """Return permission-prompt args with backend-only identity fields removed."""
    visible = dict(args_obj)
    visible.pop("delegation_context", None)
    params_obj = visible.get("params")
    if isinstance(params_obj, dict):
        params = dict(cast("dict[str, object]", params_obj))
        for key in (
            "delegation_context",
            "identity_assertion",
            "session_context",
            "session_id",
        ):
            params.pop(key, None)
        visible["params"] = params
    return visible


def _copy_coord_fields(source: dict[str, object], target: dict[str, object]) -> None:
    lat = source.get("lat")
    lon = source.get("lon")
    if isinstance(lat, int | float):
        target["lat"] = float(lat)
    if isinstance(lon, int | float):
        target["lon"] = float(lon)


def _copy_admcd_fields(source: dict[str, object], target: dict[str, object]) -> None:
    code = source.get("code")
    name = source.get("name")
    if isinstance(code, str) and code:
        target["adm_cd"] = code
    if isinstance(name, str) and name:
        target["address"] = name


def _copy_address_fields(source: dict[str, object], target: dict[str, object]) -> None:
    road = source.get("road_address")
    jibun = source.get("jibun_address")
    if isinstance(road, str) and road:
        target["address"] = road
    elif isinstance(jibun, str) and jibun:
        target["address"] = jibun


def _copy_flat_resolve_fields(source: dict[str, object], target: dict[str, object]) -> None:
    """Copy the v4 flat resolve_location payload into reusable adapter fields."""
    _copy_coord_fields(source, target)
    b_code = source.get("b_code") or source.get("adm_cd")
    if isinstance(b_code, str) and b_code:
        target["adm_cd"] = b_code
    address_name = source.get("address_name") or source.get("address")
    if isinstance(address_name, str) and address_name:
        target["address"] = address_name


def _resolve_location_fields_from_result(result: dict[str, object]) -> dict[str, object]:
    fields: dict[str, object] = {}
    kind = result.get("kind")
    if kind == "bundle":
        coords = result.get("coords")
        adm = result.get("adm_cd")
        address = result.get("address")
        if isinstance(coords, dict):
            _copy_coord_fields(cast("dict[str, object]", coords), fields)
        if isinstance(adm, dict):
            _copy_admcd_fields(cast("dict[str, object]", adm), fields)
        if isinstance(address, dict):
            _copy_address_fields(cast("dict[str, object]", address), fields)
    elif kind == "adm_cd":
        _copy_admcd_fields(result, fields)
    elif kind == "coords":
        _copy_coord_fields(result, fields)
    else:
        # Spec 2522 v4 resolve_location returns a flat payload:
        # {lat, lon, b_code, address_name, confidence, source}.  The previous
        # enrichment parser only understood the older discriminated-union
        # shape and therefore failed to pass adm_cd/address into Gov24 lookup
        # after a successful resolve_location turn.
        _copy_flat_resolve_fields(result, fields)
    return fields


def _latest_resolve_location_fields(llm_messages: list[Any]) -> dict[str, object]:
    """Extract reusable location fields from the latest resolve_location result."""
    for message in reversed(llm_messages):
        payload = _tool_message_payload(message, "resolve_location")
        if payload is None:
            continue
        result = _tool_payload_result(payload)
        if result is None:
            continue
        fields = _resolve_location_fields_from_result(result)
        if fields:
            return fields
    return {}


def _enrich_lookup_args_from_resolve_result(  # noqa: C901
    args_obj: dict[str, object],
    llm_messages: list[Any],
    registry: Any,
) -> dict[str, object]:
    """Fill missing lookup location params from prior resolve_location output.

    The signal is adapter schema metadata: only fields declared by the selected
    GovAPITool are injected. This preserves registry-driven routing and avoids
    query-keyword special cases.
    """
    tool_id = args_obj.get("tool_id")
    if not isinstance(tool_id, str) or not tool_id:
        return args_obj
    try:
        tool = registry.lookup(tool_id)
        schema = tool.input_schema.model_json_schema()
    except Exception:  # noqa: BLE001
        return args_obj
    props = schema.get("properties")
    if not isinstance(props, dict):
        return args_obj
    wanted = set(props) & {
        "adm_cd",
        "b_code",
        "h_code",
        "siGunGuCd",
        "siGunGu_cd",
        "si_do",
        "gu_gun",
        "sgg_cd",
        "address",
        "address_name",
        "lat",
        "lon",
        "latitude",
        "longitude",
        "xPos",
        "yPos",
        "x",
        "y",
    }
    if not wanted:
        return args_obj
    resolved = _latest_resolve_location_fields(llm_messages)
    if not resolved:
        return args_obj
    params_obj = args_obj.get("params")
    params: dict[str, object] = dict(params_obj) if isinstance(params_obj, dict) else {}
    changed = False
    for key in wanted:
        if key not in params and key in resolved:
            params[key] = resolved[key]
            changed = True
    lat = resolved.get("lat")
    lon = resolved.get("lon")
    if isinstance(lat, int | float) and isinstance(lon, int | float):
        coord_aliases: dict[str, float] = {
            "lat": float(lat),
            "latitude": float(lat),
            "y": float(lat),
            "yPos": float(lat),
            "lon": float(lon),
            "longitude": float(lon),
            "x": float(lon),
            "xPos": float(lon),
        }
        for key, value in coord_aliases.items():
            if key in wanted and key not in params:
                params[key] = value
                changed = True
    adm_cd = resolved.get("adm_cd") or resolved.get("b_code")
    if isinstance(adm_cd, str) and adm_cd:
        for key in ("adm_cd", "b_code", "h_code", "siGunGuCd", "siGunGu_cd", "sgg_cd"):
            if key in wanted and key not in params:
                params[key] = adm_cd
                changed = True
    address = resolved.get("address") or resolved.get("address_name")
    if isinstance(address, str) and address:
        for key in ("address", "address_name"):
            if key in wanted and key not in params:
                params[key] = address
                changed = True
    if not changed:
        return args_obj
    enriched = dict(args_obj)
    enriched["params"] = params
    return enriched


def _extract_explicit_location_text(user_query: str) -> str:
    match = re.search(r"현재 위치는\s*(.+?)\s*입니다[.。]?", user_query)
    if match:
        return match.group(1).strip()
    return ""


def _query_explicitly_requests_verify_primitive(user_query: str) -> bool:
    return bool(re.search(r"\bverify\b", user_query or "", flags=re.IGNORECASE))


def _schema_for_adapter_args(
    args_obj: dict[str, object],
    registry: Any,
) -> dict[str, object] | None:
    tool_id = args_obj.get("tool_id")
    if not isinstance(tool_id, str) or not tool_id or tool_id in _CORE_PRIMITIVE_TOOL_IDS:
        return None
    try:
        tool = registry.lookup(tool_id)
        schema = tool.input_schema.model_json_schema()
    except Exception:  # noqa: BLE001
        return None
    return cast("dict[str, object]", schema) if isinstance(schema, dict) else None


def _schema_properties(schema: dict[str, object] | None) -> dict[str, object]:
    props = schema.get("properties") if isinstance(schema, dict) else None
    return cast("dict[str, object]", props) if isinstance(props, dict) else {}


def _schema_required(schema: dict[str, object] | None) -> set[str]:
    raw = schema.get("required") if isinstance(schema, dict) else None
    if not isinstance(raw, list):
        return set()
    return {str(item) for item in raw if isinstance(item, str)}


def _schema_enum_values(meta: object, schema: dict[str, object] | None) -> list[object]:
    if not isinstance(meta, dict):
        return []
    direct = meta.get("enum")
    if isinstance(direct, list):
        return list(direct)
    for item in meta.get("anyOf", []) if isinstance(meta.get("anyOf"), list) else []:
        if isinstance(item, dict):
            values = _schema_enum_values(item, schema)
            if values:
                return values
    ref = meta.get("$ref")
    defs = schema.get("$defs") if isinstance(schema, dict) else None
    if isinstance(ref, str) and ref.startswith("#/$defs/") and isinstance(defs, dict):
        target = defs.get(ref.removeprefix("#/$defs/"))
        if isinstance(target, dict):
            target_values = target.get("enum")
            if isinstance(target_values, list):
                return list(target_values)
    return []


def _text_match_key(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def _default_for_adapter_field(  # noqa: C901
    field_name: str,
    meta: object,
    *,
    schema: dict[str, object] | None,
    user_query: str,
) -> object:
    if isinstance(meta, dict) and "default" in meta:
        return meta["default"]
    enum_values = _schema_enum_values(meta, schema)
    user_key = _text_match_key(user_query)
    for value in enum_values:
        if not isinstance(value, str) or not value:
            continue
        value_key = _text_match_key(value)
        if value in user_query or (value_key and value_key in user_key):
            return value
    if enum_values:
        return enum_values[0]
    if field_name in {"applicant_name"}:
        return "verified_citizen_mock"
    if field_name in {"purpose"}:
        return (user_query or "정부 서비스 처리")[:200]
    if field_name in {"query"}:
        return (user_query or "정부 서비스 조회")[:300]
    if field_name in {"address"}:
        return _extract_explicit_location_text(user_query) or "주소 미확인"
    if field_name in {"target_institution_code"}:
        return "KOSMOS_MOCK"
    if field_name in {"applicant_di"}:
        return "mock-applicant-di"
    if field_name in {"applicant_id"}:
        return "mock-applicant"
    if field_name in {"benefit_code"}:
        return "mock-benefit"
    if field_name in {"household_size"}:
        return 1
    if field_name in {"limit"}:
        return 5
    if field_name in {"stn_id"}:
        code = _schema_code_for_query_label(meta, user_query)
        if code is not None:
            return code
    if field_name == "year":
        if isinstance(meta, dict):
            minimum = meta.get("minimum")
            maximum = meta.get("maximum")
            year = datetime.now(UTC).year
            if isinstance(minimum, int | float):
                year = max(year, int(minimum))
            if isinstance(maximum, int | float):
                year = min(year, int(maximum))
            return year
        return datetime.now(UTC).year
    if field_name in {"fine_reference"}:
        return "mock-fine-reference"
    if field_name in {"payment_method"}:
        return "virtual_account"
    return ""


_PREGNANCY_BIRTH_INTENT_RE = re.compile(
    r"(임신|출산|산모|산전|산후|분만|진료비\s*바우처|국민행복카드|출산\s*휴가|첫만남)"
)


def _schema_code_for_label(
    meta: object,
    schema: dict[str, object] | None,
    label: str,
) -> str | None:
    """Extract an official enum code from the field description."""
    if not isinstance(meta, dict):
        return None
    description = meta.get("description")
    if not isinstance(description, str):
        return None
    patterns = (
        rf"(?P<code>\d{{3}})\s*=\s*{re.escape(label)}",
        rf"{re.escape(label)}\s*code\s*:\s*['\"]?(?P<code>\d{{3}})['\"]?",
        rf"{re.escape(label)}\s*코드\s*:\s*['\"]?(?P<code>\d{{3}})['\"]?",
    )
    enum_values = {str(value) for value in _schema_enum_values(meta, schema)}
    for pattern in patterns:
        match = re.search(pattern, description, flags=re.IGNORECASE)
        if match is None:
            continue
        code = match.group("code")
        if not enum_values or code in enum_values:
            return code
    return None


def _schema_code_for_query_label(meta: object, user_query: str) -> str | None:
    if not isinstance(meta, dict):
        return None
    description = meta.get("description")
    if not isinstance(description, str):
        return None
    query_key = _text_match_key(user_query)
    for match in re.finditer(r"(?P<label>[가-힣A-Za-z·]+)\s*=\s*(?P<code>\d{2,5})", description):
        label = match.group("label")
        if _text_match_key(label) in query_key:
            return match.group("code")
    return None


def _fill_optional_schema_filters(
    params: dict[str, object],
    props: dict[str, object],
    schema: dict[str, object] | None,
    *,
    user_query: str,
) -> None:
    """Fill optional adapter filters when schema text publishes exact codes."""
    if "stn_id" in props and "stn_id" not in params:
        code = _schema_code_for_query_label(props["stn_id"], user_query)
        if code is not None:
            params["stn_id"] = code
    if not _PREGNANCY_BIRTH_INTENT_RE.search(user_query):
        return
    if "life_array" in props and "life_array" not in params:
        code = _schema_code_for_label(props["life_array"], schema, "임신·출산")
        if code is not None:
            params["life_array"] = code
    if "intrs_thema_array" in props and "intrs_thema_array" not in params:
        code = _schema_code_for_label(props["intrs_thema_array"], schema, "임신·출산")
        if code is not None:
            params["intrs_thema_array"] = code
    if "search_wrd" in props and "search_wrd" not in params:
        params["search_wrd"] = "출산" if "출산" in user_query else "임신"


_LOCATION_ANCHOR_FIELD_NAMES: Final = {
    "adm_cd",
    "b_code",
    "h_code",
    "siGunGuCd",
    "siGunGu_cd",
    "si_do",
    "gu_gun",
    "sgg_cd",
    "address",
    "address_name",
    "lat",
    "lon",
    "latitude",
    "longitude",
    "nx",
    "ny",
    "x",
    "y",
    "xPos",
    "yPos",
}


def _has_location_anchor(params: dict[str, object]) -> bool:
    for field_name in _LOCATION_ANCHOR_FIELD_NAMES:
        value = params.get(field_name)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return True
    return False


def _fill_optional_location_anchor(
    params: dict[str, object],
    props: dict[str, object],
    *,
    user_query: str,
) -> bool:
    """Fill schema-declared optional address anchors from explicit user context.

    Some Pydantic adapters enforce an either/or location anchor in a
    model_validator, so JSON Schema cannot mark either field as individually
    required.  The Gov24 move-in lookup is one example: ``adm_cd`` and
    ``address`` are both optional in schema, but at least one is required at
    runtime.  Use only schema-declared fields and explicit prompt location text
    so this stays metadata-driven rather than adapter-id routed.
    """
    if _has_location_anchor(params):
        return False
    if "address" not in props:
        return False
    location_text = _extract_explicit_location_text(user_query)
    if not location_text:
        return False
    params["address"] = location_text
    return True


def _latest_kma_forecast_base(now: datetime | None = None) -> tuple[str, str]:
    kst_now = (now or datetime.now(tz=ZoneInfo("Asia/Seoul"))).astimezone(ZoneInfo("Asia/Seoul"))
    publication_anchor = kst_now - timedelta(minutes=10)
    anchor_hhmm = publication_anchor.strftime("%H%M")
    for base_time in reversed(_KMA_FORECAST_BASE_TIMES):
        if base_time <= anchor_hhmm:
            return publication_anchor.strftime("%Y%m%d"), base_time
    previous_day = publication_anchor - timedelta(days=1)
    return previous_day.strftime("%Y%m%d"), _KMA_FORECAST_BASE_TIMES[-1]


def _schema_declares_kma_forecast_base(props: dict[str, object]) -> bool:
    base_time_meta = props.get("base_time")
    if not isinstance(base_time_meta, dict):
        return False
    description = base_time_meta.get("description")
    return (
        isinstance(description, str)
        and "Data is published approximately 10 minutes after each base time" in description
        and all(base_time in description for base_time in _KMA_FORECAST_BASE_TIMES)
    )


def _coerce_kma_forecast_base_params(
    params: dict[str, object],
    props: dict[str, object],
) -> None:
    """Use KMA publication base time, not the citizen's travel target date."""
    if "base_date" not in props or "base_time" not in props:
        return
    if not _schema_declares_kma_forecast_base(props):
        return
    base_date, base_time = _latest_kma_forecast_base()
    params["base_date"] = base_date
    params["base_time"] = base_time


def _coerce_adapter_params_from_schema(
    args_obj: dict[str, object],
    *,
    user_query: str,
    registry: Any,
    keep_backend_fields: bool = True,
) -> dict[str, object]:
    """Prune invented params and fill Mock-safe required fields from schema."""
    schema = _schema_for_adapter_args(args_obj, registry)
    props = _schema_properties(schema)
    if not props:
        return args_obj
    params_obj = args_obj.get("params")
    params: dict[str, object] = dict(params_obj) if isinstance(params_obj, dict) else {}
    allowed = set(props)
    if keep_backend_fields:
        # Backend-owned auth/session fields are still subject to the target
        # adapter's Pydantic schema. Keeping them for read-only adapters whose
        # schema uses extra="forbid" turns a harmless verified context into an
        # invalid extra field and causes lookup retry loops.
        allowed |= {"delegation_context", "session_id", "identity_assertion"} & set(props)
    pruned = {key: value for key, value in params.items() if key in allowed}
    pruned = {
        key: value
        for key, value in pruned.items()
        if not (isinstance(value, str) and not value.strip())
    }
    required = _schema_required(schema)
    for field_name in sorted(required):
        if field_name in pruned:
            continue
        if field_name in {"delegation_context", "session_id", "identity_assertion"}:
            continue
        pruned[field_name] = _default_for_adapter_field(
            field_name,
            props.get(field_name),
            schema=schema,
            user_query=user_query,
        )
    _fill_optional_schema_filters(pruned, props, schema, user_query=user_query)
    _fill_optional_location_anchor(pruned, props, user_query=user_query)
    _coerce_kma_forecast_base_params(pruned, props)
    enriched = dict(args_obj)
    enriched["params"] = pruned
    return enriched


def _search_relevant_candidates(user_query: str, registry: Any, top_k: int = 12) -> list[Any]:
    q = (user_query or "").strip()
    if not q:
        return []
    try:
        from kosmos.tools.search import search  # noqa: PLC0415

        candidates = search(
            query=q,
            bm25_index=registry.bm25_index,
            registry=registry,
            top_k=top_k,
        )
    except Exception:  # noqa: BLE001
        logger.exception("forced follow-up retrieval failed for '%s'", q[:80])
        return []
    return _relevant_positive_candidates(candidates)


def _first_candidate_for_primitive(
    candidates: list[Any],
    primitive: str,
) -> Any | None:
    for candidate in candidates:
        if getattr(candidate, "primitive", None) != primitive:
            continue
        tool_id = getattr(candidate, "tool_id", None) or getattr(candidate, "id", None)
        if not isinstance(tool_id, str) or not tool_id or tool_id in _CORE_PRIMITIVE_TOOL_IDS:
            continue
        return candidate
    return None


def _candidate_by_tool_id(candidates: list[Any], tool_id: str, primitive: str) -> Any | None:
    for candidate in candidates:
        if getattr(candidate, "primitive", None) != primitive:
            continue
        candidate_tool_id = getattr(candidate, "tool_id", None) or getattr(candidate, "id", None)
        if candidate_tool_id == tool_id:
            return candidate
    return None


def _build_forced_resolve_location_args(user_query: str) -> dict[str, object]:
    return {
        "query": _extract_explicit_location_text(user_query) or user_query,
        "want": "coords_and_admcd",
    }


def _normalise_resolve_location_args(args_obj: dict[str, object]) -> dict[str, object]:
    """Use the bundle request when the model asks for adm_cd alone.

    ``want='adm_cd'`` is brittle in mock/live mixed environments because
    address-code backends may be unavailable while the coordinate resolver is
    still able to return a usable bundle.  The LLM-visible schema already
    describes ``coords_and_admcd`` as the safest default for chained tools, so
    normalize the narrower request at the harness boundary before dispatch and
    before the TUI paints the tool-call arguments.
    """
    if args_obj.get("want") != "adm_cd":
        return args_obj
    normalised = dict(args_obj)
    normalised["want"] = "coords_and_admcd"
    return normalised


def _gov24_minwon_types_from_query(user_query: str, registry: Any) -> list[str]:
    schema = _schema_for_adapter_args(
        {"tool_id": "mock_submit_module_gov24_minwon", "params": {}},
        registry,
    )
    props = _schema_properties(schema)
    values = _schema_enum_values(props.get("minwon_type"), schema)
    user_key = _text_match_key(user_query)
    matched: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        value_key = _text_match_key(value)
        if value in user_query or (value_key and value_key in user_key):
            matched.append(value)
            continue
        for suffix in ("신고", "신청", "감면", "연결", "등록", "예약", "증명"):
            if not value_key.endswith(suffix):
                continue
            stem = value_key[: -len(suffix)]
            if len(stem) >= 2 and stem in user_key:
                matched.append(value)
                break
        else:
            if value_key.endswith("등기") and "등기" in user_key:
                matched.append(value)
    if (
        "방문예약" in values
        and "방문예약" not in matched
        and "예약" in user_key
        and any(token in user_key for token in ("외국인등록", "체류기간", "출입국", "전자민원"))
    ):
        matched.append("방문예약")
    return matched


def _query_has_gov24_followup_minwon_intent(
    user_query: str,
    *,
    completed: set[str],
    registry: Any,
) -> bool:
    return (
        _gov24_followup_minwon_type_from_query(
            user_query,
            completed=completed,
            registry=registry,
        )
        is not None
    )


def _gov24_direct_followup_flow_completed(
    user_query: str,
    llm_messages: list[Any],
    registry: Any,
) -> bool:
    if not _conversation_has_successful_tool_id(
        llm_messages,
        "lookup",
        "mock_lookup_module_national_ax_bundle",
    ):
        return False
    completed = _successful_gov24_minwon_types(llm_messages)
    if "전입신고" not in completed:
        return False
    requested_followups = set(_gov24_minwon_types_from_query(user_query, registry)) - {
        "전입신고",
    }
    return bool(requested_followups) and requested_followups.issubset(completed)


def _gov24_direct_submit_candidate_before_lookup(
    user_query: str,
    submit_args: dict[str, object] | None,
    llm_messages: list[Any],
    registry: Any,
) -> bool:
    """Return True for target-state flows that start with a self-contained Gov24 submit.

    EDU-001's canonical chain files the move-in report before looking up
    school-transfer / care options.  Keep the rule schema-derived: the initial
    action must be the Gov24 minwon adapter with a declared ``전입신고`` enum
    value, and the same query must also contain another Gov24 minwon enum that
    remains unsubmitted.  CIV-001 still goes through the move-in dependency
    lookup first because it has no explicit second minwon enum in the request.
    """
    if _conversation_has_successful_primitive(llm_messages, "submit"):
        return False
    if _conversation_has_successful_primitive(llm_messages, "lookup"):
        return False
    if submit_args is None or submit_args.get("tool_id") != "mock_submit_module_gov24_minwon":
        return False
    params = submit_args.get("params")
    if not isinstance(params, dict) or params.get("minwon_type") != "전입신고":
        return False
    if not _extract_explicit_location_text(user_query):
        return False
    return _query_has_gov24_followup_minwon_intent(
        user_query,
        completed={"전입신고"},
        registry=registry,
    )


def _gov24_direct_submit_should_precede_lookup(
    user_query: str,
    submit_args: dict[str, object] | None,
    llm_messages: list[Any],
    registry: Any,
) -> bool:
    return _conversation_has_successful_primitive(
        llm_messages,
        "resolve_location",
    ) and _gov24_direct_submit_candidate_before_lookup(
        user_query,
        submit_args,
        llm_messages,
        registry,
    )


def _gov24_location_first_submit_should_precede_lookup(
    user_query: str,
    submit_args: dict[str, object] | None,
    llm_messages: list[Any],
    registry: Any,
) -> bool:
    if not _conversation_has_successful_primitive(llm_messages, "resolve_location"):
        return False
    if _conversation_has_successful_primitive(llm_messages, "lookup"):
        return False
    if submit_args is None or submit_args.get("tool_id") != "mock_submit_module_gov24_minwon":
        return False
    if not _gov24_query_followup_submit_allowed(
        "mock_submit_module_gov24_minwon",
        submit_args,
        user_query,
        registry,
    ):
        return False
    if _submit_args_already_succeeded(submit_args, llm_messages):
        return False
    return _query_prefers_resolve_location_before_verify(
        user_query,
        _search_relevant_candidates(user_query, registry),
    )


def _gov24_bundle_lookup_should_follow_direct_submit(
    user_query: str,
    llm_messages: list[Any],
    registry: Any,
) -> bool:
    """Prefer the bundled service lookup after an initial Gov24 move-in submit."""
    if not _conversation_has_successful_tool_id(
        llm_messages,
        "submit",
        "mock_submit_module_gov24_minwon",
    ):
        return False
    if _conversation_has_successful_tool_id(
        llm_messages,
        "lookup",
        "mock_lookup_module_national_ax_bundle",
    ):
        return False
    completed = _successful_gov24_minwon_types(llm_messages)
    return "전입신고" in completed and _query_has_gov24_followup_minwon_intent(
        user_query,
        completed=completed,
        registry=registry,
    )


def _build_forced_lookup_args(
    user_query: str,
    llm_messages: list[Any],
    registry: Any,
) -> dict[str, object] | None:
    candidates = _search_relevant_candidates(user_query, registry)
    candidate = None
    if _gov24_movein_sequence_completed(llm_messages) and not _conversation_has_successful_tool_id(
        llm_messages,
        "lookup",
        "mock_lookup_module_national_ax_bundle",
    ):
        candidate = _candidate_by_tool_id(
            candidates,
            "mock_lookup_module_national_ax_bundle",
            "lookup",
        )
    if candidate is None and _gov24_bundle_lookup_should_follow_direct_submit(
        user_query,
        llm_messages,
        registry,
    ):
        candidate = _candidate_by_tool_id(
            candidates,
            "mock_lookup_module_national_ax_bundle",
            "lookup",
        )
    if candidate is None:
        candidate = _first_candidate_for_primitive(
            candidates,
            "lookup",
        )
    if candidate is None:
        return None
    tool_id = getattr(candidate, "tool_id", None) or getattr(candidate, "id", None)
    args: dict[str, object] = {
        "tool_id": str(tool_id),
        "params": {},
    }
    args = _enrich_lookup_args_from_resolve_result(args, llm_messages, registry)
    return _coerce_adapter_params_from_schema(
        args,
        user_query=user_query,
        registry=registry,
    )


def _gov24_followup_minwon_type_from_query(
    user_query: str,
    *,
    completed: set[str],
    registry: Any,
) -> str | None:
    for value in _gov24_minwon_types_from_query(user_query, registry):
        if value not in completed:
            return value
    return None


def _successful_submit_action_types_for_tool(
    llm_messages: list[Any],
    tool_id: str,
) -> set[str]:
    args_by_id = _tool_call_args_by_id(llm_messages)
    completed: set[str] = set()
    for message in llm_messages:
        payload = _tool_message_payload(message, "submit")
        if payload is None or not _tool_payload_succeeded(payload, "submit"):
            continue
        call_id = getattr(message, "tool_call_id", None) or (
            message.get("tool_call_id") if isinstance(message, dict) else None
        )
        args = args_by_id.get(call_id, {}) if isinstance(call_id, str) else {}
        if args.get("tool_id") != tool_id:
            continue
        params = args.get("params")
        action_type = params.get("action_type") if isinstance(params, dict) else None
        if not isinstance(action_type, str) or not action_type:
            result = _tool_payload_result(payload)
            receipt = result.get("adapter_receipt") if result is not None else None
            action_type = receipt.get("action_type") if isinstance(receipt, dict) else None
        if isinstance(action_type, str) and action_type:
            completed.add(action_type)
    return completed


def _submit_args_already_succeeded(
    args_obj: dict[str, object],
    llm_messages: list[Any],
) -> bool:
    tool_id = args_obj.get("tool_id")
    if not isinstance(tool_id, str) or not tool_id:
        return False
    if tool_id == "mock_submit_module_gov24_minwon":
        params = args_obj.get("params")
        minwon_type = params.get("minwon_type") if isinstance(params, dict) else None
        return isinstance(minwon_type, str) and minwon_type in _successful_gov24_minwon_types(
            llm_messages
        )
    if tool_id == "mock_submit_module_hometax_taxreturn":
        params = args_obj.get("params")
        action_type = params.get("action_type") if isinstance(params, dict) else None
        if not isinstance(action_type, str) or not action_type:
            action_type = "file_return"
        return action_type in _successful_submit_action_types_for_tool(
            llm_messages,
            tool_id,
        )
    return _conversation_has_successful_tool_id(llm_messages, "submit", tool_id)


def _gov24_query_followup_submit_allowed(
    tool_id: str,
    coerced: dict[str, object],
    user_query: str,
    registry: Any,
) -> bool:
    if tool_id != "mock_submit_module_gov24_minwon":
        return False
    params = coerced.get("params")
    minwon_type = params.get("minwon_type") if isinstance(params, dict) else None
    return isinstance(minwon_type, str) and minwon_type in _gov24_minwon_types_from_query(
        user_query,
        registry,
    )


def _submit_candidate_allowed_after_completed_gov24(
    candidate: Any,
    *,
    tool_id: str,
    requested_gov24: set[str],
    completed_gov24: set[str],
    top_score: float,
) -> bool:
    if not requested_gov24 or not requested_gov24.issubset(completed_gov24):
        return True
    if tool_id == "mock_submit_module_gov24_minwon":
        return True
    return float(getattr(candidate, "score", 0) or 0) >= max(1.0, top_score * 0.65)


def _with_next_gov24_followup_minwon_type(
    coerced: dict[str, object],
    *,
    tool_id: str,
    user_query: str,
    completed_gov24: set[str],
    registry: Any,
) -> dict[str, object]:
    if tool_id != "mock_submit_module_gov24_minwon":
        return coerced
    params = coerced.get("params")
    if not isinstance(params, dict):
        return coerced
    followup_minwon_type = _gov24_followup_minwon_type_from_query(
        user_query,
        completed=completed_gov24,
        registry=registry,
    )
    if followup_minwon_type is None:
        return coerced
    updated = dict(coerced)
    updated_params = dict(params)
    updated_params["minwon_type"] = followup_minwon_type
    updated["params"] = updated_params
    return updated


def _hometax_followup_action_type_from_query(user_query: str) -> str:
    if re.search(r"(환급|환급\s*계좌|계좌\s*(등록|변경|신고))", user_query):
        return "register_refund_account"
    return "create_payment_deadline_reminder"


def _build_hometax_followup_submit_args(
    user_query: str,
    llm_messages: list[Any],
    registry: Any,
) -> dict[str, object] | None:
    if not _submit_payment_followup_needed(llm_messages):
        return None
    args: dict[str, object] = {
        "tool_id": "mock_submit_module_hometax_taxreturn",
        "params": {
            "action_type": _hometax_followup_action_type_from_query(user_query),
        },
    }
    coerced = _coerce_adapter_params_from_schema(
        args,
        user_query=user_query,
        registry=registry,
    )
    if not _submit_args_compatible_with_latest_auth(coerced, llm_messages, registry):
        return None
    if _submit_args_already_succeeded(coerced, llm_messages):
        return None
    return coerced


def _build_forced_submit_args(
    user_query: str,
    llm_messages: list[Any],
    registry: Any,
) -> dict[str, object] | None:
    gov24_args = _next_gov24_movein_submit_args(llm_messages)
    if gov24_args is not None:
        return _coerce_adapter_params_from_schema(
            gov24_args,
            user_query=user_query,
            registry=registry,
        )
    hometax_followup_args = _build_hometax_followup_submit_args(
        user_query,
        llm_messages,
        registry,
    )
    if hometax_followup_args is not None:
        return hometax_followup_args
    candidates = _search_relevant_candidates(user_query, registry)
    completed_gov24 = _successful_gov24_minwon_types(llm_messages)
    requested_gov24 = set(_gov24_minwon_types_from_query(user_query, registry))
    top_score = float(getattr(candidates[0], "score", 0) or 0) if candidates else 0.0
    for candidate in candidates:
        if getattr(candidate, "primitive", None) != "submit":
            continue
        tool_id = getattr(candidate, "tool_id", None) or getattr(candidate, "id", None)
        if not isinstance(tool_id, str) or not tool_id or tool_id in _CORE_PRIMITIVE_TOOL_IDS:
            continue
        if not _submit_candidate_allowed_after_completed_gov24(
            candidate,
            tool_id=tool_id,
            requested_gov24=requested_gov24,
            completed_gov24=completed_gov24,
            top_score=top_score,
        ):
            continue
        args: dict[str, object] = {
            "tool_id": tool_id,
            "params": {},
        }
        coerced = _coerce_adapter_params_from_schema(
            args,
            user_query=user_query,
            registry=registry,
        )
        coerced = _with_next_gov24_followup_minwon_type(
            coerced,
            tool_id=tool_id,
            user_query=user_query,
            completed_gov24=completed_gov24,
            registry=registry,
        )
        if not _candidate_submit_compatible_with_latest_auth(
            candidate,
            llm_messages,
            registry,
        ):
            continue
        if _submit_args_already_succeeded(coerced, llm_messages):
            continue
        return coerced
    return None


def _build_forced_subscribe_args(user_query: str, registry: Any) -> dict[str, object] | None:
    candidate = _first_candidate_for_primitive(
        _search_relevant_candidates(user_query, registry),
        "subscribe",
    )
    if candidate is None:
        try:
            tools = list(registry._tools.values())  # noqa: SLF001
        except Exception:  # noqa: BLE001
            tools = []
        candidate = _first_candidate_for_primitive(tools, "subscribe")
    if candidate is None:
        return None
    tool_id = getattr(candidate, "tool_id", None) or getattr(candidate, "id", None)
    return {
        "tool_id": str(tool_id),
        "params": {},
        "lifetime_seconds": 300,
    }


def _latest_auth_context(llm_messages: list[Any]) -> object | None:
    """Return the latest verify AuthContext as a typed model or tier stand-in."""
    result = _latest_verify_result(llm_messages)
    if result is None:
        return None
    try:
        from kosmos.primitives.verify import AuthContext  # noqa: PLC0415

        return TypeAdapter(AuthContext).validate_python(result)
    except Exception:  # noqa: BLE001
        delegation_context = result.get("delegation_context")
        if isinstance(delegation_context, dict):
            return SimpleNamespace(
                delegation_context=delegation_context,
                published_tier=result.get("published_tier"),
                nist_aal_hint=result.get("nist_aal_hint"),
                family=result.get("family"),
            )
        published_tier = result.get("published_tier")
        if isinstance(published_tier, str) and published_tier:
            return SimpleNamespace(
                published_tier=published_tier,
                nist_aal_hint=result.get("nist_aal_hint"),
                family=result.get("family"),
            )
    return None


def _aal_rank_for_tier(tier: object) -> int | None:
    if not isinstance(tier, str):
        return None
    match = re.search(r"_aal([123])$", tier)
    if match is None:
        return None
    return int(match.group(1))


def _published_tier_satisfies(caller_tier: object, required_tier: object) -> bool:
    """Mirror submit.check_tier_gate's tier relation for planning only."""
    if not isinstance(required_tier, str) or not required_tier:
        return True
    if not isinstance(caller_tier, str) or not caller_tier:
        return False
    caller_rank = _aal_rank_for_tier(caller_tier)
    required_rank = _aal_rank_for_tier(required_tier)
    if caller_rank is None or required_rank is None:
        return caller_tier == required_tier
    if caller_rank > required_rank:
        return True
    if caller_rank < required_rank:
        return False
    return caller_tier == required_tier


def _candidate_submit_compatible_with_latest_auth(
    candidate: Any,
    llm_messages: list[Any],
    registry: Any,
) -> bool:
    tool_id = getattr(candidate, "tool_id", None) or getattr(candidate, "id", None)
    if not isinstance(tool_id, str) or not tool_id:
        return False
    granted_scopes = _latest_delegation_scope_values(llm_messages)
    if granted_scopes and not _delegation_scope_grants(
        _required_scope_for_registry_tool(registry, tool_id),
        granted_scopes,
    ):
        return False
    auth_context = _latest_auth_context(llm_messages)
    if auth_context is None:
        return True
    caller_tier = getattr(auth_context, "published_tier", None)
    if caller_tier is None:
        return True
    try:
        tool = registry.lookup(tool_id)
    except Exception:  # noqa: BLE001
        return True
    required_tier = getattr(tool, "published_tier_minimum", None)
    return _published_tier_satisfies(caller_tier, required_tier)


def _submit_args_compatible_with_latest_auth(
    args_obj: dict[str, object],
    llm_messages: list[Any],
    registry: Any,
) -> bool:
    tool_id = args_obj.get("tool_id")
    if not isinstance(tool_id, str) or not tool_id or tool_id in _CORE_PRIMITIVE_TOOL_IDS:
        return True
    granted_scopes = _latest_delegation_scope_values(llm_messages)
    if granted_scopes and not _delegation_scope_grants(
        _required_scope_for_registry_tool(registry, tool_id),
        granted_scopes,
    ):
        return False
    auth_context = _latest_auth_context(llm_messages)
    if auth_context is None:
        return True
    caller_tier = getattr(auth_context, "published_tier", None)
    if caller_tier is None:
        return True
    try:
        tool = registry.lookup(tool_id)
    except Exception:  # noqa: BLE001
        return True
    return _published_tier_satisfies(
        caller_tier,
        getattr(tool, "published_tier_minimum", None),
    )


def _required_scope_for_registry_tool(registry: Any, tool_id: str) -> str | None:
    """Read a tool module's declared _REQUIRED_SCOPE through registry metadata."""
    try:
        tool = registry.lookup(tool_id)
    except Exception:  # noqa: BLE001
        return None
    input_schema = getattr(tool, "input_schema", None)
    module_path = getattr(input_schema, "__module__", None)
    if not isinstance(module_path, str) or not module_path:
        return None
    try:
        import importlib  # noqa: PLC0415

        module = importlib.import_module(module_path)
    except Exception:  # noqa: BLE001
        return None
    scope = getattr(module, "_REQUIRED_SCOPE", None)
    return scope if isinstance(scope, str) and scope else None


def _delegation_scope_bundle_for_registry_tool(registry: Any, tool_id: str) -> list[str]:
    """Read a tool module's declared same-consent scope bundle, if present."""
    try:
        tool = registry.lookup(tool_id)
    except Exception:  # noqa: BLE001
        return []
    input_schema = getattr(tool, "input_schema", None)
    module_path = getattr(input_schema, "__module__", None)
    if not isinstance(module_path, str) or not module_path:
        return []
    try:
        import importlib  # noqa: PLC0415

        module = importlib.import_module(module_path)
    except Exception:  # noqa: BLE001
        return []
    raw_bundle = getattr(module, "_DELEGATION_SCOPE_BUNDLE", None)
    if not isinstance(raw_bundle, list | tuple | set):
        return []
    return [scope for scope in raw_bundle if _is_valid_delegation_scope(scope)]


def _is_valid_delegation_scope(scope: object) -> bool:
    return isinstance(scope, str) and bool(_DELEGATION_SCOPE_RE.match(scope.strip()))


def _delegation_scope_namespace(scope: str) -> str | None:
    if not _is_valid_delegation_scope(scope):
        return None
    _, resource = scope.split(":", 1)
    namespace = resource.split(".", 1)[0]
    return namespace or None


def _delegation_scope_values_from_context(
    delegation_context: dict[str, object] | None,
) -> set[str]:
    if not isinstance(delegation_context, dict):
        return set()
    token = delegation_context.get("token")
    if not isinstance(token, dict):
        return set()
    values: set[str] = set()
    raw_scope = token.get("scope")
    if isinstance(raw_scope, str):
        values.update(scope.strip() for scope in raw_scope.split(",") if scope.strip())
    raw_scope_list = token.get("scope_list")
    if isinstance(raw_scope_list, list):
        values.update(scope for scope in raw_scope_list if isinstance(scope, str) and scope)
    return {scope for scope in values if _is_valid_delegation_scope(scope)}


def _latest_delegation_scope_values(llm_messages: list[Any]) -> set[str]:
    return _delegation_scope_values_from_context(_latest_delegation_context(llm_messages))


def _delegation_scope_grants(required_scope: str | None, granted_scopes: set[str]) -> bool:
    if not _is_valid_delegation_scope(required_scope):
        return True
    return required_scope in granted_scopes


def _identity_scope_for_verify_tool_id(tool_id: object) -> str:
    if isinstance(tool_id, str) and tool_id:
        try:
            from kosmos.tools.verify_canonical_map import resolve_family  # noqa: PLC0415

            family = resolve_family(tool_id)
        except Exception:  # noqa: BLE001
            family = None
        if isinstance(family, str) and family:
            return f"verify:{family}.identity"
    return "verify:ganpyeon.identity"


def _relevant_positive_candidates(candidates: list[Any]) -> list[Any]:
    """Return a score-bounded shortlist instead of every weak BM25 hit.

    The delegation planner previously granted scopes from all positive
    candidates. On broad citizen requests this pulled in unrelated low-score
    submit adapters, over-broadening the consent grant and causing the LLM to
    chase irrelevant tools. Keep only the score band that is plausibly tied to
    the top retrieval result, while still allowing multi-adapter bundles.
    """
    positive = [candidate for candidate in candidates if getattr(candidate, "score", 0) > 0]
    if not positive:
        return []
    top_score = float(getattr(positive[0], "score", 0) or 0)
    if top_score <= 0:
        return []
    # Target-state citizen requests often contain several legitimate agency
    # actions in one utterance (e.g. move-in + school/care + reminders).  A
    # 0.35 band kept only the dominant first agency and hid the second action
    # candidate from the recovery gates.  Keep a narrower absolute floor while
    # still dropping weak near-zero BM25 noise.
    floor = max(1.0, top_score * 0.15)
    score_band = {
        id(candidate)
        for candidate in positive
        if float(getattr(candidate, "score", 0) or 0) >= floor
    }
    best_by_primitive: dict[str, int] = {}
    for candidate in positive:
        primitive = getattr(candidate, "primitive", None)
        if not isinstance(primitive, str) or primitive in best_by_primitive:
            continue
        score = float(getattr(candidate, "score", 0) or 0)
        if score >= 1.0:
            best_by_primitive[primitive] = id(candidate)
    retained = score_band | set(best_by_primitive.values())
    return [candidate for candidate in positive if id(candidate) in retained]


def _candidate_is_policy_gated(candidate: Any) -> bool:
    tool_id = getattr(candidate, "tool_id", None) or getattr(candidate, "id", None)
    if not isinstance(tool_id, str) or not tool_id or tool_id in _CORE_PRIMITIVE_TOOL_IDS:
        return False
    gate = getattr(candidate, "citizen_facing_gate", None)
    return isinstance(gate, str) and gate != "read-only"


def _candidate_is_location_readonly_lookup(candidate: Any) -> bool:
    gate = getattr(candidate, "citizen_facing_gate", None)
    return (
        getattr(candidate, "primitive", None) == "lookup"
        and gate == "read-only"
        and _candidate_requires_resolved_location(candidate)
    )


def _retrieval_policy_requires_initial_verify(candidates: list[Any]) -> bool:
    """Return True when a registry shortlist contains a real gated step.

    The earlier gate inspected only the top candidate. Target-state bundle
    lookups intentionally rank high because they explain the workflow, but many
    citizen requests also retrieve submit/login adapters that must not be
    called without a DelegationContext. Conversely, emergency/location lookups
    often retrieve weak, unrelated submit hits; when a coordinate-input
    read-only lookup dominates the ranking, keep the first turn location-first.
    """
    positive_candidates = _relevant_positive_candidates(candidates)
    if not positive_candidates:
        return False
    strong_gate_floor = max(1.0, float(getattr(positive_candidates[0], "score", 0) or 0) * 0.25)
    gated_candidates = [
        candidate
        for candidate in positive_candidates
        if _candidate_is_policy_gated(candidate)
        and float(getattr(candidate, "score", 0) or 0) >= strong_gate_floor
    ]
    if not gated_candidates:
        return False
    top_candidate = positive_candidates[0]
    top_score = float(getattr(top_candidate, "score", 0) or 0)
    best_gated_score = max(
        float(getattr(candidate, "score", 0) or 0) for candidate in gated_candidates
    )
    top_tool_id = getattr(top_candidate, "tool_id", None) or getattr(top_candidate, "id", None)
    if top_tool_id == "resolve_location" and top_score > 0 and top_score >= best_gated_score:
        return False
    return not (
        top_score > 0
        and _candidate_is_location_readonly_lookup(top_candidate)
        and best_gated_score < top_score * 0.50
    )


def _retrieval_has_strong_policy_gated_candidate(candidates: list[Any]) -> bool:
    positive_candidates = _relevant_positive_candidates(candidates)
    if not positive_candidates:
        return False
    floor = max(1.0, float(getattr(positive_candidates[0], "score", 0) or 0) * 0.25)
    return any(
        _candidate_is_policy_gated(candidate)
        and float(getattr(candidate, "score", 0) or 0) >= floor
        for candidate in positive_candidates
    )


def _query_prefers_resolve_location_before_verify(
    user_query: str,
    candidates: list[Any],
) -> bool:
    """Return True when registry evidence says location must anchor the flow first.

    This keeps the decision metadata-derived instead of scenario-keyword based.
    A privileged Gov24 submit can outrank the location primitive after schema
    hints are improved; for emergency/location flows we still need to resolve
    the citizen's explicit current location before issuing a delegation token.
    Login-gated lookup workflows such as move-in keep verify first.
    """
    if not _extract_explicit_location_text(user_query):
        return False
    positive_candidates = _relevant_positive_candidates(candidates)
    if not positive_candidates or not _retrieval_has_strong_policy_gated_candidate(candidates):
        return False
    top_score = float(getattr(positive_candidates[0], "score", 0) or 0)
    if top_score <= 0:
        return False
    if getattr(positive_candidates[0], "primitive", None) == "subscribe":
        strong_verify_floor = max(1.0, top_score * 0.25)
        if any(
            getattr(candidate, "primitive", None) == "verify"
            and float(getattr(candidate, "score", 0) or 0) >= strong_verify_floor
            for candidate in positive_candidates
        ):
            return False

    resolve_score = max(
        (
            float(getattr(candidate, "score", 0) or 0)
            for candidate in positive_candidates
            if (getattr(candidate, "tool_id", None) or getattr(candidate, "id", None))
            == "resolve_location"
        ),
        default=0.0,
    )
    location_lookup_score = max(
        (
            float(getattr(candidate, "score", 0) or 0)
            for candidate in positive_candidates
            if _candidate_is_location_readonly_lookup(candidate)
        ),
        default=0.0,
    )
    if resolve_score <= 0 or location_lookup_score <= 0:
        return False

    gated_lookup_score = max(
        (
            float(getattr(candidate, "score", 0) or 0)
            for candidate in positive_candidates
            if _candidate_is_policy_gated(candidate)
            and getattr(candidate, "primitive", None) == "lookup"
        ),
        default=0.0,
    )
    if gated_lookup_score >= location_lookup_score:
        return False
    return location_lookup_score >= max(1.0, top_score * 0.25)


def _delegation_plan_from_candidates(  # noqa: C901
    candidates: list[Any],
    registry: Any,
) -> tuple[str | None, list[str]]:
    """Derive compatible verify adapter + scope_list from retrieved adapters."""
    verify_tool_id: str | None = None
    scopes_by_source: dict[str, list[str]] = {}
    scope_scores: dict[str, float] = {}
    source_scores: dict[str, float] = {}
    source_has_scope: dict[str, bool] = {}
    source_counts: dict[str, int] = {}
    source_order: dict[str, int] = {}
    verify_candidates: list[str] = []
    retained_candidates = _relevant_positive_candidates(candidates)
    for index, candidate in enumerate(retained_candidates):
        primitive = getattr(candidate, "primitive", None)
        tool_id = getattr(candidate, "tool_id", None) or getattr(candidate, "id", None)
        if (
            primitive == "verify"
            and isinstance(tool_id, str)
            and tool_id
            and tool_id not in _CORE_PRIMITIVE_TOOL_IDS
        ):
            verify_candidates.append(tool_id)
        source = getattr(candidate, "delegation_source_tool_id", None)
        if isinstance(source, str) and source:
            if primitive == "submit":
                source_scores[source] = source_scores.get(source, 0.0) + float(
                    getattr(candidate, "score", 0) or 0
                )
                source_counts[source] = source_counts.get(source, 0) + 1
                source_order.setdefault(source, index)
            if verify_tool_id is None:
                verify_tool_id = source
        if primitive not in {"lookup", "submit", "subscribe"}:
            continue
        if not isinstance(source, str) or not source:
            continue
        scope = _required_scope_for_registry_tool(
            registry,
            str(getattr(candidate, "tool_id", "")),
        )
        if isinstance(scope, str) and _is_valid_delegation_scope(scope):
            source_has_scope[source] = True
            scope_scores[scope] = max(
                scope_scores.get(scope, 0.0),
                float(getattr(candidate, "score", 0) or 0),
            )
            source_scopes = scopes_by_source.setdefault(source, [])
            if scope not in source_scopes:
                source_scopes.append(scope)
            if primitive == "submit" and isinstance(tool_id, str):
                for bundled_scope in _delegation_scope_bundle_for_registry_tool(
                    registry,
                    tool_id,
                ):
                    scope_scores[bundled_scope] = max(
                        scope_scores.get(bundled_scope, 0.0),
                        float(getattr(candidate, "score", 0) or 0),
                    )
                    if bundled_scope not in source_scopes:
                        source_scopes.append(bundled_scope)
    if source_scores:
        top_source_score = max(source_scores.values())
        close_scoped_sources = [
            source
            for source, score in source_scores.items()
            if source_has_scope.get(source) and score >= max(1.0, top_source_score * 0.80)
        ]
        eligible_sources = close_scoped_sources or list(source_scores)
        verify_tool_id = max(
            eligible_sources,
            key=lambda source: (
                source_scores[source],
                source_counts.get(source, 0),
                -source_order.get(source, 0),
            ),
        )
    elif verify_candidates:
        verify_tool_id = verify_candidates[0]
    namespace_score_floor = max(
        1.0,
        source_scores.get(verify_tool_id or "", 0.0) * 0.50,
    )
    scopes = [
        scope
        for scope in scopes_by_source.get(verify_tool_id or "", [])
        if scope_scores.get(scope, 0.0) >= namespace_score_floor
    ]
    selected_namespaces = {
        namespace
        for scope in scopes
        if (namespace := _delegation_scope_namespace(scope)) is not None
    }
    if selected_namespaces:
        scopes = list(scopes)
        for source_scopes in scopes_by_source.values():
            for scope in source_scopes:
                namespace = _delegation_scope_namespace(scope)
                if (
                    namespace in selected_namespaces
                    and scope not in scopes
                    and scope_scores.get(scope, 0.0) >= namespace_score_floor
                ):
                    scopes.append(scope)
    return verify_tool_id, scopes


def _derive_delegation_plan_for_query(
    user_query: str,
    registry: Any,
    *,
    top_k: int = 12,
) -> tuple[str | None, list[str]]:
    q = (user_query or "").strip()
    if not q:
        return None, []
    try:
        from kosmos.tools.search import search  # noqa: PLC0415

        candidates = search(
            query=q,
            bm25_index=registry.bm25_index,
            registry=registry,
            top_k=top_k,
        )
    except Exception:  # noqa: BLE001
        logger.exception("delegation plan retrieval failed for '%s'", q[:80])
        return None, []
    return _delegation_plan_from_candidates(candidates, registry)


def _forced_tool_choice_name(tool_choice: object) -> str | None:
    """Return the primitive name from an OpenAI explicit tool_choice object."""
    if not isinstance(tool_choice, dict):
        return None
    function = tool_choice.get("function")
    if not isinstance(function, dict):
        return None
    name = function.get("name")
    return name if isinstance(name, str) and name else None


def _build_policy_forced_verify_args(
    user_query: str,
    registry: Any,
) -> dict[str, object] | None:
    """Build a registry-derived verify call for empty forced-tool turns.

    FriendliAI/K-EXAONE occasionally ends a turn with no tool_call even when
    the backend sent explicit ``tool_choice=verify``.  The permission boundary
    cannot be left to a silent empty answer: derive the verify adapter and
    scope list from the same registry shortlist that produced the policy gate,
    then dispatch the real verify primitive through the normal tool pipeline.
    """
    verify_tool_id, required_scopes = _derive_delegation_plan_for_query(
        user_query,
        registry,
    )
    if not verify_tool_id or not required_scopes:
        if not verify_tool_id:
            return None
        required_scopes = [_identity_scope_for_verify_tool_id(verify_tool_id)]
    return {
        "tool_id": verify_tool_id,
        "params": {
            "scope_list": required_scopes,
            "purpose_ko": (user_query or "정부 서비스 위임 처리").strip(),
            "purpose_en": "Citizen-requested delegated government service workflow.",
        },
    }


def _enrich_verify_args_from_policy(
    args_obj: dict[str, object],
    user_query: str,
    registry: Any,
) -> dict[str, object]:
    """Fill missing verify scope/purpose fields from adapter policy metadata."""
    params_obj = args_obj.get("params")
    params: dict[str, object] = dict(params_obj) if isinstance(params_obj, dict) else {}
    scope_list = params.get("scope_list")
    existing_scopes = (
        [scope.strip() for scope in scope_list if _is_valid_delegation_scope(scope)]
        if isinstance(scope_list, list)
        else []
    )
    discarded_scopes = (
        [
            scope
            for scope in scope_list
            if isinstance(scope, str) and scope.strip() and not _is_valid_delegation_scope(scope)
        ]
        if isinstance(scope_list, list)
        else []
    )
    if discarded_scopes:
        logger.warning(
            "verify policy enrichment discarded invalid delegation scopes: %s",
            discarded_scopes,
        )
    purpose_ko = params.get("purpose_ko")
    purpose_en = params.get("purpose_en")
    needs_enrichment = (
        not existing_scopes
        or bool(discarded_scopes)
        or not isinstance(purpose_ko, str)
        or not purpose_ko.strip()
        or not isinstance(purpose_en, str)
        or not purpose_en.strip()
    )
    if not needs_enrichment:
        return args_obj
    verify_tool_id, required_scopes = _derive_delegation_plan_for_query(user_query, registry)
    current_tool_id = args_obj.get("tool_id")
    legacy_family = args_obj.get("family_hint") or args_obj.get("family")
    if (
        verify_tool_id
        and not (isinstance(current_tool_id, str) and current_tool_id.strip())
        and not (isinstance(legacy_family, str) and legacy_family.strip())
        and not _query_explicitly_requests_verify_primitive(user_query)
    ):
        args_obj = dict(args_obj)
        args_obj["tool_id"] = verify_tool_id
    merged_scopes = list(existing_scopes)
    for scope in required_scopes:
        if scope not in merged_scopes:
            merged_scopes.append(scope)
    if not merged_scopes:
        merged_scopes.append(_identity_scope_for_verify_tool_id(args_obj.get("tool_id")))
    if merged_scopes:
        params["scope_list"] = merged_scopes
    if not isinstance(purpose_ko, str) or not purpose_ko.strip():
        params["purpose_ko"] = (user_query or "정부 서비스 위임 처리").strip()
    if not isinstance(purpose_en, str) or not purpose_en.strip():
        params["purpose_en"] = "Citizen-requested delegated government service workflow."
    args_obj = dict(args_obj)
    args_obj["params"] = params
    return args_obj


def _submit_result_from_tool_message(message: Any) -> dict[str, object] | None:
    payload = _tool_message_payload(message, "submit")
    if payload is None or not _tool_payload_succeeded(payload, "submit"):
        return None
    result = _tool_payload_result(payload)
    if isinstance(result, dict) and result.get("status") == "succeeded":
        return result
    return None


def _submit_receipt_payment_state(result: dict[str, object]) -> object:
    receipt = result.get("adapter_receipt")
    if not isinstance(receipt, dict):
        return None
    action_type = receipt.get("action_type")
    if action_type in {
        "create_payment_deadline_reminder",
        "mock_payment_after_confirmation",
        "register_refund_account",
    }:
        return action_type
    preflight = receipt.get("preflight_validation")
    if isinstance(preflight, dict):
        return preflight.get("payment")
    return None


def _submit_payment_followup_needed(llm_messages: list[Any]) -> bool:
    """Return True when a submit receipt explicitly requires a payment follow-up."""
    needed = False
    for message in llm_messages:
        result = _submit_result_from_tool_message(message)
        if result is None:
            continue
        payment_state = _submit_receipt_payment_state(result)
        if payment_state in {
            "create_payment_deadline_reminder",
            "mock_payment_after_confirmation",
        }:
            needed = False
        elif payment_state == "separate_submit_required_before_payment":
            needed = True
    return needed


def _submit_payment_followup_completed(llm_messages: list[Any]) -> bool:
    """Return True once a successful payment reminder/payment submit exists."""
    for message in llm_messages:
        result = _submit_result_from_tool_message(message)
        if result is None:
            continue
        if _submit_receipt_payment_state(result) in {
            "create_payment_deadline_reminder",
            "mock_payment_after_confirmation",
            "register_refund_account",
        }:
            return True
    return False


def _latest_gov24_movein_sequence_item(llm_messages: list[Any]) -> dict[str, object] | None:
    """Return the latest Gov24 move-in sequence lookup item, if present."""
    for message in reversed(llm_messages):
        payload = _tool_message_payload(message, "lookup")
        if payload is None or not _tool_payload_succeeded(payload, "lookup"):
            continue
        result = _tool_payload_result(payload)
        if result is None:
            continue
        item = result.get("item")
        if not isinstance(item, dict):
            continue
        if item.get("workflow_kind") == "gov24_movein_dependent_sequence":
            return cast("dict[str, object]", item)
    return None


def _gov24_movein_required_minwon_types(item: dict[str, object]) -> list[str]:
    sequence = item.get("required_sequence")
    if not isinstance(sequence, list):
        return []
    minwon_types: list[str] = []
    for step in sequence:
        if not isinstance(step, dict):
            continue
        if step.get("primitive") != "submit":
            continue
        if step.get("tool_id") != "mock_submit_module_gov24_minwon":
            continue
        minwon_type = step.get("minwon_type")
        if isinstance(minwon_type, str) and minwon_type and minwon_type not in minwon_types:
            minwon_types.append(minwon_type)
    return minwon_types


def _gov24_movein_suggested_submit_params(
    item: dict[str, object],
    minwon_type: str,
) -> dict[str, object]:
    suggested = item.get("suggested_submit_params")
    if isinstance(suggested, dict):
        for value in suggested.values():
            if not isinstance(value, dict):
                continue
            params = value.get("params")
            if not isinstance(params, dict):
                continue
            if params.get("minwon_type") == minwon_type:
                return dict(cast("dict[str, object]", params))
    return {"minwon_type": minwon_type}


def _successful_gov24_minwon_types(llm_messages: list[Any]) -> set[str]:
    args_by_id = _tool_call_args_by_id(llm_messages)
    completed: set[str] = set()
    for message in llm_messages:
        payload = _tool_message_payload(message, "submit")
        if payload is None or not _tool_payload_succeeded(payload, "submit"):
            continue
        call_id = getattr(message, "tool_call_id", None) or (
            message.get("tool_call_id") if isinstance(message, dict) else None
        )
        args = args_by_id.get(call_id, {}) if isinstance(call_id, str) else {}
        if args.get("tool_id") != "mock_submit_module_gov24_minwon":
            continue
        params = args.get("params")
        minwon_type = params.get("minwon_type") if isinstance(params, dict) else None
        if not isinstance(minwon_type, str) or not minwon_type:
            result = _tool_payload_result(payload)
            receipt = result.get("adapter_receipt") if result is not None else None
            minwon_type = receipt.get("minwon_type") if isinstance(receipt, dict) else None
        if isinstance(minwon_type, str) and minwon_type:
            completed.add(minwon_type)
    return completed


def _conversation_has_successful_tool_id(
    llm_messages: list[Any],
    primitive_name: str,
    tool_id: str,
) -> bool:
    args_by_id = _tool_call_args_by_id(llm_messages)
    for message in llm_messages:
        payload = _tool_message_payload(message, primitive_name)
        if payload is None or not _tool_payload_succeeded(payload, primitive_name):
            continue
        call_id = getattr(message, "tool_call_id", None) or (
            message.get("tool_call_id") if isinstance(message, dict) else None
        )
        args = args_by_id.get(call_id, {}) if isinstance(call_id, str) else {}
        if args.get("tool_id") == tool_id:
            return True
    return False


def _next_gov24_movein_submit_args(
    llm_messages: list[Any],
) -> dict[str, object] | None:
    """Build the next Gov24 submit envelope required by a move-in lookup."""
    item = _latest_gov24_movein_sequence_item(llm_messages)
    if item is None:
        return None
    completed = _successful_gov24_minwon_types(llm_messages)
    for minwon_type in _gov24_movein_required_minwon_types(item):
        if minwon_type in completed:
            continue
        params = _gov24_movein_suggested_submit_params(item, minwon_type)
        params.setdefault("minwon_type", minwon_type)
        params.setdefault("delivery_method", "online")
        # Mock-mode identity comes from the prior verify DelegationContext.
        # Do not ask for resident ID/name in chat; live mode will hydrate this
        # from the official identity assertion.
        params.setdefault("applicant_name", "verified_citizen_mock")
        return {
            "tool_id": "mock_submit_module_gov24_minwon",
            "params": params,
        }
    return None


def _gov24_movein_followup_needed(llm_messages: list[Any]) -> bool:
    return _next_gov24_movein_submit_args(llm_messages) is not None


def _gov24_movein_sequence_completed(llm_messages: list[Any]) -> bool:
    """Return True after all lookup-declared Gov24 move-in submits succeeded."""
    return (
        _latest_gov24_movein_sequence_item(llm_messages) is not None
        and _next_gov24_movein_submit_args(llm_messages) is None
    )


def _verify_pre_permission_arg_error(args_obj: dict[str, object]) -> str | None:
    tool_id = args_obj.get("tool_id")
    if not isinstance(tool_id, str) or not tool_id:
        return None
    legacy_family = args_obj.get("family_hint") or args_obj.get("family")
    if not legacy_family:
        from kosmos.tools.verify_canonical_map import resolve_family  # noqa: PLC0415

        if resolve_family(tool_id) is None:
            return (
                f"unknown verify tool_id: {tool_id!r}. Select one of the "
                "tool_ids listed in <verify_families> or the adapter "
                "delegation_source_tool_id metadata."
            )
    params = args_obj.get("params")
    if not isinstance(params, dict):
        return (
            "invalid verify params: citizen-shape verify(tool_id=...) requires "
            "params.scope_list (non-empty list[str]), params.purpose_ko, "
            "and params.purpose_en."
        )
    scope_list = params.get("scope_list")
    if (
        not isinstance(scope_list, list)
        or not scope_list
        or not all(_is_valid_delegation_scope(scope) for scope in scope_list)
        or not isinstance(params.get("purpose_ko"), str)
        or not str(params.get("purpose_ko")).strip()
        or not isinstance(params.get("purpose_en"), str)
        or not str(params.get("purpose_en")).strip()
    ):
        return (
            "invalid verify params: citizen-shape verify(tool_id=...) requires "
            "params.scope_list (non-empty list[str]), params.purpose_ko, "
            "and params.purpose_en. Use the adapter's delegation_source_tool_id "
            "and required scope metadata from <available_adapters>."
        )
    return None


def _check_privileged_chain_terminated_early(  # noqa: C901
    llm_messages: list[Any],
    user_query: str,
    registry: Any = None,
) -> tuple[str, str] | None:
    """Detect verify→final early exits for registry-selected privileged chains."""
    if not _conversation_has_verify(llm_messages):
        return None
    if _latest_auth_context(llm_messages) is None:
        return None
    q = (user_query or "").strip()
    if not q:
        return None
    if registry is None:
        return None
    try:
        from kosmos.tools.registry import ToolRegistry  # noqa: PLC0415
        from kosmos.tools.search import search  # noqa: PLC0415

        reg = cast("ToolRegistry", registry)
        candidates = search(query=q, bm25_index=reg.bm25_index, registry=reg, top_k=12)
    except Exception:  # noqa: BLE001
        logger.exception("privileged chain policy retrieval failed for '%s'", q[:80])
        return None

    positive_candidates = _relevant_positive_candidates(candidates)
    lookup_ids = [
        candidate.tool_id
        for candidate in positive_candidates
        if candidate.primitive == "lookup" and candidate.tool_id != "resolve_location"
    ]
    submit_ids = []
    for candidate in positive_candidates:
        if candidate.primitive != "submit" or candidate.tool_id in _CORE_PRIMITIVE_TOOL_IDS:
            continue
        if not _candidate_submit_compatible_with_latest_auth(
            candidate,
            llm_messages,
            registry,
        ):
            continue
        submit_ids.append(candidate.tool_id)
    subscribe_ids = [
        candidate.tool_id
        for candidate in positive_candidates
        if candidate.primitive == "subscribe" and candidate.tool_id not in _CORE_PRIMITIVE_TOOL_IDS
    ]
    pending_submit_args = _build_forced_submit_args(q, llm_messages, registry)

    if (
        subscribe_ids
        and positive_candidates
        and getattr(positive_candidates[0], "primitive", None) == "subscribe"
        and _conversation_has_successful_primitive(llm_messages, "resolve_location")
        and not _conversation_has_successful_primitive(llm_messages, "subscribe")
    ):
        return (
            "subscribe",
            (
                "The registry-selected top candidate is a subscribe adapter, "
                "and the location context has already been resolved. Continue "
                "with subscribe before any follow-up lookup so the citizen gets "
                f"the requested alert handle: {subscribe_ids[:3]}."
            ),
        )

    if (
        lookup_ids
        and submit_ids
        and _gov24_direct_submit_candidate_before_lookup(
            q,
            pending_submit_args,
            llm_messages,
            registry,
        )
    ):
        if not _conversation_has_successful_primitive(
            llm_messages,
            "resolve_location",
        ):
            return (
                "resolve_location",
                (
                    "A self-contained Gov24 move-in submit is pending, but "
                    "the citizen supplied a new-address workflow and no "
                    "successful resolve_location result exists yet. Resolve "
                    "the address first, then submit the move-in report before "
                    "bundled school/care service discovery."
                ),
            )
        return (
            "submit",
            (
                "A self-contained Gov24 move-in submit is the next canonical "
                "step for this registry-selected workflow before bundled "
                "school/care service discovery. Continue with submit using "
                "the backend-selected adapter and schema-derived params."
            ),
        )
    if (
        lookup_ids
        and submit_ids
        and _gov24_location_first_submit_should_precede_lookup(
            q,
            pending_submit_args,
            llm_messages,
            registry,
        )
    ):
        return (
            "submit",
            (
                "The citizen's explicit current-location workflow has a "
                "location-resolved Gov24 minwon submit pending before any "
                "registry-selected lookup. Continue with submit using the "
                "backend-selected adapter and schema-derived params, then "
                "advance to the next requested Gov24 minwon or subscribe step."
            ),
        )
    if lookup_ids and not _conversation_has_successful_primitive(llm_messages, "lookup"):
        return (
            "lookup",
            (
                "A DelegationContext is already available from verify, but the "
                "privileged lookup step was skipped. Continue the tool chain now: "
                f"call lookup with one of these registry-selected candidates: {lookup_ids[:3]}. "
                "Pass the verify result's delegation_context in params. Do not ask "
                "the citizen for resident ID digits, raw session_id, certificate "
                "PINs, or other PII in chat; omit optional Mock fixture fields."
            ),
        )
    if submit_ids and not _conversation_has_successful_primitive(llm_messages, "submit"):
        return (
            "submit",
            (
                "A DelegationContext is already available from verify, but the "
                "privileged submit step was skipped. Continue the tool chain now: "
                f"call submit with one of these registry-selected candidates: {submit_ids[:3]}. "
                "Pass the verify result's delegation_context in params; omit "
                "backend-injected session_id and optional Mock fixture fields. "
                "If payment was requested but explicit payment confirmation is "
                "absent, create a payment deadline reminder rather than executing payment."
            ),
        )
    if submit_ids and _submit_payment_followup_needed(llm_messages):
        return (
            "submit",
            (
                "The previous submit receipt explicitly says payment still requires "
                "a separate submit step before any payment can be executed. Continue "
                "with the same registry-selected submit adapter now, but set "
                "params.action_type='create_payment_deadline_reminder'. Do not "
                "execute payment unless the citizen gives an explicit post-filing "
                "confirmation."
            ),
        )
    if (
        subscribe_ids
        and _conversation_has_successful_primitive(llm_messages, "submit")
        and not _conversation_has_successful_primitive(llm_messages, "subscribe")
        and pending_submit_args is None
    ):
        return (
            "subscribe",
            (
                "A registry-selected submit receipt already exists, and this "
                "workflow also selected a subscribe adapter for future due dates, "
                "status changes, or alerts. No schema-compatible submit action "
                "remains for the current verified identity, so continue the tool "
                "chain now: call subscribe with one of these registry-selected "
                f"candidates: {subscribe_ids[:3]}."
            ),
        )
    if submit_ids and _gov24_movein_followup_needed(llm_messages):
        return (
            "submit",
            (
                "The Gov24 move-in lookup returned a required submit sequence, "
                "and at least one required minwon_type remains unsubmitted. "
                "Continue with submit(tool_id='mock_submit_module_gov24_minwon') "
                "now. Use the next required params from the lookup result's "
                "suggested_submit_params; do not ask the citizen for resident "
                "ID digits or raw identity data in chat."
            ),
        )
    requested_gov24_minwon = set(_gov24_minwon_types_from_query(q, registry))
    completed_gov24_minwon = _successful_gov24_minwon_types(llm_messages)
    if (
        pending_submit_args is not None
        and pending_submit_args.get("tool_id") == "mock_submit_module_gov24_minwon"
        and requested_gov24_minwon - completed_gov24_minwon
        and not _submit_args_already_succeeded(pending_submit_args, llm_messages)
    ):
        return (
            "submit",
            (
                "The citizen requested multiple Gov24 certificate/minwon types, "
                "and at least one requested minwon_type remains unsubmitted. "
                "Continue with submit(tool_id='mock_submit_module_gov24_minwon') "
                "using the next unsubmitted enum value derived from the adapter "
                "schema. Do not final-answer before the receipt is emitted."
            ),
        )
    if (
        "mock_lookup_module_national_ax_bundle" in lookup_ids
        and _gov24_movein_sequence_completed(llm_messages)
        and not _conversation_has_successful_tool_id(
            llm_messages,
            "lookup",
            "mock_lookup_module_national_ax_bundle",
        )
    ):
        return (
            "lookup",
            (
                "The Gov24 move-in sequence is complete, but the bundled "
                "target-state service discovery step has not run yet. Continue "
                "with lookup(tool_id='mock_lookup_module_national_ax_bundle') "
                "before any final answer so school/care or other follow-up "
                "service boundaries are grounded."
            ),
        )
    if (
        submit_ids
        and (
            _gov24_movein_sequence_completed(llm_messages)
            or _conversation_has_successful_tool_id(
                llm_messages,
                "lookup",
                "mock_lookup_module_national_ax_bundle",
            )
        )
        and pending_submit_args is not None
        and not _submit_args_already_succeeded(pending_submit_args, llm_messages)
    ):
        return (
            "submit",
            (
                "A registry-selected submit action remains after the previous "
                "tool results. Continue the tool chain now with submit using "
                "the backend-selected adapter and schema-derived params; do not "
                "final-answer before the receipt is emitted."
            ),
        )
    if subscribe_ids and not _conversation_has_successful_primitive(llm_messages, "subscribe"):
        return (
            "subscribe",
            (
                "A DelegationContext is already available from verify, but the "
                "privileged subscribe step was skipped. Continue the tool chain now: "
                "call subscribe with one of these registry-selected candidates: "
                f"{subscribe_ids[:3]}."
            ),
        )
    return None


def _check_public_subscribe_terminated_early(
    llm_messages: list[Any],
    user_query: str,
    registry: Any = None,
) -> tuple[str, str] | None:
    """Detect read-only lookup chains that stop before a registry-selected subscribe.

    Some target-state public-safety and mobility flows are intentionally
    location/read-only first, so they never create a DelegationContext and the
    privileged-chain gate does not run. If retrieval still surfaces a concrete
    subscribe adapter, keep the loop going until the citizen gets a durable
    alert/status handle instead of a one-shot lookup answer.
    """
    if registry is None:
        return None
    if _conversation_has_verify(llm_messages):
        return None
    if _conversation_has_successful_primitive(llm_messages, "subscribe"):
        return None
    if not (
        _conversation_has_successful_primitive(llm_messages, "lookup")
        or _conversation_has_successful_primitive(llm_messages, "resolve_location")
    ):
        return None
    candidates = _search_relevant_candidates(user_query, registry)
    top_score = float(getattr(candidates[0], "score", 0) or 0) if candidates else 0.0
    subscribe_floor = max(1.0, top_score * 0.75)
    subscribe_ids = [
        getattr(candidate, "tool_id", "")
        for candidate in candidates
        if getattr(candidate, "primitive", None) == "subscribe"
        and getattr(candidate, "tool_id", "") not in _CORE_PRIMITIVE_TOOL_IDS
        and float(getattr(candidate, "score", 0) or 0) >= subscribe_floor
    ]
    if not subscribe_ids:
        return None
    return (
        "subscribe",
        (
            "A public read-only lookup chain is about to terminate, but "
            "registry retrieval selected a subscribe adapter for this citizen "
            "request. Continue the tool chain now: call subscribe with one of "
            f"these registry-selected candidates: {subscribe_ids[:3]}."
        ),
    )


def _check_submit_prerequisite(
    fname: str,
    llm_messages: list[Any],
    user_query: str,
    registry: Any = None,
) -> tuple[str, str] | None:
    """Reject submit attempts that skip registry-selected prerequisite tools."""
    if fname != "submit":
        return None
    q = (user_query or "").strip()
    if not q or registry is None:
        return None
    try:
        from kosmos.tools.registry import ToolRegistry  # noqa: PLC0415
        from kosmos.tools.search import search  # noqa: PLC0415

        reg = cast("ToolRegistry", registry)
        candidates = search(query=q, bm25_index=reg.bm25_index, registry=reg, top_k=8)
    except Exception:  # noqa: BLE001
        logger.exception("submit prerequisite retrieval failed for '%s'", q[:80])
        return None

    positive_candidates = _relevant_positive_candidates(candidates)
    needs_location = any(
        candidate.tool_id == "resolve_location" for candidate in positive_candidates
    )
    lookup_ids = [
        candidate.tool_id
        for candidate in positive_candidates
        if candidate.primitive == "lookup" and candidate.tool_id != "resolve_location"
    ]

    if needs_location and not _conversation_has_successful_primitive(
        llm_messages,
        "resolve_location",
    ):
        return (
            "resolve_location",
            (
                "Submit prerequisite missing: registry retrieval selected "
                "resolve_location for this citizen request, but no successful "
                "resolve_location result exists yet. Call resolve_location first "
                "with the citizen's location/address, then continue the lookup "
                "and submit chain. Do not submit from unresolved address text."
            ),
        )
    pending_submit_args = _build_forced_submit_args(q, llm_messages, registry)
    if _gov24_direct_submit_should_precede_lookup(
        q,
        pending_submit_args,
        llm_messages,
        registry,
    ):
        return None
    if _gov24_location_first_submit_should_precede_lookup(
        q,
        pending_submit_args,
        llm_messages,
        registry,
    ):
        return None
    if lookup_ids and not _conversation_has_successful_primitive(llm_messages, "lookup"):
        return (
            "lookup",
            (
                "Submit prerequisite missing: registry retrieval selected a "
                "privileged lookup step before submit. Call lookup with one of "
                f"these registry-selected candidates first: {lookup_ids[:3]}. "
                "Pass the verify result's delegation_context in params, then "
                "continue submit using the returned record/collection."
            ),
        )
    return None


def _check_pending_submit_before_non_submit(
    fname: str,
    llm_messages: list[Any],
    user_query: str,
    registry: Any = None,
) -> tuple[str, str] | None:
    """Reject lookup/subscribe drift when a schema-safe submit remains.

    This is the tool-call side of the final-answer privileged-chain gate. It
    stops the model from opening a subscription or retrying another lookup
    while the registry-selected write sequence still has an unsubmitted,
    auth-compatible adapter call.
    """
    if fname not in {"lookup", "subscribe"}:
        return None
    if registry is None or not _conversation_has_verify(llm_messages):
        return None
    if _latest_auth_context(llm_messages) is None:
        return None
    pending_submit_args = _build_forced_submit_args(
        user_query,
        llm_messages,
        registry,
    )
    if (
        pending_submit_args is not None
        and pending_submit_args.get("tool_id") == "mock_submit_module_gov24_minwon"
        and _conversation_has_successful_primitive(llm_messages, "resolve_location")
        and _gov24_location_first_submit_should_precede_lookup(
            user_query,
            pending_submit_args,
            llm_messages,
            registry,
        )
        and not _submit_args_already_succeeded(pending_submit_args, llm_messages)
    ):
        tool_id = pending_submit_args.get("tool_id")
        return (
            "submit",
            (
                "A location-resolved Gov24 submit action remains before this "
                f"{fname} step. Continue with submit(tool_id={tool_id!r}) using "
                "the backend-selected, schema-derived params; do not run another "
                "lookup before the receipt is emitted."
            ),
        )
    if fname == "lookup" and _gov24_bundle_lookup_should_follow_direct_submit(
        user_query,
        llm_messages,
        registry,
    ):
        return None
    if not (
        _conversation_has_successful_primitive(llm_messages, "lookup")
        or _conversation_has_successful_primitive(llm_messages, "submit")
    ):
        return None
    if pending_submit_args is None:
        return None
    if _submit_args_already_succeeded(pending_submit_args, llm_messages):
        return None
    tool_id = pending_submit_args.get("tool_id")
    return (
        "submit",
        (
            "A registry-selected submit action remains before this "
            f"{fname} step. Continue with submit(tool_id={tool_id!r}) using "
            "the backend-selected, schema-derived params; do not subscribe, "
            "retry lookup, or final-answer before the receipt is emitted."
        ),
    )


def _check_tool_call_after_completed_submit_subscribe(
    fname: str,
    llm_messages: list[Any],
    user_query: str,
    registry: Any = None,
) -> tuple[str, str] | None:
    """Reject post-completion tool drift after durable submit+subscribe receipts."""
    if fname not in {"lookup", "submit", "subscribe"}:
        return None
    if not (
        _conversation_has_successful_primitive(llm_messages, "submit")
        and _conversation_has_successful_primitive(llm_messages, "subscribe")
    ):
        return None
    if registry is not None:
        pending_submit_args = _build_forced_submit_args(
            user_query,
            llm_messages,
            registry,
        )
        if pending_submit_args is not None and not _submit_args_already_succeeded(
            pending_submit_args, llm_messages
        ):
            return None
    return (
        "final",
        (
            "A successful submit receipt and a successful subscribe handle already "
            "exist for this citizen request, and no registry-selected pending "
            "submit remains. Do not call lookup, submit, or subscribe again in "
            "this turn; produce a final answer grounded only in the existing "
            "tool payloads and receipts."
        ),
    )


def _check_tool_call_after_completed_submit(
    fname: str,
    llm_messages: list[Any],
    user_query: str,
    registry: Any = None,
) -> tuple[str, str] | None:
    """Reject lookup drift after submit when no pending write remains."""
    if fname not in {"lookup", "submit", "verify"}:
        return None
    if registry is None:
        return None
    if not _conversation_has_successful_primitive(llm_messages, "submit"):
        return None
    pending_submit_args = _build_forced_submit_args(
        user_query,
        llm_messages,
        registry,
    )
    if pending_submit_args is not None and not _submit_args_already_succeeded(
        pending_submit_args, llm_messages
    ):
        return None
    candidates = _search_relevant_candidates(user_query, registry)
    top_score = float(getattr(candidates[0], "score", 0) or 0) if candidates else 0.0
    subscribe_floor = max(1.0, top_score * 0.20)
    strong_subscribe_ids = [
        getattr(candidate, "tool_id", "")
        for candidate in candidates
        if getattr(candidate, "primitive", None) == "subscribe"
        and getattr(candidate, "tool_id", "") not in _CORE_PRIMITIVE_TOOL_IDS
        and float(getattr(candidate, "score", 0) or 0) >= subscribe_floor
    ]
    if strong_subscribe_ids and not _conversation_has_successful_primitive(
        llm_messages,
        "subscribe",
    ):
        return (
            "subscribe",
            (
                "A registry-selected submit receipt already exists and the "
                "remaining high-confidence follow-up is subscribe, not another "
                "lookup. Continue with subscribe using one of these candidates: "
                f"{strong_subscribe_ids[:3]}."
            ),
        )
    return (
        "final",
        (
            "A successful submit receipt already exists for this citizen request, "
            "no schema-compatible pending submit remains, and registry retrieval "
            "does not select a high-confidence subscribe follow-up. Do not run "
            "another lookup, submit, or verify in this turn; produce a final "
            "answer grounded only in the existing lookup and submit payloads."
        ),
    )


def _check_resolve_location_without_location_context(
    args_obj: dict[str, object],
    user_query: str,
    registry: Any = None,
) -> tuple[str, str] | None:
    if registry is None:
        return None
    query = args_obj.get("query")
    query_text = query if isinstance(query, str) else user_query
    if _extract_explicit_location_text(query_text) or _extract_explicit_location_text(user_query):
        return None
    candidates = _search_relevant_candidates(user_query, registry)
    if candidates and getattr(candidates[0], "tool_id", None) == "resolve_location":
        return None
    return (
        "lookup",
        (
            "resolve_location was requested with a service workflow sentence but "
            "no explicit address/location text. Do not retry location resolution "
            "on the same sentence; continue with registry-selected lookup or "
            "submit workflow discovery instead."
        ),
    )


_FINAL_SPECULATIVE_AVAILABILITY_RE = re.compile(
    r"(운영\s*가능성|야간\s*진료\s*가능|진료\s*가능|현재\s*진료\s*중|"
    r"가능성.{0,20}(병원|응급실|진료)|"
    r"(병원|응급실|진료|운영).{0,20}가능성|24\s*시간\s*운영)"
)
_FINAL_UNSUPPORTED_INSURANCE_RE = re.compile(
    r"건강보험\s*적용|"
    r"(본인\s*부담|실비|진료비).{0,40}"
    r"(약\s*)?\d+(?:\.\d+)?\s*(?:[-~]\s*\d+(?:\.\d+)?)?\s*(?:%|퍼센트)"
)
_FINAL_MEDICAL_ADVICE_RE = re.compile(
    r"((?<![A-Za-z0-9])39\s*(?:°\s*)?C(?![A-Za-z0-9])|"
    r"39\s*도|해열제|수분\s*공급|의식이\s*흐려)"
)
_FINAL_ALREADY_RESOLVED_ADDRESS_RE = re.compile(
    r"(?:새\s*)?주소.{0,24}(?:알려|말씀|제공|입력|기재)"
)
_FINAL_DENIES_REGISTERED_TOOL_RE = re.compile(
    r"((도구|어댑터).{0,30}(등록되어\s*있지\s*않|없(?:습니다|다))|"
    r"등록된\s*(도구|어댑터).{0,24}없)"
)
_FINAL_EXTERNAL_HANDOFF_AFTER_TOOL_RE = re.compile(
    r"((공식\s*)?(사이트|채널|포털|서비스).{0,36}(직접|확인|진행|처리|납부|예약|신청)|"
    r"(직접|별도).{0,36}(진행|처리|납부|예약|신청|확인).{0,12}"
    r"(하세요|하셔야|하시는|하십시오|해\s*주세요|해야|필요)|"
    r"(safedriving|efine|wetax|위택스|이파인|안전운전).{0,36}"
    r"(직접|확인|진행|처리|납부|예약))",
    re.IGNORECASE,
)
_FINAL_DISMISSES_SUBSCRIBE_RE = re.compile(r"(구독|알림).{0,40}(무관|불필요|종료해야|취소해야)")
_FINAL_UNSUPPORTED_PROCEDURAL_AFTER_SUBMIT_RE = re.compile(
    r"("
    r"필요\s*서류|담당\s*기관|지원\s*금액|처리\s*기간|"
    r"비과세|상속세|취득세|검인|콜센터|"
    r"사망일로부터|온라인\s*신청|방문\s*신청|지역번호\s*\+\s*120|"
    r"지원금\s*유형|자격요건|신청방법|회사\s*규모|업종|근로자\s*수|"
    r"고용유지지원금|고용촉진지원금|청년고용|사회보험료|세제혜택|"
    r"표준\s*근로계약서|원천징수|"
    r"\b110\b|\b1355\b"
    r")"
)
_FINAL_UNSUPPORTED_ALERT_ALL_CLEAR_RE = re.compile(
    r"(미세먼지|정전|단수).{0,40}(경보|알림|위험|발령).{0,40}"
    r"(없|없습니다|아니|않|미발령|발령되지)"
)
_FINAL_UNSUPPORTED_TRANSIT_RE = re.compile(
    r"(KTX|코레일|고속버스|시외버스|대중교통|열차|버스).{0,60}"
    r"(추천|안전|정시|지연|운행|소요|비용|저렴|도착)"
)


def _conversation_has_domain_source(llm_messages: list[Any], *needles: str) -> bool:
    haystack_parts: list[str] = []
    for m in llm_messages:
        content = getattr(m, "content", None) or (m.get("content") if isinstance(m, dict) else None)
        if isinstance(content, str):
            haystack_parts.append(content.lower())
        tool_calls = getattr(m, "tool_calls", None) or (
            m.get("tool_calls") if isinstance(m, dict) else None
        )
        if tool_calls:
            haystack_parts.append(str(tool_calls).lower())
    haystack = "\n".join(haystack_parts)
    return any(needle.lower() in haystack for needle in needles)


def _tool_payload_has_domain_source(llm_messages: list[Any], *needles: str) -> bool:
    haystack_parts: list[str] = []
    for m in llm_messages:
        role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else None)
        if role != "tool":
            continue
        content = getattr(m, "content", None) or (m.get("content") if isinstance(m, dict) else None)
        if isinstance(content, str):
            haystack_parts.append(content.lower())
    haystack = "\n".join(haystack_parts)
    return any(needle.lower() in haystack for needle in needles)


def _tool_payload_has_structured_key(llm_messages: list[Any], *keys: str) -> bool:
    key_set = {key for key in keys if key}
    if not key_set:
        return False

    def _contains(value: object) -> bool:
        if isinstance(value, dict):
            if any(isinstance(key, str) and key in key_set for key in value):
                return True
            return any(_contains(v) for v in value.values())
        if isinstance(value, list):
            return any(_contains(item) for item in value)
        return False

    for m in llm_messages:
        role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else None)
        if role != "tool":
            continue
        content = getattr(m, "content", None) or (m.get("content") if isinstance(m, dict) else None)
        if not isinstance(content, str):
            continue
        payload = _result_payload_from_tool_content(content)
        if payload is not None and _contains(payload):
            return True
    return False


def _final_has_unsupported_procedure_after_submit(
    text: str,
    llm_messages: list[Any],
) -> bool:
    if not _FINAL_UNSUPPORTED_PROCEDURAL_AFTER_SUBMIT_RE.search(text):
        return False
    if not _conversation_has_successful_primitive(llm_messages, "submit"):
        return False
    return not _tool_payload_has_structured_key(
        llm_messages,
        "required_documents",
        "documents_required",
        "support_amount",
        "processing_period",
        "official_contact",
        "deadline_days",
        "statutory_deadline",
    )


def _post_tool_final_answer_violations(text: str, llm_messages: list[Any]) -> list[str]:
    violations: list[str] = []
    has_submit_or_subscribe = _conversation_has_successful_primitive(
        llm_messages,
        "submit",
    ) or _conversation_has_successful_primitive(llm_messages, "subscribe")
    if _FINAL_DENIES_REGISTERED_TOOL_RE.search(text) and has_submit_or_subscribe:
        violations.append(
            "claiming no registered tool is available after submit/subscribe tools succeeded"
        )
    if _FINAL_EXTERNAL_HANDOFF_AFTER_TOOL_RE.search(text) and has_submit_or_subscribe:
        violations.append(
            "redirecting the citizen to direct external-site handling after "
            "submit/subscribe receipts already succeeded"
        )
    if _FINAL_DISMISSES_SUBSCRIBE_RE.search(text) and _conversation_has_successful_primitive(
        llm_messages, "subscribe"
    ):
        violations.append(
            "describing a successful registry-selected subscribe handle as "
            "irrelevant, unnecessary, or something to terminate"
        )
    if _final_has_unsupported_procedure_after_submit(text, llm_messages):
        violations.append(
            "procedural document, deadline, amount, contact, legal, or tax claims "
            "not present in the submit/lookup payloads"
        )
    if _FINAL_UNSUPPORTED_ALERT_ALL_CLEAR_RE.search(text) and not _tool_payload_has_domain_source(
        llm_messages,
        "airkorea",
        "kepco",
        "water",
        "상수도",
        "수도",
    ):
        violations.append(
            "all-clear claims for fine-dust, outage, or water-shutdown domains "
            "without a corresponding domain status payload"
        )
    if _FINAL_UNSUPPORTED_TRANSIT_RE.search(text) and not _tool_payload_has_domain_source(
        llm_messages,
        "korail",
        "rail",
        "bus",
        "transit",
        "대중교통",
        "열차",
        "버스",
    ):
        violations.append(
            "rail, bus, transit delay, travel-time, or route recommendation claims "
            "without a corresponding transit payload"
        )
    return violations


def _check_final_answer_grounding(text: str, llm_messages: list[Any]) -> str | None:
    """Reject unsupported final-answer claims before they reach the citizen.

    This is the terminal-turn analogue of CC's tool validation boundary: if the
    model drafts a final answer that upgrades a registry result into real-time
    availability, insurance coverage, or medical triage advice without a tool
    result for that domain, the loop feeds a corrective tool message back to
    the model and asks it to rewrite from the observed payload only.
    """
    if not text.strip():
        return None
    violations: list[str] = []
    if _FINAL_SPECULATIVE_AVAILABILITY_RE.search(text):
        violations.append(
            "availability/status claims such as emergency operation, night treatment, "
            "24-hour operation, or facility availability"
        )
    if _FINAL_UNSUPPORTED_INSURANCE_RE.search(text) and not _conversation_has_domain_source(
        llm_messages,
        "nhis",
        "health_insurance",
        "국민건강보험공단",
    ):
        violations.append("insurance coverage or payment claims")
    if _FINAL_MEDICAL_ADVICE_RE.search(text) and not _conversation_has_domain_source(
        llm_messages,
        "guideline",
        "질병관리청",
        "medical_guideline",
    ):
        violations.append("medical triage thresholds or treatment advice")
    if _FINAL_ALREADY_RESOLVED_ADDRESS_RE.search(text) and _conversation_has_successful_primitive(
        llm_messages, "resolve_location"
    ):
        violations.append("asking again for an address that was already resolved by tools")
    violations.extend(_post_tool_final_answer_violations(text, llm_messages))
    if not violations:
        return None
    return (
        "Final answer grounding violation: the draft contained unsupported "
        + "; ".join(violations)
        + ". Rewrite using only fields explicitly present in the latest tool "
        "payloads. Do not introduce unrelated service domains, handoff steps, "
        "external-site instructions, medical guidance, or policy claims that are "
        "not present in the observed tool results."
    )


def _tool_call_args_by_id(llm_messages: list[Any]) -> dict[str, dict[str, object]]:
    args_by_id: dict[str, dict[str, object]] = {}
    for m in llm_messages:
        role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else None)
        if role != "assistant":
            continue
        tool_calls = getattr(m, "tool_calls", None) or (
            m.get("tool_calls") if isinstance(m, dict) else None
        )
        if not tool_calls:
            continue
        for tc in tool_calls:
            call_id = getattr(tc, "id", None) or (tc.get("id") if isinstance(tc, dict) else None)
            fn = getattr(getattr(tc, "function", None), "arguments", None) or (
                tc.get("function", {}).get("arguments") if isinstance(tc, dict) else None
            )
            if not isinstance(call_id, str) or not isinstance(fn, str):
                continue
            try:
                parsed = _stdlib_json.loads(fn)
            except ValueError:
                continue
            if isinstance(parsed, dict):
                args_by_id[call_id] = parsed
    return args_by_id


def _result_payload_from_tool_content(content: str) -> dict[str, object] | None:
    try:
        decoded = _stdlib_json.loads(content)
    except ValueError:
        return None
    if not isinstance(decoded, dict):
        return None
    result = decoded.get("result")
    if isinstance(result, dict):
        return result
    return decoded


_INTERNAL_RECOVERY_ERROR_REASONS: Final = {
    "chain_followup_missing",
    "privileged_chain_followup_missing",
    "public_subscribe_followup_missing",
    "submit_auth_tier_incompatible",
    "completed_submit_subscribe_chain",
    "completed_submit_chain",
    "pending_submit_before_non_submit",
    "gov24_direct_followup_flow_completed",
    "gov24_movein_sequence_pending",
    "bundle_lookup_already_grounded",
    "submit_chain_already_completed",
    "gov24_movein_sequence_completed",
    "submit_prerequisite_missing",
    "final_answer_grounding_violation",
    "resolve_location_context_missing",
    "lookup_delegation_prerequisite_missing",
    "repeat_call_blocked",
    "repeat_successful_submit_blocked",
}


def _payload_is_internal_recovery_error(payload: dict[str, object]) -> bool:
    if payload.get("kind") != "error":
        return False
    reason = payload.get("reason")
    return isinstance(reason, str) and reason in _INTERNAL_RECOVERY_ERROR_REASONS


def _item_display_fields(item: object) -> tuple[str, str, str, str]:
    if not isinstance(item, dict):
        return (str(item), "", "", "")
    name = str(
        item.get("yadmNm")
        or item.get("dutyName")
        or item.get("name")
        or item.get("title")
        or item.get("facility_name")
        or "기관명 정보 없음"
    )
    addr = str(item.get("addr") or item.get("dutyAddr") or item.get("address") or "")
    tel = str(item.get("telno") or item.get("dutyTel1") or item.get("phone") or "")
    distance_raw = item.get("distance")
    distance = ""
    if distance_raw is not None and distance_raw != "":
        try:
            distance = f"{float(distance_raw):.0f}m"
        except (TypeError, ValueError):
            distance = str(distance_raw)
    return (name, addr, tel, distance)


def _collect_grounded_result_summaries(
    llm_messages: list[Any],
) -> tuple[list[str], list[tuple[str, list[object]]]]:
    args_by_id = _tool_call_args_by_id(llm_messages)
    zero_tools: list[str] = []
    collections: list[tuple[str, list[object]]] = []
    for m in llm_messages:
        role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else None)
        if role != "tool":
            continue
        content = getattr(m, "content", None) or (m.get("content") if isinstance(m, dict) else None)
        call_id = getattr(m, "tool_call_id", None) or (
            m.get("tool_call_id") if isinstance(m, dict) else None
        )
        if not isinstance(content, str) or not isinstance(call_id, str):
            continue
        payload = _result_payload_from_tool_content(content)
        if payload is None:
            continue
        if _payload_is_internal_recovery_error(payload):
            continue
        args = args_by_id.get(call_id, {})
        tool_id = str(args.get("tool_id") or getattr(m, "name", None) or "tool")
        kind = payload.get("kind")
        if kind == "collection":
            raw_items = payload.get("items")
            items = raw_items if isinstance(raw_items, list) else []
            total = payload.get("total_count")
            if not items or total == 0:
                zero_tools.append(tool_id)
            else:
                collections.append((tool_id, items))
        elif kind == "error":
            zero_tools.append(tool_id)
    return zero_tools, collections


def _build_grounded_safety_answer(llm_messages: list[Any]) -> str | None:
    """Build a deterministic, payload-only answer after grounding rejection."""
    zero_tools, collections = _collect_grounded_result_summaries(llm_messages)
    if not zero_tools and not collections:
        return _build_tool_result_completion_answer(llm_messages)
    domain_tool_ids = [*zero_tools, *(tool_id for tool_id, _ in collections)]
    medical_grounding = any(
        re.search(r"(hira|nmc|hospital|emergency|egen|e-gen|응급|병원)", tool_id, re.I)
        for tool_id in domain_tool_ids
    )
    if not medical_grounding:
        return _build_tool_result_completion_answer(llm_messages)

    lines: list[str] = [
        "조회된 도구 결과에 근거해서만 안내드립니다.",
        "",
    ]
    for tool_id in zero_tools:
        lines.append(f"- `{tool_id}` 조회 결과: 해당 조건의 결과가 없습니다.")
    for tool_id, items in collections[:2]:
        lines.append(f"- `{tool_id}` 조회 결과: 일반 기관 정보 {len(items)}건이 반환되었습니다.")
        for index, item in enumerate(items[:5], start=1):
            name, addr, tel, distance = _item_display_fields(item)
            suffix_parts = [part for part in (addr, tel, distance) if part]
            suffix = " / ".join(suffix_parts)
            lines.append(f"  {index}. {name}" + (f" — {suffix}" if suffix else ""))
    lines.extend(
        [
            "",
            "위 일반 기관 목록만으로는 응급실 운영, 야간진료, 병상, 대기시간, "
            "보험 정보가 확인되지 않습니다.",
            "아이 상태가 급하거나 판단이 어렵다면 119에 바로 문의하거나 "
            "E-Gen 응급의료포털 및 각 병원 전화로 현재 접수 여부를 확인하세요.",
        ]
    )
    return "\n".join(lines)


def _tool_message_parts(message: Any) -> tuple[str, str, str | None] | None:
    role = getattr(message, "role", None) or (
        message.get("role") if isinstance(message, dict) else None
    )
    if role != "tool":
        return None
    name = getattr(message, "name", None) or (
        message.get("name") if isinstance(message, dict) else None
    )
    content = getattr(message, "content", None) or (
        message.get("content") if isinstance(message, dict) else None
    )
    call_id = getattr(message, "tool_call_id", None) or (
        message.get("tool_call_id") if isinstance(message, dict) else None
    )
    if not isinstance(name, str) or not isinstance(content, str):
        return None
    return (name, content, call_id if isinstance(call_id, str) else None)


def _submit_completion_line(payload: dict[str, object]) -> str:
    receipt = payload.get("adapter_receipt")
    receipt_obj = receipt if isinstance(receipt, dict) else {}
    receipt_id = (
        receipt_obj.get("receipt_id")
        or receipt_obj.get("receipt_number")
        or payload.get("receipt_id")
        or payload.get("transaction_id")
    )
    status = receipt_obj.get("status") or payload.get("status")
    action = receipt_obj.get("action_type")
    mode = receipt_obj.get("_mode") or payload.get("_mode")
    prefix = "모의 제출" if mode == "mock" else "제출"
    if _status_is_rejected_or_failed(status):
        reason = receipt_obj.get("reason") or receipt_obj.get("error") or "사유 미상"
        return (
            f"- {prefix}: 반려/실패"
            + (f" · 접수번호 {receipt_id}" if receipt_id else "")
            + f" · 사유 {reason}"
        )
    return (
        f"- {prefix}: 접수"
        + (f" · 처리 {action}" if action else "")
        + (f" · 접수번호 {receipt_id}" if receipt_id else "")
        + (f" · 상태 {status}" if status else "")
    )


def _completion_line_for_tool_payload(
    name: str,
    tool_id: str,
    payload: dict[str, object],
) -> str | None:
    if name == "verify":
        return "- 인증: 완료" if payload.get("kind") != "error" else None
    if name == "lookup":
        kind = payload.get("kind")
        if kind == "collection":
            total = payload.get("total_count")
            return f"- 조회 `{tool_id}`: {total if total is not None else '복수'}건"
        if kind == "record":
            return f"- 조회 `{tool_id}`: 1건"
        if kind == "timeseries":
            points = payload.get("points")
            count = len(points) if isinstance(points, list) else "복수"
            return f"- 조회 `{tool_id}`: 시계열 {count}건"
        if kind == "error":
            reason = payload.get("reason") or payload.get("message") or "error"
            return f"- 조회 `{tool_id}`: 오류({reason})"
    if name == "submit":
        return _submit_completion_line(payload)
    if name == "subscribe":
        status = payload.get("status") or payload.get("kind") or "등록됨"
        return f"- 알림 `{tool_id}`: {status}"
    return None


def _build_tool_result_completion_answer(llm_messages: list[Any]) -> str | None:
    """Build a deterministic citizen-facing close when the model returns empty text."""
    args_by_id = _tool_call_args_by_id(llm_messages)
    lines: list[str] = []
    for message in llm_messages:
        parts = _tool_message_parts(message)
        if parts is None:
            continue
        name, content, call_id = parts
        payload = _result_payload_from_tool_content(content)
        if payload is None:
            continue
        if _payload_is_internal_recovery_error(payload):
            continue
        args = args_by_id.get(call_id, {}) if call_id is not None else {}
        tool_id = str(args.get("tool_id") or name)
        line = _completion_line_for_tool_payload(name, tool_id, payload)
        if line is not None:
            lines.append(line)

    if not lines:
        return None
    return "\n".join(
        [
            "도구 결과 기준으로 처리 상태를 정리합니다.",
            *lines,
            "표시된 모의 결과는 실제 행정 효력이 없으며, 운영 전환 시 기관 공식 "
            "엔드포인트와 권한 정책을 따라야 합니다.",
        ]
    )


def _check_resolve_terminated_without_followup(  # noqa: C901
    llm_messages: list[Any],
    user_query: str,
    *,
    registry: object | None = None,
) -> str | None:
    """Return chain-recovery error message when the LLM is about to terminate
    a turn without invoking a follow-up ``lookup`` after ``resolve_location``.

    Triggers when ALL of the following hold:
    1. The conversation contains at least one assistant turn that called
       ``resolve_location`` AND the corresponding ``role='tool'`` result.
    2. The conversation contains NO assistant turn that called
       ``lookup`` with ``mode='fetch'`` (or shape-equivalent bare
       ``{tool_id, params}``) on a coord/admcd-input adapter.
    3. The user query mentions a location-bound observable that demands a
       follow-up lookup (weather / hospital / ER / accident / 119 / welfare).

    Returns ``None`` when the call is allowed; returns a descriptive
    error message that the caller injects as a synthetic tool_result so the
    next agentic-loop turn produces the missing ``lookup`` call.

    CC reference parallel: ``Tool.validateInput`` rejection on missing
    prerequisite. The KOSMOS port runs at the *terminal-turn* boundary
    (``if not tool_call_buf:``) because the failure mode here is the inverse
    of the ``_check_chain_prerequisite`` pattern — instead of "called
    coord-input tool too early", this is "stopped after resolve and never
    called the coord-input tool at all".
    """
    if not _query_implies_followup_lookup(user_query, registry=registry):
        return None

    saw_resolve_result = False
    saw_followup_lookup = False
    for m in llm_messages:
        role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else None)
        # Detect resolve_location tool result message
        if role == "tool":
            name = getattr(m, "name", None) or (m.get("name") if isinstance(m, dict) else None)
            if name == "resolve_location":
                saw_resolve_result = True
            continue
        if role != "assistant":
            continue
        tool_calls = getattr(m, "tool_calls", None) or (
            m.get("tool_calls") if isinstance(m, dict) else None
        )
        if not tool_calls:
            continue
        for tc in tool_calls:
            call_fn = getattr(getattr(tc, "function", None), "name", None) or (
                tc.get("function", {}).get("name") if isinstance(tc, dict) else None
            )
            if call_fn != "lookup":
                continue
            # Inspect arguments to confirm fetch-mode against an adapter.
            raw_args = getattr(getattr(tc, "function", None), "arguments", None) or (
                tc.get("function", {}).get("arguments") if isinstance(tc, dict) else None
            )
            if isinstance(raw_args, str):
                try:
                    import json as _j  # noqa: PLC0415

                    parsed_args: object = _j.loads(raw_args)
                except Exception:  # noqa: BLE001
                    parsed_args = {}
            else:
                parsed_args = raw_args or {}
            if not isinstance(parsed_args, dict):
                continue
            mode = parsed_args.get("mode")
            tool_id = parsed_args.get("tool_id")
            if mode in (None, "fetch") and isinstance(tool_id, str) and tool_id:
                saw_followup_lookup = True
                break
        if saw_followup_lookup:
            break

    if not saw_resolve_result:
        return None
    if saw_followup_lookup:
        return None
    return (
        "Chain incomplete: this conversation invoked resolve_location but did NOT "
        "follow up with lookup(mode='fetch', tool_id=<adapter>, params={...}) on "
        "any coord/admcd-input adapter. The citizen query asks about an "
        "observable (weather / hospital / accident / 119 / welfare) whose "
        "authoritative value lives in an external agency API — answering from "
        "coordinates alone IS fabrication (citizen-safety violation per "
        "system_v1.md CRITICAL directive). RECOVERY: in the next turn, choose "
        "the correct adapter from the <available_adapters> block and call "
        "lookup(mode='fetch', tool_id='<adapter>', params={lat: <resolved>, "
        "lon: <resolved>, ...}) using the coordinates returned by the prior "
        "resolve_location turn. Do NOT produce a final answer this turn."
    )


def _utcnow() -> str:
    """Return current UTC time as RFC 3339 string."""
    from datetime import datetime

    return (
        datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.")
        + f"{datetime.now(tz=UTC).microsecond // 1000:03d}Z"
    )


async def _emit_exit_frame(session_id: str) -> None:
    """Write a ``session_event {event='exit'}`` frame and flush stdout."""
    exit_frame = SessionEventFrame(
        session_id=session_id,
        correlation_id=str(uuid.uuid4()),
        role="backend",
        ts=_utcnow(),
        kind="session_event",
        event="exit",
        payload={},
    )
    await write_frame(exit_frame)
    logger.debug("Emitted session_event exit frame")


# ---------------------------------------------------------------------------
# Session-event dispatcher
# ---------------------------------------------------------------------------


async def _dispatch_session_event(
    event: str,
    payload: dict[str, Any],
    session_id: str,
    sm: SessionManager,
    shutdown: asyncio.Event,
    correlation_id: str,
) -> None:
    """Route a ``session_event`` frame to the appropriate :class:`SessionManager` method.

    This helper is intentionally kept free of any ``try/except`` so that the
    caller (``_handle_frame``) can catch errors uniformly and emit an
    ``ErrorFrame`` back to the TUI (FR-010 resilience rule).

    Parameters
    ----------
    event:
        One of ``save | load | list | resume | new | exit``.
    payload:
        Event-specific payload dict from the inbound frame.
    session_id:
        The ``session_id`` carried on the inbound frame — used for reply frames.
    sm:
        Active :class:`~kosmos.session.manager.SessionManager` instance.
    shutdown:
        Event that signals the stdio loop to exit when set.
    """
    from kosmos.session.store import list_sessions as _list_sessions

    if event == "new":
        meta = await sm.new_session()
        reply = SessionEventFrame(
            session_id=meta.session_id,
            correlation_id=correlation_id,
            role="backend",
            ts=_utcnow(),
            kind="session_event",
            event="new",
            payload={"session_id": meta.session_id},
        )
        await write_frame(reply)
        logger.debug("session_event new — created session %s", meta.session_id)

    elif event == "save":
        # save_turn is called by the tool-loop per-turn; /save is a checkpoint
        # command.  Emit an ack so the TUI can update its status bar.
        active_sid = sm.session_id or session_id
        reply = SessionEventFrame(
            session_id=active_sid,
            correlation_id=correlation_id,
            role="backend",
            ts=_utcnow(),
            kind="session_event",
            event="save",
            payload={"session_id": active_sid},
        )
        await write_frame(reply)
        logger.debug("session_event save — ack for session %s", active_sid)

    elif event == "list":
        metas = await _list_sessions(session_dir=sm._session_dir)  # noqa: SLF001
        sessions_payload = [
            {
                "id": m.session_id,
                "created_at": m.created_at.isoformat(),
                "turn_count": m.message_count // 2,
            }
            for m in metas
        ]
        active_sid = sm.session_id or session_id
        reply = SessionEventFrame(
            session_id=active_sid,
            correlation_id=correlation_id,
            role="backend",
            ts=_utcnow(),
            kind="session_event",
            event="list",
            payload={"sessions": sessions_payload},
        )
        await write_frame(reply)
        logger.debug("session_event list — returned %d sessions", len(sessions_payload))

    elif event == "resume":
        target_id: str = payload["id"]
        messages = await sm.resume_session(target_id)
        reply = SessionEventFrame(
            session_id=target_id,
            correlation_id=correlation_id,
            role="backend",
            ts=_utcnow(),
            kind="session_event",
            event="load",
            payload={
                "session_id": target_id,
                "messages": [msg.model_dump(mode="json") for msg in messages],
            },
        )
        await write_frame(reply)
        logger.debug(
            "session_event resume — loaded session %s (%d messages)",
            target_id,
            len(messages),
        )

    elif event == "load":
        # load is backend → TUI only; reject TUI → backend direction.
        err = ErrorFrame(
            session_id=session_id,
            correlation_id=correlation_id,
            role="backend",
            ts=_utcnow(),
            kind="error",
            code="invalid_direction",
            message="session_event 'load' is a backend-to-TUI frame; TUI must use 'resume'",
            details={"event": event},
        )
        await write_frame(err)
        logger.warning("session_event load received from TUI — rejected (invalid direction)")

    elif event == "exit":
        logger.debug("session_event exit — setting shutdown flag")
        shutdown.set()

    else:
        # Forward-compatible: unknown events are logged and dropped.
        logger.warning("Unknown session_event: %r", event)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run(  # noqa: C901
    session_id: str | None = None,
    on_frame: Callable[[IPCFrame], Any] | None = None,
    session_manager: SessionManager | None = None,
) -> None:
    """Run the asyncio JSONL stdio loop until stdin closes or a signal arrives.

    Parameters
    ----------
    session_id:
        Session ULID shared with the TUI.  If omitted a random placeholder is
        used (suitable for smoke tests).
    on_frame:
        Callable invoked for every inbound ``IPCFrame``.  May be a coroutine
        function.  Defaults to the built-in ``_handle_frame`` handler that
        echoes ``user_input`` frames and routes ``session_event`` frames to the
        session manager.
    session_manager:
        :class:`~kosmos.session.manager.SessionManager` instance used by the
        default ``_handle_frame`` handler to implement session lifecycle
        operations.  When ``None`` a default ``SessionManager()`` is
        constructed (uses ``~/.kosmos/sessions``).
    """
    from kosmos.session.manager import SessionManager as _SessionManager

    sid = session_id or str(uuid.uuid4())

    # ---- spec-multi-turn-contamination diagnostic — optional log file
    # The TUI bridge spawns this process with `stderr: 'pipe'` and never
    # drains the pipe, so `logger.info(...)` lines are invisible to any
    # external observer (tmux pane, asciinema cast). When the operator
    # sets KOSMOS_BACKEND_LOG_FILE=<path>, attach a FileHandler at INFO
    # so the diagnostic [CHAT_REQUEST_DUMP] / [LATEST_USER_UTT] /
    # [REASONING_PREVIEW] lines persist to disk for post-hoc analysis.
    # Off by default — production behaviour is unchanged when the env
    # var is unset.
    _log_path = os.getenv("KOSMOS_BACKEND_LOG_FILE")
    if _log_path:
        try:
            _root = logging.getLogger()
            _already = any(
                isinstance(h, logging.FileHandler)
                and getattr(h, "baseFilename", "") == os.path.abspath(_log_path)
                for h in _root.handlers
            )
            if not _already:
                _fh = logging.FileHandler(_log_path, mode="a", encoding="utf-8")
                _fh.setLevel(logging.INFO)
                _fh.setFormatter(
                    logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
                )
                _root.addHandler(_fh)
                _root.setLevel(min(_root.level or logging.INFO, logging.INFO))
                logger.info(
                    "spec-multi-turn-contamination: attached FileHandler -> %s",
                    _log_path,
                )
        except Exception:  # noqa: BLE001 — telemetry must never raise
            sys.stderr.write(f"[KOSMOS BACKEND] failed to attach log file {_log_path}\n")

    logger.info("IPC stdio loop starting — session_id=%s", sid)

    # Resolve session manager; always non-None inside this coroutine.
    _sm: _SessionManager = session_manager if session_manager is not None else _SessionManager()

    # Install shutdown flag
    _shutdown = asyncio.Event()

    def _handle_signal(signum: int, _frame: FrameType | None = None) -> None:
        sig_name = signal.Signals(signum).name
        logger.info("Received signal %s — initiating graceful shutdown", sig_name)
        _shutdown.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _handle_signal, int(sig))
        except (ValueError, NotImplementedError):
            # Windows or restricted environments — fall back to signal.signal
            signal.signal(sig, _handle_signal)

    # Connect asyncio StreamReader to sys.stdin.buffer.
    #
    # macOS / kqueue fix (Fix Strategy 2 — thread-based bypass):
    #
    # When the backend is spawned as a child process by Bun.spawn
    # (tui/src/ipc/bridge.ts) with stdin: 'pipe', Python's
    # asyncio.SelectorEventLoop on macOS uses kqueue.  kqueue raises
    # OSError: [Errno 22] Invalid argument (EINVAL) when
    # connect_read_pipe attempts to register a pipe fd via kqueue.control().
    # This happens even after setting O_NONBLOCK on the dup'd fd because
    # the fd type (anonymous pipe) is not accepted by kqueue on macOS 15+
    # (Darwin 25).  The same error also manifests when stdin is a tty.
    #
    # Fix: run a blocking sys.stdin.buffer.readline() loop inside a thread
    # (via loop.run_in_executor with None = default ThreadPoolExecutor),
    # push each line directly into a StreamReader via feed_data()/feed_eof().
    # This bypasses connect_read_pipe entirely so kqueue never sees the fd.
    # On Linux (epoll-based asyncio) connect_read_pipe works fine; we still
    # use the thread path there for portability since run_in_executor has
    # negligible overhead compared to inter-process pipe I/O.
    #
    # Unit-test compatibility: the in-process harness (tests/ipc/test_stdio.py,
    # _run_with_frame) wraps an os.pipe() read-end as sys.stdin.buffer.
    # The thread reads from the same buffer object, so the test payload arrives
    # via the same readline() path — no change needed in the tests.
    # KOSMOS Epic #2077 — limit=16 MiB. The default asyncio.StreamReader limit
    # is 64 KiB (asyncio.streams._DEFAULT_LIMIT), which is too small once the
    # TUI's ChatRequestFrame includes the full 11-tool catalog (~13 KB JSON)
    # plus accumulated message history across agentic-loop turns. A single
    # ``\n``-terminated line easily exceeds 64 KiB after 3-5 turns, causing
    # ``readline()`` to raise ``ValueError('Separator is found, but chunk is
    # longer than limit')`` and the IPC reader loop to silently die — the
    # TUI then waits forever for assistant_chunk frames that never come.
    # 16 MiB matches the K-EXAONE 1M-token context budget in bytes (1M tokens
    # × ~1.5 byte/token UTF-8 average × 10× safety margin).
    stdin_reader = asyncio.StreamReader(limit=16 * 1024 * 1024)
    _stdin_buf_capture = sys.stdin.buffer  # capture now; monkeypatching may change sys.stdin

    async def _stdin_feed_task() -> None:
        """Read stdin synchronously in a thread executor; push lines into stdin_reader.

        Thread loop: blocks on readline() until EOF, then feeds EOF to the
        StreamReader so _reader_loop terminates naturally.  Any OSError or
        ValueError (e.g. closed file during shutdown) also terminates the loop.

        On task cancellation (signalled by the outer shutdown coordinator at
        :func:`run`'s ``asyncio.wait`` boundary), the in-flight ``readline()``
        executor Future is cancelled so the awaiting coroutine returns and
        ``stdin_reader.feed_eof()`` runs in ``finally`` (Codex P1, PR #2111).
        The blocked worker thread itself does not exit — Python cannot kill
        threads — but Python's default-executor shutdown path on
        ``asyncio.run()`` exit is bounded by ``shutdown_default_executor``'s
        timeout, so the interpreter still terminates.
        """
        loop_inner = asyncio.get_running_loop()
        try:
            while True:
                line: bytes = await loop_inner.run_in_executor(None, _stdin_buf_capture.readline)
                if not line:
                    break
                stdin_reader.feed_data(line)
        except (OSError, ValueError, asyncio.CancelledError):
            pass
        finally:
            stdin_reader.feed_eof()

    _stdin_feed_handle = asyncio.create_task(_stdin_feed_task(), name="ipc-stdin-feed")

    # Default on_frame: route `user_input` to the FriendliAI LLM (Epic #1633
    # FR-007/FR-017) and `session_event` to the session manager. Wraps every
    # handler in try/except so malformed payloads never crash the loop
    # (FR-010).
    #
    # Per-session conversation history is kept in `_llm_sessions` below; each
    # user_input appends one message, the model's reply is appended as
    # assistant, and subsequent turns see the full history. System prompt is
    # loaded lazily from Spec 026 PromptLoader on first turn.
    _llm_sessions: dict[str, list[dict[str, object]]] = {}
    _llm_client_ref: list[object] = []  # holds the singleton LLMClient
    _llm_system_prompt_cached: list[str | None] = [None]

    # Spec 1978 T026 — pending tool calls registry per data-model.md D1.
    # Keyed by call_id (ULID emitted in ToolCallFrame), valued by an asyncio
    # Future that resolves when the matching ToolResultFrame arrives.
    _pending_calls: dict[str, asyncio.Future[Any]] = {}

    # Spec 1978 T043-T049 — pending permission requests (D2 invariant).
    # Keyed by request_id (UUID4), resolved when the TUI sends a
    # permission_response frame with the matching request_id.
    # Timeout = 60s; synthetic deny on expiry.
    _pending_perms: dict[str, asyncio.Future[Any]] = {}

    # Per-session auto-approved tool IDs (allow_session grants).
    # Keyed by session_id → set of tool_ids approved for the session lifetime.
    _session_grants: dict[str, set[str]] = {}
    # Per-session verified AuthContext, populated by verify dispatch and used by
    # side-effecting primitives for the SC-005 published_tier gate.
    _session_auth_contexts: dict[str, object] = {}

    # Epic #2077 T010 — single ToolRegistry + ToolExecutor instance pair
    # reused across every chat_request. Adapter registration happens lazily
    # on first access by invoking ``register_all_tools(registry, executor)``
    # exactly once (Spec 1634); per-turn reconstruction would force every
    # adapter ``register()`` call to re-execute and would also rebuild BM25
    # for no observable gain. The list-of-one indirection mirrors the
    # ``_llm_client_ref`` pattern above so the closure-bound name binding
    # survives reassignment under typing strictness.
    #
    # Bug fix (2026-05-01, citizen "부산 날씨" report):  the previous
    # implementation created an empty ``ToolRegistry()`` here AND another
    # empty pair inside ``_dispatch_primitive`` for every lookup call, so
    # ``lookup(mode="search", ...)`` always returned ``reason="empty_registry"``
    # and ``mode="fetch"`` always failed with ``unknown_tool``. The comment
    # claimed registration happened "via register_all side-effects" but no
    # such side-effects exist — registration is a function call, not a
    # module-level statement. This pair is now the single source of truth
    # for *all* dispatcher paths (search/fetch/export_core_tools_openai).
    _tool_registry_ref: list[object] = []
    _tool_executor_ref: list[object] = []

    def _ensure_tool_registry() -> object:
        # CC reference: (no direct CC analog — KOSMOS-only IPC adaptation).
        # CC's QueryEngine.ts assumes ToolRegistry populated at SDK construction
        # time (Anthropic SDK ``new Anthropic({...}).messages.stream(...)`` has
        # the registry baked in). KOSMOS's stdio JSONL backend is invoked once
        # per process, ahead of any chat_request, so registration must be lazy
        # to avoid bootstrapping cost when the user runs ``kosmos --list-sessions``
        # or other non-LLM commands. Justified as SWAP/llm-provider per
        # parity-matrix.md § 2026-05-01.
        if not _tool_registry_ref:
            from kosmos.tools.executor import ToolExecutor  # noqa: PLC0415
            from kosmos.tools.register_all import register_all_tools  # noqa: PLC0415
            from kosmos.tools.registry import ToolRegistry  # noqa: PLC0415

            registry = ToolRegistry()
            executor = ToolExecutor(registry=registry)
            register_all_tools(registry, executor)
            # Cache only after full success — a partial registration leaves
            # the registry in a mixed state, so let the exception propagate
            # and a subsequent call retry from scratch.
            _tool_registry_ref.append(registry)
            _tool_executor_ref.append(executor)

            # SWAP/llm-provider(2521): emit AdapterManifestSyncFrame to the
            # TUI so the frontend's LookupPrimitive.validateInput can resolve
            # tool_ids. Without this frame, isManifestSynced() stays false
            # and every lookup(mode="fetch") returns "Adapter manifest not
            # yet synced from backend" — the LLM then retries lookup
            # endlessly while fabricating answers from BM25 search candidates
            # (citizen-traced 2026-05-01: fake hourly-temperature tables).
            # emit_manifest() writes the JSONL frame directly to sys.stdout,
            # bypassing the asyncio write_frame helper because lazy init runs
            # outside the event loop's task graph.
            try:
                import sys as _sys  # noqa: PLC0415

                from kosmos.ipc.adapter_manifest_emitter import (  # noqa: PLC0415
                    emit_manifest,
                )

                emit_manifest(_sys.stdout, registry)
                logger.info("Emitted AdapterManifestSyncFrame to TUI")
            except Exception as _exc:
                logger.exception("Failed to emit adapter manifest: %s", _exc)
        return _tool_registry_ref[0]

    def _ensure_tool_executor() -> object:
        """Return the ToolExecutor paired with the singleton ToolRegistry.

        Triggers lazy registration if neither has been built yet so callers
        that need only the executor stay correct without taking a registry
        reference first.
        """
        if not _tool_executor_ref:
            _ensure_tool_registry()  # populates both refs in one shot
        return _tool_executor_ref[0]

    async def _ensure_llm_client() -> object:
        if not _llm_client_ref:
            from kosmos.llm.client import LLMClient  # noqa: PLC0415
            from kosmos.llm.config import LLMClientConfig  # noqa: PLC0415

            cfg = LLMClientConfig()
            _llm_client_ref.append(LLMClient(config=cfg))
        return _llm_client_ref[0]

    async def _ensure_system_prompt() -> str | None:
        if _llm_system_prompt_cached[0] is not None:
            return _llm_system_prompt_cached[0] or None
        try:
            from pathlib import Path  # noqa: PLC0415

            from kosmos.context.prompt_loader import PromptLoader  # noqa: PLC0415

            # Default manifest lives at repo-root/prompts/manifest.yaml. The
            # stdio backend runs from repo root when invoked via
            # `uv run kosmos --ipc stdio`, so resolve relative to CWD.
            manifest = Path("prompts") / "manifest.yaml"
            if not manifest.is_file():
                _llm_system_prompt_cached[0] = ""
                return None
            loader = PromptLoader(manifest_path=manifest)
            _llm_system_prompt_cached[0] = loader.load("system_v1")
        except Exception:  # noqa: BLE001
            _llm_system_prompt_cached[0] = ""  # remember "tried and failed"
        return _llm_system_prompt_cached[0] or None

    async def _handle_user_input_llm(frame: IPCFrame) -> None:  # noqa: C901
        from kosmos.ipc.frame_schema import (  # noqa: PLC0415
            AssistantChunkFrame,
            UserInputFrame,
        )
        from kosmos.llm.models import ChatMessage  # noqa: PLC0415

        if not isinstance(frame, UserInputFrame):
            return

        history = _llm_sessions.setdefault(frame.session_id, [])
        if not history:
            system_text = await _ensure_system_prompt()
            if system_text:
                history.append({"role": "system", "content": system_text})
        history.append({"role": "user", "content": frame.text})

        client = await _ensure_llm_client()
        messages: list[ChatMessage] = []
        for m in history:
            role = str(m.get("role", "user"))
            content = m.get("content")
            if role in ("system", "user", "assistant", "tool") and isinstance(content, str):
                messages.append(
                    ChatMessage(
                        role=role,  # type: ignore[arg-type]
                        content=content,
                    )
                )

        message_id = str(uuid.uuid4())
        assistant_text_chunks: list[str] = []
        stream_error: Exception | None = None

        try:
            async for event in client.stream(  # type: ignore[attr-defined]
                messages=messages, max_tokens=2048
            ):
                event_type = getattr(event, "type", None)
                if event_type == "content_delta":
                    delta = getattr(event, "content", "") or ""
                    if delta:
                        assistant_text_chunks.append(delta)
                        chunk_frame = AssistantChunkFrame(
                            session_id=frame.session_id,
                            correlation_id=frame.correlation_id,
                            role="llm",
                            ts=_utcnow(),
                            kind="assistant_chunk",
                            message_id=message_id,
                            delta=delta,
                            done=False,
                        )
                        await write_frame(chunk_frame)
                elif event_type == "done":
                    break
                elif event_type == "error":
                    stream_error = RuntimeError(
                        str(getattr(event, "content", "unknown stream error"))
                    )
                    break
        except Exception as exc:  # noqa: BLE001
            stream_error = exc

        full_text = "".join(assistant_text_chunks)
        if stream_error is not None:
            err = ErrorFrame(
                session_id=frame.session_id,
                correlation_id=frame.correlation_id or str(uuid.uuid4()),
                role="backend",
                ts=_utcnow(),
                kind="error",
                code="llm_stream_error",
                message=str(stream_error),
                details={"message_id": message_id},
            )
            await write_frame(err)
            return

        # Terminal chunk — done=True signals end-of-turn to the TS side.
        terminal = AssistantChunkFrame(
            session_id=frame.session_id,
            correlation_id=frame.correlation_id,
            role="llm",
            ts=_utcnow(),
            kind="assistant_chunk",
            message_id=message_id,
            delta="",
            done=True,
        )
        await write_frame(terminal)

        history.append({"role": "assistant", "content": full_text})

    import os as _os_chat_env  # noqa: PLC0415

    # Spec 1978 T030 — tool-result wait timeout (env-overridable).
    # contracts/tool-bridge-protocol.md gates the asyncio.gather on this value.
    _TOOL_RESULT_TIMEOUT_S = float(  # noqa: N806 — env-derived constant, function-scoped to avoid module-import-time env reads
        _os_chat_env.environ.get("KOSMOS_TOOL_RESULT_TIMEOUT_SECONDS", "120")
    )
    # Spec 1978 T029 — bound the CC query-engine agentic loop to prevent
    # infinite tool-recall. KOSMOS adopts the CC 2.1.88 query engine
    # architecture (native function calling + streaming + parallel tool
    # dispatch), NOT the academic ReAct paradigm — see memory
    # `feedback_kosmos_uses_cc_query_engine`. The KOSMOS_REACT_MAX_TURNS env
    # name is preserved for backward compatibility with already-shipped
    # configuration; the documented variable is logically the agentic-loop
    # max-turn cap.
    _AGENTIC_LOOP_MAX_TURNS = int(  # noqa: N806 — env-derived constant
        _os_chat_env.environ.get(
            "KOSMOS_AGENTIC_LOOP_MAX_TURNS",
            _os_chat_env.environ.get("KOSMOS_REACT_MAX_TURNS", "8"),
        )
    )
    # Epic #2152 R4 — separator between the cacheable static prefix (the
    # PromptLoader-resolved citizen system prompt + the augmented
    # ``## Available tools`` block) and the per-turn dynamic suffix. The
    # literal mirrors CC ``prompts.ts:572-575`` so the same identifier reads
    # familiar to anyone with CC source-map context. Downstream tooling
    # (kosmos.prompt.hash slicing in ``kosmos.llm.client``) splits on this
    # marker to compute the static-prefix-only hash.
    _DYNAMIC_BOUNDARY_MARKER = "\nSYSTEM_PROMPT_DYNAMIC_BOUNDARY\n"  # noqa: N806

    # Spec 2521 (2026-05-01) — BM25 candidate count for the dynamic
    # ``<available_adapters>`` block. Must be small enough to keep the
    # dynamic suffix LLM-readable (over-injecting blows the suffix budget
    # and reduces prompt-cache effectiveness for the static prefix). Five
    # mirrors the historical ``lookup(mode='search')`` default top_k that
    # K-EXAONE had been calling explicitly, so token-budget impact is
    # neutral relative to pre-2521 behavior.
    _AVAILABLE_ADAPTERS_TOP_K = int(  # noqa: N806 — env-derived constant
        _os_chat_env.environ.get("KOSMOS_AVAILABLE_ADAPTERS_TOP_K", "5")
    )

    def _build_available_adapters_suffix(user_query: str) -> str:  # noqa: C901
        """Run BM25 against the live registry and emit the citizen-turn
        ``<available_adapters>`` XML block for the dynamic system-prompt
        suffix.

        Returns an empty string on any retrieval failure or when the
        query is blank — fail-open so a flaky retriever does not break
        the citizen path (FR-002 mirror of the lookup primitive's own
        fail-open contract). Logged warnings are picked up by the OTEL
        spans Spec 028 already wires.
        """
        q = (user_query or "").strip()
        if not q:
            return ""
        try:
            from kosmos.tools.registry import ToolRegistry  # noqa: PLC0415
            from kosmos.tools.search import search  # noqa: PLC0415

            registry = cast("ToolRegistry", _ensure_tool_registry())
            candidates = search(
                query=q,
                bm25_index=registry.bm25_index,
                registry=registry,
                top_k=_AVAILABLE_ADAPTERS_TOP_K,
            )
        except Exception:
            logger.exception("BM25 retrieval failed for '%s'", q[:80])
            return ""
        if not candidates:
            return ""
        # Build a compact, LLM-readable block.
        #
        # Spec 2521 (2026-05-02) — emit per-field schema signatures so the
        # LLM can fill ``params`` against each adapter's actual REST shape.
        # The previous suffix only carried ``search_hint`` and assumed the
        # LLM could "infer params from search_hint" — K-EXAONE on FriendliAI
        # consistently invented ``{"location": "...", "date": "..."}`` style
        # payloads which fail every adapter's pydantic validation
        # (``Invalid parameters for tool``). Rendering each field with its
        # type + required flag + truncated description gives K-EXAONE
        # enough signal to call e.g. ``{"lat": 37.5, "lon": 129.0,
        # "base_date": "20260502", "base_time": "0500"}`` correctly.
        lines: list[str] = [
            f'<available_adapters query="{q[:120]}">',
            f"백엔드 BM25 후보 (top {len(candidates)}, 점수 내림차순):",
            "",
        ]
        # Audit G4 / F-beta-02 fix — emit per-candidate ``[primitive=...]``
        # label so the LLM cannot silently route a subscribe/verify/submit-
        # only adapter through ``lookup``. β6 capture (2026-05-05): K-EXAONE
        # called ``lookup(mock_cbs_disaster_v1)`` because that tool_id appeared
        # in the BM25 candidate list (it IS registered, primitive='subscribe')
        # but the suffix did not state which primitive each tool binds to.
        # The ``primitive`` field on AdapterCandidate is populated by
        # ``search.py:142`` already; surfacing it costs zero retrieval work.
        # See ``research/g4-backend.md § 2``.
        for c in candidates:
            hint = (c.search_hint or "").strip()
            if len(hint) > 90:
                hint = hint[:87] + "..."
            prim_label = f" [primitive={c.primitive}]" if c.primitive else ""
            mode_label = f" [mode={c.adapter_mode}]" if c.adapter_mode else ""
            gate_label = (
                f" [citizen_facing_gate={c.citizen_facing_gate}]" if c.citizen_facing_gate else ""
            )
            policy_label = (
                f" [policy_url={c.real_classification_url}]" if c.real_classification_url else ""
            )
            delegation_label = (
                f" [delegation_source={c.delegation_source_tool_id}]"
                if c.delegation_source_tool_id
                else ""
            )
            lines.append(
                f"- {c.tool_id} [{c.score:.2f}]{prim_label}{mode_label}"
                f"{gate_label}{policy_label}{delegation_label} — "
                f"{hint or '(설명 없음)'}"
            )
            # Render the adapter's llm_description (usage prose, ORDERING RULE,
            # prerequisites, worked examples) so the LLM sees the complete
            # "먼저 resolve_location 호출" ordering rule.
            # Bug: without this, the per-field description for nx is truncated
            # and K-EXAONE skips resolve_location, producing invalid_params.
            if c.llm_description:
                desc_text = c.llm_description.strip().replace("\n", " ")
                # Emit at most 300 chars — enough for the ORDERING RULE and
                # worked example without blowing the per-turn token budget.
                if len(desc_text) > 300:
                    desc_text = desc_text[:297] + "..."
                lines.append(f"  설명: {desc_text}")
            # Render input schema signature so the LLM sees exact field
            # names + types + required flags + (truncated) descriptions.
            # Field desc limit raised 80→120 so nx/ny examples fit untruncated.
            schema = c.input_schema_json or {}
            properties = schema.get("properties") if isinstance(schema, dict) else None
            required: set[str] = set()
            raw_required = schema.get("required") if isinstance(schema, dict) else None
            if isinstance(raw_required, list):
                required = {str(item) for item in raw_required if isinstance(item, str)}
            # Spec 2522 T010 — ORDERING directive removed.
            # The Spec 2521 ORDERING block ("nx/ny 는 KMA 격자 좌표 — 반드시
            # resolve_location 을 먼저 호출") forced a cross-domain chain that
            # contradicts both the user directive ("chain X / KOSMOS does not
            # force cross-domain chain") and v4 description 5-section
            # self_contained_decl ("이 도구 단독 호출로 완결. resolve_location 등
            # cross-domain chain 불필요"). With both signals present K-EXAONE
            # ignored both and hallucinated nx/ny → Spec 2521 regression.
            # Each adapter's description (섹션 4 domain_quirk + 섹션 5
            # self_contained_decl + 섹션 3 short_reference 17 광역시도 표) is now
            # self-sufficient. The model decides chain vs single-tool autonomously.
            # Reference: research-stdio-ordering.md, frames-busan-weather/ T042 evidence.
            # Spec 2522 T047 fix — resolve $ref to $defs and inline enum values.
            # KOROAD KoroadAccidentSearchInput.search_year_cd uses
            # `$ref: #/$defs/SearchYearCd` (20 values). The previous renderer
            # only inlined `properties.<f>.enum` and gave up on $ref, leaving
            # K-EXAONE to guess plain '2024' (invalid). Spec 2522 frames-gangnam-
            # accident-fix2 evidence: invalid_params persisted after T042 fix.
            # Fix: resolve $ref against schema['$defs'] + raise threshold 8→25.
            defs_raw = schema.get("$defs") if isinstance(schema, dict) else None
            defs: dict[str, Any] | None = defs_raw if isinstance(defs_raw, dict) else None

            def _resolve_enum(
                meta: dict[str, Any], defs: dict[str, Any] | None
            ) -> list[Any] | None:
                # direct enum
                e = meta.get("enum")
                if isinstance(e, list):
                    return e
                # $ref → $defs/<name>
                ref = meta.get("$ref")
                if isinstance(ref, str) and ref.startswith("#/$defs/") and isinstance(defs, dict):
                    name = ref.removeprefix("#/$defs/")
                    target = defs.get(name)
                    if isinstance(target, dict):
                        target_enum = target.get("enum")
                        if isinstance(target_enum, list):
                            return target_enum
                return None

            def _resolve_enum_with_names(
                meta: dict[str, Any], defs: dict[str, Any] | None
            ) -> list[tuple[Any, str]] | None:
                """Spec 2522 — agency 자체 코드체계 (KOROAD GugunCode SEOUL_GANGNAM=680
                등) 의 IntEnum name 을 의미 매핑으로 노출. pydantic JSON schema 의
                $defs 안 IntEnum 의 'enum' (값) + 'x-enum-varnames' (name) 또는
                'description' (docstring) 을 묶어서 LLM 에 보여줌.
                """
                ref = meta.get("$ref")
                if not (isinstance(ref, str) and ref.startswith("#/$defs/")):
                    return None
                if not isinstance(defs, dict):
                    return None
                name = ref.removeprefix("#/$defs/")
                target = defs.get(name)
                if not isinstance(target, dict):
                    return None
                values = target.get("enum")
                if not isinstance(values, list):
                    return None
                # IntEnum name 추출 — pydantic v2 가 'x-enum-varnames' 또는
                # 'enumNames' 로 export 하지 않음. 대신 module-level dict 조회.
                varnames = target.get("x-enum-varnames")
                if isinstance(varnames, list) and len(varnames) == len(values):
                    return list(zip(values, varnames, strict=False))
                return None

            if isinstance(properties, dict) and properties:
                for fname, fmeta in properties.items():
                    if not isinstance(fmeta, dict):
                        continue
                    ftype = fmeta.get("type") or fmeta.get("anyOf") or "any"
                    if isinstance(ftype, list):
                        ftype = "|".join(str(t) for t in ftype)
                    fdesc = str(fmeta.get("description", "")).strip().replace("\n", " ")
                    # Spec 2522 — agency 자체 코드체계 (KOROAD 68 시군구 매핑 ≈ 1600
                    # chars + 기존 description ≈ 600 chars = ~2200 chars / KMA 156
                    # station 등) 인라인 허용. 일반 도구는 100자 미만이라 영향 X.
                    if len(fdesc) > 5000:
                        fdesc = fdesc[:4997] + "..."
                    pat = fmeta.get("pattern")
                    pat_part = f" pattern={pat!r}" if isinstance(pat, str) else ""
                    enum = _resolve_enum(fmeta, defs)
                    # Spec 2522 T047 — threshold 25→200 — KOROAD GugunCode (115) /
                    # SearchYearCd (20) / SidoCode (17) 등 모두 노출. 의미 매핑은
                    # field description 에 따로 인라인 (Pydantic IntEnum 의 name
                    # 은 JSON schema 표준 export 안 됨).
                    if isinstance(enum, list) and len(enum) <= 200:
                        enum_part = f" enum={enum}"
                    else:
                        enum_part = ""
                    flag = "필수" if fname in required else "선택"
                    lines.append(
                        f"    · {fname} ({ftype}, {flag}{pat_part}{enum_part})"
                        + (f" — {fdesc}" if fdesc else "")
                    )
        lines.append("")
        lines.append(
            '규칙: 위 목록의 tool_id 만 lookup({"tool_id":"...", "params":{...}})'
            " 으로 호출하세요. 동일 tool_id 를 한 turn 안에서 반복 호출하지 마세요."
        )
        lines.append(
            'params 는 위에 표시된 정확한 필드명만 사용하세요 — 일반적인 "location"/'
            '"date" 같은 추측 키는 모든 어댑터에서 invalid_params 로 거부됩니다.'
        )
        lines.append(
            "BM25 도구 발견은 백엔드 internal 기능 — lookup(mode='search') 같은 호출은"
            " 무효화됩니다 (Spec 2521)."
        )
        # Audit G4 / F-beta-02 — primitive routing strict allow-list.
        lines.append(
            "각 후보의 [primitive=...] 라벨을 확인하세요. lookup 후보가 아닌 도구를"
            " lookup 으로 호출하면 unknown_tool 오류가 납니다 — subscribe 도구는"
            " subscribe 호출, verify 도구는 verify 호출, submit 도구는 submit 호출"
            " 만 허용됩니다."
        )
        # Tool-selection deep-research follow-up (2026-05-05): BM25/dense rank
        # is a progressive-disclosure shortlist, not a deterministic router.
        # OpenAI/Anthropic tool-search guidance and the CC ToolSearch reference
        # both rely on the model choosing from a loaded candidate set after
        # reading schema and behavior metadata. KOSMOS therefore tells
        # K-EXAONE to arbitrate by primitive + policy gate + schema fit instead
        # of blindly calling the top-ranked tool_id.
        lines.append(
            "BM25 점수는 후보 shortlist 신호입니다 — top-1 이 시민 의도,"
            " [primitive=...], [mode=...], [citizen_facing_gate=...],"
            " [policy_url=...], delegation_source, input schema required fields"
            " 와 맞지 않으면 다음 후보를 검토하세요."
            " 맞는 후보가 없으면 tool_id 를 지어내거나 lookup(mode='search') 를"
            " 재시도하지 말고, 한 가지 좁은 확인 질문 또는 현재 등록 도구로 처리"
            " 불가 답변을 사용하세요."
        )
        lines.append(
            "각 후보의 [citizen_facing_gate=...] 라벨을 확인하세요. read-only 가 아닌"
            " 후보는 시민 본인확인/위임이 필요한 개인자료 또는 실행 도구입니다."
            " DelegationContext 가 아직 없으면 먼저 primitive=verify 후보를 호출하세요."
            " 후보에 [delegation_source=...] 가 있으면 그 verify tool_id 를 사용하고,"
            " 그 결과의 delegation_context 를 후속 lookup/submit/subscribe params 에"
            " 포함하세요."
        )
        # Audit G4 / F-beta-03 — NO DATA / dedup companion guidance.
        lines.append(
            "동일 tool_id 를 같은 params 로 두 번째 호출하지 마세요. 도구 결과가"
            " NO DATA / empty / kind='error' 면 데이터 없음을 의미하며, 재호출해도"
            " 결과는 동일합니다. 다른 params 또는 다른 도구로 시도하거나, 시민에게"
            " '해당 조건의 데이터를 찾지 못했습니다' 라고 즉시 답변하세요."
        )
        lines.append("</available_adapters>")
        return "\n".join(lines)

    def _retrieval_requires_initial_verify(user_query: str) -> bool:
        """Use the live registry policy graph to decide first-turn verify.

        No domain keywords are encoded here. The decision comes from the same
        BM25/dense retrieval path that builds ``<available_adapters>``: if the
        current citizen request retrieves any candidate whose agency-cited
        ``citizen_facing_gate`` is not ``read-only``, the first primitive must
        be ``verify`` so the later tool call has a DelegationContext.
        """
        q = (user_query or "").strip()
        if not q:
            return False
        if _query_explicitly_requests_verify_primitive(q):
            return False
        try:
            from kosmos.tools.registry import ToolRegistry  # noqa: PLC0415
            from kosmos.tools.search import search  # noqa: PLC0415

            registry = cast("ToolRegistry", _ensure_tool_registry())
            candidates = search(
                query=q,
                bm25_index=registry.bm25_index,
                registry=registry,
                top_k=max(_AVAILABLE_ADAPTERS_TOP_K, 12),
            )
        except Exception:
            logger.exception("initial verify policy retrieval failed for '%s'", q[:80])
            return False
        positive_candidates = _relevant_positive_candidates(candidates)
        if _query_prefers_resolve_location_before_verify(q, candidates):
            return False
        if _retrieval_policy_requires_initial_verify(candidates):
            gated = [
                candidate
                for candidate in positive_candidates
                if _candidate_is_policy_gated(candidate)
            ]
            top_gated = gated[0] if gated else positive_candidates[0]
            logger.info(
                "initial verify policy: candidate %s requires gate=%s",
                top_gated.tool_id,
                top_gated.citizen_facing_gate,
            )
            return True
        return False

    def _retrieval_prefers_initial_resolve_location(user_query: str) -> bool:
        q = (user_query or "").strip()
        if not q:
            return False
        if _query_explicitly_requests_verify_primitive(q):
            return False
        try:
            from kosmos.tools.registry import ToolRegistry  # noqa: PLC0415
            from kosmos.tools.search import search  # noqa: PLC0415

            registry = cast("ToolRegistry", _ensure_tool_registry())
            candidates = search(
                query=q,
                bm25_index=registry.bm25_index,
                registry=registry,
                top_k=max(_AVAILABLE_ADAPTERS_TOP_K, 12),
            )
        except Exception:
            logger.exception("initial resolve policy retrieval failed for '%s'", q[:80])
            return False
        return _query_prefers_resolve_location_before_verify(q, candidates)

    def _build_policy_plan_suffix(user_query: str) -> str:
        q = (user_query or "").strip()
        if not q:
            return ""
        if _query_explicitly_requests_verify_primitive(q):
            return ""
        try:
            from kosmos.tools.registry import ToolRegistry  # noqa: PLC0415
            from kosmos.tools.search import search  # noqa: PLC0415

            registry = cast("ToolRegistry", _ensure_tool_registry())
            candidates = search(
                query=q,
                bm25_index=registry.bm25_index,
                registry=registry,
                top_k=max(_AVAILABLE_ADAPTERS_TOP_K, 12),
            )
        except Exception:
            logger.exception("policy plan retrieval failed for '%s'", q[:80])
            return ""
        positive_candidates = [candidate for candidate in candidates if candidate.score > 0]
        if not positive_candidates:
            return ""
        if _query_prefers_resolve_location_before_verify(q, candidates):
            delegation_source, required_scopes = _delegation_plan_from_candidates(
                _relevant_positive_candidates(candidates),
                registry,
            )
            lines = [
                "<policy_derived_first_action>",
                (
                    "First action: call resolve_location because the citizen "
                    "provided an explicit current location and registry "
                    "retrieval selected strong location-dependent read-only "
                    "adapters before the privileged Gov24 action."
                ),
            ]
            if delegation_source and required_scopes:
                lines.append(
                    "After resolve_location, call verify with "
                    f"tool_id={delegation_source} and scope_list="
                    f"{required_scopes}; then continue the submit/subscribe chain."
                )
            lines.append("</policy_derived_first_action>")
            return "\n".join(lines)
        candidate = positive_candidates[0]
        if not candidate.citizen_facing_gate or candidate.citizen_facing_gate == "read-only":
            return ""
        delegation_source, required_scopes = _delegation_plan_from_candidates(
            positive_candidates,
            registry,
        )
        lines = [
            "<policy_derived_first_action>",
            (
                f"Top policy-gated candidate: {candidate.tool_id} "
                f"(primitive={candidate.primitive}, "
                f"citizen_facing_gate={candidate.citizen_facing_gate})."
            ),
            "First primitive: verify.",
        ]
        if delegation_source:
            lines.append(f"Use verify tool_id: {delegation_source}.")
        if required_scopes:
            lines.append(f"Use verify params.scope_list: {required_scopes}.")
        lines.append(
            "After verify returns, pass result.delegation_context to the "
            "policy-gated adapter params."
        )
        lines.append("</policy_derived_first_action>")
        return "\n".join(lines)

    def _check_lookup_delegation_prerequisite(
        fname: str,
        args_obj: dict[str, object],
    ) -> str | None:
        """Validate lookup prerequisites from adapter policy metadata.

        This is the CC-style ``Tool.validateInput`` boundary for sensitive
        lookup adapters. It is intentionally generic: the adapter's cited
        ``citizen_facing_gate`` is the only policy input.
        """
        if fname != "lookup":
            return None
        inner_tool_id = args_obj.get("tool_id")
        if not isinstance(inner_tool_id, str) or not inner_tool_id:
            return None
        params = args_obj.get("params")
        if not isinstance(params, dict):
            params = {}
        try:
            tool = _ensure_tool_registry().lookup(inner_tool_id)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "lookup delegation prerequisite: cannot resolve %s (%s)",
                inner_tool_id,
                type(exc).__name__,
            )
            return None
        gate = tool.policy.citizen_facing_gate if tool.policy is not None else "login"
        if gate == "read-only" or "delegation_context" in params:
            return None
        return (
            f"Adapter {inner_tool_id!r} has citizen_facing_gate={gate!r}, so lookup "
            "requires a DelegationContext from a prior verify primitive call. "
            "Do not call this lookup first. Call verify, then retry this adapter "
            "with params.delegation_context set to the returned DelegationContext."
        )

    # Spec 1978 T053 — eager-import the Mock adapter tree so every adapter
    # self-registers with its primitive dispatcher before the first chat
    # turn arrives. Equivalent to plan.md "Mock adapter activation"; failure
    # is logged-only because Live tooling can still serve simple queries.
    try:
        import kosmos.tools.mock  # noqa: F401, PLC0415
    except Exception:  # noqa: BLE001
        logger.exception("failed to import kosmos.tools.mock — Mock adapters unavailable")

    # -----------------------------------------------------------------------
    # Spec 1978 T043-T049/T052 — Permission gauntlet bridge
    # -----------------------------------------------------------------------

    _PERM_TIMEOUT_S: float = float(  # noqa: N806 — env-derived constant
        _os_chat_env.environ.get("KOSMOS_PERMISSION_TIMEOUT_SECONDS", "60")
    )

    # Primitives that require a citizen permission request when called outside
    # an existing session-grant. verify is a light gate (delegation-only
    # identity binding); submit/subscribe are heavy gates (side effects or
    # persistent streams). lookup/resolve_location remain auto-allowed unless
    # lookup's inner adapter policy declares a non-read-only gate below.
    #
    # Epic #2077 T010 (FR-003) — single-source-of-truth migration: read the
    # gated set from ``kosmos.primitives.GATED_PRIMITIVES`` rather than
    # duplicating the literal set here. The local alias is preserved for
    # downstream call-site brevity (and to keep diff churn minimal in this
    # epic) but the literal set is no longer maintained in this module.
    from kosmos.primitives import (
        GATED_PRIMITIVES as _PERMISSION_GATED_PRIMITIVES,  # noqa: PLC0415, N811
    )

    async def _check_permission_gate(  # noqa: C901
        call_id: str,
        fname: str,
        args_obj: dict[str, object],
        session_id: str,
        correlation_id: str,
    ) -> bool:
        """Return True if the tool call is permitted to proceed.

        For gated primitives (submit/subscribe):
        1. Check session_grants cache — auto-allow if already approved.
        2. Emit PermissionRequestFrame and await citizen decision (60 s).
        3. On allow_session: cache grant; write consent receipt.
        4. On allow_once: write consent receipt, no cache.
        5. On deny or timeout: emit synthetic tool_result with error, return False.

        For non-gated primitives (lookup/resolve_location/verify): return True
        immediately without touching the bridge.
        """
        from kosmos.ipc.frame_schema import (  # noqa: PLC0415
            PermissionRequestFrame,
            ToolResultEnvelope,
            ToolResultFrame,
        )

        if _pre_permission_arg_error(fname, args_obj) is not None:
            with _tracer.start_as_current_span("kosmos.permission") as span:
                span.set_attribute("kosmos.permission.mode", "auto_allow")
                span.set_attribute("kosmos.permission.decision", "skip_invalid_params")
                span.set_attribute("kosmos.tool.dispatched", fname)
            return True

        # F-beta-04 fix (Wave-2 G1, PIPA §22): when the LLM dispatches via
        # `lookup(mode='fetch', tool_id=<adapter>, params=...)`, the gate must
        # consult the *adapter's* `policy.citizen_facing_gate` because the
        # adapter — not the primitive — owns the citizen-consent contract
        # (AGENTS.md L1-B B4: "KOSMOS does not invent permission policy —
        # adapters cite the agency's own published policy"). Adapters whose
        # gate is anything other than ``"read-only"`` (login / action / sign /
        # submit) require a Spec 035 modal turn before dispatch, even though
        # the carrying primitive is `lookup`. The auto-allow short-circuit
        # below is preserved only for `read-only` lookup adapters and for
        # `resolve_location` (a coord-only public utility).
        if fname not in _PERMISSION_GATED_PRIMITIVES:
            _lookup_needs_modal = False
            if fname == "lookup":
                _inner_tool_id = args_obj.get("tool_id")
                if isinstance(_inner_tool_id, str) and _inner_tool_id:
                    try:
                        _registry_for_gate = _ensure_tool_registry()
                        _adapter_tool = _registry_for_gate.lookup(  # type: ignore[attr-defined]
                            _inner_tool_id
                        )
                        _adapter_gate = (
                            _adapter_tool.policy.citizen_facing_gate
                            if _adapter_tool.policy is not None
                            else "login"
                        )
                        if _adapter_gate != "read-only":
                            _lookup_params = args_obj.get("params")
                            _has_delegation_context = (
                                isinstance(_lookup_params, dict)
                                and "delegation_context" in _lookup_params
                            )
                            if _has_delegation_context:
                                logger.info(
                                    "permission: lookup adapter %s uses prior "
                                    "DelegationContext; skipping duplicate modal "
                                    "(citizen_facing_gate=%s)",
                                    _inner_tool_id,
                                    _adapter_gate,
                                )
                            else:
                                _lookup_needs_modal = True
                                logger.info(
                                    "permission: lookup adapter %s requires modal "
                                    "(citizen_facing_gate=%s)",
                                    _inner_tool_id,
                                    _adapter_gate,
                                )
                    except Exception as exc:  # noqa: BLE001
                        # Fail-closed: when the registry cannot resolve the
                        # adapter (boot race / unknown id), require modal
                        # rather than risk an unconsented L3 dispatch. The
                        # downstream invoke() will produce a precise
                        # unknown_tool envelope after consent if the citizen
                        # grants — but we never auto-pass an unknown id.
                        _lookup_needs_modal = True
                        logger.warning(
                            "permission: lookup adapter resolution failed "
                            "for %s (%s); failing closed to modal",
                            _inner_tool_id,
                            type(exc).__name__,
                        )
            if not _lookup_needs_modal:
                with _tracer.start_as_current_span("kosmos.permission") as span:
                    span.set_attribute("kosmos.permission.mode", "auto_allow")
                    span.set_attribute("kosmos.permission.decision", "allow_once")
                    span.set_attribute("kosmos.tool.dispatched", fname)
                return True

        # Check session grant cache first (allow_session shortcut — T048).
        session_grant_set = _session_grants.get(session_id, set())
        tool_key = f"{fname}:{args_obj.get('tool_id', fname)}"
        if tool_key in session_grant_set:
            with _tracer.start_as_current_span("kosmos.permission") as span:
                span.set_attribute("kosmos.permission.mode", "auto_allow")
                span.set_attribute("kosmos.permission.decision", "allow_session")
                span.set_attribute("kosmos.tool.dispatched", fname)
            logger.debug("permission: session_grant hit for %s session=%s", tool_key, session_id)
            return True

        # Determine risk level and description from primitive type.
        # verify is LIGHT_GATE (low risk, identity delegation read-only).
        # submit/subscribe are HEAVY_GATE (medium/high risk, side-effecting).
        # `lookup` enters this branch only when the inner adapter has a
        # non-`read-only` policy.citizen_facing_gate (F-beta-04 fix above) —
        # NMC emergency search, HIRA L3 variants, login-gated KMA endpoints,
        # etc. Treat as medium risk: the citizen is reading sensitive but
        # not write-side data.
        _PRIM_RISK: dict[str, str] = {  # noqa: N806
            "verify": "low",
            "submit": "high",
            "subscribe": "medium",
            "lookup": "medium",
        }
        _PRIM_KO: dict[str, str] = {  # noqa: N806
            "verify": "신원 확인을 위해 인증 위임을 요청합니다.",
            "submit": "정부 API에 데이터를 제출합니다. 이 작업은 되돌릴 수 없습니다.",
            "subscribe": "공공 데이터 스트림을 구독합니다.",
            "lookup": (
                "민감 정보 도구를 호출합니다. 어댑터 정책상 시민 동의가 필요한 데이터입니다."
            ),
        }
        _PRIM_EN: dict[str, str] = {  # noqa: N806
            "verify": "Request identity delegation for verification.",
            "submit": "Submit data to a government API. This action is irreversible.",
            "subscribe": "Subscribe to a public data stream.",
            "lookup": (
                "Invoke a sensitive lookup tool whose adapter policy "
                "requires explicit citizen consent."
            ),
        }

        request_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        _pending_perms[request_id] = loop.create_future()

        with _tracer.start_as_current_span("kosmos.permission") as perm_span:
            perm_span.set_attribute("kosmos.permission.mode", "ask")
            perm_span.set_attribute("kosmos.tool.dispatched", fname)

            # Audit-4 P0-10 fix — propagate the resolving adapter id
            # (e.g. `mock_verify_mobile_id`) as both `worker_id` and the new
            # `tool_id` field. Without this the TUI rendered the literal
            # `"main"` in every permission modal title because
            # `pushIpcPermissionRequest` (ipcPermissionBridge.ts:153) read
            # `frame.worker_id || frame.primitive_kind`.
            _resolved_tool_id = str(args_obj.get("tool_id", fname))
            try:
                await write_frame(
                    PermissionRequestFrame(
                        session_id=session_id,
                        correlation_id=correlation_id,
                        role="backend",
                        ts=_utcnow(),
                        kind="permission_request",
                        request_id=request_id,
                        worker_id=_resolved_tool_id,
                        primitive_kind=fname,  # type: ignore[arg-type]
                        description_ko=_PRIM_KO.get(fname, "도구를 실행합니다."),
                        description_en=_PRIM_EN.get(fname, "Invoke tool."),
                        risk_level=_PRIM_RISK.get(fname, "medium"),  # type: ignore[arg-type]
                        tool_id=_resolved_tool_id,
                        arguments=_permission_visible_arguments(args_obj),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("permission: failed to emit permission_request: %s", exc)
                _pending_perms.pop(request_id, None)
                perm_span.set_attribute("kosmos.permission.decision", "deny")
                return False

            # Await citizen decision with timeout (D2 invariant).
            decision_frame: Any = None
            try:
                decision_frame = await asyncio.wait_for(
                    _pending_perms[request_id],
                    timeout=_PERM_TIMEOUT_S,
                )
                perm_span.set_attribute("kosmos.permission.decision", "allow_once")
            except TimeoutError:
                logger.warning(
                    "permission: timeout waiting for response to request_id=%s", request_id
                )
                perm_span.set_attribute("kosmos.permission.decision", "timeout")
                _pending_perms.pop(request_id, None)
                # Emit synthetic denied tool_result so the LLM turn resolves.
                denied_env = ToolResultEnvelope(
                    kind=cast("Any", fname),
                    **{"error": "permission_timeout", "denied": True},
                )
                fut = _pending_calls.get(call_id)
                if fut and not fut.done():
                    denied_result_frame = ToolResultFrame(
                        session_id=session_id,
                        correlation_id=correlation_id,
                        role="backend",
                        ts=_utcnow(),
                        kind="tool_result",
                        call_id=call_id,
                        envelope=denied_env,
                    )
                    fut.set_result(denied_result_frame)
                return False
            finally:
                _pending_perms.pop(request_id, None)

            # Map PermissionResponseFrame.decision → allow/deny per Spec 1978
            # ADR-0002. Spec 287 baseline emitted only "granted" / "denied"; the
            # 3-decision UI vocabulary (allow_once | allow_session | deny) is
            # accepted now that frame_schema.py extends the Literal.
            raw_decision: str = getattr(decision_frame, "decision", "denied")
            is_deny = raw_decision in {"denied", "deny"}
            is_allow_session = raw_decision == "allow_session"
            if is_deny:
                perm_span.set_attribute("kosmos.permission.decision", "deny")
                # Audit-4 P0-2 — append HMAC-sealed deny record so the audit
                # trail captures BOTH the request emission and the citizen's
                # negative decision. Without this, "permission_denied" tool
                # results have no integrity-verified provenance in the ledger.
                try:
                    from kosmos.permissions.action_digest import (  # noqa: PLC0415
                        compute_action_digest,
                        generate_nonce,
                    )
                    from kosmos.permissions.ledger import (  # noqa: PLC0415
                        append as _ledger_append_deny,
                    )
                    from kosmos.settings import (  # noqa: PLC0415
                        settings as _kosmos_settings_deny,
                    )

                    _deny_args = {k: v for k, v in args_obj.items() if k != "delegation_context"}
                    _deny_digest = compute_action_digest(
                        str(args_obj.get("tool_id", fname)),
                        _deny_args,
                        generate_nonce(),
                    )
                    _ledger_append_deny(
                        tool_id=str(args_obj.get("tool_id", fname)),
                        mode="default",
                        granted=False,
                        action_digest=_deny_digest,
                        action="deny",
                        session_id=session_id,
                        correlation_id=correlation_id,
                        ledger_path=_kosmos_settings_deny.permission_ledger_path,
                        key_path=_kosmos_settings_deny.permission_key_path,
                        key_registry_path=_kosmos_settings_deny.permission_key_registry_path,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("permission: ledger.append(deny) failed: %s", exc)
                # Emit synthetic denied tool_result.
                denied_env2 = ToolResultEnvelope(
                    kind=cast("Any", fname),
                    **{"error": "permission_denied", "denied": True},
                )
                fut2 = _pending_calls.get(call_id)
                if fut2 and not fut2.done():
                    denied_result_frame2 = ToolResultFrame(
                        session_id=session_id,
                        correlation_id=correlation_id,
                        role="backend",
                        ts=_utcnow(),
                        kind="tool_result",
                        call_id=call_id,
                        envelope=denied_env2,
                    )
                    fut2.set_result(denied_result_frame2)
                return False

            # Granted — write consent receipt + optionally update session grant cache.
            # Audit-4 P0-4 fix — emit `rcpt-<8-char-hex>` so the format matches the
            # TUI regex `^rcpt-[A-Za-z0-9_-]{8,}$` (schemas/ui-l2/permission.ts:26)
            # AND the executeConsentRevoke validator (commands/consent.ts:90).
            # Without the prefix every backend-issued receipt was rejected by the
            # citizen-facing /consent revoke flow with `invalid_id`.
            receipt_id = f"rcpt-{uuid.uuid4().hex[:8]}"
            decision_label = "allow_session" if is_allow_session else "allow_once"
            perm_span.set_attribute("kosmos.permission.decision", decision_label)
            perm_span.set_attribute("kosmos.consent.receipt_id", receipt_id)

            # Spec 1978 T049 — allow_session caches the (primitive, tool_id)
            # pair so subsequent same-session same-tool calls bypass the
            # bridge entirely (lookup at the top of this function via
            # _session_grants). Audit-4 alignment fix (2026-05-04): the
            # storage key MUST match the lookup key. The lookup at line
            # 1406 uses `f"{fname}:{tool_id}"`; the prior storage stored
            # only `tool_id` → cache miss on every "allow_session" call.
            if is_allow_session:
                tool_key_for_cache = f"{fname}:{args_obj.get('tool_id', fname)}"
                _session_grants.setdefault(session_id, set()).add(tool_key_for_cache)
            try:
                import json as _json_receipt  # noqa: PLC0415
                from pathlib import Path as _Path  # noqa: PLC0415

                consent_dir = _Path.home() / ".kosmos" / "memdir" / "user" / "consent"
                consent_dir.mkdir(parents=True, exist_ok=True)
                receipt_path = consent_dir / f"{receipt_id}.json"
                receipt_data = {
                    "receipt_id": receipt_id,
                    "session_id": session_id,
                    "tool_id": str(args_obj.get("tool_id", fname)),
                    "primitive": fname,
                    "decision": decision_label,
                    "granted_at": _utcnow(),
                    "revoked_at": None,
                }
                receipt_path.write_text(
                    _json_receipt.dumps(receipt_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                logger.debug("permission: wrote consent receipt %s", receipt_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("permission: failed to write consent receipt: %s", exc)

            # Audit-4 P0-2 — append HMAC-sealed, hash-chained ledger record so the
            # consent receipt JSON in the memdir layer is BACKED by an integrity-
            # verified entry in the canonical Spec 033 PIPA ledger
            # (~/.kosmos/consent_ledger.jsonl). Without this append, allow paths
            # left receipts forgeable: no HMAC seal, no chain prev_hash, no key_id.
            #
            # Failures are logged-only — the citizen has already approved the
            # action and the synthetic tool_result must still be emitted. A
            # follow-up `kosmos permissions verify` run will surface any drift.
            try:
                from kosmos.permissions.action_digest import (  # noqa: PLC0415
                    compute_action_digest,
                    generate_nonce,
                )
                from kosmos.permissions.ledger import (  # noqa: PLC0415
                    append as _ledger_append,
                )
                from kosmos.settings import settings as _kosmos_settings  # noqa: PLC0415

                _ledger_args = {k: v for k, v in args_obj.items() if k != "delegation_context"}
                _digest = compute_action_digest(
                    str(args_obj.get("tool_id", fname)),
                    _ledger_args,
                    generate_nonce(),
                )
                _ledger_append(
                    tool_id=str(args_obj.get("tool_id", fname)),
                    mode="default",
                    granted=True,
                    action_digest=_digest,
                    action="allow",
                    consent_receipt_id=receipt_id,
                    session_id=session_id,
                    correlation_id=correlation_id,
                    ledger_path=_kosmos_settings.permission_ledger_path,
                    key_path=_kosmos_settings.permission_key_path,
                    key_registry_path=_kosmos_settings.permission_key_registry_path,
                )
                logger.debug(
                    "permission: ledger.append(allow) ok receipt_id=%s tool=%s",
                    receipt_id,
                    args_obj.get("tool_id", fname),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "permission: ledger.append(allow) failed (receipt_id=%s): %s",
                    receipt_id,
                    exc,
                )

            # Gap A fix — emit PermissionResponseFrame echo back to TUI so
            # that addReceipt() callsites can capture the receipt_id without
            # a separate /consent list round-trip. This is a backend→TUI
            # echo, not a new request; the TUI ignores it safely if it
            # doesn't recognise the receipt_id field (backward-compat via
            # Optional default=None in frame_schema.py).
            from kosmos.ipc.frame_schema import (  # noqa: PLC0415
                PermissionResponseFrame as _PermissionResponseFrame,
            )

            try:
                await write_frame(
                    _PermissionResponseFrame(
                        session_id=session_id,
                        correlation_id=correlation_id,
                        role="backend",
                        ts=_utcnow(),
                        kind="permission_response",
                        request_id=request_id,
                        decision=decision_label,  # type: ignore[arg-type]
                        receipt_id=receipt_id,
                        # Audit-4 P0-6 / P0-7 — propagate enough context for the
                        # TUI's usePermissionReceiptWatcher to recompute the
                        # gauntlet layer (1=green / 2=orange / 3=red) and render
                        # the human-readable adapter name in /consent list.
                        # Without these the TUI hardcoded layer=1 and tool_name=
                        # 'unknown' for every receipt regardless of primitive.
                        primitive_kind=fname,  # type: ignore[arg-type]
                        tool_id=_resolved_tool_id,
                    )
                )
                logger.debug("permission: emitted receipt echo (receipt_id=%s)", receipt_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("permission: failed to emit receipt echo: %s", exc)

            return True

    def _pre_permission_arg_error(fname: str, args_obj: dict[str, object]) -> str | None:
        """Reject malformed primitive calls before opening a permission modal."""
        if "_raw" in args_obj:
            return (
                f"malformed {fname} tool arguments: expected a JSON object matching "
                "the primitive schema. Re-emit a valid JSON object using tool_id "
                "from <available_adapters>; do not ask the citizen for backend-"
                "injected session_id, DelegationContext internals, or identity numbers."
            )
        if "_value" in args_obj:
            return (
                f"invalid {fname} tool arguments: expected a JSON object, got "
                "a non-object JSON value. Re-emit a valid object with tool_id and params."
            )
        if fname in {"lookup", "submit", "subscribe"}:
            tool_id = args_obj.get("tool_id")
            if not isinstance(tool_id, str) or not tool_id:
                return (
                    f"invalid {fname} params: tool_id must be a non-empty adapter id "
                    "selected from <available_adapters>."
                )
        if fname == "verify":
            return _verify_pre_permission_arg_error(args_obj)
        return None

    async def _handle_permission_response(frame: IPCFrame) -> None:
        """Spec 1978 T047 — consume permission_response and resolve pending Future.

        Maps incoming PermissionResponseFrame.request_id to the waiting
        _pending_perms entry. Frames with no matching request_id are logged
        and silently dropped (forward-compat: stale responses after timeout).
        """
        from kosmos.ipc.frame_schema import PermissionResponseFrame  # noqa: PLC0415

        if not isinstance(frame, PermissionResponseFrame):
            return
        fut = _pending_perms.pop(frame.request_id, None)
        if fut is None:
            logger.debug(
                "permission_response with no pending request (request_id=%s) — ignoring",
                frame.request_id,
            )
            return
        if not fut.done():
            fut.set_result(frame)

    # -----------------------------------------------------------------------
    # Spec 1978 T053b — internal primitive dispatcher
    # -----------------------------------------------------------------------

    async def _dispatch_primitive(  # noqa: C901, PLR0912
        call_id: str,
        fname: str,
        args_obj: dict[str, object],
        session_id: str,
        correlation_id: str,
    ) -> None:
        """Dispatch a single primitive call internally and resolve its pending Future.

        CC reference: ``services/tools/toolOrchestration.ts:19-72`` (CC's ``runTools``
        async generator). Note partition policy divergence: KOSMOS dispatches all
        primitive calls in parallel via ``asyncio.gather`` since the citizen-facing
        primitives (lookup/resolve_location/verify) are read-only-equivalent. CC
        partitions by ``isConcurrencySafe`` (read-only batches parallel,
        write-side serial). Tracking the partition adoption as Deferred Item #2574.

        Called immediately after a tool_call frame is emitted and the Future
        is registered in _pending_calls. Routes by fname, awaits the primitive,
        wraps the result in a ToolResultFrame, emits it to the TUI, then
        resolves _pending_calls[call_id] so the agentic-loop continuation can
        inject the result as a role="tool" message.

        Permission gate: submit/subscribe go through _check_permission_gate
        first. On denial/timeout, the gate itself resolves the Future with an
        error envelope, so this function exits early without double-resolution.

        OTEL: sets kosmos.tool.dispatched on the existing session span.
        """

        from kosmos.ipc.frame_schema import (  # noqa: PLC0415
            ToolResultEnvelope,
            ToolResultFrame,
        )

        with _tracer.start_as_current_span("kosmos.tool.dispatch") as span:
            span.set_attribute("kosmos.tool.dispatched", fname)
            span.set_attribute("kosmos.session.id", session_id)

            pre_permission_error = _pre_permission_arg_error(fname, args_obj)
            if pre_permission_error is not None:
                result_frame = ToolResultFrame(
                    session_id=session_id,
                    correlation_id=correlation_id,
                    role="backend",
                    ts=_utcnow(),
                    kind="tool_result",
                    call_id=call_id,
                    envelope=ToolResultEnvelope(
                        kind=cast("Any", fname),
                        **{
                            "error": pre_permission_error,
                            "tool_id": str(args_obj.get("tool_id", fname)),
                        },
                    ),
                )
                try:
                    await write_frame(result_frame)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "_dispatch_primitive: failed to emit pre-permission error: %s",
                        exc,
                    )
                fut = _pending_calls.pop(call_id, None)
                if fut is not None and not fut.done():
                    fut.set_result(result_frame)
                return

            # ----- Permission gate (T043-T049) -----
            allowed = await _check_permission_gate(
                call_id, fname, args_obj, session_id, correlation_id
            )
            if not allowed:
                # Gate already resolved the Future with an error envelope.
                span.set_attribute("kosmos.permission.decision", "deny")
                return

            result_payload: dict[str, object] = {}
            dispatch_error: str | None = None
            # Each primitive returns a different Pydantic model. Annotate as
            # Any so the branches below can assign without mypy assignment
            # narrowing complaints.
            raw: Any

            # Spec 2521 (2026-05-01) — open an outbound HTTP trace scope so
            # any ``data.go.kr`` / agency call the adapter makes is captured
            # and attached to the envelope as ``outbound_traces``. The TUI's
            # verbose render reads this field to show the citizen / operator
            # the exact request/response JSON.
            from kosmos.tools._outbound_trace import (  # noqa: PLC0415
                consume_outbound_capture,
                start_outbound_capture,
            )

            _outbound_trace_token = start_outbound_capture()

            try:
                if fname == "verify":
                    from kosmos.primitives.verify import (  # noqa: PLC0415
                        verify,
                    )
                    from kosmos.tools.verify_canonical_map import (  # noqa: PLC0415
                        resolve_family,
                    )

                    # Spec 2297 / Issue #C1 (2026-05-04) — translate
                    # ``tool_id`` → ``family_hint`` via the canonical map
                    # parsed from ``prompts/system_v1.md`` ``<verify_families>``.
                    # The mvp_surface ``_VerifyInputForLLM.translate_tool_id_shape``
                    # validator only fires when the LLM call goes through Pydantic
                    # schema validation; the IPC stdio dispatcher bypasses that
                    # path and historically read ``family_hint`` directly from
                    # the args dict, leaving every K-EXAONE-emitted
                    # ``verify({tool_id: …})`` call resolving to ``family_hint=""``
                    # → "No verify adapter registered for family ''".
                    # Accept both ``family`` (citizen-facing tool schema) and
                    # ``family_hint`` (primitive's internal arg name) for
                    # legacy / tools-bridge compatibility.
                    tool_id = str(args_obj.get("tool_id") or "")
                    resolved_family = resolve_family(tool_id) if tool_id else None
                    family_hint = resolved_family or str(
                        args_obj.get("family_hint") or args_obj.get("family") or ""
                    )
                    if tool_id and resolved_family is None and not family_hint:
                        dispatch_error = (
                            f"unknown verify tool_id: {tool_id!r}. Select one of the "
                            "tool_ids listed in <verify_families> or the adapter "
                            "delegation_source_tool_id metadata."
                        )
                    # Accept the LLM-facing citizen shape
                    # {tool_id, params={scope_list, purpose_ko, ...}} and the
                    # legacy primitive shape {family_hint, session_context}.
                    # mvp_surface._VerifyInputForLLM performs this packing for
                    # schema-validated callers, but stdio dispatch receives the
                    # already-decoded tool_call args directly.
                    raw_session_ctx = args_obj.get("session_context")
                    session_ctx: dict[str, object] = (
                        dict(raw_session_ctx) if isinstance(raw_session_ctx, dict) else {}
                    )
                    raw_params = args_obj.get("params")
                    if isinstance(raw_params, dict):
                        session_ctx.update(cast("dict[str, object]", raw_params))
                    if "session_id" not in session_ctx:
                        session_ctx["session_id"] = session_id
                    if tool_id and dispatch_error is None:
                        missing_param_keys = [
                            key
                            for key in ("scope_list", "purpose_ko", "purpose_en")
                            if key not in session_ctx
                        ]
                        scope_list = session_ctx.get("scope_list")
                        if (
                            missing_param_keys
                            or not isinstance(scope_list, list)
                            or not scope_list
                            or not all(
                                isinstance(scope, str) and scope.strip() for scope in scope_list
                            )
                        ):
                            dispatch_error = (
                                "invalid verify params: citizen-shape verify(tool_id=...) "
                                "requires params.scope_list (non-empty list[str]), "
                                "params.purpose_ko, and params.purpose_en. "
                                "Use the adapter's delegation_source_tool_id and "
                                "required scope metadata from <available_adapters>."
                            )
                    if dispatch_error is None:
                        raw = await verify(family_hint=family_hint, session_context=session_ctx)
                        if getattr(raw, "published_tier", None) is not None:
                            _session_auth_contexts[session_id] = raw
                        result_payload = {
                            "family": family_hint,
                            "result": _serialize_primitive_result(raw),
                        }

                elif fname == "lookup":
                    # Spec 2521 (2026-05-01): the LLM-visible ``lookup``
                    # surface is fetch-only. BM25 adapter discovery is a
                    # backend-internal mechanism (auto-injected into the
                    # ``<available_adapters>`` dynamic suffix) — the LLM
                    # MUST NOT see "search" as a callable mode. Stale
                    # ``mode='search'`` payloads from older sessions are
                    # rejected with a typed LookupError so the agentic
                    # loop continues without painting an "internal
                    # function as tool" UI block.
                    from kosmos.tools.errors import LookupErrorReason  # noqa: PLC0415
                    from kosmos.tools.lookup import lookup  # noqa: PLC0415
                    from kosmos.tools.models import (  # noqa: PLC0415
                        LookupError,  # noqa: A004 — Pydantic model named LookupError; intentional shadow with module-level alias not feasible in narrow import scope
                        LookupFetchInput,
                    )

                    requested_mode = args_obj.get("mode")
                    if requested_mode is not None and str(requested_mode) != "fetch":
                        logger.warning(
                            "lookup: rejected mode=%r — LLM-visible surface is "
                            "fetch-only since Spec 2521. Skipping dispatch.",
                            requested_mode,
                        )
                        raw = LookupError(
                            kind="error",
                            reason=LookupErrorReason.invalid_params,
                            message=(
                                "lookup(mode='search') 는 백엔드 internal 기능입니다 — "
                                "직접 호출하지 마십시오. 시스템 프롬프트의 "
                                "<available_adapters> 에서 tool_id 를 골라 fetch 호출만 사용하세요."
                            ),
                            retryable=False,
                        )
                        result_payload = {
                            "kind": "lookup",
                            "result": _serialize_primitive_result(raw),
                        }
                    else:
                        # Use the session-scoped singleton populated by
                        # register_all_tools (Spec 1634). Constructing a fresh
                        # empty ToolRegistry / ToolExecutor here would trigger
                        # reason="empty_registry" for every fetch — the very
                        # bug fixed on 2026-05-01.
                        registry = _ensure_tool_registry()
                        executor = _ensure_tool_executor()
                        inp_lk = LookupFetchInput(
                            mode="fetch",
                            tool_id=str(args_obj.get("tool_id", "")),
                            params=cast("dict[str, object]", args_obj.get("params") or {}),
                        )
                        raw = await lookup(
                            inp_lk,
                            registry=registry,
                            executor=executor,
                            session_identity=session_id,
                        )
                        result_payload = {
                            "kind": "lookup",
                            "result": _serialize_primitive_result(raw),
                        }

                elif fname == "resolve_location":
                    from kosmos.tools.models import ResolveLocationInput  # noqa: PLC0415
                    from kosmos.tools.resolve_location import resolve_location  # noqa: PLC0415

                    inp_rl = ResolveLocationInput(
                        query=str(args_obj.get("query", "")),
                        want=str(args_obj.get("want", "coords_and_admcd")),  # type: ignore[arg-type]
                    )
                    raw = await resolve_location(inp_rl)
                    result_payload = {
                        "kind": "resolve_location",
                        "result": _serialize_primitive_result(raw),
                    }

                elif fname == "submit":
                    from kosmos.primitives.submit import submit  # noqa: PLC0415

                    submit_params = cast("dict[str, object]", args_obj.get("params") or {})
                    _submit_tool_id = str(args_obj.get("tool_id", ""))
                    _schema_args: dict[str, object] = {
                        "tool_id": _submit_tool_id,
                        "params": submit_params,
                    }
                    _submit_schema = _schema_for_adapter_args(_schema_args, _ensure_tool_registry())
                    _submit_props = _schema_properties(_submit_schema)
                    if "session_id" in _submit_props and "session_id" not in submit_params:
                        submit_params = dict(submit_params)
                        submit_params["session_id"] = session_id
                    raw = await submit(
                        tool_id=_submit_tool_id,
                        params=submit_params,
                        auth_context=_session_auth_contexts.get(session_id),
                        session_id=session_id,
                    )
                    result_payload = {
                        "kind": "submit",
                        "result": _serialize_primitive_result(raw),
                    }

                elif fname == "subscribe":
                    # T069 streaming events are deferred. Return the SubscriptionHandle.
                    from kosmos.ipc.frame_schema import (  # noqa: PLC0415
                        WorkerStatusFrame,
                    )
                    from kosmos.primitives.subscribe import (  # noqa: PLC0415
                        SubscribeInput,
                        _SubscribeIterator,
                        subscribe,
                    )

                    inp_sub = SubscribeInput(
                        tool_id=str(args_obj.get("tool_id", "")),
                        params=cast("dict[str, object]", args_obj.get("params") or {}),
                        lifetime_seconds=int(cast("Any", args_obj.get("lifetime_seconds", 300))),
                    )
                    iterator_or_error = subscribe(inp_sub)
                    if isinstance(iterator_or_error, _SubscribeIterator):
                        # Audit-5 P0-2 fix (2026-05-04): use the canonical
                        # subscription_id from the real ``SubscriptionHandle``
                        # so the TUI ``subscriptionRegistry`` key matches every
                        # subsequent OTEL span / drop event / consent ledger
                        # entry. Synthetic ``uuid.uuid4()`` removed.
                        handle = iterator_or_error.peek_handle()
                        result_payload = {
                            "kind": "subscribe",
                            "subscription_id": handle.subscription_id,
                            "handle_id": handle.subscription_id,  # alias for TS-side
                            "tool_id": inp_sub.tool_id,
                            "opened_at": handle.opened_at.isoformat(),
                            "closes_at": handle.closes_at.isoformat(),
                            "lifetime_seconds": int(inp_sub.lifetime_seconds),
                            "status": "opened",
                            "note": "Streaming events deferred (T069).",
                        }

                        # Audit-5 P0-4 fix (2026-05-04): emit a WorkerStatusFrame
                        # so the TUI ``AgentVisibilityPanel`` (subscribed via
                        # ``bridge.frames()``) records the active subscription
                        # channel as a "running" ministry agent. The panel maps
                        # ``role_id`` → display label; we pass the adapter
                        # ``tool_id`` so the citizen sees the real source name.
                        # The frontend ``subscriptionRegistry`` (TS-side) and
                        # this ``worker_status`` IPC stream now agree on the
                        # same ``worker_id`` (``subscribe:<subscription_id>``).
                        try:
                            ws_frame = WorkerStatusFrame(
                                session_id=session_id,
                                correlation_id=correlation_id,
                                ts=_utcnow(),
                                role="backend",
                                kind="worker_status",
                                worker_id=f"subscribe:{handle.subscription_id}",
                                role_id=inp_sub.tool_id,
                                current_primitive="subscribe",
                                status="running",
                            )
                            await write_frame(ws_frame)
                        except Exception as _ws_exc:  # noqa: BLE001
                            logger.warning(
                                "subscribe: failed to emit worker_status frame: %s",
                                _ws_exc,
                            )
                    else:
                        # AdapterNotFoundError or similar
                        result_payload = {
                            "kind": "subscribe",
                            "error": str(iterator_or_error),
                            "tool_id": str(args_obj.get("tool_id", "")),
                        }

                else:
                    dispatch_error = f"unknown primitive {fname!r}"

            except Exception as exc:  # noqa: BLE001
                logger.exception("_dispatch_primitive: %s dispatch failed: %s", fname, exc)
                dispatch_error = str(exc)

            if dispatch_error:
                result_payload = {
                    "kind": fname,
                    "error": dispatch_error,
                    "tool_id": str(args_obj.get("tool_id", fname)),
                }

            # Drain the outbound HTTP trace buffer + attach to the envelope.
            outbound_traces = consume_outbound_capture(_outbound_trace_token)
            if outbound_traces:
                # Pydantic model_dump → JSON-serialisable dict; envelope
                # accepts the extra field via ``extra="allow"``.
                result_payload["outbound_traces"] = [t.model_dump() for t in outbound_traces]

            # Build ToolResultEnvelope + ToolResultFrame.
            # ToolResultEnvelope uses extra="allow" so extra payload fields are kept.
            # Strip any payload-level "kind" so the kwarg is single-valued.
            payload_kw = {k: v for k, v in result_payload.items() if k != "kind"}
            envelope = ToolResultEnvelope(kind=cast("Any", fname), **payload_kw)
            result_frame = ToolResultFrame(
                session_id=session_id,
                correlation_id=correlation_id,
                role="backend",
                ts=_utcnow(),
                kind="tool_result",
                call_id=call_id,
                envelope=envelope,
            )

            # Emit to TUI for display.
            try:
                await write_frame(result_frame)
            except Exception as exc:  # noqa: BLE001
                logger.warning("_dispatch_primitive: failed to emit tool_result frame: %s", exc)

            # Resolve the pending Future so the agentic loop can continue.
            fut = _pending_calls.pop(call_id, None)
            if fut is not None and not fut.done():
                fut.set_result(result_frame)

    async def _handle_chat_request(frame: IPCFrame) -> None:  # noqa: C901, PLR0915
        """Spec 1978 ADR-0001 — tools-aware chat handler.

        CC reference: ``QueryEngine.ts`` (whole, 1295 lines) + ``query.ts:120-410``
        (yieldMissingToolResultBlocks pattern). Behavior-mirror: KOSMOS preserves
        CC's per-turn message_id, structured tool_calls dispatch, role="tool"
        injection between turns, max_turns termination semantics. The only
        divergence is the I/O surface — CC reads from Anthropic SDK stream,
        KOSMOS reads from FriendliAI OpenAI-compat SSE via LLMClient and emits
        IPCFrames over stdio JSONL (Spec 287 / Spec 032 IPC contract).

        Implements the CC (Claude Code 2.1.88) query-engine agentic loop —
        native function calling + token streaming + parallel tool dispatch
        + content_block accumulation, NOT the academic ReAct paradigm
        (text-marker-based Thought/Action). See memory
        ``feedback_kosmos_uses_cc_query_engine`` for the architectural
        rationale.

        Replaces ``_handle_user_input_llm`` for ``ChatRequestFrame``. Streams
        text deltas as ``AssistantChunkFrame``, emits one ``ToolCallFrame``
        per K-EXAONE function-call, awaits each matching ``ToolResultFrame``
        via ``_pending_calls`` Futures, then injects synthetic
        ``role="tool"`` messages into the local history and re-invokes
        ``LLMClient.stream`` (agentic-loop continuation per ADR-0005).

        Loop is bounded by ``KOSMOS_AGENTIC_LOOP_MAX_TURNS`` (default 8;
        also accepts the legacy ``KOSMOS_REACT_MAX_TURNS``) and the
        per-call wait by ``KOSMOS_TOOL_RESULT_TIMEOUT_SECONDS`` (default 120).
        """
        from kosmos.ipc.frame_schema import (  # noqa: PLC0415
            AssistantChunkFrame,
            ChatRequestFrame,
            ToolCallFrame,
        )
        from kosmos.llm.models import (  # noqa: PLC0415
            ChatMessage as LLMChatMessage,
        )
        from kosmos.llm.models import (
            FunctionCall as LLMFunctionCall,
        )
        from kosmos.llm.models import (
            ToolCall as LLMToolCall,
        )
        from kosmos.llm.models import (
            ToolDefinition as LLMToolDefinition,
        )
        from kosmos.llm.system_prompt_builder import (  # noqa: PLC0415
            build_system_prompt_with_tools,
        )

        if not isinstance(frame, ChatRequestFrame):
            return

        # ---- spec-multi-turn-contamination diagnostic emit (FR-001/FR-002)
        # Increment the per-session turn counter and dump the inbound
        # ChatRequestFrame.messages tail so we can prove which user turn
        # K-EXAONE actually saw on the wire. Off by default; gated by
        # KOSMOS_CHAT_REQUEST_DUMP=1. Truncates each message content to
        # 256 chars to keep the log line bounded.
        # Always increment the counter so OTEL `kosmos.chat.turn_index`
        # works regardless of the env-gated stderr dump.
        _diag_turn_idx = _session_turn_counter.get(frame.session_id, 0) + 1
        _session_turn_counter[frame.session_id] = _diag_turn_idx
        # Additive Spec 021 OTEL extension — annotate the parent
        # `kosmos.ipc.frame` span (opened by the reader loop) with the
        # turn index so Langfuse traces can group multi-turn flows.
        try:
            _current_span = trace.get_current_span()
            if _current_span is not None:
                _current_span.set_attribute("kosmos.chat.turn_index", _diag_turn_idx)
        except Exception:  # noqa: BLE001, S110 — telemetry must never raise
            pass
        if _diag_chat_request_enabled():
            try:
                _dump_payload = [
                    {
                        "role": m.role,
                        "content": (m.content or "")[:256],
                        "name": m.name,
                        "tool_call_id": m.tool_call_id,
                    }
                    for m in frame.messages
                ]
                logger.info(
                    "[CHAT_REQUEST_DUMP] turn=%d session=%s correlation=%s "
                    "messages_count=%d messages=%s",
                    _diag_turn_idx,
                    frame.session_id,
                    frame.correlation_id,
                    len(frame.messages),
                    _stdlib_json.dumps(_dump_payload, ensure_ascii=False),
                )
            except Exception:  # noqa: BLE001 — diagnostic must never raise
                logger.exception("[CHAT_REQUEST_DUMP] failed to serialise")

        # Tool inventory — backend ToolRegistry is the single source of
        # truth, BUT only the five LLM-callable primitives go into the
        # ``tools`` parameter the model sees. KOSMOS architecture
        # (docs/vision.md L1-C): `system prompt exposes primitive
        # signatures only; BM25 surfaces adapters dynamically`. Adapter
        # tools (kma_*, hira_*, nmc_*, koroad_*, mohw_*, nfa_*) are
        # invoked via `lookup(tool_id="<adapter_id>", params={...})`,
        # never directly. The previous version of this block
        # (commit 5050417f) emitted every core_tool — primitive AND
        # adapter — into the tools[] parameter, which let K-EXAONE call
        # adapter ids directly (e.g. `kma_current_observation()` instead
        # of `lookup(tool_id="kma_current_observation", params=...)`).
        # The dispatcher then rejected the call with "Model requested
        # unknown tool 'kma_current_observation'" because PRIMITIVE_REGISTRY
        # only contains the five primitives. Captured live in
        # specs/integration-verification/donga-univ-poi-bug/
        # snap-001-01-kma-now (2026-05-04).
        #
        # Filtering by `ministry == "KOSMOS"` AND id in the primitive
        # whitelist matches the intent of mvp_surface.py — the five
        # GovAPITool entries with `primitive=` field set are exactly
        # the LLM-callable surface. Adapters (every other ministry) flow
        # through the `<available_adapters>` system-prompt suffix that
        # `_build_available_adapters_suffix` emits below.
        registry = cast("Any", _ensure_tool_registry())
        from kosmos.primitives import PRIMITIVE_REGISTRY  # noqa: PLC0415

        backend_tools_raw = [
            t.to_openai_tool()
            for t in registry.core_tools()
            if t.ministry == "KOSMOS" and t.id in PRIMITIVE_REGISTRY
        ]
        backend_tool_names: set[object] = set()
        for raw_tool in backend_tools_raw:
            if not isinstance(raw_tool, dict):
                continue
            function = raw_tool.get("function")
            if isinstance(function, dict):
                backend_tool_names.add(function.get("name"))
        llm_tools: list[LLMToolDefinition] = [
            LLMToolDefinition.model_validate(raw) for raw in backend_tools_raw
        ]
        for t in frame.tools:
            tui_name = getattr(getattr(t, "function", None), "name", None)
            if tui_name and tui_name in backend_tool_names:
                continue
            llm_tools.append(LLMToolDefinition.model_validate(t.model_dump()))

        # Build LLMClient input from the frame payload. Conversation history
        # lives in the TUI per ADR-0005 — backend receives the full slate.
        # Epic #2077 T010 (Step 3) — augment the system prompt with a
        # ``## Available tools`` section so K-EXAONE sees the same inventory
        # in BOTH the structured ``tools`` param AND the prose system message
        # (mirrors ``_cc_reference/api.ts:appendSystemContext``). Returns
        # ``base`` unchanged when ``llm_tools`` is empty (no inventory to
        # publish), so the no-tools path is byte-stable with the old code.
        # Epic #2152 R3 + R4 — when the TUI sends an empty ``frame.system``
        # (the new default after R5 dev-context excision), fall back to the
        # PromptLoader-resolved citizen system prompt. Append the boundary
        # marker so the prefix hash emitted by the LLM client is meaningful.
        from kosmos.ipc.citizen_request import (  # noqa: PLC0415
            wrap_citizen_request,
        )

        # G-class chain enforcement (2026-05-04) — top-level scope so the
        # follow-up-lookup gate inside the agentic loop can read the original
        # citizen utterance to decide whether the conversation must end with a
        # `lookup(mode='fetch', ...)` call (weather / hospital / accident /
        # 119 / welfare queries) before the LLM is allowed to produce a final
        # answer. Lifted out of the BM25 try-block so the variable survives
        # the suffix-builder failure path.
        latest_user_utt = ""

        base_system = frame.system
        if not base_system:
            loaded = await _ensure_system_prompt()
            base_system = loaded or ""
        augmented_system = build_system_prompt_with_tools(base_system, llm_tools)
        if augmented_system:
            augmented_system = augmented_system + _DYNAMIC_BOUNDARY_MARKER
            # KOSMOS hotfix #2520 (2026-04-30 user report — 날짜 hallucination):
            # CC 원본 (.references/claude-code-sourcemap/restored-src/src/constants/
            # prompts.ts:452) 은 system prompt 첫 paragraph 에 동적으로
            # `Date: ${getSessionStartDate()}` 를 inject. KOSMOS 는 prompts/
            # system_v1.md (static markdown) 만 사용해서 LLM 이 자기 추측으로 날짜
            # 답변 → "현재 날짜인 2026년 3월 5일 기준으로 부산 사하구의 날씨 정보"
            # 같은 hallucination. _DYNAMIC_BOUNDARY_MARKER 뒤는 prompt-cache의
            # dynamic-context section 이므로 여기에 today 주입해도 cache prefix
            #
            # KOSMOS hotfix (2026-05-04, KMA base_time hallucination 차단):
            # `오늘 날짜 (UTC)` 만 inject 하면 LLM 이 KMA `base_time` (KST HHMM)
            # 을 추측 (e.g. `0700`). KMA 단기예보/실황 발표 시각은 KST
            # 0200/0500/0800/1100/1400/1700/2000/2300 — 잘못된 base_time 은
            # 4-9 시간 시차의 fabrication 으로 이어짐. 시민 안전 directive 위반.
            # 따라서 KST 날짜 + KST 현재 시각 (HH:MM, HHMM) 둘 다 inject —
            # 도구 description 이 "직전 정시" 를 참조할 수 있도록.
            # invariant 유지. ISO 8601 date format (YYYY-MM-DD) 으로 표기.
            from datetime import datetime  # noqa: PLC0415
            from zoneinfo import ZoneInfo  # noqa: PLC0415

            _kst = ZoneInfo("Asia/Seoul")
            _now_kst = datetime.now(tz=_kst)
            today_kst_iso = _now_kst.strftime("%Y-%m-%d")
            now_kst_hm = _now_kst.strftime("%H:%M")
            now_kst_hhmm = _now_kst.strftime("%H%M")
            # KMA base_time 은 KST 정시 발표 (0200/0500/0800/1100/1400/
            # 1700/2000/2300). 현재 KST 시각의 직전 정시 hint 도 함께 emit
            # — LLM 이 추측하지 않도록.
            _valid_base_times = (2, 5, 8, 11, 14, 17, 20, 23)
            _h = _now_kst.hour
            _prev = max(
                (b for b in _valid_base_times if b <= _h),
                default=_valid_base_times[-1],
            )
            # 오늘 시각이 첫 발표(0200) 이전이면 어제 2300 사용
            if _h < _valid_base_times[0]:
                _kma_base_date = (_now_kst.replace(hour=23, minute=0)).strftime("%Y%m%d")
                _kma_base_time = "2300"
                _kma_hint_note = "어제"
            else:
                _kma_base_date = _now_kst.strftime("%Y%m%d")
                _kma_base_time = f"{_prev:02d}00"
                _kma_hint_note = "오늘"
            augmented_system = (
                augmented_system + f"\n\n## Current session context\n\n"
                f"오늘 날짜 (KST): {today_kst_iso}.\n"
                f"현재 시각 (KST): {now_kst_hm} ({now_kst_hhmm}).\n"
                "이 날짜/시각을 기준으로 시간 표현을 해석합니다. "
                "날짜/시간 정보를 추측 또는 fabricate 하지 말고, "
                "필요하면 도구 (예: kma_short_term_forecast) 를 호출해서 "
                "실제 데이터를 받아 응답에 인용합니다.\n"
                "KMA 단기예보/실황 발표 시각은 KST 정시 8회: "
                "0200/0500/0800/1100/1400/1700/2000/2300. "
                f"현재 KST 시각의 직전 발표는 {_kma_hint_note} "
                f"base_date={_kma_base_date}, base_time={_kma_base_time}. "
                "base_time 추측 금지 — 위 hint 또는 그 이전 정시 사용.\n"
            )

            # Spec 2521 (2026-05-01) — BM25 adapter discovery is a backend
            # function, NOT an LLM-callable tool. Run the search against the
            # latest citizen utterance and inject the top-K candidates into
            # the dynamic suffix as ``<available_adapters>``. The LLM picks
            # a tool_id from this block and calls ``lookup({tool_id, params})``
            # — search-mode calls were the source of the "● lookup(search:)"
            # phantom tool-UI noise that user surfaced via Layer 5 frame
            # capture (specs/2521 frames/raw.cast frame_0160 onwards).
            try:
                for m in reversed(frame.messages):
                    if m.role == "user" and m.content:
                        latest_user_utt = m.content
                        break
                # spec-multi-turn-contamination diagnostic emit — log the
                # extracted latest user utterance BEFORE the BM25 suffix
                # builder runs. If this string disagrees with the wire-level
                # tail in [CHAT_REQUEST_DUMP] above, the bug is in the
                # extraction loop; if both agree but the model reasons over
                # an older turn, the bug is in K-EXAONE / Hermes (H2/H3).
                if _diag_chat_request_enabled():
                    logger.info(
                        "[LATEST_USER_UTT] turn=%d utt_first256=%s",
                        _diag_turn_idx,
                        (latest_user_utt or "")[:256],
                    )
                if latest_user_utt:
                    suffix_block = _build_available_adapters_suffix(latest_user_utt)
                    if suffix_block:
                        augmented_system = augmented_system + "\n\n" + suffix_block + "\n"
                    policy_plan_block = _build_policy_plan_suffix(latest_user_utt)
                    if policy_plan_block:
                        augmented_system = augmented_system + "\n\n" + policy_plan_block + "\n"
            except Exception:  # noqa: BLE001 — fail-open per FR-002
                logger.exception(
                    "available_adapters auto-inject failed — continuing without suffix"
                )
        llm_messages: list[LLMChatMessage] = []
        if augmented_system:
            llm_messages.append(LLMChatMessage(role="system", content=augmented_system))
        for m in frame.messages:
            # Epic #2152 R3 — wrap citizen utterances in <citizen_request>
            # XML tags so prompt-injection-shaped pastes cannot escalate into
            # instructions (contract chat-request-envelope.md I-C3, I-C4, I-C6).
            content = m.content
            if m.role == "user" and content:
                content = wrap_citizen_request(content)
            # Lead-Diag-4 (2026-05-04, role='tool' wire conversion) — forward
            # the wire-side ``tool_calls`` array (assistant turns that
            # requested one or more tool invocations) into the LLMClient
            # message so the OpenAI multi-turn pairing invariant survives the
            # round-trip. Backward compat: ``m.tool_calls`` is ``None`` for
            # legacy senders that pre-date the wire-format extension, in
            # which case we omit the field entirely (LLMChatMessage default
            # is ``None``).
            llm_tool_calls: list[LLMToolCall] | None = None
            if m.tool_calls:
                llm_tool_calls = [
                    LLMToolCall(
                        id=tc.id,
                        type=tc.type,
                        function=LLMFunctionCall(
                            name=tc.function.name,
                            arguments=tc.function.arguments,
                        ),
                    )
                    for tc in m.tool_calls
                ]
            llm_messages.append(
                LLMChatMessage(
                    role=m.role,
                    content=content,
                    name=m.name,
                    tool_call_id=m.tool_call_id,
                    tool_calls=llm_tool_calls,
                )
            )

        client = await _ensure_llm_client()

        # ---- CC query-engine agentic loop ---------------------------------
        import json as _json  # noqa: PLC0415

        # Epic #2152 follow-up — citizen-facing stream gate. K-EXAONE may
        # interleave a textual ``<tool_call>{...}</tool_call>`` marker with
        # the natural-language reply even when the structured ``tool_calls``
        # field is also populated, so the marker leaks into the streamed
        # AssistantChunkFrame content unless filtered. The gate strips those
        # blocks character-accurately while ``assistant_text_chunks`` still
        # accumulates the *full raw stream* — the post-stream
        # ``extract_textual_tool_calls`` fallback (below) needs the markers
        # to synthesise tool_call_buf entries when the structured form is
        # absent.
        from kosmos.llm.tool_call_parser import StreamGate  # noqa: PLC0415

        # Neurosymbolic constraint flag — set when the chain-prerequisite
        # gate rejected a coord-input tool call earlier in the loop. The
        # next LLM turn forces tool_choice=resolve_location, removing the
        # bypass path the LLM used in donga-univ-poi-bug captures
        # (the LLM read the chain hint and then refused the tool anyway,
        # answering "I don't have a location resolver" — a documented
        # failure mode in the 2026 hallucination literature: business
        # rules in prompts are interpreted as suggestions, not constraints,
        # so the constraint must move to the API layer where the model
        # cannot bypass it). Once a turn fires resolve_location the flag
        # clears so the agentic loop returns to free tool_choice.
        force_resolve_location_next_turn = False
        force_verify_next_turn = False
        force_followup_primitive_next_turn: str | None = None

        # Audit G4 / F-beta-03 dedup guard.
        #
        # Track (tool_id, params_hash) → outcome across the agentic loop. When
        # the LLM re-issues the same call after a prior NO_DATA / empty / error
        # outcome we short-circuit with a synthetic tool_result that explains
        # the redundancy in the LLM's own context. β7 evidence (2026-05-05)
        # showed `mohw_welfare_eligibility_search` called 5x with identical
        # params after each returned NO_DATA, hanging the turn at
        # `Ruminating…`. This is a KOSMOS-specific addition (CC's query engine
        # has no content-hash dedup); it sits at the dispatch layer below the
        # IPC envelope so wire-level CC parity is preserved.
        # See research/g4-backend.md § 4.
        _seen_calls: dict[str, str] = {}  # hash → outcome ('no_data' | 'error' | 'ok')

        def _hash_call(tool_id: str, params: dict[str, object]) -> str:
            # Wave-4 G11 / F-beta-03 — param normalization before hashing.
            # K-EXAONE varies whitespace in string values, emits whole-number
            # floats (1.0 instead of 1), and varies pagination fields across
            # retries. All produce different hashes for semantically identical
            # calls, circumventing the dedup gate. Normalize before hashing:
            #   1. Strip high-cardinality pagination keys (page_no / num_of_rows /
            #      order_by / pageNo / numOfRows) — paginating the same query is
            #      the same semantic call; a prior NO_DATA on page 1 means page 2
            #      will also be empty for that query scope.
            #   2. Collapse internal whitespace in string values.
            #   3. Coerce whole-number floats to int (1.0 → 1).
            import hashlib as _hashlib  # noqa: PLC0415
            import json as _json_dedup  # noqa: PLC0415

            _pagination_keys: frozenset[str] = frozenset(
                {"page_no", "num_of_rows", "order_by", "pageNo", "numOfRows", "pageSize"}
            )
            _auth_context_keys: frozenset[str] = frozenset(
                {"delegation_context", "session_id", "identity_assertion"}
            )
            _ignored_keys = _pagination_keys | _auth_context_keys

            def _norm_val(v: object) -> object:
                if isinstance(v, str):
                    return " ".join(v.split())  # collapse internal whitespace
                if isinstance(v, float) and v == int(v):
                    return int(v)  # 1.0 → 1
                if isinstance(v, dict):
                    return {
                        str(k): _norm_val(value)
                        for k, value in v.items()
                        if str(k) not in _ignored_keys
                    }
                if isinstance(v, list):
                    return [_norm_val(item) for item in v]
                return v

            normalized = {k: _norm_val(v) for k, v in params.items() if k not in _ignored_keys}
            try:
                canonical = _json_dedup.dumps(
                    normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                )
            except (TypeError, ValueError):
                canonical = repr(normalized)
            logger.debug(
                "DEDUP key=%s tool_id=%s params_canonical=%s",
                _hashlib.sha256(f"{tool_id}|{canonical}".encode()).hexdigest()[:16],
                tool_id,
                canonical[:120],
            )
            return _hashlib.sha256(f"{tool_id}|{canonical}".encode()).hexdigest()[:16]

        _issued_submit_signatures: set[str] = set()
        _issued_singleton_submit_tool_ids: set[str] = set()
        _SINGLETON_SUBMIT_TOOL_IDS = frozenset({"mock_traffic_fine_pay_v1"})  # noqa: N806

        def _submit_semantic_signature(args_obj: dict[str, object]) -> str | None:
            """Return a write-side duplicate signature, ignoring backend auth fields."""
            tool_id = args_obj.get("tool_id")
            if not isinstance(tool_id, str) or not tool_id:
                return None
            params_obj = args_obj.get("params")
            params = dict(params_obj) if isinstance(params_obj, dict) else {}
            if tool_id == "mock_traffic_fine_pay_v1":
                semantic = {
                    key: params.get(key)
                    for key in ("fine_reference", "payment_method", "action_type")
                    if key in params
                }
            elif tool_id == "mock_submit_module_gov24_minwon":
                semantic = {
                    key: params.get(key)
                    for key in ("minwon_type", "delivery_method", "target_institution_code")
                    if key in params
                }
            elif tool_id == "mock_submit_module_hometax_taxreturn":
                semantic = {
                    key: params.get(key)
                    for key in ("tax_year", "income_type", "action_type")
                    if key in params
                }
            else:
                semantic = params
            return _hash_call(tool_id, {"params": semantic})

        def _classify_envelope_outcome(env: dict[str, object]) -> str:  # noqa: C901
            """Classify a tool result envelope outcome for the dedup guard.

            Returns one of 'no_data' | 'error' | 'ok'.
            """
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
            if kind == "search":
                cands = env.get("candidates")
                if isinstance(cands, list) and len(cands) == 0:
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
            if kind == "timeseries":
                points = env.get("points")
                if isinstance(points, list) and len(points) == 0:
                    return "no_data"
                return "ok"
            return "ok"

        for _turn in range(_AGENTIC_LOOP_MAX_TURNS):
            message_id = str(uuid.uuid4())
            assistant_text_chunks: list[str] = []
            # Epic #2766 issue B — render-order fix. K-EXAONE emits the
            # assistant's prose preamble ("내과 병원을 검색해 보겠습니다.")
            # BEFORE the structured ``tool_call_delta`` events arrive in the
            # SAME turn. If we forward those prose chunks immediately, the
            # citizen sees ``assistant text → tool_call → result``, the
            # opposite of CC's canonical ``tool_call → result → assistant
            # text`` order. The fix: buffer prose chunks for this turn; emit
            # them as a single AssistantChunkFrame ONLY after we know whether
            # this turn invoked tools. When tools are invoked we suppress the
            # preamble entirely — the next turn produces the real answer
            # after the tool result is appended to context. When no tools
            # are invoked we flush the buffer as a single chunk so the prose
            # still reaches the citizen.
            buffered_visible: list[str] = []
            tool_call_buf: dict[int, dict[str, str]] = {}
            stream_error: Exception | None = None
            stream_gate = StreamGate()

            # spec-multi-turn-contamination diagnostic — accumulate the K-EXAONE
            # reasoning_content stream so we can compare its first 1024 bytes
            # against [LATEST_USER_UTT]. If reasoning starts with text that
            # paraphrases an earlier turn, H2 (model-side state contamination)
            # is confirmed even when the wire-level messages are correct.
            # Off by default; gated by KOSMOS_CHAT_REQUEST_DUMP=1.
            _diag_reasoning_buf: list[str] = []
            _diag_reasoning_emitted = False

            # Materialise the tool_choice for this turn from the gate flag.
            # When forced, OpenAI/FriendliAI accept the explicit-function
            # form (verified live against FriendliAI Serverless 2026-05-04);
            # K-EXAONE on FriendliAI honours it as a hard constraint at the
            # decoding boundary rather than a system-prompt hint.
            stream_tool_choice: str | dict[str, object] | None = None
            if _retrieval_prefers_initial_resolve_location(
                latest_user_utt
            ) and not _conversation_has_successful_primitive(
                llm_messages,
                "resolve_location",
            ):
                stream_tool_choice = {
                    "type": "function",
                    "function": {"name": "resolve_location"},
                }
                logger.warning(
                    "_handle_chat_request: forcing tool_choice=resolve_location "
                    "for turn %d (registry policy requires location anchor first)",
                    _turn,
                )
            elif force_verify_next_turn or (
                _retrieval_requires_initial_verify(latest_user_utt)
                and not _conversation_has_verify(llm_messages)
            ):
                stream_tool_choice = {
                    "type": "function",
                    "function": {"name": "verify"},
                }
                logger.warning(
                    "_handle_chat_request: forcing tool_choice=verify for "
                    "turn %d (registry policy requires DelegationContext)",
                    _turn,
                )
            elif force_resolve_location_next_turn:
                stream_tool_choice = {
                    "type": "function",
                    "function": {"name": "resolve_location"},
                }
                logger.warning(
                    "_handle_chat_request: forcing tool_choice=resolve_location for "
                    "turn %d (chain gate previously rejected a coord-input call)",
                    _turn,
                )
            elif force_followup_primitive_next_turn in {"lookup", "submit", "subscribe"}:
                stream_tool_choice = {
                    "type": "function",
                    "function": {"name": force_followup_primitive_next_turn},
                }
                logger.warning(
                    "_handle_chat_request: forcing tool_choice=%s for turn %d "
                    "(privileged chain gate rejected an early final answer)",
                    force_followup_primitive_next_turn,
                    _turn,
                )
            pre_synthesised_forced_tool = False
            forced_tool_name = _forced_tool_choice_name(stream_tool_choice)
            if forced_tool_name is not None:
                forced_args: dict[str, object] | None = None
                if forced_tool_name == "verify":
                    forced_args = _build_policy_forced_verify_args(
                        latest_user_utt,
                        _ensure_tool_registry(),
                    )
                elif forced_tool_name == "resolve_location":
                    forced_args = _build_forced_resolve_location_args(latest_user_utt)
                elif forced_tool_name == "lookup":
                    forced_args = _build_forced_lookup_args(
                        latest_user_utt,
                        llm_messages,
                        _ensure_tool_registry(),
                    )
                elif forced_tool_name == "submit":
                    forced_args = _build_forced_submit_args(
                        latest_user_utt,
                        llm_messages,
                        _ensure_tool_registry(),
                    )
                elif forced_tool_name == "subscribe":
                    forced_args = _build_forced_subscribe_args(
                        latest_user_utt,
                        _ensure_tool_registry(),
                    )
                if forced_args is not None:
                    tool_call_buf[0] = {
                        "id": str(uuid.uuid4()),
                        "name": forced_tool_name,
                        "args": _json.dumps(forced_args, ensure_ascii=False),
                    }
                    buffered_visible.clear()
                    pre_synthesised_forced_tool = True
                    logger.warning(
                        "_handle_chat_request: pre-synthesised %s tool_call "
                        "from harness-owned forced tool_choice",
                        forced_tool_name,
                    )
                elif forced_tool_name in {"lookup", "submit", "subscribe"}:
                    logger.warning(
                        "_handle_chat_request: clearing forced tool_choice=%s "
                        "because no schema-safe forced args could be derived",
                        forced_tool_name,
                    )
                    stream_tool_choice = None
                    force_followup_primitive_next_turn = None
                    forced_tool_name = None
            try:

                async def _empty_forced_stream() -> Any:
                    if False:
                        yield None

                stream_events = (
                    _empty_forced_stream()
                    if pre_synthesised_forced_tool
                    else client.stream(  # type: ignore[attr-defined]
                        messages=llm_messages,
                        tools=llm_tools or None,
                        temperature=frame.temperature,
                        top_p=frame.top_p,
                        max_tokens=frame.max_tokens,
                        tool_choice=stream_tool_choice,
                    )
                )
                async for event in stream_events:
                    event_type = getattr(event, "type", None)
                    if event_type == "content_delta":
                        delta = getattr(event, "content", "") or ""
                        if delta:
                            assistant_text_chunks.append(delta)
                            visible = stream_gate.feed(delta)
                            if visible:
                                buffered_visible.append(visible)
                    elif event_type == "thinking_delta":
                        # K-EXAONE chain-of-thought channel — mirrors CC's
                        # Anthropic ``thinking_delta`` content_block_delta
                        # (``kosmos/llm/_cc_reference/claude.ts:2148-2161``).
                        # Forward as an AssistantChunkFrame on the
                        # ``thinking`` channel; the TUI's deps.ts projects
                        # this to a ``stream_event{thinking_delta}`` and
                        # ``handleMessageFromStream`` routes it via
                        # ``onUpdateLength`` into ``streamingThinking`` so
                        # ``AssistantThinkingMessage`` paints the reasoning
                        # inline. CoT is *not* appended to
                        # ``assistant_text_chunks`` — the inline-tool-call
                        # XML parser only inspects the visible answer
                        # channel, and we never persist reasoning back to
                        # the LLM context.
                        thinking_text = getattr(event, "thinking", "") or ""
                        if thinking_text:
                            # spec-multi-turn-contamination diagnostic —
                            # accumulate reasoning until 1024 bytes, then
                            # emit once per turn. Bounded buffer (cap at 4096
                            # so a runaway CoT can't eat memory).
                            if (
                                _diag_chat_request_enabled()
                                and not _diag_reasoning_emitted
                                and sum(len(s) for s in _diag_reasoning_buf) < 4096
                            ):
                                _diag_reasoning_buf.append(thinking_text)
                                _running_len = sum(len(s) for s in _diag_reasoning_buf)
                                if _running_len >= 1024:
                                    _preview = "".join(_diag_reasoning_buf)[:1024]
                                    logger.info(
                                        "[REASONING_PREVIEW] turn=%d first1024=%s",
                                        _diag_turn_idx,
                                        _preview,
                                    )
                                    _diag_reasoning_emitted = True
                            await write_frame(
                                AssistantChunkFrame(
                                    session_id=frame.session_id,
                                    correlation_id=frame.correlation_id,
                                    role="llm",
                                    ts=_utcnow(),
                                    kind="assistant_chunk",
                                    message_id=message_id,
                                    delta="",
                                    thinking=thinking_text,
                                    done=False,
                                )
                            )
                    elif event_type == "tool_call_delta":
                        idx = int(getattr(event, "tool_call_index", 0) or 0)
                        slot = tool_call_buf.setdefault(idx, {"id": "", "name": "", "args": ""})
                        cid = getattr(event, "tool_call_id", None)
                        if cid:
                            slot["id"] = cid
                        fname = getattr(event, "function_name", None)
                        if fname:
                            slot["name"] = fname
                        fargs = getattr(event, "function_args_delta", None)
                        if fargs:
                            slot["args"] += fargs
                    elif event_type == "done":
                        # spec-multi-turn-contamination diagnostic — flush a
                        # short reasoning buffer (<1024 bytes) on stream
                        # completion so the [REASONING_PREVIEW] line is
                        # emitted exactly once per turn even when the model
                        # produced little CoT.
                        if (
                            _diag_chat_request_enabled()
                            and not _diag_reasoning_emitted
                            and _diag_reasoning_buf
                        ):
                            _preview = "".join(_diag_reasoning_buf)[:1024]
                            logger.info(
                                "[REASONING_PREVIEW] turn=%d first1024=%s",
                                _diag_turn_idx,
                                _preview,
                            )
                            _diag_reasoning_emitted = True
                        break
                    elif event_type == "error":
                        stream_error = RuntimeError(
                            str(getattr(event, "content", "unknown stream error"))
                        )
                        break
            except Exception as exc:  # noqa: BLE001
                stream_error = exc

            # Drain any pending bytes the stream gate held back at stream end.
            # ``flush()`` returns the safe trailing window (i.e. bytes that
            # were too short to disambiguate during streaming but are now
            # known not to be the start of a ``<tool_call>`` marker).
            tail = stream_gate.flush()
            if tail:
                buffered_visible.append(tail)

            if stream_error is not None:
                # Schema constraint: ErrorFrame.role ∈ {'backend','tui'} —
                # 'llm' was rejected by Pydantic validation. Backend is the
                # correct sender role since this frame originates from the
                # backend's own LLM-stream error handler.
                await write_frame(
                    ErrorFrame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id or str(uuid.uuid4()),
                        role="backend",
                        ts=_utcnow(),
                        kind="error",
                        code="llm_stream_error",
                        message=str(stream_error),
                        details={"message_id": message_id},
                    )
                )
                return

            # Epic #2152 follow-up — K-EXAONE on FriendliAI sometimes emits
            # its tool-call intent as a textual ``<tool_call>{...}</tool_call>``
            # marker inside the assistant content rather than the OpenAI
            # ``tool_calls`` field. Extract any such markers from the
            # accumulated turn text and synthesise ``tool_call_buf`` entries so
            # the existing dispatch path picks them up as if the model had used
            # the structured form. The cleaned text (markers stripped) is what
            # we record into the assistant history for the next turn.
            assistant_text_full = "".join(assistant_text_chunks)
            cleaned_text = assistant_text_full
            if not tool_call_buf and "<tool_call>" in assistant_text_full:
                from kosmos.llm.tool_call_parser import (  # noqa: PLC0415
                    extract_textual_tool_calls,
                )

                parsed_calls, cleaned_text = extract_textual_tool_calls(assistant_text_full)
                for synth_idx, parsed in enumerate(parsed_calls):
                    tool_call_buf[synth_idx] = {
                        "id": str(uuid.uuid4()),
                        "name": parsed.name,
                        "args": _json.dumps(parsed.arguments, ensure_ascii=False),
                    }
                if parsed_calls:
                    logger.info(
                        "_handle_chat_request: synthesised %d tool_call(s) from "
                        "K-EXAONE textual <tool_call> markers (Epic #2152 follow-up)",
                        len(parsed_calls),
                    )

            # Provider-boundary recovery (2026-05-05): when KOSMOS forces
            # ``tool_choice=verify`` from registry policy, an empty/no-tool
            # stream is not a valid terminal turn. Synthesize the same verify
            # call the model was required to emit, using registry-derived
            # delegation metadata, then let the normal permission + dispatch
            # pipeline render the real ToolCallFrame/ToolResultFrame. This
            # mirrors CC's API-layer constraint boundary: prompt guidance is
            # advisory, but the harness owns the tool loop invariants.
            if not tool_call_buf:
                forced_tool_name = _forced_tool_choice_name(stream_tool_choice)
                if forced_tool_name == "verify":
                    forced_verify_args = _build_policy_forced_verify_args(
                        latest_user_utt,
                        _ensure_tool_registry(),
                    )
                    if forced_verify_args is not None:
                        tool_call_buf[0] = {
                            "id": str(uuid.uuid4()),
                            "name": "verify",
                            "args": _json.dumps(forced_verify_args, ensure_ascii=False),
                        }
                        cleaned_text = ""
                        buffered_visible.clear()
                        logger.warning(
                            "_handle_chat_request: synthesised verify tool_call "
                            "after provider returned no tool_call under explicit "
                            "tool_choice=verify"
                        )
                elif forced_tool_name == "submit":
                    forced_submit_args = _build_forced_submit_args(
                        latest_user_utt,
                        llm_messages,
                        _ensure_tool_registry(),
                    )
                    if forced_submit_args is not None:
                        tool_call_buf[0] = {
                            "id": str(uuid.uuid4()),
                            "name": "submit",
                            "args": _json.dumps(forced_submit_args, ensure_ascii=False),
                        }
                        cleaned_text = ""
                        buffered_visible.clear()
                        logger.warning(
                            "_handle_chat_request: synthesised submit tool_call "
                            "after provider returned no tool_call under explicit "
                            "tool_choice=submit"
                        )
                elif forced_tool_name == "resolve_location":
                    forced_resolve_args = _build_forced_resolve_location_args(latest_user_utt)
                    tool_call_buf[0] = {
                        "id": str(uuid.uuid4()),
                        "name": "resolve_location",
                        "args": _json.dumps(forced_resolve_args, ensure_ascii=False),
                    }
                    cleaned_text = ""
                    buffered_visible.clear()
                    logger.warning(
                        "_handle_chat_request: synthesised resolve_location tool_call "
                        "after provider returned no tool_call under explicit "
                        "tool_choice=resolve_location"
                    )
                elif forced_tool_name == "lookup":
                    forced_lookup_args = _build_forced_lookup_args(
                        latest_user_utt,
                        llm_messages,
                        _ensure_tool_registry(),
                    )
                    if forced_lookup_args is not None:
                        tool_call_buf[0] = {
                            "id": str(uuid.uuid4()),
                            "name": "lookup",
                            "args": _json.dumps(forced_lookup_args, ensure_ascii=False),
                        }
                        cleaned_text = ""
                        buffered_visible.clear()
                        logger.warning(
                            "_handle_chat_request: synthesised lookup tool_call "
                            "after provider returned no tool_call under explicit "
                            "tool_choice=lookup"
                        )
                elif forced_tool_name == "subscribe":
                    forced_subscribe_args = _build_forced_subscribe_args(
                        latest_user_utt,
                        _ensure_tool_registry(),
                    )
                    if forced_subscribe_args is not None:
                        tool_call_buf[0] = {
                            "id": str(uuid.uuid4()),
                            "name": "subscribe",
                            "args": _json.dumps(forced_subscribe_args, ensure_ascii=False),
                        }
                        cleaned_text = ""
                        buffered_visible.clear()
                        logger.warning(
                            "_handle_chat_request: synthesised subscribe tool_call "
                            "after provider returned no tool_call under explicit "
                            "tool_choice=subscribe"
                        )

            # Epic #2766 issue B — render-order fix flush.
            # No tool calls this turn → emit the FULL buffered prose as a
            # single chunk (or empty) before the terminal done=True frame.
            # The TUI's StreamingMarkdown accumulates `delta` over the
            # message_id, so emitting the full text in one chunk yields the
            # same visible result as the per-chunk streaming would have —
            # only the perceived latency changes (full text appears at
            # end-of-turn rather than typewriter-streamed). This is the
            # cost of the ordering guarantee: until end-of-stream we cannot
            # know whether a tool_call follows in this turn.
            if not tool_call_buf:
                # ---- G-class fabrication gate (2026-05-04) ---------------
                # Before emitting a final-answer turn, check whether the
                # conversation invoked resolve_location but never followed up
                # with a coord/admcd-input lookup despite registry retrieval
                # selecting a location-parameterized data adapter. The
                # donga-univ-poi-bug snap-001-01-kma-now
                # capture (2026-05-04) showed K-EXAONE producing 16°C / 84%
                # humidity by parametric memory — 4.7°C / 61%p drift versus
                # the raw KMA observation — because the agentic loop allowed
                # the answer turn to fire without a tool result in scope.
                # Inject a synthetic chain-recovery tool_result and continue
                # the loop so the next turn produces the missing lookup call.
                chain_followup_msg = _check_resolve_terminated_without_followup(
                    llm_messages,
                    latest_user_utt,
                    registry=_ensure_tool_registry(),
                )
                if chain_followup_msg is not None:
                    synth_call_id = str(uuid.uuid4())
                    # Synthesise an assistant turn that appears to have
                    # called a sentinel "chain_gate" — keeps the message
                    # ordering invariant (assistant tool_calls precede the
                    # role='tool' content). The model will not see this
                    # call_id again — only the role='tool' content matters.
                    llm_messages.append(
                        LLMChatMessage(
                            role="assistant",
                            content="",
                            tool_calls=[
                                LLMToolCall(
                                    id=synth_call_id,
                                    type="function",
                                    function=LLMFunctionCall(
                                        name="lookup",
                                        arguments=_json.dumps(
                                            {
                                                "mode": "fetch",
                                                "tool_id": "<chain-gate-pending>",
                                                "params": {},
                                            }
                                        ),
                                    ),
                                )
                            ],
                        )
                    )
                    llm_messages.append(
                        LLMChatMessage(
                            role="tool",
                            content=_json.dumps(
                                {
                                    "kind": "error",
                                    "reason": "chain_followup_missing",
                                    "message": chain_followup_msg,
                                },
                                ensure_ascii=False,
                            ),
                            name="lookup",
                            tool_call_id=synth_call_id,
                        )
                    )
                    logger.warning(
                        "_handle_chat_request: rejected final-answer turn — "
                        "resolve_location ran but follow-up lookup was never "
                        "invoked despite citizen query implying it. "
                        "Re-entering loop with chain-recovery hint."
                    )
                    # Drop the buffered prose so the citizen never sees the
                    # fabrication that the LLM was about to emit.
                    buffered_visible.clear()
                    continue

                privileged_followup = _check_privileged_chain_terminated_early(
                    llm_messages,
                    latest_user_utt,
                    registry=_ensure_tool_registry(),
                )
                if privileged_followup is not None:
                    next_primitive, followup_msg = privileged_followup
                    synth_call_id = str(uuid.uuid4())
                    llm_messages.append(
                        LLMChatMessage(
                            role="assistant",
                            content="",
                            tool_calls=[
                                LLMToolCall(
                                    id=synth_call_id,
                                    type="function",
                                    function=LLMFunctionCall(
                                        name=next_primitive,
                                        arguments=_json.dumps(
                                            {
                                                "tool_id": "<privileged-chain-gate>",
                                                "params": {},
                                            }
                                        ),
                                    ),
                                )
                            ],
                        )
                    )
                    llm_messages.append(
                        LLMChatMessage(
                            role="tool",
                            content=_json.dumps(
                                {
                                    "kind": "error",
                                    "reason": "privileged_chain_followup_missing",
                                    "message": followup_msg,
                                },
                                ensure_ascii=False,
                            ),
                            name=next_primitive,
                            tool_call_id=synth_call_id,
                        )
                    )
                    logger.warning(
                        "_handle_chat_request: rejected final-answer turn — "
                        "privileged chain follow-up %s was missing after verify",
                        next_primitive,
                    )
                    buffered_visible.clear()
                    force_followup_primitive_next_turn = next_primitive
                    continue

                public_subscribe_followup = _check_public_subscribe_terminated_early(
                    llm_messages,
                    latest_user_utt,
                    registry=_ensure_tool_registry(),
                )
                if public_subscribe_followup is not None:
                    next_primitive, followup_msg = public_subscribe_followup
                    synth_call_id = str(uuid.uuid4())
                    llm_messages.append(
                        LLMChatMessage(
                            role="assistant",
                            content="",
                            tool_calls=[
                                LLMToolCall(
                                    id=synth_call_id,
                                    type="function",
                                    function=LLMFunctionCall(
                                        name=next_primitive,
                                        arguments=_json.dumps(
                                            {
                                                "tool_id": "<public-subscribe-chain-gate>",
                                                "params": {},
                                            }
                                        ),
                                    ),
                                )
                            ],
                        )
                    )
                    llm_messages.append(
                        LLMChatMessage(
                            role="tool",
                            content=_json.dumps(
                                {
                                    "kind": "error",
                                    "reason": "public_subscribe_followup_missing",
                                    "message": followup_msg,
                                },
                                ensure_ascii=False,
                            ),
                            name=next_primitive,
                            tool_call_id=synth_call_id,
                        )
                    )
                    logger.warning(
                        "_handle_chat_request: rejected final-answer turn — "
                        "public subscribe follow-up was missing after lookup"
                    )
                    buffered_visible.clear()
                    force_followup_primitive_next_turn = next_primitive
                    continue

                merged_prose = "".join(buffered_visible)
                if not merged_prose.strip():
                    completion_answer = _build_tool_result_completion_answer(llm_messages)
                    if completion_answer is not None:
                        await write_frame(
                            AssistantChunkFrame(
                                session_id=frame.session_id,
                                correlation_id=frame.correlation_id,
                                role="llm",
                                ts=_utcnow(),
                                kind="assistant_chunk",
                                message_id=message_id,
                                delta=completion_answer,
                                done=True,
                            )
                        )
                        logger.warning(
                            "_handle_chat_request: replaced empty final answer "
                            "with deterministic tool-result completion summary"
                        )
                        return
                if merged_prose:
                    grounding_msg = _check_final_answer_grounding(merged_prose, llm_messages)
                    if grounding_msg is not None:
                        grounded_answer = _build_grounded_safety_answer(llm_messages)
                        if grounded_answer is not None:
                            await write_frame(
                                AssistantChunkFrame(
                                    session_id=frame.session_id,
                                    correlation_id=frame.correlation_id,
                                    role="llm",
                                    ts=_utcnow(),
                                    kind="assistant_chunk",
                                    message_id=message_id,
                                    delta=grounded_answer,
                                    done=True,
                                )
                            )
                            logger.warning(
                                "_handle_chat_request: replaced unsupported final answer "
                                "with deterministic payload-only safety answer"
                            )
                            return
                        synth_call_id = str(uuid.uuid4())
                        llm_messages.append(
                            LLMChatMessage(
                                role="assistant",
                                content="",
                                tool_calls=[
                                    LLMToolCall(
                                        id=synth_call_id,
                                        type="function",
                                        function=LLMFunctionCall(
                                            name="lookup",
                                            arguments=_json.dumps(
                                                {
                                                    "mode": "fetch",
                                                    "tool_id": "<grounding-gate>",
                                                    "params": {},
                                                }
                                            ),
                                        ),
                                    )
                                ],
                            )
                        )
                        llm_messages.append(
                            LLMChatMessage(
                                role="tool",
                                content=_json.dumps(
                                    {
                                        "kind": "error",
                                        "reason": "final_answer_grounding_violation",
                                        "message": grounding_msg,
                                    },
                                    ensure_ascii=False,
                                ),
                                name="lookup",
                                tool_call_id=synth_call_id,
                            )
                        )
                        logger.warning(
                            "_handle_chat_request: rejected final-answer turn — "
                            "unsupported groundedness claim detected"
                        )
                        buffered_visible.clear()
                        continue
                    await write_frame(
                        AssistantChunkFrame(
                            session_id=frame.session_id,
                            correlation_id=frame.correlation_id,
                            role="llm",
                            ts=_utcnow(),
                            kind="assistant_chunk",
                            message_id=message_id,
                            delta=merged_prose,
                            done=False,
                        )
                    )
                await write_frame(
                    AssistantChunkFrame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id,
                        role="llm",
                        ts=_utcnow(),
                        kind="assistant_chunk",
                        message_id=message_id,
                        delta="",
                        done=True,
                    )
                )
                return
            # Tool calls present → suppress the prose preamble entirely.
            # The next agentic-loop turn will produce the real answer after
            # appending tool_result to context. CC-style ordering preserved:
            # `tool_call → tool_result → final assistant prose`.
            buffered_visible.clear()

            # ---- T027/T029 — emit tool_call frames + register Futures -----
            loop = asyncio.get_event_loop()
            issued_calls: list[tuple[str, str]] = []  # (call_id, name)
            # Audit G4 / F-beta-03 — call_id → dedup_key mirror so the result
            # loop can update _seen_calls with the actual outcome.
            issued_dedup_keys: dict[str, str] = {}
            assistant_tool_calls: list[LLMToolCall] = []
            internal_recovery_inserted = False
            tool_call_indices = sorted(tool_call_buf.keys())
            if len(tool_call_indices) > 1:
                selected_idx = tool_call_indices[0]
                dropped = tool_call_indices[1:]
                logger.warning(
                    "_handle_chat_request: received %d tool calls in one LLM turn; "
                    "dispatching index %s only and dropping indices %s to enforce "
                    "one observed tool result per turn",
                    len(tool_call_indices),
                    selected_idx,
                    dropped,
                )
                tool_call_indices = [selected_idx]
            for idx in tool_call_indices:
                slot = tool_call_buf[idx]
                call_id = slot["id"] or str(uuid.uuid4())
                malformed_json_args = False
                try:
                    args_obj = _json.loads(slot["args"]) if slot["args"] else {}
                except _json.JSONDecodeError:
                    malformed_json_args = True
                    args_obj = {"_raw": slot["args"]}
                if not isinstance(args_obj, dict):
                    args_obj = {"_value": args_obj}

                fname = slot["name"]
                # Epic #2077 FR-003 — registry-derived whitelist. spec.md
                # § Out of Scope (Permanent) forbids hardcoded enumerations
                # outside the registry; ``PRIMITIVE_REGISTRY`` is the single
                # source of truth for LLM-visible primitive names.
                from kosmos.primitives import PRIMITIVE_REGISTRY  # noqa: PLC0415

                if fname not in PRIMITIVE_REGISTRY:
                    await write_frame(
                        ErrorFrame(
                            session_id=frame.session_id,
                            correlation_id=frame.correlation_id or str(uuid.uuid4()),
                            role="backend",
                            ts=_utcnow(),
                            kind="error",
                            code="unknown_tool",
                            message=f"Model requested unknown tool {fname!r}",
                            details={"call_id": call_id},
                        )
                    )
                    continue

                if malformed_json_args:
                    recovery_args: dict[str, object] = {
                        "_malformed_json": True,
                        "raw_length": len(str(slot["args"] or "")),
                    }
                    recovery_msg = (
                        f"Malformed JSON arguments were emitted for {fname}. "
                        "Retry the same primitive with a valid JSON object using "
                        "the registry-selected adapter tool_id. Reuse already "
                        "verified DelegationContext from the prior verify result; "
                        "do not ask the citizen for session IDs or identity digits."
                    )
                    llm_messages.append(
                        LLMChatMessage(
                            role="assistant",
                            content="",
                            tool_calls=[
                                LLMToolCall(
                                    id=call_id,
                                    type="function",
                                    function=LLMFunctionCall(
                                        name=fname,
                                        arguments=_json.dumps(recovery_args),
                                    ),
                                )
                            ],
                        )
                    )
                    llm_messages.append(
                        LLMChatMessage(
                            role="tool",
                            content=_json.dumps(
                                {
                                    "kind": "error",
                                    "reason": "malformed_json_arguments",
                                    "message": recovery_msg,
                                },
                                ensure_ascii=False,
                            ),
                            name=fname,
                            tool_call_id=call_id,
                        )
                    )
                    logger.warning(
                        "_handle_chat_request: suppressed malformed JSON %s "
                        "call_id=%s before permission gate (raw_length=%d)",
                        fname,
                        call_id[:12],
                        len(str(slot["args"] or "")),
                    )
                    if fname == "verify":
                        force_verify_next_turn = True
                    elif fname in {"lookup", "submit", "subscribe"}:
                        force_followup_primitive_next_turn = fname
                    continue

                if fname == "resolve_location":
                    args_obj = _normalise_resolve_location_args(args_obj)
                    resolve_prerequisite = _check_resolve_location_without_location_context(
                        args_obj,
                        latest_user_utt,
                        registry=_ensure_tool_registry(),
                    )
                    if resolve_prerequisite is not None:
                        next_primitive, prerequisite_msg = resolve_prerequisite
                        llm_messages.append(
                            LLMChatMessage(
                                role="assistant",
                                content="",
                                tool_calls=[
                                    LLMToolCall(
                                        id=call_id,
                                        type="function",
                                        function=LLMFunctionCall(
                                            name=fname,
                                            arguments=_json.dumps(args_obj),
                                        ),
                                    )
                                ],
                            )
                        )
                        llm_messages.append(
                            LLMChatMessage(
                                role="tool",
                                content=_json.dumps(
                                    {
                                        "kind": "error",
                                        "reason": "resolve_location_context_missing",
                                        "message": prerequisite_msg,
                                    },
                                    ensure_ascii=False,
                                ),
                                name=fname,
                                tool_call_id=call_id,
                            )
                        )
                        force_followup_primitive_next_turn = next_primitive
                        internal_recovery_inserted = True
                        logger.warning(
                            "_handle_chat_request: suppressed resolve_location "
                            "call_id=%s with no explicit location context",
                            call_id[:12],
                        )
                        continue

                if fname == "verify":
                    args_obj = _enrich_verify_args_from_policy(
                        args_obj,
                        latest_user_utt,
                        _ensure_tool_registry(),
                    )

                if fname in {"lookup", "submit", "subscribe"}:
                    params_obj = args_obj.get("params")
                    params_dict: dict[str, object] = (
                        dict(params_obj) if isinstance(params_obj, dict) else {}
                    )
                    delegation_context = _latest_delegation_context(
                        llm_messages
                    ) or _delegation_context_from_auth_context(
                        _session_auth_contexts.get(frame.session_id)
                    )
                    if delegation_context is None and isinstance(args_obj.get("tool_id"), str):
                        _adapter_schema = _schema_for_adapter_args(
                            args_obj,
                            _ensure_tool_registry(),
                        )
                        if "delegation_context" in _schema_required(_adapter_schema):
                            delegation_context = _mock_delegation_context_for_tool(
                                str(args_obj["tool_id"]),
                                session_id=frame.session_id,
                                user_query=latest_user_utt,
                                registry=_ensure_tool_registry(),
                            )
                    if delegation_context is not None:
                        # The LLM may summarize or partially reconstruct the
                        # DelegationContext in later turns. The backend owns the
                        # original verified object, so prefer it over any
                        # model-supplied copy before Pydantic validation.
                        params_dict["delegation_context"] = delegation_context
                    if fname == "submit" and "session_id" not in params_dict:
                        _submit_schema = _schema_for_adapter_args(
                            args_obj,
                            _ensure_tool_registry(),
                        )
                        if "session_id" in _schema_properties(_submit_schema):
                            params_dict["session_id"] = frame.session_id
                    if fname == "submit":
                        latest_auth_context = _latest_auth_context(llm_messages)
                        if latest_auth_context is not None:
                            _session_auth_contexts[frame.session_id] = latest_auth_context
                        gov24_next_submit = _next_gov24_movein_submit_args(llm_messages)
                        if gov24_next_submit is not None and args_obj.get(
                            "tool_id"
                        ) == gov24_next_submit.get("tool_id"):
                            next_params = gov24_next_submit.get("params")
                            if isinstance(next_params, dict):
                                for key, value in next_params.items():
                                    params_dict.setdefault(key, value)
                                expected_minwon_type = next_params.get("minwon_type")
                                if isinstance(expected_minwon_type, str):
                                    params_dict["minwon_type"] = expected_minwon_type
                        if _submit_payment_followup_needed(llm_messages):
                            params_dict["action_type"] = _hometax_followup_action_type_from_query(
                                latest_user_utt
                            )
                    if params_dict is not params_obj:
                        args_obj = dict(args_obj)
                        args_obj["params"] = params_dict

                    if fname == "lookup":
                        args_obj = _enrich_lookup_args_from_resolve_result(
                            args_obj,
                            llm_messages,
                            _ensure_tool_registry(),
                        )
                    if fname in {"lookup", "submit"}:
                        args_obj = _coerce_adapter_params_from_schema(
                            args_obj,
                            user_query=latest_user_utt,
                            registry=_ensure_tool_registry(),
                        )

                    if fname == "submit" and not _submit_args_compatible_with_latest_auth(
                        args_obj,
                        llm_messages,
                        _ensure_tool_registry(),
                    ):
                        pending_compatible_submit = _build_forced_submit_args(
                            latest_user_utt,
                            llm_messages,
                            _ensure_tool_registry(),
                        )
                        recovery_msg = (
                            "The requested submit adapter is not compatible with "
                            "the latest verified identity tier. Do not retry this "
                            "tool_id in the current turn; continue only with an "
                            "auth-compatible registry-selected submit, subscribe, "
                            "or final answer grounded in existing successful receipts."
                        )
                        llm_messages.append(
                            LLMChatMessage(
                                role="assistant",
                                content="",
                                tool_calls=[
                                    LLMToolCall(
                                        id=call_id,
                                        type="function",
                                        function=LLMFunctionCall(
                                            name=fname,
                                            arguments=_json.dumps(args_obj),
                                        ),
                                    )
                                ],
                            )
                        )
                        llm_messages.append(
                            LLMChatMessage(
                                role="tool",
                                content=_json.dumps(
                                    {
                                        "kind": "error",
                                        "reason": "submit_auth_tier_incompatible",
                                        "message": recovery_msg,
                                    },
                                    ensure_ascii=False,
                                ),
                                name=fname,
                                tool_call_id=call_id,
                            )
                        )
                        logger.warning(
                            "_handle_chat_request: suppressed submit call_id=%s — "
                            "adapter %s is incompatible with latest auth tier",
                            call_id[:12],
                            args_obj.get("tool_id"),
                        )
                        if pending_compatible_submit is not None:
                            force_followup_primitive_next_turn = "submit"
                        internal_recovery_inserted = True
                        continue

                    completed_chain_prerequisite = (
                        _check_tool_call_after_completed_submit_subscribe(
                            fname,
                            llm_messages,
                            latest_user_utt,
                            registry=_ensure_tool_registry(),
                        )
                    )
                    if completed_chain_prerequisite is not None:
                        _, prerequisite_msg = completed_chain_prerequisite
                        llm_messages.append(
                            LLMChatMessage(
                                role="assistant",
                                content="",
                                tool_calls=[
                                    LLMToolCall(
                                        id=call_id,
                                        type="function",
                                        function=LLMFunctionCall(
                                            name=fname,
                                            arguments=_json.dumps(args_obj),
                                        ),
                                    )
                                ],
                            )
                        )
                        llm_messages.append(
                            LLMChatMessage(
                                role="tool",
                                content=_json.dumps(
                                    {
                                        "kind": "error",
                                        "reason": "completed_submit_subscribe_chain",
                                        "message": prerequisite_msg,
                                    },
                                    ensure_ascii=False,
                                ),
                                name=fname,
                                tool_call_id=call_id,
                            )
                        )
                        logger.warning(
                            "_handle_chat_request: suppressed %s call_id=%s — "
                            "submit+subscribe chain already completed",
                            fname,
                            call_id[:12],
                        )
                        internal_recovery_inserted = True
                        continue

                    completed_submit_prerequisite = _check_tool_call_after_completed_submit(
                        fname,
                        llm_messages,
                        latest_user_utt,
                        registry=_ensure_tool_registry(),
                    )
                    if completed_submit_prerequisite is not None:
                        next_primitive, prerequisite_msg = completed_submit_prerequisite
                        llm_messages.append(
                            LLMChatMessage(
                                role="assistant",
                                content="",
                                tool_calls=[
                                    LLMToolCall(
                                        id=call_id,
                                        type="function",
                                        function=LLMFunctionCall(
                                            name=fname,
                                            arguments=_json.dumps(args_obj),
                                        ),
                                    )
                                ],
                            )
                        )
                        llm_messages.append(
                            LLMChatMessage(
                                role="tool",
                                content=_json.dumps(
                                    {
                                        "kind": "error",
                                        "reason": "completed_submit_chain",
                                        "message": prerequisite_msg,
                                    },
                                    ensure_ascii=False,
                                ),
                                name=fname,
                                tool_call_id=call_id,
                            )
                        )
                        logger.warning(
                            "_handle_chat_request: suppressed %s call_id=%s — "
                            "submit chain already completed",
                            fname,
                            call_id[:12],
                        )
                        if next_primitive != "final":
                            force_followup_primitive_next_turn = next_primitive
                        internal_recovery_inserted = True
                        continue

                    pending_submit_prerequisite = None
                    if not (
                        fname == "lookup"
                        and args_obj.get("tool_id") == "mock_lookup_module_national_ax_bundle"
                        and _gov24_bundle_lookup_should_follow_direct_submit(
                            latest_user_utt,
                            llm_messages,
                            _ensure_tool_registry(),
                        )
                    ):
                        pending_submit_prerequisite = _check_pending_submit_before_non_submit(
                            fname,
                            llm_messages,
                            latest_user_utt,
                            registry=_ensure_tool_registry(),
                        )
                    if pending_submit_prerequisite is not None:
                        from kosmos.ipc.frame_schema import (  # noqa: PLC0415
                            ToolResultEnvelope,
                            ToolResultFrame,
                        )

                        next_primitive, prerequisite_msg = pending_submit_prerequisite
                        await write_frame(
                            ToolCallFrame(
                                session_id=frame.session_id,
                                correlation_id=frame.correlation_id,
                                role="backend",
                                ts=_utcnow(),
                                kind="tool_call",
                                call_id=call_id,
                                name=fname,  # type: ignore[arg-type]
                                arguments=args_obj,
                            )
                        )
                        err_envelope = ToolResultEnvelope.model_validate(
                            {
                                "kind": cast("Any", fname),
                                "result": {
                                    "kind": "error",
                                    "reason": "pending_submit_before_non_submit",
                                    "message": prerequisite_msg,
                                    "retryable": False,
                                },
                            }
                        )
                        await write_frame(
                            ToolResultFrame(
                                session_id=frame.session_id,
                                correlation_id=frame.correlation_id,
                                role="backend",
                                ts=_utcnow(),
                                kind="tool_result",
                                call_id=call_id,
                                envelope=err_envelope,
                            )
                        )
                        llm_messages.append(
                            LLMChatMessage(
                                role="assistant",
                                content="",
                                tool_calls=[
                                    LLMToolCall(
                                        id=call_id,
                                        type="function",
                                        function=LLMFunctionCall(
                                            name=fname,
                                            arguments=_json.dumps(args_obj),
                                        ),
                                    )
                                ],
                            )
                        )
                        llm_messages.append(
                            LLMChatMessage(
                                role="tool",
                                content=_json.dumps(
                                    {
                                        "kind": "error",
                                        "reason": "pending_submit_before_non_submit",
                                        "message": prerequisite_msg,
                                    },
                                    ensure_ascii=False,
                                ),
                                name=fname,
                                tool_call_id=call_id,
                            )
                        )
                        logger.warning(
                            "_handle_chat_request: rejected %s call_id=%s — "
                            "pending submit prerequisite remains",
                            fname,
                            call_id[:12],
                        )
                        force_followup_primitive_next_turn = next_primitive
                        continue

                    if (
                        fname == "lookup"
                        and args_obj.get("tool_id") == "mock_lookup_module_gov24_movein_sequence"
                        and _gov24_direct_followup_flow_completed(
                            latest_user_utt,
                            llm_messages,
                            _ensure_tool_registry(),
                        )
                    ):
                        llm_messages.append(
                            LLMChatMessage(
                                role="assistant",
                                content="",
                                tool_calls=[
                                    LLMToolCall(
                                        id=call_id,
                                        type="function",
                                        function=LLMFunctionCall(
                                            name=fname,
                                            arguments=_json.dumps(args_obj),
                                        ),
                                    )
                                ],
                            )
                        )
                        llm_messages.append(
                            LLMChatMessage(
                                role="tool",
                                content=_json.dumps(
                                    {
                                        "kind": "error",
                                        "reason": "gov24_direct_followup_flow_completed",
                                        "message": (
                                            "The direct Gov24 move-in submit, "
                                            "bundled school/care lookup, and "
                                            "all query-matched follow-up Gov24 "
                                            "minwon submissions are already "
                                            "complete. Do not run the broader "
                                            "move-in dependency sequence or "
                                            "submit unrelated address-change "
                                            "minwon in this citizen turn; answer "
                                            "from the existing receipts."
                                        ),
                                    },
                                    ensure_ascii=False,
                                ),
                                name=fname,
                                tool_call_id=call_id,
                            )
                        )
                        internal_recovery_inserted = True
                        logger.warning(
                            "_handle_chat_request: suppressed Gov24 move-in "
                            "sequence lookup call_id=%s after direct follow-up "
                            "flow completed",
                            call_id[:12],
                        )
                        continue

                    if (
                        fname == "lookup"
                        and args_obj.get("tool_id") == "mock_lookup_module_national_ax_bundle"
                        and _gov24_movein_followup_needed(llm_messages)
                    ):
                        llm_messages.append(
                            LLMChatMessage(
                                role="assistant",
                                content="",
                                tool_calls=[
                                    LLMToolCall(
                                        id=call_id,
                                        type="function",
                                        function=LLMFunctionCall(
                                            name=fname,
                                            arguments=_json.dumps(args_obj),
                                        ),
                                    )
                                ],
                            )
                        )
                        llm_messages.append(
                            LLMChatMessage(
                                role="tool",
                                content=_json.dumps(
                                    {
                                        "kind": "error",
                                        "reason": "gov24_movein_sequence_pending",
                                        "message": (
                                            "The Gov24 move-in lookup already "
                                            "returned required submit steps. "
                                            "Complete submit(tool_id="
                                            "'mock_submit_module_gov24_minwon') "
                                            "for the remaining minwon_type before "
                                            "running bundled target-state service "
                                            "discovery."
                                        ),
                                    },
                                    ensure_ascii=False,
                                ),
                                name=fname,
                                tool_call_id=call_id,
                            )
                        )
                        force_followup_primitive_next_turn = "submit"
                        internal_recovery_inserted = True
                        logger.warning(
                            "_handle_chat_request: deferred national AX bundle "
                            "lookup call_id=%s until Gov24 move-in sequence completes",
                            call_id[:12],
                        )
                        continue

                    if (
                        fname == "lookup"
                        and args_obj.get("tool_id") == "mock_lookup_module_national_ax_bundle"
                        and _conversation_has_successful_tool_id(
                            llm_messages,
                            "lookup",
                            "mock_lookup_module_national_ax_bundle",
                        )
                    ):
                        llm_messages.append(
                            LLMChatMessage(
                                role="assistant",
                                content="",
                                tool_calls=[
                                    LLMToolCall(
                                        id=call_id,
                                        type="function",
                                        function=LLMFunctionCall(
                                            name=fname,
                                            arguments=_json.dumps(args_obj),
                                        ),
                                    )
                                ],
                            )
                        )
                        llm_messages.append(
                            LLMChatMessage(
                                role="tool",
                                content=_json.dumps(
                                    {
                                        "kind": "error",
                                        "reason": "bundle_lookup_already_grounded",
                                        "message": (
                                            "The national AX bundle lookup already "
                                            "returned a workflow inventory in this "
                                            "citizen turn. Do not call the same "
                                            "grounding lookup again; continue to "
                                            "submit or subscribe using the existing "
                                            "lookup result."
                                        ),
                                    },
                                    ensure_ascii=False,
                                ),
                                name=fname,
                                tool_call_id=call_id,
                            )
                        )
                        force_followup_primitive_next_turn = "submit"
                        internal_recovery_inserted = True
                        logger.warning(
                            "_handle_chat_request: suppressed repeated national "
                            "AX bundle lookup call_id=%s and forced submit follow-up",
                            call_id[:12],
                        )
                        continue

                    if fname == "submit" and _submit_payment_followup_completed(llm_messages):
                        recovery_args = {
                            "tool_id": args_obj.get("tool_id", "submit"),
                            "params": {
                                "reason": "submit_chain_already_completed",
                            },
                        }
                        recovery_msg = (
                            "A successful tax filing submit and a successful payment "
                            "deadline reminder submit are already present in the tool "
                            "results. Do not call submit again in this citizen turn. "
                            "Answer from the existing receipts and explain that real "
                            "payment still requires explicit confirmation."
                        )
                        llm_messages.append(
                            LLMChatMessage(
                                role="assistant",
                                content="",
                                tool_calls=[
                                    LLMToolCall(
                                        id=call_id,
                                        type="function",
                                        function=LLMFunctionCall(
                                            name=fname,
                                            arguments=_json.dumps(recovery_args),
                                        ),
                                    )
                                ],
                            )
                        )
                        llm_messages.append(
                            LLMChatMessage(
                                role="tool",
                                content=_json.dumps(
                                    {
                                        "kind": "error",
                                        "reason": "submit_chain_already_completed",
                                        "message": recovery_msg,
                                    },
                                    ensure_ascii=False,
                                ),
                                name=fname,
                                tool_call_id=call_id,
                            )
                        )
                        logger.warning(
                            "_handle_chat_request: suppressed extra submit "
                            "call_id=%s after payment follow-up completion",
                            call_id[:12],
                        )
                        internal_recovery_inserted = True
                        continue

                    if (
                        fname == "submit"
                        and args_obj.get("tool_id") == "mock_submit_module_gov24_minwon"
                        and _gov24_movein_sequence_completed(llm_messages)
                    ):
                        recovery_args = {
                            "tool_id": args_obj.get("tool_id", "submit"),
                            "params": {
                                "reason": "gov24_movein_sequence_completed",
                            },
                        }
                        recovery_msg = (
                            "The Gov24 move-in lookup's required submit sequence "
                            "has already completed in this citizen turn. Do not "
                            "call submit again; answer from the existing receipts."
                        )
                        llm_messages.append(
                            LLMChatMessage(
                                role="assistant",
                                content="",
                                tool_calls=[
                                    LLMToolCall(
                                        id=call_id,
                                        type="function",
                                        function=LLMFunctionCall(
                                            name=fname,
                                            arguments=_json.dumps(recovery_args),
                                        ),
                                    )
                                ],
                            )
                        )
                        llm_messages.append(
                            LLMChatMessage(
                                role="tool",
                                content=_json.dumps(
                                    {
                                        "kind": "error",
                                        "reason": "gov24_movein_sequence_completed",
                                        "message": recovery_msg,
                                    },
                                    ensure_ascii=False,
                                ),
                                name=fname,
                                tool_call_id=call_id,
                            )
                        )
                        logger.warning(
                            "_handle_chat_request: suppressed extra Gov24 move-in "
                            "submit call_id=%s after required sequence completion",
                            call_id[:12],
                        )
                        internal_recovery_inserted = True
                        continue

                    submit_prerequisite = _check_submit_prerequisite(
                        fname,
                        llm_messages,
                        latest_user_utt,
                        registry=_ensure_tool_registry(),
                    )
                    if submit_prerequisite is not None:
                        from kosmos.ipc.frame_schema import (  # noqa: PLC0415
                            ToolResultEnvelope,
                            ToolResultFrame,
                        )

                        next_primitive, prerequisite_msg = submit_prerequisite
                        await write_frame(
                            ToolCallFrame(
                                session_id=frame.session_id,
                                correlation_id=frame.correlation_id,
                                role="backend",
                                ts=_utcnow(),
                                kind="tool_call",
                                call_id=call_id,
                                name=fname,  # type: ignore[arg-type]
                                arguments=args_obj,
                            )
                        )
                        err_envelope = ToolResultEnvelope.model_validate(
                            {
                                "kind": cast("Any", fname),
                                "result": {
                                    "kind": "error",
                                    "reason": "submit_prerequisite_missing",
                                    "message": prerequisite_msg,
                                    "retryable": False,
                                },
                            }
                        )
                        await write_frame(
                            ToolResultFrame(
                                session_id=frame.session_id,
                                correlation_id=frame.correlation_id,
                                role="backend",
                                ts=_utcnow(),
                                kind="tool_result",
                                call_id=call_id,
                                envelope=err_envelope,
                            )
                        )
                        llm_messages.append(
                            LLMChatMessage(
                                role="assistant",
                                content="",
                                tool_calls=[
                                    LLMToolCall(
                                        id=call_id,
                                        type="function",
                                        function=LLMFunctionCall(
                                            name=fname,
                                            arguments=_json.dumps(args_obj),
                                        ),
                                    )
                                ],
                            )
                        )
                        llm_messages.append(
                            LLMChatMessage(
                                role="tool",
                                content=_json.dumps(
                                    {
                                        "kind": "error",
                                        "reason": "submit_prerequisite_missing",
                                        "message": prerequisite_msg,
                                    },
                                    ensure_ascii=False,
                                ),
                                name=fname,
                                tool_call_id=call_id,
                            )
                        )
                        logger.warning(
                            "_handle_chat_request: rejected submit call_id=%s — "
                            "prerequisite %s missing",
                            call_id[:12],
                            next_primitive,
                        )
                        if next_primitive == "resolve_location":
                            force_resolve_location_next_turn = True
                        else:
                            force_followup_primitive_next_turn = next_primitive
                        continue

                pre_permission_error_msg = _pre_permission_arg_error(fname, args_obj)
                if pre_permission_error_msg is not None:
                    from kosmos.ipc.frame_schema import (  # noqa: PLC0415
                        ToolResultEnvelope,
                        ToolResultFrame,
                    )

                    await write_frame(
                        ToolCallFrame(
                            session_id=frame.session_id,
                            correlation_id=frame.correlation_id,
                            role="backend",
                            ts=_utcnow(),
                            kind="tool_call",
                            call_id=call_id,
                            name=fname,  # type: ignore[arg-type]
                            arguments=args_obj,
                        )
                    )
                    err_envelope = ToolResultEnvelope.model_validate(
                        {
                            "kind": cast("Any", fname),
                            "result": {
                                "kind": "error",
                                "reason": "invalid_params",
                                "message": pre_permission_error_msg,
                                "retryable": False,
                            },
                        }
                    )
                    await write_frame(
                        ToolResultFrame(
                            session_id=frame.session_id,
                            correlation_id=frame.correlation_id,
                            role="backend",
                            ts=_utcnow(),
                            kind="tool_result",
                            call_id=call_id,
                            envelope=err_envelope,
                        )
                    )
                    llm_messages.append(
                        LLMChatMessage(
                            role="assistant",
                            content="",
                            tool_calls=[
                                LLMToolCall(
                                    id=call_id,
                                    type="function",
                                    function=LLMFunctionCall(
                                        name=fname,
                                        arguments=_json.dumps(args_obj),
                                    ),
                                )
                            ],
                        )
                    )
                    llm_messages.append(
                        LLMChatMessage(
                            role="tool",
                            content=_json.dumps(
                                {
                                    "kind": "error",
                                    "reason": "invalid_params",
                                    "message": pre_permission_error_msg,
                                },
                                ensure_ascii=False,
                            ),
                            name=fname,
                            tool_call_id=call_id,
                        )
                    )
                    logger.warning(
                        "_handle_chat_request: rejected %s call_id=%s — "
                        "invalid params before permission",
                        fname,
                        call_id[:12],
                    )
                    if fname == "verify":
                        force_verify_next_turn = True
                    elif fname in {"lookup", "submit", "subscribe"}:
                        force_followup_primitive_next_turn = fname
                    continue

                delegation_error_msg = _check_lookup_delegation_prerequisite(fname, args_obj)
                if delegation_error_msg is not None:
                    llm_messages.append(
                        LLMChatMessage(
                            role="assistant",
                            content="",
                            tool_calls=[
                                LLMToolCall(
                                    id=call_id,
                                    type="function",
                                    function=LLMFunctionCall(
                                        name=fname,
                                        arguments=_json.dumps(args_obj),
                                    ),
                                )
                            ],
                        )
                    )
                    llm_messages.append(
                        LLMChatMessage(
                            role="tool",
                            content=_json.dumps(
                                {
                                    "kind": "error",
                                    "reason": "lookup_delegation_prerequisite_missing",
                                    "message": delegation_error_msg,
                                },
                                ensure_ascii=False,
                            ),
                            name=fname,
                            tool_call_id=call_id,
                        )
                    )
                    logger.warning(
                        "_handle_chat_request: rejected %s call_id=%s — "
                        "lookup DelegationContext prerequisite missing",
                        fname,
                        call_id[:12],
                    )
                    force_verify_next_turn = True
                    continue

                # Chain prerequisite gate — donga-univ-poi-bug Epic #2766.
                # CC mirror: ``Tool.validateInput?(input, context)`` from
                # ``.references/claude-code-sourcemap/restored-src/src/Tool.ts:489``
                # — tool-scoped prerequisite hook that inspects the
                # surrounding ToolUseContext and may reject with a
                # message the LLM sees in the tool_result. KOSMOS port:
                # we run the check here, before issuing the ToolCallFrame
                # and before the dispatch task starts, so a rejected call
                # never burns an outbound HTTP request and the LLM gets
                # a deterministic chain-recovery instruction in the same
                # turn it tried to skip the prerequisite.
                #
                # Concretely: when fname == "lookup" + the chosen tool_id
                # is a coordinate/admcd-input adapter (kma_*, hira_*, nmc_*,
                # koroad_*) AND the citizen-supplied params already carry
                # the coordinates AND no prior turn in llm_messages
                # invoked resolve_location, that means the LLM guessed
                # the coordinates from prior knowledge instead of routing
                # through the canonical resolver. Three live captures
                # under specs/integration-verification/donga-univ-poi-bug/
                # showed this exact pattern producing wrong-region
                # hospital lists. Rejecting here forces the next turn
                # through resolve_location.
                chain_error_msg = _check_chain_prerequisite(
                    fname, args_obj, llm_messages, registry=_ensure_tool_registry()
                )
                if chain_error_msg is not None:
                    from kosmos.ipc.frame_schema import (  # noqa: PLC0415
                        ToolResultEnvelope,
                        ToolResultFrame,
                    )

                    # Emit a ToolCallFrame first so the TUI registers the
                    # call_id in seenToolUseIds (deps.ts L420). Without it
                    # the subsequent ToolResultFrame surfaces as a
                    # `tool_result_orphan` system error in the transcript.
                    await write_frame(
                        ToolCallFrame(
                            session_id=frame.session_id,
                            correlation_id=frame.correlation_id,
                            role="backend",
                            ts=_utcnow(),
                            kind="tool_call",
                            call_id=call_id,
                            name=fname,  # type: ignore[arg-type]
                            arguments=args_obj,
                        )
                    )
                    err_envelope = ToolResultEnvelope.model_validate(
                        {
                            "kind": cast("Any", fname),
                            "result": {
                                "kind": "error",
                                "reason": "chain_prerequisite_missing",
                                "message": chain_error_msg,
                                "retryable": False,
                            },
                        }
                    )
                    await write_frame(
                        ToolResultFrame(
                            session_id=frame.session_id,
                            correlation_id=frame.correlation_id,
                            role="backend",
                            ts=_utcnow(),
                            kind="tool_result",
                            call_id=call_id,
                            envelope=err_envelope,
                        )
                    )
                    # Inject a synthetic tool message into history so the
                    # next LLM turn sees the chain hint and follows it.
                    llm_messages.append(
                        LLMChatMessage(
                            role="assistant",
                            content="",
                            tool_calls=[
                                LLMToolCall(
                                    id=call_id,
                                    type="function",
                                    function=LLMFunctionCall(
                                        name=fname,
                                        arguments=_json.dumps(args_obj),
                                    ),
                                )
                            ],
                        )
                    )
                    llm_messages.append(
                        LLMChatMessage(
                            role="tool",
                            content=_json.dumps(
                                {
                                    "kind": "error",
                                    "reason": "chain_prerequisite_missing",
                                    "message": chain_error_msg,
                                },
                                ensure_ascii=False,
                            ),
                            name=fname,
                            tool_call_id=call_id,
                        )
                    )
                    logger.warning(
                        "_handle_chat_request: rejected %s call_id=%s — chain prerequisite missing",
                        fname,
                        call_id[:12],
                    )
                    # Neurosymbolic constraint — the next LLM turn must
                    # call resolve_location before any other tool. Set the
                    # flag here so the next loop iteration's tool_choice
                    # forces the model down the chain. See the flag
                    # comment at the loop start for the full rationale.
                    force_resolve_location_next_turn = True
                    continue

                # Audit G4 / F-beta-03 — dedup guard. If the same
                # (tool_id, params) was already attempted this chat turn AND
                # the prior outcome was NO_DATA / error, short-circuit with a
                # synthetic tool_result + explicit instruction. K-EXAONE on
                # FriendliAI repeated `mohw_welfare_eligibility_search` 5x
                # with identical params in β7 (2026-05-05); each produced
                # NO_DATA but the model did not recognise the redundancy.
                _dedup_inner_id = (
                    args_obj.get("tool_id") if fname in {"lookup", "submit", "subscribe"} else fname
                )
                _dedup_key = _hash_call(str(_dedup_inner_id), args_obj)
                _prior_outcome = _seen_calls.get(_dedup_key)
                _repeat_successful_submit_scheduled = False
                if fname == "submit":
                    _submit_tool_id = args_obj.get("tool_id")
                    if (
                        isinstance(_submit_tool_id, str)
                        and _submit_tool_id in _SINGLETON_SUBMIT_TOOL_IDS
                        and _submit_tool_id in _issued_singleton_submit_tool_ids
                    ):
                        _repeat_successful_submit_scheduled = True
                    elif (
                        isinstance(_submit_tool_id, str)
                        and _submit_tool_id in _SINGLETON_SUBMIT_TOOL_IDS
                    ):
                        _issued_singleton_submit_tool_ids.add(_submit_tool_id)
                    _submit_sig = _submit_semantic_signature(args_obj)
                    if _submit_sig is not None and _submit_sig in _issued_submit_signatures:
                        _repeat_successful_submit_scheduled = True
                    elif _submit_sig is not None:
                        _issued_submit_signatures.add(_submit_sig)
                if _prior_outcome in ("no_data", "error") or (
                    fname == "submit"
                    and (_prior_outcome == "ok" or _repeat_successful_submit_scheduled)
                ):
                    from kosmos.ipc.frame_schema import (  # noqa: PLC0415
                        ToolResultEnvelope,
                        ToolResultFrame,
                    )

                    if fname == "submit" and (
                        _prior_outcome == "ok" or _repeat_successful_submit_scheduled
                    ):
                        repeat_reason = "repeat_successful_submit_blocked"
                        repeat_msg_ko = (
                            "이 submit(tool_id, params) 조합은 이번 turn 에서 이미 "
                            "실행 중이거나 성공했습니다. 동일 제출은 중복 접수 위험이 "
                            "있으므로 재실행하지 마세요. 기존 접수 결과를 사용하거나, "
                            "다른 후속 단계가 필요하면 다른 tool_id/params 또는 "
                            "subscribe로 전환하세요."
                        )
                    else:
                        repeat_reason = "repeat_call_blocked"
                        repeat_msg_ko = (
                            "이 (tool_id, params) 조합은 이번 turn 에서 이미 호출되었고 "
                            f"결과가 '{_prior_outcome}' 였습니다. 동일 호출은 동일 결과를 "
                            "반환하므로 재시도하지 마세요. 다른 params 또는 다른 도구로 "
                            "전환하거나, 시민에게 데이터 없음을 안내하세요."
                        )
                    if fname == "submit":
                        await write_frame(
                            ToolCallFrame(
                                session_id=frame.session_id,
                                correlation_id=frame.correlation_id,
                                role="backend",
                                ts=_utcnow(),
                                kind="tool_call",
                                call_id=call_id,
                                name=fname,  # type: ignore[arg-type]
                                arguments=args_obj,
                            )
                        )
                        dedup_envelope = ToolResultEnvelope.model_validate(
                            {
                                "kind": cast("Any", fname),
                                "result": {
                                    "kind": "error",
                                    "reason": repeat_reason,
                                    "message": repeat_msg_ko,
                                    "retryable": False,
                                },
                            }
                        )
                        await write_frame(
                            ToolResultFrame(
                                session_id=frame.session_id,
                                correlation_id=frame.correlation_id,
                                role="backend",
                                ts=_utcnow(),
                                kind="tool_result",
                                call_id=call_id,
                                envelope=dedup_envelope,
                            )
                        )
                    llm_messages.append(
                        LLMChatMessage(
                            role="assistant",
                            content="",
                            tool_calls=[
                                LLMToolCall(
                                    id=call_id,
                                    type="function",
                                    function=LLMFunctionCall(
                                        name=fname,
                                        arguments=_json.dumps(args_obj),
                                    ),
                                )
                            ],
                        )
                    )
                    llm_messages.append(
                        LLMChatMessage(
                            role="tool",
                            content=_json.dumps(
                                {
                                    "kind": "error",
                                    "reason": repeat_reason,
                                    "message": repeat_msg_ko,
                                },
                                ensure_ascii=False,
                            ),
                            name=fname,
                            tool_call_id=call_id,
                        )
                    )
                    logger.warning(
                        "_handle_chat_request: dedup blocked %s call_id=%s "
                        "(prior outcome=%s, key=%s)",
                        fname,
                        call_id[:12],
                        _prior_outcome,
                        _dedup_key,
                    )
                    internal_recovery_inserted = True
                    continue
                # Reserve the dedup slot now so other calls in the same turn
                # can detect duplicates within the SAME tool_call_buf.
                _seen_calls.setdefault(_dedup_key, "ok")
                issued_dedup_keys[call_id] = _dedup_key

                _pending_calls[call_id] = loop.create_future()
                issued_calls.append((call_id, fname))
                assistant_tool_calls.append(
                    LLMToolCall(
                        id=call_id,
                        type="function",
                        function=LLMFunctionCall(
                            name=fname,
                            arguments=_json.dumps(args_obj),
                        ),
                    )
                )
                await write_frame(
                    ToolCallFrame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id,
                        role="backend",
                        ts=_utcnow(),
                        kind="tool_call",
                        call_id=call_id,
                        name=fname,  # type: ignore[arg-type]
                        arguments=args_obj,
                    )
                )

                # Spec 1978 T053b — fire internal primitive dispatch as a
                # background task. The task resolves _pending_calls[call_id]
                # when the primitive returns, allowing the gather below to
                # proceed without waiting for an external tool_result frame.
                asyncio.create_task(
                    _dispatch_primitive(
                        call_id,
                        fname,
                        args_obj,
                        frame.session_id,
                        frame.correlation_id,
                    ),
                    name=f"primitive-{fname}-{call_id[:8]}",
                )

                # Neurosymbolic constraint — clear the force flag once a
                # resolve_location turn has actually been dispatched. Any
                # subsequent turn returns to free tool_choice so the LLM
                # can route to the actual coord-input adapter (KMA/HIRA/
                # NMC) with the resolved coordinates.
                if fname == "resolve_location":
                    force_resolve_location_next_turn = False
                if fname == "verify":
                    force_verify_next_turn = False
                if fname == force_followup_primitive_next_turn:
                    force_followup_primitive_next_turn = None

            # If every tool call was rejected (whitelist), terminate.
            # Exception: when the chain gate fired (force flag set) we
            # MUST continue to the next iteration so the forced
            # tool_choice=resolve_location actually gets a chance to run.
            # Returning here would leave the citizen with the chain-error
            # tool_result frame as the only visible output.
            if not issued_calls:
                if (
                    force_resolve_location_next_turn
                    or force_verify_next_turn
                    or force_followup_primitive_next_turn is not None
                    or internal_recovery_inserted
                ):
                    # Synthetic tool_result already injected into
                    # llm_messages; the next loop iteration will fire the
                    # LLM again with tool_choice forced to the required
                    # primitive.
                    continue
                await write_frame(
                    AssistantChunkFrame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id,
                        role="llm",
                        ts=_utcnow(),
                        kind="assistant_chunk",
                        message_id=message_id,
                        delta="",
                        done=True,
                    )
                )
                return

            # Append the assistant message that requested tools — the CC
            # query-engine contract requires the function-call envelope to
            # precede the tool messages in the next turn.
            #
            # Epic #2152 follow-up — record the *cleaned* text (markers
            # stripped) into the LLM history so subsequent turns don't see
            # the textual ``<tool_call>`` blocks and double-emit them. The
            # post-stream extractor above sets ``cleaned_text`` only when
            # it ran (i.e. tool_call_buf was empty + marker present); when
            # both structured tool_calls AND a textual marker were emitted
            # in the same turn, run the extractor here too so the marker is
            # stripped from history even though we don't synthesise an
            # additional tool_call_buf entry.
            if "<tool_call>" in cleaned_text:
                from kosmos.llm.tool_call_parser import (  # noqa: PLC0415
                    extract_textual_tool_calls,
                )

                _, cleaned_text = extract_textual_tool_calls(cleaned_text)
            llm_messages.append(
                LLMChatMessage(
                    role="assistant",
                    content=cleaned_text,
                    tool_calls=assistant_tool_calls,
                )
            )

            # ---- Await tool_result Futures (gated by T030 timeout) -------
            tasks = [_pending_calls[cid] for cid, _ in issued_calls]
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=_TOOL_RESULT_TIMEOUT_S,
                )
            except TimeoutError:
                # Per contracts/tool-bridge-protocol.md timeout → synthetic
                # error result. Drop pending entries to avoid leaks.
                for cid, _ in issued_calls:
                    pending = _pending_calls.pop(cid, None)
                    if pending and not pending.done():
                        pending.cancel()
                await write_frame(
                    ErrorFrame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id or str(uuid.uuid4()),
                        role="backend",
                        ts=_utcnow(),
                        kind="error",
                        code="tool_timeout",
                        message=(f"Tool result timeout after {_TOOL_RESULT_TIMEOUT_S:.0f}s"),
                        details={
                            "call_ids": [cid for cid, _ in issued_calls],
                        },
                    )
                )
                return

            # ---- Inject tool messages, continue agentic loop --------------
            for (cid, fname), result in zip(issued_calls, results, strict=False):
                if isinstance(result, BaseException):
                    payload = _json.dumps({"error": "tool_dispatch_failed", "detail": str(result)})
                    # Audit G4 / F-beta-03 — record outcome for dedup guard.
                    _dk = issued_dedup_keys.get(cid)
                    if _dk:
                        _seen_calls[_dk] = "error"
                else:
                    # ToolResultFrame.envelope is a Pydantic model.
                    envelope = getattr(result, "envelope", None)
                    if envelope is not None and hasattr(envelope, "model_dump"):
                        env_dump = envelope.model_dump()
                        payload = _json.dumps(
                            env_dump,
                            ensure_ascii=False,
                            default=str,
                        )
                        # Audit G4 / F-beta-03 — classify outcome for the dedup
                        # guard. NO_DATA / empty / kind=error all map to
                        # 'no_data' or 'error' so the next identical
                        # (tool_id, params) call short-circuits.
                        _dk = issued_dedup_keys.get(cid)
                        if _dk:
                            _outcome = _classify_envelope_outcome(env_dump)
                            if _outcome != "ok":
                                _seen_calls[_dk] = _outcome
                    else:
                        payload = _json.dumps({"result": str(result)}, ensure_ascii=False)
                llm_messages.append(
                    LLMChatMessage(
                        role="tool",
                        content=payload,
                        name=fname,
                        tool_call_id=cid,
                    )
                )

            issued_tool_names = {fname for _, fname in issued_calls}
            if (
                issued_tool_names == {"verify"}
                and not _conversation_has_primitive(llm_messages, "resolve_location")
                and _query_implies_followup_lookup(
                    latest_user_utt,
                    registry=_ensure_tool_registry(),
                )
            ):
                force_resolve_location_next_turn = True
                logger.warning(
                    "_handle_chat_request: post-verify chain gate forcing "
                    "tool_choice=resolve_location for next turn"
                )
            if (
                issued_tool_names == {"resolve_location"}
                and not _conversation_has_verify(llm_messages)
                and _retrieval_has_strong_policy_gated_candidate(
                    _search_relevant_candidates(
                        latest_user_utt,
                        _ensure_tool_registry(),
                    )
                )
            ):
                force_verify_next_turn = True
                logger.warning(
                    "_handle_chat_request: post-resolve chain gate forcing "
                    "tool_choice=verify before policy-gated follow-up"
                )
            post_tool_followup = (
                None
                if force_resolve_location_next_turn
                else _check_privileged_chain_terminated_early(
                    llm_messages,
                    latest_user_utt,
                    registry=_ensure_tool_registry(),
                )
            )
            if post_tool_followup is not None:
                post_primitive, _post_reason = post_tool_followup
                if post_primitive == "verify":
                    force_verify_next_turn = True
                elif post_primitive == "resolve_location":
                    force_resolve_location_next_turn = True
                elif post_primitive in {"lookup", "submit", "subscribe"}:
                    force_followup_primitive_next_turn = post_primitive
                logger.warning(
                    "_handle_chat_request: post-tool chain gate forcing "
                    "tool_choice=%s for next turn",
                    post_primitive,
                )

            # Loop back: re-invoke client.stream with extended history.

        # Loop bound exhausted — emit terminal chunk anyway so the TUI
        # un-spins; the model will not be re-invoked beyond the bound.
        completion_answer = _build_tool_result_completion_answer(llm_messages)
        if completion_answer is not None:
            logger.warning(
                "agentic loop hit KOSMOS_AGENTIC_LOOP_MAX_TURNS=%d; "
                "emitting deterministic tool-result completion summary",
                _AGENTIC_LOOP_MAX_TURNS,
            )
            await write_frame(
                AssistantChunkFrame(
                    session_id=frame.session_id,
                    correlation_id=frame.correlation_id,
                    role="llm",
                    ts=_utcnow(),
                    kind="assistant_chunk",
                    message_id=str(uuid.uuid4()),
                    delta=completion_answer,
                    done=True,
                )
            )
            return
        logger.warning(
            "agentic loop hit KOSMOS_AGENTIC_LOOP_MAX_TURNS=%d; terminating",
            _AGENTIC_LOOP_MAX_TURNS,
        )
        await write_frame(
            AssistantChunkFrame(
                session_id=frame.session_id,
                correlation_id=frame.correlation_id,
                role="llm",
                ts=_utcnow(),
                kind="assistant_chunk",
                message_id=str(uuid.uuid4()),
                delta="",
                done=True,
            )
        )

    async def _handle_tool_result(frame: IPCFrame) -> None:
        """Spec 1978 T028 — consume ``tool_result`` and resolve pending Future.

        Looks up ``_pending_calls[call_id]``; if found, sets the Future
        result so any awaiting ``_handle_chat_request`` continuation can
        resume the agentic loop. Frames with no matching pending call are
        logged at debug level (out-of-band tool results are tolerated for
        the demo path; deep validation deferred to subsequent commits).
        """
        from kosmos.ipc.frame_schema import ToolResultFrame  # noqa: PLC0415

        if not isinstance(frame, ToolResultFrame):
            return
        fut = _pending_calls.pop(frame.call_id, None)
        if fut is None:
            logger.debug(
                "tool_result with no pending call (call_id=%s) — ignoring",
                frame.call_id,
            )
            return
        if not fut.done():
            fut.set_result(frame)

    # KOSMOS_IPC_HANDLER env var selects the user_input handler:
    #   - "llm" (default): route UserInputFrame → LLMClient.stream() → FriendliAI
    #   - "echo": mirror UserInputFrame back as AssistantChunkFrame "[echo] {text}"
    # Echo mode is used by integration tests that spawn the real backend but
    # must not depend on FRIENDLI_API_KEY or network reachability.
    import os as _os  # noqa: PLC0415

    _handler_mode = (_os.environ.get("KOSMOS_IPC_HANDLER") or "llm").lower()

    async def _handle_user_input_echo(frame: IPCFrame) -> None:
        from kosmos.ipc.frame_schema import (  # noqa: PLC0415
            AssistantChunkFrame,
            UserInputFrame,
        )

        if not isinstance(frame, UserInputFrame):
            return

        echo_frame = AssistantChunkFrame(
            session_id=frame.session_id,
            correlation_id=frame.correlation_id,
            role="backend",
            ts=_utcnow(),
            kind="assistant_chunk",
            message_id=str(uuid.uuid4()),
            delta=f"[echo] {frame.text}",
            done=True,
        )
        await write_frame(echo_frame)

    if on_frame is None:
        _chat_request_lock = asyncio.Lock()
        _background_tasks: set[asyncio.Task[None]] = set()

        async def _run_chat_request_background(frame: IPCFrame) -> None:
            """Run one chat turn without blocking the stdin reader loop."""
            async with _chat_request_lock:
                try:
                    await _handle_chat_request(frame)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("chat_request handler failed: %s", exc)
                    err = ErrorFrame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id or str(uuid.uuid4()),
                        role="llm",
                        ts=_utcnow(),
                        kind="error",
                        code="chat_request_error",
                        message=f"chat_request handler failed: {exc}",
                        details={},
                    )
                    await write_frame(err)

        def _track_background_task(task: asyncio.Task[None]) -> None:
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)

        async def _handle_frame(frame: IPCFrame) -> None:  # noqa: C901
            if frame.kind == "user_input":
                try:
                    if _handler_mode == "echo":
                        await _handle_user_input_echo(frame)
                    else:
                        await _handle_user_input_llm(frame)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("user_input handler failed: %s", exc)
                    err = ErrorFrame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id or str(uuid.uuid4()),
                        role="backend",
                        ts=_utcnow(),
                        kind="error",
                        code="llm_handler_error",
                        message=f"LLM handler failed: {exc}",
                        details={},
                    )
                    await write_frame(err)

            elif frame.kind == "chat_request":
                # Spec 1978 ADR-0001 — tools-aware chat path. The chat turn
                # can pause on backend-owned permission futures; keep stdin
                # draining so permission_response frames can resolve them.
                task_name_corr = frame.correlation_id or str(uuid.uuid4())
                task = asyncio.create_task(
                    _run_chat_request_background(frame),
                    name=f"chat-request-{task_name_corr[:8]}",
                )
                _track_background_task(task)

            elif frame.kind == "tool_result":
                # Spec 1978 T028 — resolve pending tool call Future.
                try:
                    await _handle_tool_result(frame)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("tool_result handler failed: %s", exc)

            elif frame.kind == "permission_response":
                # Spec 1978 T047 — resolve pending permission Future.
                try:
                    await _handle_permission_response(frame)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("permission_response handler failed: %s", exc)

            elif frame.kind == "session_event":
                evt = frame.event
                payload = frame.payload
                try:
                    await _dispatch_session_event(
                        evt,
                        payload,
                        frame.session_id,
                        _sm,
                        _shutdown,
                        frame.correlation_id,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.exception("session_event handler raised: %s", exc)
                    err = ErrorFrame(
                        session_id=frame.session_id,
                        correlation_id=str(uuid.uuid4()),
                        role="backend",
                        ts=_utcnow(),
                        kind="error",
                        code="session_event_error",
                        message=f"Failed to handle session_event {evt!r}: {exc}",
                        details={"event": evt},
                    )
                    await write_frame(err)

            elif frame.kind == "consent_revoke_request":
                # Epic 2 — consent revoke IPC arm (arm 22).
                try:
                    await _handle_consent_revoke_request(frame)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("consent_revoke_request handler failed: %s", exc)
                    from kosmos.ipc.frame_schema import (
                        ConsentRevokeResponseFrame as _ConsentRevokeResponseFrame,  # noqa: PLC0415
                    )

                    err_resp = _ConsentRevokeResponseFrame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id or str(uuid.uuid4()),
                        role="backend",
                        ts=_utcnow(),
                        kind="consent_revoke_response",
                        request_id=getattr(frame, "request_id", ""),
                        ok=False,
                        error="io_error",
                    )
                    await write_frame(err_resp)

            elif frame.kind == "plugin_op":
                # Spec 1979 — plugin_op IPC dispatcher arm. Routes citizen
                # /plugin install / uninstall / list slash commands to the
                # backend installer (Spec 1636) via the IPCConsentBridge
                # (60s wait_for + Spec 033 PermissionRequestFrame round-trip).
                try:
                    from kosmos.ipc.plugin_op_dispatcher import (  # noqa: PLC0415
                        handle_plugin_op_request,
                    )
                    from kosmos.plugins.consent_bridge import (  # noqa: PLC0415
                        IPCConsentBridge,
                    )
                    from kosmos.tools.executor import ToolExecutor  # noqa: PLC0415

                    consent_bridge = IPCConsentBridge(
                        write_frame=write_frame,
                        pending_perms=_pending_perms,
                        session_id=frame.session_id,
                    )
                    _registry = _ensure_tool_registry()
                    # Wave-5 (F-ε-03 micro-fix): outer timeout so a stuck
                    # catalog fetch / SLSA verifier / unknown plugin id never
                    # leaves the citizen with a silent placeholder. Spec 1636
                    # SC-005 SLO is 30s; we cap at 90s (3× SLO) to allow real
                    # network slowness while still surfacing a terminal error
                    # frame instead of indefinite spinner.
                    try:
                        await asyncio.wait_for(
                            handle_plugin_op_request(
                                frame,
                                registry=_registry,
                                executor=ToolExecutor(registry=_registry),  # type: ignore[arg-type]
                                write_frame=write_frame,
                                consent_bridge=consent_bridge,
                                session_id=frame.session_id,
                            ),
                            timeout=90.0,
                        )
                    except TimeoutError:
                        timeout_err = ErrorFrame(
                            session_id=frame.session_id,
                            correlation_id=frame.correlation_id or str(uuid.uuid4()),
                            role="backend",
                            ts=_utcnow(),
                            kind="error",
                            code="plugin_op_timeout",
                            message=(
                                "plugin_op 처리가 90초를 초과해 중단되었습니다. "
                                "카탈로그 조회 / 번들 다운로드 / SLSA 검증 단계 "
                                "중 하나가 응답하지 않습니다. 다시 시도하시거나 "
                                "다른 플러그인 id 를 사용해주세요."
                            ),
                            details={
                                "request_op": getattr(frame, "request_op", None),
                                "slo_30s": True,
                                "cap_90s": True,
                            },
                        )
                        await write_frame(timeout_err)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("plugin_op handler failed: %s", exc)
                    err = ErrorFrame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id or str(uuid.uuid4()),
                        role="backend",
                        ts=_utcnow(),
                        kind="error",
                        code="plugin_op_error",
                        message=f"plugin_op handler failed: {exc}",
                        details={"request_op": getattr(frame, "request_op", None)},
                    )
                    await write_frame(err)

        async def _handle_consent_revoke_request(frame: IPCFrame) -> None:  # noqa: C901, PLR0912
            """Epic 2 — consent revoke request handler (arm 22).

            Reads the target receipt JSON from
            ``~/.kosmos/memdir/user/consent/<receipt_id>.json``, marks it
            revoked (atomic temp+rename write), appends a withdrawal entry to
            the canonical Spec 033 PIPA ledger via
            ``kosmos.permissions.ledger.append`` (HMAC-sealed, hash-chained,
            fcntl-locked), emits an OTEL span, and responds with a
            ``consent_revoke_response`` frame.

            Audit-4 P0-3 (2026-05-04): Replaced ad-hoc unsealed
            ``hashlib.sha256(json.dumps(entry))`` + parallel
            ``~/.kosmos/memdir/user/consent/ledger.jsonl`` path with
            ``kosmos.permissions.ledger.append(action="withdraw", ...)``.
            The ad-hoc path lacked HMAC, hash-chain prev_hash, key_id, and
            fcntl lock — entries were forgeable and could not be verified by
            ``kosmos permissions verify``. The unified path writes to the
            canonical ledger configured by ``settings.permission_ledger_path``
            (default ``~/.kosmos/consent_ledger.jsonl``).

            Error cases:
            - ``not_found``:   receipt file does not exist.
            - ``already_revoked``: receipt already has ``revoked_at`` set.
            - ``io_error``:    any filesystem / JSON parse error.
            """
            import json as _json_revoke  # noqa: PLC0415
            import os as _os_revoke  # noqa: PLC0415
            import tempfile as _tempfile  # noqa: PLC0415
            from datetime import datetime as _dt_revoke  # noqa: PLC0415
            from pathlib import Path as _Path  # noqa: PLC0415

            from kosmos.ipc.frame_schema import (  # noqa: PLC0415
                ConsentRevokeResponseFrame as _CRRespFrame,
            )
            from kosmos.permissions.action_digest import (  # noqa: PLC0415
                compute_action_digest as _compute_action_digest,
            )
            from kosmos.permissions.action_digest import (  # noqa: PLC0415
                generate_nonce as _generate_nonce,
            )
            from kosmos.permissions.ledger import (  # noqa: PLC0415
                append as _ledger_append_withdraw,
            )
            from kosmos.settings import (  # noqa: PLC0415
                settings as _kosmos_settings_revoke,
            )

            request_id: str = getattr(frame, "request_id", "")
            receipt_id: str = getattr(frame, "receipt_id", "")
            scope: str = getattr(frame, "scope", "once")
            reason: str | None = getattr(frame, "reason", None)
            session_id: str = frame.session_id

            with _tracer.start_as_current_span("kosmos.consent.revoke") as revoke_span:
                revoke_span.set_attribute("kosmos.consent.receipt_id", receipt_id)
                revoke_span.set_attribute("kosmos.consent.scope", scope)
                revoke_span.set_attribute("kosmos.session.id", session_id)

                consent_dir = _Path.home() / ".kosmos" / "memdir" / "user" / "consent"
                receipt_path = consent_dir / f"{receipt_id}.json"

                async def _emit_response(
                    ok: bool,
                    revoked_at: str | None = None,
                    record_hash: str | None = None,
                    error: str | None = None,
                ) -> None:
                    resp = _CRRespFrame(
                        session_id=session_id,
                        correlation_id=frame.correlation_id or str(uuid.uuid4()),
                        role="backend",
                        ts=_utcnow(),
                        kind="consent_revoke_response",
                        request_id=request_id,
                        ok=ok,
                        revoked_at=revoked_at,
                        record_hash=record_hash,
                        error=error,  # type: ignore[arg-type]
                    )
                    await write_frame(resp)

                # Determine which receipts to revoke.
                if scope == "session-all":
                    # Collect all receipt files for the current session.
                    try:
                        all_paths = sorted(consent_dir.glob("rcpt-*.json"))
                    except Exception:
                        all_paths = []
                    target_paths = []
                    for p in all_paths:
                        try:
                            raw = p.read_text(encoding="utf-8")
                            data = _json_revoke.loads(raw)
                            if data.get("session_id") == session_id and not data.get("revoked_at"):
                                target_paths.append(p)
                        except Exception:  # noqa: BLE001, S112
                            continue
                else:
                    # scope == "once" — single receipt.
                    if not receipt_path.exists():
                        revoke_span.set_attribute("kosmos.consent.revoke_error", "not_found")
                        revoke_span.set_status(Status(StatusCode.ERROR, "not_found"))
                        await _emit_response(ok=False, error="not_found")
                        return
                    target_paths = [receipt_path]

                if not target_paths:
                    # Nothing to revoke — either empty session or single path already handled.
                    revoke_span.set_attribute("kosmos.consent.revoke_error", "already_revoked")
                    revoke_span.set_status(Status(StatusCode.ERROR, "already_revoked"))
                    await _emit_response(ok=False, error="already_revoked")
                    return

                # Revoke each target receipt atomically.
                revoked_at_ts = _utcnow()
                last_record_hash: str | None = None
                any_error = False
                for target_path in target_paths:
                    try:
                        raw = target_path.read_text(encoding="utf-8")
                        data = _json_revoke.loads(raw)
                        if data.get("revoked_at") and scope != "session-all":
                            # Single-receipt revoke on already-revoked receipt.
                            revoke_span.set_attribute(
                                "kosmos.consent.revoke_error",
                                "already_revoked",
                            )
                            revoke_span.set_status(Status(StatusCode.ERROR, "already_revoked"))
                            await _emit_response(ok=False, error="already_revoked")
                            return
                        if data.get("revoked_at"):
                            # session-all: skip already-revoked receipts silently.
                            continue

                        data["revoked_at"] = revoked_at_ts
                        if reason:
                            data["revoke_reason"] = reason

                        # Atomic write: write to temp file then rename.
                        updated_json = _json_revoke.dumps(data, ensure_ascii=False, indent=2)
                        fd, tmp_path_str = _tempfile.mkstemp(
                            dir=str(consent_dir), suffix=".tmp", prefix="rcpt_"
                        )
                        try:
                            with _os_revoke.fdopen(fd, "w", encoding="utf-8") as fh:
                                fh.write(updated_json)
                            _os_revoke.replace(tmp_path_str, str(target_path))
                        except Exception:
                            _os_revoke.unlink(tmp_path_str)
                            raise

                        # Audit-4 P0-3 — append withdraw record to the canonical
                        # Spec 033 PIPA ledger via kosmos.permissions.ledger.
                        # Replaces the prior ad-hoc unsealed hashlib path:
                        # this call computes prev_hash from the prior record,
                        # SHA-256 record_hash over canonical JCS, and seals
                        # with HMAC-SHA-256 under the key_id from registry.json.
                        target_receipt_id = str(data.get("receipt_id", target_path.stem))
                        target_tool_id = str(data.get("tool_id", "unknown"))
                        withdraw_args: dict[str, object] = {
                            "scope_receipt_id": target_receipt_id,
                            "scope": scope,
                            "session_id": session_id,
                        }
                        if reason:
                            withdraw_args["reason"] = reason
                        withdraw_digest = _compute_action_digest(
                            target_tool_id,
                            withdraw_args,
                            _generate_nonce(),
                        )
                        withdraw_record = _ledger_append_withdraw(
                            tool_id=target_tool_id,
                            mode="default",
                            granted=False,
                            action_digest=withdraw_digest,
                            action="withdraw",
                            scope_receipt_id=target_receipt_id,
                            withdrawn_at=_dt_revoke.fromisoformat(
                                revoked_at_ts.replace("Z", "+00:00")
                            )
                            if revoked_at_ts.endswith("Z")
                            else _dt_revoke.fromisoformat(revoked_at_ts),
                            session_id=session_id,
                            correlation_id=frame.correlation_id,
                            ledger_path=_kosmos_settings_revoke.permission_ledger_path,
                            key_path=_kosmos_settings_revoke.permission_key_path,
                            key_registry_path=(
                                _kosmos_settings_revoke.permission_key_registry_path
                            ),
                        )
                        record_hash = withdraw_record.record_hash
                        last_record_hash = record_hash

                        revoke_span.set_attribute("kosmos.consent.record_hash", record_hash)
                        logger.debug(
                            "consent_revoke: revoked %s sealed_hash=%s seq=%d",
                            target_path.name,
                            record_hash[:16],
                            withdraw_record.sequence,
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("consent_revoke: io_error on %s: %s", target_path.name, exc)
                        any_error = True

                if any_error and last_record_hash is None:
                    revoke_span.set_status(Status(StatusCode.ERROR, "io_error"))
                    await _emit_response(ok=False, error="io_error")
                    return

                revoke_span.set_status(Status(StatusCode.OK))
                await _emit_response(
                    ok=True,
                    revoked_at=revoked_at_ts,
                    record_hash=last_record_hash,
                )

        on_frame = _handle_frame

    # Spec 1978 T081 / ADR-0004 — root span ``kosmos.session`` covers the
    # entire stdio session lifetime. All inbound/outbound frame spans
    # (kosmos.ipc.frame), LLM chat spans, tool dispatch spans, and
    # permission spans are nested under this root via OTEL implicit
    # context propagation. Closes at session exit (graceful shutdown
    # path or session_event{event=exit}).
    with _tracer.start_as_current_span("kosmos.session") as _session_span:
        _session_span.set_attribute("kosmos.session.id", sid)
        _session_span.set_attribute("kosmos.ipc.handler_mode", _handler_mode)

        # Run reader loop concurrently with shutdown watcher
        reader_task = asyncio.create_task(
            _reader_loop(stdin_reader, on_frame, sid),
            name="ipc-reader",
        )
        shutdown_task = asyncio.create_task(_shutdown.wait(), name="ipc-shutdown")

        done, pending = await asyncio.wait(
            {reader_task, shutdown_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Record which task completed first so post-mortem traces show
        # whether the session ended on stdin EOF (reader_task) vs SIGTERM /
        # session_event{event=exit} (shutdown_task).
        if reader_task in done:
            _session_span.set_attribute("kosmos.session.exit_reason", "stdin_closed")
        elif shutdown_task in done:
            _session_span.set_attribute("kosmos.session.exit_reason", "shutdown_signal")

        # Cancel whatever is still running
        for task in pending:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

        for task in list(locals().get("_background_tasks", set())):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

        # Cancel the stdin feed task too — its awaiting coroutine winds
        # down so finally runs feed_eof() (Codex P1, PR #2111). The blocked
        # readline() thread keeps running but asyncio.run()'s
        # shutdown_default_executor step bounds the wait at process exit.
        _stdin_feed_handle.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await _stdin_feed_handle

        # Emit exit frame and flush
        try:
            await _emit_exit_frame(sid)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to emit exit frame: %s", exc)

        logger.info("IPC stdio loop exited cleanly — session_id=%s", sid)


__all__ = [
    "run",
    "write_frame",
]
