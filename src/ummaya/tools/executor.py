# SPDX-License-Identifier: Apache-2.0
"""Tool dispatcher for the UMMAYA Tool System module.

Resolves tool calls from the LLM by name, validates input/output against
Pydantic schemas, enforces rate limits, and returns a structured ToolResult.
The executor never raises — all error paths are captured in ToolResult.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Literal

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from pydantic import BaseModel, ValidationError

from ummaya.observability import (
    ERROR_TYPE,
    GEN_AI_OPERATION_NAME,
    GEN_AI_TOOL_CALL_ID,
    GEN_AI_TOOL_NAME,
    GEN_AI_TOOL_TYPE,
    filter_metadata,
)
from ummaya.tools.envelope import make_error_envelope, normalize
from ummaya.tools.errors import (
    EnvelopeNormalizationError,
    LookupErrorReason,
    ToolNotFoundError,
    UmmayaToolError,
)
from ummaya.tools.models import ToolResult
from ummaya.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from ummaya.observability.event_logger import ObservabilityEventLogger
    from ummaya.observability.metrics import MetricsCollector
    from ummaya.recovery.executor import RecoveryExecutor

logger = logging.getLogger(__name__)

_tracer = trace.get_tracer(__name__)

AdapterFn = Callable[[BaseModel], Awaitable[dict[str, Any]]]

_LOOKUP_ENVELOPE_KINDS: frozenset[str] = frozenset(
    {"record", "collection", "timeseries", "error", "search"}
)


def _log_adapter_exception(message: str, tool_id: str, exc: Exception) -> None:
    """Log expected adapter-domain failures without polluting audit logs with tracebacks."""
    if isinstance(exc, UmmayaToolError):
        logger.warning(
            "%s %s raised %s: %s",
            message,
            tool_id,
            type(exc).__name__,
            exc,
        )
        return
    logger.warning(message + " %s raised %s", tool_id, type(exc).__name__, exc_info=True)


def _classify_adapter_exception(exc: Exception) -> tuple[LookupErrorReason, bool]:
    """Map adapter exceptions to (reason, retryable) for the error envelope."""
    import httpx  # noqa: PLC0415

    from ummaya.tools.errors import Layer3GateViolation  # noqa: PLC0415
    from ummaya.tools.kma.projection import KMADomainError  # noqa: PLC0415
    from ummaya.tools.live_proxy import (  # noqa: PLC0415
        LiveAdapterProxyConfigurationError,
    )

    if isinstance(exc, Layer3GateViolation):
        # Programming error: stub handler was reached despite auth-gate — never retry.
        return (LookupErrorReason.upstream_unavailable, False)
    if isinstance(exc, LiveAdapterProxyConfigurationError):
        return (LookupErrorReason.upstream_unavailable, False)
    if isinstance(exc, (ValueError, TypeError, KMADomainError)):
        return (LookupErrorReason.invalid_params, False)
    if isinstance(exc, httpx.TimeoutException):
        return (LookupErrorReason.timeout, True)
    if isinstance(exc, (httpx.HTTPStatusError, httpx.RequestError)):
        return (LookupErrorReason.upstream_unavailable, True)
    return (LookupErrorReason.upstream_unavailable, True)


def _is_lookup_envelope_dict(value: dict[str, Any]) -> bool:
    """Return True when an adapter already emitted a LookupOutput-shaped envelope."""
    kind = value.get("kind")
    return isinstance(kind, str) and kind in _LOOKUP_ENVELOPE_KINDS


class ToolExecutor:
    """Dispatch LLM tool calls through validation, rate-limiting, and execution.

    The dispatch pipeline (in order):
    1. Lookup tool in registry.
    2. Parse and validate JSON arguments against input_schema.
    3. Verify adapter exists.
    4. Check and record rate limit.
    5. If RecoveryExecutor is present: delegate for retry / circuit-breaker /
       cache.  If absent: call adapter directly.
    6. Validate adapter output against output_schema.
    7. Return ToolResult(success=True, data=...).

    Any step failure returns ToolResult(success=False, ...) with an
    appropriate error_type. The executor itself never raises.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        recovery_executor: RecoveryExecutor | None = None,
        metrics: MetricsCollector | None = None,
        event_logger: ObservabilityEventLogger | None = None,
        live_adapter_mode: Literal["auto", "proxy", "direct"] | None = None,
    ) -> None:
        """Initialize the executor with a ToolRegistry.

        Args:
            registry: The tool registry used for lookup and rate-limit access.
            recovery_executor: Optional RecoveryExecutor providing Layer 6
                error recovery (retry, circuit breaker, cache fallback).
                When absent, the adapter is called directly (backward-compatible).
            metrics: Optional MetricsCollector for recording tool call telemetry.
                When absent, metrics instrumentation is skipped (backward-compatible).
            event_logger: Optional ObservabilityEventLogger for structured events.
                When absent, event emission is skipped (backward-compatible).
            live_adapter_mode: Optional route override for live public-API
                adapters. Gateway processes set this to ``"direct"`` so an
                inbound proxy request cannot recurse into the proxy client.
        """
        self._registry = registry
        self._adapters: dict[str, AdapterFn] = {}
        self._recovery_executor = recovery_executor
        self._metrics: MetricsCollector | None = metrics
        self._event_logger: ObservabilityEventLogger | None = event_logger
        self._live_adapter_mode = live_adapter_mode

    def register_adapter(self, tool_id: str, adapter: AdapterFn) -> None:
        """Register an async adapter function for a tool.

        Args:
            tool_id: The stable snake_case tool identifier.
            adapter: Async callable accepting a validated Pydantic model instance
                     and returning a plain dict matching output_schema.
        """
        self._adapters[tool_id] = adapter
        logger.debug("Registered adapter for tool: %s", tool_id)

    async def invoke_raw(  # noqa: C901
        self,
        tool_id: str,
        params: dict[str, object],
        request_id: str,
        *,
        session_identity: object | None = None,
    ) -> object:
        """Invoke an adapter without forcing the ``find`` LookupOutput envelope.

        ``find`` adapters use :meth:`invoke`, which normalizes every handler
        response into the 5-variant LookupOutput envelope. Other primitives
        (notably ``locate``) have their own result unions, but should still use
        the same central registry, auth gate, input validation, rate limit, and
        ingress-safety path. This method is that shared adapter execution path.
        """

        start_ns = time.monotonic_ns()

        def _elapsed() -> int:
            return (time.monotonic_ns() - start_ns) // 1_000_000

        try:
            tool = self._registry.find(tool_id)
        except ToolNotFoundError:
            logger.warning("invoke_raw: tool not found: %s", tool_id)
            return make_error_envelope(
                tool_id=tool_id,
                reason=LookupErrorReason.unknown_tool,
                message=f"No tool registered with id {tool_id!r}.",
                request_id=request_id,
                elapsed_ms=_elapsed(),
                retryable=False,
            )

        gate = tool.policy.citizen_facing_gate if tool.policy is not None else "login"
        if gate != "read-only" and session_identity is None:
            logger.info("invoke_raw: auth_required short-circuit for tool %s", tool_id)
            return make_error_envelope(
                tool_id=tool_id,
                reason=LookupErrorReason.auth_required,
                message=f"Tool {tool_id!r} requires authentication. Provide a session identity.",
                request_id=request_id,
                elapsed_ms=_elapsed(),
                retryable=False,
            )

        adapter = self._adapters.get(tool_id)
        if adapter is None:
            logger.warning("invoke_raw: no adapter registered for tool: %s", tool_id)
            return make_error_envelope(
                tool_id=tool_id,
                reason=LookupErrorReason.unknown_tool,
                message=f"No adapter registered for tool {tool_id!r}.",
                request_id=request_id,
                elapsed_ms=_elapsed(),
                retryable=False,
            )

        try:
            validated_input = tool.input_schema.model_validate(params)
        except ValidationError as exc:
            field_paths = [".".join(str(p) for p in e["loc"]) for e in exc.errors()]
            field_summary = ", ".join(field_paths) if field_paths else "(no field info)"
            return make_error_envelope(
                tool_id=tool_id,
                reason=LookupErrorReason.invalid_params,
                message=(
                    f"Invalid parameters for tool {tool_id!r}. "
                    f"Missing or invalid fields: {field_summary}. "
                    "Read this adapter's input_schema in <available_adapters> and retry "
                    "with the exact field names."
                ),
                request_id=request_id,
                elapsed_ms=_elapsed(),
                retryable=False,
            )

        rate_limiter = self._registry.get_rate_limiter(tool_id)
        if not rate_limiter.check():
            return make_error_envelope(
                tool_id=tool_id,
                reason=LookupErrorReason.upstream_unavailable,
                message=f"Rate limit exceeded for tool {tool_id!r}.",
                request_id=request_id,
                elapsed_ms=_elapsed(),
                retryable=True,
            )

        try:
            from ummaya.tools.live_proxy import (  # noqa: PLC0415
                invoke_live_adapter_proxy,
                should_use_live_adapter_proxy,
            )

            rate_limiter.record()
            if should_use_live_adapter_proxy(tool, mode_override=self._live_adapter_mode):
                raw_output = await invoke_live_adapter_proxy(
                    tool=tool,
                    params=validated_input.model_dump(mode="json"),
                    request_id=request_id,
                    session_identity=session_identity,
                )
            else:
                raw_output = await adapter(validated_input)
        except Exception as exc:
            _log_adapter_exception("invoke_raw: adapter", tool_id, exc)
            reason, retryable = _classify_adapter_exception(exc)
            return make_error_envelope(
                tool_id=tool_id,
                reason=reason,
                message=(
                    f"Adapter '{tool_id}' raised {type(exc).__name__}: {str(exc)[:240]}. "
                    "Do NOT fabricate a response from prior knowledge; use another "
                    "appropriate adapter or explain that the lookup failed."
                ),
                request_id=request_id,
                elapsed_ms=_elapsed(),
                retryable=retryable,
            )

        from ummaya.safety._ingress import apply_ingress_safety  # noqa: PLC0415
        from ummaya.safety._span import emit_safety_event  # noqa: PLC0415
        from ummaya.settings import settings  # noqa: PLC0415

        scan_dict: dict[str, Any] | None = None
        if isinstance(raw_output, BaseModel):
            scan_dict = raw_output.model_dump(mode="python")
        elif isinstance(raw_output, dict):
            scan_dict = raw_output

        if scan_dict is not None:
            sanitized, safety_event = apply_ingress_safety(scan_dict, settings.safety)
            if safety_event is not None:
                emit_safety_event(safety_event)
            if sanitized is None:
                return make_error_envelope(
                    tool_id=tool_id,
                    reason=LookupErrorReason.injection_detected,
                    message="Tool output blocked by injection detector.",
                    request_id=request_id,
                    elapsed_ms=_elapsed(),
                    retryable=False,
                )
            if isinstance(raw_output, BaseModel):
                return sanitized
            return sanitized

        return raw_output

    async def invoke(  # noqa: C901
        self,
        tool_id: str,
        params: dict[str, object],
        request_id: str,
        *,
        session_identity: object | None = None,
    ) -> object:
        """Invoke an adapter handler through the Layer 3 auth-gate + envelope normalizer.

        This is the typed invocation path for ``find`` adapter calls.  The
        legacy ``dispatch()`` path remains for backward compatibility with
        existing callers that pass JSON strings.

        Layer 3 short-circuit (FR-025, FR-026):
            If ``tool.policy.citizen_facing_gate`` is not 'read-only' and
            ``session_identity`` is None, return ``LookupError(reason="auth_required")``
            with ZERO upstream calls.  This check is unconditional — no bypass, no test shortcut.
            Fail-closed when policy is None (pre-migration adapter).

        Args:
            tool_id: Stable adapter identifier.
            params: Raw parameter dict (validated against adapter input_schema).
            request_id: UUID string for tracing (injected into meta).
            session_identity: Caller identity token.  None = unauthenticated.

        Returns:
            A validated LookupOutput instance (LookupRecord / LookupCollection /
            LookupTimeseries / LookupError).
        """
        import time  # noqa: PLC0415

        from pydantic import ValidationError  # noqa: PLC0415

        from ummaya.tools.envelope import normalize  # noqa: PLC0415
        from ummaya.tools.errors import EnvelopeNormalizationError  # noqa: PLC0415

        start_ns = time.monotonic_ns()

        def _elapsed() -> int:
            return (time.monotonic_ns() - start_ns) // 1_000_000

        # --- Tool lookup -------------------------------------------------------
        try:
            tool = self._registry.find(tool_id)
        except ToolNotFoundError:
            logger.warning("invoke: tool not found: %s", tool_id)
            return make_error_envelope(
                tool_id=tool_id,
                reason=LookupErrorReason.unknown_tool,
                message=f"No tool registered with id {tool_id!r}.",
                request_id=request_id,
                elapsed_ms=_elapsed(),
                retryable=False,
            )

        # --- Layer 3 auth-gate (FR-025, FR-026) — UNCONDITIONAL ----------------
        # Epic δ #2295: auth-gate based on policy.citizen_facing_gate.
        # read-only = public access; login/action/sign/submit = auth required.
        # Fail-closed when policy is None (pre-migration adapter).
        _gate = tool.policy.citizen_facing_gate if tool.policy is not None else "login"
        if _gate != "read-only" and session_identity is None:
            logger.info(
                "invoke: auth_required short-circuit for tool %s (zero upstream calls)",
                tool_id,
            )
            return make_error_envelope(
                tool_id=tool_id,
                reason=LookupErrorReason.auth_required,
                message=(
                    f"Tool {tool_id!r} requires authentication. "
                    "Provide a session identity to proceed."
                ),
                request_id=request_id,
                elapsed_ms=_elapsed(),
                retryable=False,
            )

        # --- Adapter lookup -----------------------------------------------------
        adapter = self._adapters.get(tool_id)
        if adapter is None:
            logger.warning("invoke: no adapter registered for tool: %s", tool_id)
            return make_error_envelope(
                tool_id=tool_id,
                reason=LookupErrorReason.unknown_tool,
                message=f"No adapter registered for tool {tool_id!r}.",
                request_id=request_id,
                elapsed_ms=_elapsed(),
                retryable=False,
            )

        # --- Input validation ---------------------------------------------------
        try:
            validated_input = tool.input_schema.model_validate(params)
        except ValidationError as exc:
            field_paths = [".".join(str(p) for p in e["loc"]) for e in exc.errors()]
            logger.warning(
                "invoke: input validation failed for %s (%d errors, fields: %s)",
                tool_id,
                exc.error_count(),
                ", ".join(field_paths),
            )
            # Build a chain-recovery message that names the missing fields and,
            # when the missing fields look like coordinates / admin codes /
            # grid points, points the LLM at resolve_location explicitly.
            # Generic "Invalid parameters" silently failed K-EXAONE — the
            # model interpreted it as "tool unavailable" and either
            # hallucinated coordinates or refused to use the tool. Naming
            # the missing fields + the recovery action keeps the agentic
            # loop on a deterministic chain instead of guessing.
            coord_fields = {
                "xPos",
                "yPos",
                "lat",
                "lon",
                "latitude",
                "longitude",
                "origin_lat",
                "origin_lon",
                "nx",
                "ny",
                "x",
                "y",
            }
            admcd_fields = {"adm_cd", "siGunGuCd", "siGunGu_cd", "sgg_cd", "h_code", "b_code"}
            need_resolve = any(
                fp.split(".")[-1] in coord_fields or fp.split(".")[-1] in admcd_fields
                for fp in field_paths
            )
            recovery_hint = ""
            if tool_id == "nmc_emergency_search":
                recovery_hint = (
                    " LOCATE FIRST: call locate with a locate adapter from"
                    " <available_adapters>. For a named place use"
                    " locate({tool_id:'kakao_keyword_search', params:{query:'<지역명>'}}),"
                    " then call locate({tool_id:'kakao_coord_to_region',"
                    " params:{lat:<lat>, lon:<lon>}}). Re-invoke this tool with"
                    " params {mode:'region', q0:region.region_1depth_name,"
                    " q1:region.region_2depth_name, origin_lat:<lat>, origin_lon:<lon>,"
                    " limit:<N>}. Do NOT guess coordinates or invent NMC filters such as QZ."
                )
            elif need_resolve:
                recovery_hint = (
                    " LOCATE FIRST: call locate with the appropriate locate adapter"
                    " from <available_adapters> to obtain the missing coordinates /"
                    " admin code, then re-invoke this tool with the returned values."
                    " Do NOT guess coordinates or codes from prior knowledge."
                )
            field_summary = ", ".join(field_paths) if field_paths else "(no field info)"
            return make_error_envelope(
                tool_id=tool_id,
                reason=LookupErrorReason.invalid_params,
                message=(
                    f"Invalid parameters for tool {tool_id!r}. "
                    f"Missing or invalid fields: {field_summary}.{recovery_hint}"
                ),
                request_id=request_id,
                elapsed_ms=_elapsed(),
                retryable=False,
            )

        # --- Handler invocation -------------------------------------------------
        # Epic #2766 issue C — HIRA / KMA / KOROAD timeout diagnostics.
        # Annotate the current execute_tool span with `ummaya.tool.stage`
        # transitions so OTLP / Langfuse traces show whether latency comes
        # from `find` (registry+gate, sub-millisecond), `fetch` (HTTP RTT),
        # or `parse` (envelope normalisation). Citizens experiencing slow
        # turns on long-tail HIRA queries can now see where the time went.
        from opentelemetry import trace as _otel_trace  # noqa: PLC0415

        _stage_span = _otel_trace.get_current_span()
        _stage_span.set_attribute("ummaya.tool.stage", "fetch")
        _stage_fetch_start = time.monotonic_ns()
        try:
            from ummaya.tools.live_proxy import (  # noqa: PLC0415
                invoke_live_adapter_proxy,
                should_use_live_adapter_proxy,
            )

            if should_use_live_adapter_proxy(tool, mode_override=self._live_adapter_mode):
                _stage_span.set_attribute("ummaya.tool.route", "proxy")
                raw_output = await invoke_live_adapter_proxy(
                    tool=tool,
                    params=validated_input.model_dump(mode="json"),
                    request_id=request_id,
                    session_identity=session_identity,
                )
            else:
                _stage_span.set_attribute("ummaya.tool.route", "direct")
                raw_output = await adapter(validated_input)
        except Exception as exc:
            _stage_span.set_attribute("ummaya.tool.stage", "fetch_failed")
            _stage_span.set_attribute(
                "ummaya.tool.fetch_ms",
                (time.monotonic_ns() - _stage_fetch_start) // 1_000_000,
            )
            _log_adapter_exception("invoke: adapter", tool_id, exc)
            reason, retryable = _classify_adapter_exception(exc)
            # Anthropic tool-use guidance (https://platform.claude.com/docs/en/
            # agents-and-tools/tool-use/handle-tool-calls#handling-errors-with-is_error):
            # "Write instructive error messages. Instead of generic errors like
            #  'failed', include what went wrong and what Claude should try
            #  next." The previous "Tool execution failed." string was a
            # documented citizen-mis-info trigger (2026-05-04) — K-EXAONE
            # treated the opaque message as "tool unavailable" and fabricated
            # a fire-station statistic from prior knowledge. Surface the
            # concrete exception class + message so the LLM has enough context
            # to either retry, switch tools, or refuse with a citation.
            _exc_summary = f"{type(exc).__name__}: {str(exc)[:240]}"
            return make_error_envelope(
                tool_id=tool_id,
                reason=reason,
                message=(
                    f"Adapter '{tool_id}' raised an exception during upstream call. "
                    f"Detail: {_exc_summary}. "
                    "Do NOT fabricate a response from prior knowledge — tell the citizen "
                    "the lookup failed, cite the official agency channel, and offer to "
                    "retry or try a different tool."
                ),
                request_id=request_id,
                elapsed_ms=_elapsed(),
                retryable=retryable,
            )
        _stage_span.set_attribute(
            "ummaya.tool.fetch_ms",
            (time.monotonic_ns() - _stage_fetch_start) // 1_000_000,
        )
        _stage_span.set_attribute("ummaya.tool.stage", "parse")

        # --- Epic #466 Layers A+C: ingress safety (FR-006, FR-013) --------------
        # Detector first, then redactor. BaseModel outputs are dumped to dict so
        # the scanners see every field value — a trusted schema does not imply
        # trusted data (adapter responses can still carry PII or injected
        # directives from upstream). The sanitized dict is handed back to
        # normalize(), which accepts dicts equivalently to BaseModels.
        from ummaya.safety._ingress import apply_ingress_safety  # noqa: PLC0415
        from ummaya.safety._span import emit_safety_event  # noqa: PLC0415
        from ummaya.settings import settings  # noqa: PLC0415

        scan_dict: dict[str, Any] | None = None
        if isinstance(raw_output, BaseModel):
            scan_dict = raw_output.model_dump(mode="python")
        elif isinstance(raw_output, dict):
            scan_dict = raw_output

        if scan_dict is not None:
            sanitized, safety_event = apply_ingress_safety(scan_dict, settings.safety)
            if safety_event is not None:
                emit_safety_event(safety_event)
            if sanitized is None:
                # Injection detector blocked — short-circuit via error envelope.
                return make_error_envelope(
                    tool_id=tool_id,
                    reason=LookupErrorReason.injection_detected,
                    message="Tool output blocked by injection detector.",
                    request_id=request_id,
                    elapsed_ms=_elapsed(),
                    retryable=False,
                )
            raw_output = sanitized

        # --- Envelope normalisation (FR-015, FR-014) ----------------------------
        try:
            return normalize(
                output=raw_output,
                tool=tool,
                request_id=request_id,
                elapsed_ms=_elapsed(),
            )
        except EnvelopeNormalizationError as exc:
            logger.error("invoke: envelope normalisation failed for %s: %s", tool_id, exc)
            # Anthropic tool-use guidance — instructive error messages (see
            # adapter-exception block above for the full citation). The old
            # "Response processing failed." string was the second documented
            # citizen-mis-info trigger (2026-05-04 MOHW welfare fabrication
            # of 12 services + bokjiro.go.kr URLs), because K-EXAONE could
            # not distinguish "envelope mismatch" from "no data available"
            # and defaulted to the catalog it had seen during training.
            _exc_detail = str(exc)[:240]
            return make_error_envelope(
                tool_id=tool_id,
                reason=LookupErrorReason.upstream_unavailable,
                message=(
                    f"Adapter '{tool_id}' returned a response that did not match the "
                    f"expected envelope schema. Detail: {_exc_detail}. "
                    "Do NOT fabricate a response from prior knowledge — tell the citizen "
                    "the data could not be parsed, cite the official agency channel, and "
                    "offer to retry or try a different tool."
                ),
                request_id=request_id,
                elapsed_ms=_elapsed(),
                retryable=False,
            )

    async def dispatch(  # noqa: C901
        self,
        tool_name: str,
        arguments_json: str,
        tool_call_id: str | None = None,
    ) -> ToolResult:
        """Execute a tool call end-to-end.

        Args:
            tool_name: The tool identifier to look up in the registry.
            arguments_json: JSON string of the tool arguments.
            tool_call_id: Optional LLM-assigned tool call identifier; when
                provided it is attached to the OTel span as
                ``gen_ai.tool.call.id`` (contract § Span 3).

        Returns:
            ToolResult with success=True and data on success, or
            success=False with error/error_type on any failure.
        """
        with _tracer.start_as_current_span(f"execute_tool {tool_name}") as span:
            span.set_attribute(GEN_AI_OPERATION_NAME, "execute_tool")
            span.set_attribute(GEN_AI_TOOL_NAME, tool_name)
            span.set_attribute(GEN_AI_TOOL_TYPE, "function")
            if tool_call_id is not None:
                span.set_attribute(GEN_AI_TOOL_CALL_ID, tool_call_id)

            dispatch_start = time.monotonic()
            self._metrics_increment("tool.call_count", tool_name)
            _final_result: ToolResult | None = None

            try:
                # Step 1: Lookup tool
                try:
                    tool = self._registry.find(tool_name)
                except ToolNotFoundError as exc:
                    logger.warning("Tool not found: %s", tool_name)
                    self._metrics_increment("tool.error_count", tool_name)
                    _final_result = ToolResult(
                        tool_id=tool_name,
                        success=False,
                        error=str(exc),
                        error_type="not_found",
                    )
                    return _final_result

                # Warn when the legacy dispatch() path is used for auth-required tools.
                # dispatch() has no session_identity parameter, so the auth gate in
                # invoke() can never fire here — flag this for operational visibility.
                _dispatch_gate = (
                    tool.policy.citizen_facing_gate if tool.policy is not None else "login"
                )
                if _dispatch_gate != "read-only":
                    logger.debug(
                        "dispatch() called for auth-required tool %r without auth gate",
                        tool_name,
                    )

                # Step 2: Parse and validate input
                try:
                    raw_args = json.loads(arguments_json)
                    validated_input = tool.input_schema.model_validate(raw_args)
                except (TypeError, json.JSONDecodeError, ValidationError) as exc:
                    # Avoid logging the raw arguments — they may carry user PII
                    # (addresses, names, IDs). Log only length metadata here;
                    # the corrective-hint payload already surfaces the structural
                    # problem to the model.
                    _raw_len = len(arguments_json) if isinstance(arguments_json, str) else 0
                    logger.warning(
                        "Input validation failed for tool %s: %s | raw_args_len=%d",
                        tool_name,
                        exc,
                        _raw_len,
                    )
                    self._metrics_increment("tool.error_count", tool_name)
                    _final_result = ToolResult(
                        tool_id=tool_name,
                        success=False,
                        error=str(exc),
                        error_type="validation",
                    )
                    return _final_result

                # Step 3: Verify adapter exists before consuming a rate-limit slot
                adapter = self._adapters.get(tool_name)
                if adapter is None:
                    logger.warning("No adapter registered for tool: %s", tool_name)
                    self._metrics_increment("tool.error_count", tool_name)
                    _final_result = ToolResult(
                        tool_id=tool_name,
                        success=False,
                        error=f"No adapter registered for tool {tool_name!r}",
                        error_type="execution",
                    )
                    return _final_result

                # Step 4/5: Execute adapter with rate limiting + optional recovery.
                #
                # Rate-limit check runs first to reject early when over quota.
                # ``record()`` is deferred to just before the actual adapter call so
                # that RecoveryExecutor short-circuits (cache hit, circuit-open) do
                # NOT consume a rate-limit slot.
                rate_limiter = self._registry.get_rate_limiter(tool_name)
                if not rate_limiter.check():
                    logger.warning("Rate limit exceeded for tool: %s", tool_name)
                    self._metrics_increment("tool.error_count", tool_name)
                    _final_result = ToolResult(
                        tool_id=tool_name,
                        success=False,
                        error=f"Rate limit exceeded for tool {tool_name!r}",
                        error_type="rate_limit",
                    )
                    return _final_result

                if self._recovery_executor is not None:
                    # Pass rate_limiter to RecoveryExecutor so record() is called
                    # only when the adapter is actually invoked (not on cache hit
                    # or circuit-open short-circuit).
                    recovery_result = await self._recovery_executor.execute(
                        tool,
                        adapter,
                        validated_input,
                        is_foreground=True,
                        rate_limiter=rate_limiter,
                    )
                    tool_result = recovery_result.tool_result
                    if not tool_result.success:
                        self._metrics_increment("tool.error_count", tool_name)
                        self._metrics_observe_duration(
                            "tool.duration_ms",
                            tool_name,
                            (time.monotonic() - dispatch_start) * 1000,
                        )
                        _final_result = tool_result
                        return _final_result
                    result_dict = dict(tool_result.data or {})
                else:
                    rate_limiter.record()
                    try:
                        result_dict = await adapter(validated_input)
                    except Exception as exc:
                        _log_adapter_exception("Adapter", tool_name, exc)
                        self._metrics_increment("tool.error_count", tool_name)
                        self._metrics_observe_duration(
                            "tool.duration_ms",
                            tool_name,
                            (time.monotonic() - dispatch_start) * 1000,
                        )
                        _final_result = ToolResult(
                            tool_id=tool_name,
                            success=False,
                            error="Tool execution failed.",
                            error_type="execution",
                        )
                        return _final_result

                # --- Epic #466 Layers A+C: ingress safety (FR-006, FR-013) ------
                # Detector first, then redactor; applies to BOTH the recovery
                # branch (result_dict derived from ToolResult.data) and the direct
                # adapter branch above.
                from ummaya.safety._ingress import apply_ingress_safety  # noqa: PLC0415
                from ummaya.safety._span import emit_safety_event  # noqa: PLC0415
                from ummaya.settings import settings  # noqa: PLC0415

                sanitized_dict, safety_event = apply_ingress_safety(result_dict, settings.safety)
                if safety_event is not None:
                    emit_safety_event(safety_event)
                if sanitized_dict is None:
                    # Injection detector blocked — surface as ToolResult failure.
                    self._metrics_increment("tool.error_count", tool_name)
                    self._metrics_observe_duration(
                        "tool.duration_ms",
                        tool_name,
                        (time.monotonic() - dispatch_start) * 1000,
                    )
                    _final_result = ToolResult(
                        tool_id=tool_name,
                        success=False,
                        error="Tool output blocked by injection detector.",
                        error_type="injection_detected",
                    )
                    return _final_result
                result_dict = sanitized_dict

                # Step 6: Validate output
                if tool.primitive == "find" and _is_lookup_envelope_dict(result_dict):
                    try:
                        normalized_output = normalize(
                            output=result_dict,
                            tool=tool,
                            request_id=tool_call_id or f"{tool_name}-dispatch",
                            elapsed_ms=int((time.monotonic() - dispatch_start) * 1000),
                        )
                    except EnvelopeNormalizationError as exc:
                        logger.warning(
                            "Lookup envelope mismatch for tool %s: %s",
                            tool_name,
                            exc,
                        )
                        self._metrics_increment("tool.error_count", tool_name)
                        self._metrics_observe_duration(
                            "tool.duration_ms",
                            tool_name,
                            (time.monotonic() - dispatch_start) * 1000,
                        )
                        _final_result = ToolResult(
                            tool_id=tool_name,
                            success=False,
                            error=str(exc),
                            error_type="schema_mismatch",
                        )
                        return _final_result

                    logger.info("Tool dispatch succeeded: %s", tool_name)
                    self._metrics_increment("tool.success_count", tool_name)
                    self._metrics_observe_duration(
                        "tool.duration_ms",
                        tool_name,
                        (time.monotonic() - dispatch_start) * 1000,
                    )
                    _final_result = ToolResult(
                        tool_id=tool_name,
                        success=True,
                        data=normalized_output.model_dump()
                        if isinstance(normalized_output, BaseModel)
                        else result_dict,
                    )
                    return _final_result

                try:
                    validated_output = tool.output_schema.model_validate(result_dict)
                except ValidationError as exc:
                    logger.warning("Output schema mismatch for tool %s: %s", tool_name, exc)
                    self._metrics_increment("tool.error_count", tool_name)
                    self._metrics_observe_duration(
                        "tool.duration_ms",
                        tool_name,
                        (time.monotonic() - dispatch_start) * 1000,
                    )
                    _final_result = ToolResult(
                        tool_id=tool_name,
                        success=False,
                        error=str(exc),
                        error_type="schema_mismatch",
                    )
                    return _final_result

                # Step 7: Return success
                logger.info("Tool dispatch succeeded: %s", tool_name)
                self._metrics_increment("tool.success_count", tool_name)
                self._metrics_observe_duration(
                    "tool.duration_ms", tool_name, (time.monotonic() - dispatch_start) * 1000
                )
                _final_result = ToolResult(
                    tool_id=tool_name,
                    success=True,
                    data=validated_output.model_dump(),
                )
                return _final_result

            except Exception as exc:
                # Catch unexpected exceptions so dispatch() never raises and the
                # finally block can still emit the tool_call event (AC-A6).
                _final_result = self._handle_unexpected_error(tool_name, exc)
                return _final_result

            finally:
                # Map ToolResult.success=False → OTel ERROR status (contract § Span 3).
                if _final_result is not None and not _final_result.success:
                    span.set_status(Status(StatusCode.ERROR))
                    if _final_result.error_type is not None:
                        filtered = filter_metadata({"error_class": _final_result.error_type})
                        if "error_class" in filtered:
                            span.set_attribute(ERROR_TYPE, str(filtered["error_class"]))

                # FR-017: emit ummaya.tool.outcome exactly once per execute_tool span.
                # Derived from _final_result.success — "ok" on success, "error" on failure.
                if _final_result is not None:
                    span.set_attribute(
                        "ummaya.tool.outcome",
                        "ok" if _final_result.success else "error",
                    )

                # Emit structured tool_call event (AC-A6).
                if _final_result is not None:
                    _duration_ms = (time.monotonic() - dispatch_start) * 1000
                    self._event_emit_tool_call(
                        tool_name=tool_name,
                        success=_final_result.success,
                        duration_ms=_duration_ms,
                        error_type=_final_result.error_type,
                    )

    # ------------------------------------------------------------------
    # Private metrics helpers (fail-safe: never raise)
    # ------------------------------------------------------------------

    def _handle_unexpected_error(self, tool_name: str, exc: BaseException) -> ToolResult:
        """Convert an unexpected exception to a ToolResult (never raises)."""
        logger.error(
            "Unexpected error during dispatch of tool %s: %s", tool_name, exc, exc_info=True
        )
        self._metrics_increment("tool.error_count", tool_name)
        return ToolResult(
            tool_id=tool_name,
            success=False,
            error="Internal error occurred.",
            error_type="execution",
        )

    def _metrics_increment(self, name: str, tool_name: str, value: int = 1) -> None:
        if self._metrics is None:
            return
        try:
            self._metrics.increment(name, value=value, labels={"tool_id": tool_name})
        except Exception:  # noqa: BLE001
            logger.debug("metrics.increment failed for %s", name, exc_info=True)

    def _metrics_observe_duration(self, name: str, tool_name: str, duration_ms: float) -> None:
        if self._metrics is None:
            return
        try:
            self._metrics.observe(name, duration_ms, labels={"tool_id": tool_name})
        except Exception:  # noqa: BLE001
            logger.debug("metrics.observe failed for %s", name, exc_info=True)

    def _event_emit_tool_call(
        self,
        tool_name: str,
        success: bool,
        duration_ms: float,
        error_type: str | None,
    ) -> None:
        """Emit a structured tool_call event; silently skip if no event_logger."""
        if self._event_logger is None:
            return
        try:
            from ummaya.observability.events import ObservabilityEvent  # noqa: PLC0415

            metadata: dict[str, str] = {"tool_id": tool_name}
            if error_type is not None:
                metadata["error_class"] = error_type
            self._event_logger.emit(
                ObservabilityEvent(
                    event_type="tool_call",
                    tool_id=tool_name,
                    success=success,
                    duration_ms=duration_ms,
                    metadata=metadata,
                )
            )
        except Exception:  # noqa: BLE001
            logger.debug("ToolExecutor: event_logger.emit failed", exc_info=True)
