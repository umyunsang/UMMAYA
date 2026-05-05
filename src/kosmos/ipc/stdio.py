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
import signal
import sys
import time
import uuid
from collections.abc import Callable
from datetime import UTC
from types import FrameType
from typing import TYPE_CHECKING, Any, Literal, cast

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
_COORD_INPUT_FIELDS: frozenset[str] = frozenset({
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
})
_ADMCD_INPUT_FIELDS: frozenset[str] = frozenset({
    "adm_cd",
    "siGunGuCd",
    "sgg_cd",
    "h_code",
    "b_code",
})


def _check_chain_prerequisite(
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
    params = args_obj.get("params") if isinstance(args_obj.get("params"), dict) else {}

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
        role = getattr(m, "role", None) or (
            m.get("role") if isinstance(m, dict) else None
        )
        if role != "assistant":
            continue
        tool_calls = getattr(m, "tool_calls", None) or (
            m.get("tool_calls") if isinstance(m, dict) else None
        )
        if tool_calls:
            for tc in tool_calls:
                call_fn = (
                    getattr(getattr(tc, "function", None), "name", None)
                    or (
                        tc.get("function", {}).get("name")
                        if isinstance(tc, dict)
                        else None
                    )
                )
                if call_fn == "resolve_location":
                    return None
        content = getattr(m, "content", None) or (
            m.get("content") if isinstance(m, dict) else None
        )
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
# Citizen query keywords that signal "the LLM needs to call a follow-up
# adapter (lookup mode='fetch') after resolve_location returns coordinates
# or admcd". Without the follow-up, LLM fabricates the data from parametric
# memory (the donga-univ-poi-bug 1-day-newer regression: snap-001 captured
# 4.7°C drift / 61%p humidity drift between LLM-claimed values and the raw
# KMA observation).  This list is the policy hint — adapter_id is decided
# by BM25 from the available_adapters suffix.
_FOLLOWUP_REQUIRED_KEYWORDS_KO: frozenset[str] = frozenset({
    "날씨", "기온", "온도", "습도", "강수", "비", "눈", "바람", "풍속",
    "예보", "특보", "폭염", "한파", "황사", "미세먼지",
    "병원", "응급실", "응급의료", "의료기관", "약국",
    "사고", "교통사고", "위험", "스쿨존", "어린이보호구역",
    "구급", "119", "소방서", "재해",
    "복지", "급여", "보조금", "지원금",
})
_FOLLOWUP_REQUIRED_KEYWORDS_EN: frozenset[str] = frozenset({
    "weather", "temperature", "humidity", "rainfall", "wind",
    "forecast", "warning",
    "hospital", "er", "emergency", "pharmacy",
    "accident", "traffic", "hazard",
    "ambulance", "fire", "disaster",
    "welfare", "benefit", "subsidy",
})


def _query_implies_followup_lookup(user_query: str) -> bool:
    """Return True when the citizen query semantics require a follow-up
    ``lookup(mode='fetch', tool_id=...)`` after ``resolve_location`` resolves
    coordinates.

    G-class chain enforcement: the integration-verification capture
    ``snap-001-01-kma-now`` showed K-EXAONE calling ``resolve_location`` twice
    and then producing a fabricated weather answer (16°C / 84% humidity vs
    raw KMA 20.7°C / 23%) without ever invoking ``lookup(kma_current_observation)``.
    The fabrication mode is deterministic when the citizen query mentions a
    location-bound observable (weather / hospital / accident / 119) — no
    adapter shipped today answers those purely from coordinates.
    """
    if not user_query:
        return False
    q = user_query.lower()
    for kw in _FOLLOWUP_REQUIRED_KEYWORDS_KO:
        if kw in user_query:  # Korean — case is irrelevant
            return True
    for kw in _FOLLOWUP_REQUIRED_KEYWORDS_EN:
        if kw in q:
            return True
    return False


def _check_resolve_terminated_without_followup(
    llm_messages: list[Any],
    user_query: str,
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
    if not _query_implies_followup_lookup(user_query):
        return None

    saw_resolve_result = False
    saw_followup_lookup = False
    for m in llm_messages:
        role = getattr(m, "role", None) or (
            m.get("role") if isinstance(m, dict) else None
        )
        # Detect resolve_location tool result message
        if role == "tool":
            name = getattr(m, "name", None) or (
                m.get("name") if isinstance(m, dict) else None
            )
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
            call_fn = (
                getattr(getattr(tc, "function", None), "name", None)
                or (
                    tc.get("function", {}).get("name")
                    if isinstance(tc, dict)
                    else None
                )
            )
            if call_fn != "lookup":
                continue
            # Inspect arguments to confirm fetch-mode against an adapter.
            raw_args = (
                getattr(getattr(tc, "function", None), "arguments", None)
                or (
                    tc.get("function", {}).get("arguments")
                    if isinstance(tc, dict)
                    else None
                )
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
                    logging.Formatter(
                        "%(asctime)s %(levelname)s %(name)s %(message)s"
                    )
                )
                _root.addHandler(_fh)
                _root.setLevel(min(_root.level or logging.INFO, logging.INFO))
                logger.info(
                    "spec-multi-turn-contamination: attached FileHandler -> %s",
                    _log_path,
                )
        except Exception:  # noqa: BLE001 — telemetry must never raise
            sys.stderr.write(
                f"[KOSMOS BACKEND] failed to attach log file {_log_path}\n"
            )

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
        for c in candidates:
            hint = (c.search_hint or "").strip()
            if len(hint) > 90:
                hint = hint[:87] + "..."
            lines.append(f"- {c.tool_id} [{c.score:.2f}] — {hint or '(설명 없음)'}")
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
        lines.append("</available_adapters>")
        return "\n".join(lines)

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
    # an existing session-grant. Spec 033 Layer 1 (L1) exempts verify/lookup/
    # resolve_location (read-only, public-tier); submit/subscribe are side-
    # effecting (Layer 2/3) and always enter the bridge.
    #
    # Epic #2077 T010 (FR-003) — single-source-of-truth migration: read the
    # gated set from ``kosmos.primitives.GATED_PRIMITIVES`` rather than
    # duplicating the literal set here. The local alias is preserved for
    # downstream call-site brevity (and to keep diff churn minimal in this
    # epic) but the literal set is no longer maintained in this module.
    from kosmos.primitives import (
        GATED_PRIMITIVES as _PERMISSION_GATED_PRIMITIVES,  # noqa: PLC0415, N811
    )

    async def _check_permission_gate(
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

        if fname not in _PERMISSION_GATED_PRIMITIVES:
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
        _PRIM_RISK: dict[str, str] = {  # noqa: N806
            "verify": "low",
            "submit": "high",
            "subscribe": "medium",
        }
        _PRIM_KO: dict[str, str] = {  # noqa: N806
            "verify": "신원 확인을 위해 인증 위임을 요청합니다.",
            "submit": "정부 API에 데이터를 제출합니다. 이 작업은 되돌릴 수 없습니다.",
            "subscribe": "공공 데이터 스트림을 구독합니다.",
        }
        _PRIM_EN: dict[str, str] = {  # noqa: N806
            "verify": "Request identity delegation for verification.",
            "submit": "Submit data to a government API. This action is irreversible.",
            "subscribe": "Subscribe to a public data stream.",
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

                    _deny_args = {
                        k: v
                        for k, v in args_obj.items()
                        if k != "delegation_context"
                    }
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
                    logger.warning(
                        "permission: ledger.append(deny) failed: %s", exc
                    )
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
                tool_key_for_cache = (
                    f"{fname}:{args_obj.get('tool_id', fname)}"
                )
                _session_grants.setdefault(session_id, set()).add(
                    tool_key_for_cache
                )
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

                _ledger_args = {
                    k: v
                    for k, v in args_obj.items()
                    if k != "delegation_context"
                }
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
            from kosmos.ipc.frame_schema import PermissionResponseFrame as _PRF  # noqa: PLC0415

            try:
                await write_frame(
                    _PRF(
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
                logger.debug(
                    "permission: emitted receipt echo (receipt_id=%s)", receipt_id
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("permission: failed to emit receipt echo: %s", exc)

            return True

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
                    family_hint = (
                        resolve_family(tool_id)
                        or str(args_obj.get("family_hint") or args_obj.get("family") or "")
                    )
                    session_ctx = cast("dict[str, object]", args_obj.get("session_context") or {})
                    raw = await verify(family_hint=family_hint, session_context=session_ctx)
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

                    raw = await submit(
                        tool_id=str(args_obj.get("tool_id", "")),
                        params=cast("dict[str, object]", args_obj.get("params") or {}),
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
                _current_span.set_attribute(
                    "kosmos.chat.turn_index", _diag_turn_idx
                )
        except Exception:  # noqa: BLE001 — telemetry must never raise
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
        registry = _ensure_tool_registry()
        from kosmos.primitives import PRIMITIVE_REGISTRY  # noqa: PLC0415

        backend_tools_raw = [
            t.to_openai_tool()
            for t in registry.core_tools()  # type: ignore[attr-defined]
            if t.ministry == "KOSMOS" and t.id in PRIMITIVE_REGISTRY
        ]
        backend_tool_names = {
            r.get("function", {}).get("name")  # type: ignore[union-attr]
            for r in backend_tools_raw
            if isinstance(r, dict)
        }
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
                augmented_system
                + f"\n\n## Current session context\n\n"
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
            if force_resolve_location_next_turn:
                stream_tool_choice = {
                    "type": "function",
                    "function": {"name": "resolve_location"},
                }
                logger.warning(
                    "_handle_chat_request: forcing tool_choice=resolve_location for "
                    "turn %d (chain gate previously rejected a coord-input call)",
                    _turn,
                )
            try:
                async for event in client.stream(  # type: ignore[attr-defined]
                    messages=llm_messages,
                    tools=llm_tools or None,
                    temperature=frame.temperature,
                    top_p=frame.top_p,
                    max_tokens=frame.max_tokens,
                    tool_choice=stream_tool_choice,
                ):
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
                                        "[REASONING_PREVIEW] turn=%d "
                                        "first1024=%s",
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
                # with a coord/admcd-input lookup despite the citizen query
                # demanding one (weather / hospital / accident / 119 /
                # welfare). The donga-univ-poi-bug snap-001-01-kma-now
                # capture (2026-05-04) showed K-EXAONE producing 16°C / 84%
                # humidity by parametric memory — 4.7°C / 61%p drift versus
                # the raw KMA observation — because the agentic loop allowed
                # the answer turn to fire without a tool result in scope.
                # Inject a synthetic chain-recovery tool_result and continue
                # the loop so the next turn produces the missing lookup call.
                chain_followup_msg = _check_resolve_terminated_without_followup(
                    llm_messages, latest_user_utt
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

                merged_prose = "".join(buffered_visible)
                if merged_prose:
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
            assistant_tool_calls: list[LLMToolCall] = []
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
                try:
                    args_obj = _json.loads(slot["args"]) if slot["args"] else {}
                except _json.JSONDecodeError:
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
                    err_envelope = ToolResultEnvelope(
                        kind=cast("Any", fname),
                        result={
                            "kind": "error",
                            "reason": "chain_prerequisite_missing",
                            "message": chain_error_msg,
                            "retryable": False,
                        },
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

            # If every tool call was rejected (whitelist), terminate.
            # Exception: when the chain gate fired (force flag set) we
            # MUST continue to the next iteration so the forced
            # tool_choice=resolve_location actually gets a chance to run.
            # Returning here would leave the citizen with the chain-error
            # tool_result frame as the only visible output.
            if not issued_calls:
                if force_resolve_location_next_turn:
                    # Synthetic tool_result already injected into
                    # llm_messages; the next loop iteration will fire the
                    # LLM again with tool_choice forced to resolve_location.
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
                else:
                    # ToolResultFrame.envelope is a Pydantic model.
                    envelope = getattr(result, "envelope", None)
                    if envelope is not None and hasattr(envelope, "model_dump"):
                        payload = _json.dumps(
                            envelope.model_dump(),
                            ensure_ascii=False,
                            default=str,
                        )
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

            # Loop back: re-invoke client.stream with extended history.

        # Loop bound exhausted — emit terminal chunk anyway so the TUI
        # un-spins; the model will not be re-invoked beyond the bound.
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
                # Spec 1978 ADR-0001 — tools-aware chat path.
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
                    from kosmos.ipc.frame_schema import ConsentRevokeResponseFrame as _CRRFE  # noqa: PLC0415

                    err_resp = _CRRFE(
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
                    await handle_plugin_op_request(
                        frame,
                        registry=_registry,
                        executor=ToolExecutor(registry=_registry),  # type: ignore[arg-type]
                        write_frame=write_frame,
                        consent_bridge=consent_bridge,
                        session_id=frame.session_id,
                    )
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
                        except Exception:  # noqa: BLE001
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
                            revoke_span.set_attribute("kosmos.consent.revoke_error", "already_revoked")
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
                        target_receipt_id = str(
                            data.get("receipt_id", target_path.stem)
                        )
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

                        revoke_span.set_attribute(
                            "kosmos.consent.record_hash", record_hash
                        )
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
