# SPDX-License-Identifier: Apache-2.0
"""Async LLM client for the KOSMOS project (FriendliAI Serverless endpoint)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import httpx
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from pydantic import ValidationError

from kosmos.llm.config import LLMClientConfig
from kosmos.llm.errors import (
    AuthenticationError,
    BudgetExceededError,
    ConfigurationError,
    LLMResponseError,
    StreamInterruptedError,
)
from kosmos.llm.models import (
    ChatCompletionResponse,
    ChatMessage,
    FunctionCall,
    StreamEvent,
    TokenUsage,
    ToolCall,
    ToolDefinition,
)
from kosmos.llm.usage import UsageTracker
from kosmos.observability.semconv import (
    ERROR_TYPE,
    GEN_AI_OPERATION_NAME,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_RESPONSE_FINISH_REASONS,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
)

# Spec 2521 (2026-05-01) — backend-side stream pacing knobs (now OFF
# by default; see history below).
#
# Initial implementation paced sub-chunks server-side. Layer 5 frame
# capture (post-d11c835-raw.cast frame_0903) confirmed that even with
# the most aggressive backend defaults (CHUNK=8 / PACE=80 ms) Ink's
# React reconciler folds rapid setStates into a single commit, so the
# whole paragraph still paints in one cell-grid transition. The fix
# moved to the frontend (tui/src/query/deps.ts ``_typewriter``) which
# can sleep *between* setState dispatches and force one Ink reconcile
# per codepoint.
#
# Backend pacing therefore now defaults to OFF — leaving it on at the
# same time as the frontend typewriter would just stack two paces
# (e.g. 80 ms backend + 30 ms frontend = ~110 ms per byte), making
# the citizen wait for K-EXAONE answers without adding any visible
# streaming benefit. The knobs survive for headless / no-Ink callers
# that still want server-side cadence:
#
#   KOSMOS_LLM_STREAM_CHUNK_MAX_CHARS  default 999  (no extra splitting)
#   KOSMOS_LLM_STREAM_PACE_MS          default 0    (disabled — natural cadence)
#
# Spec 2521 (2026-05-01) — pacing now disabled by default. The
# paragraph-batch repaint root cause was Ink's
# ``FRAME_INTERVAL_MS = 16`` throttle folding K-EXAONE's 13-17 ms inter-
# chunk arrival latency into one render. Fix is to lower the throttle
# (``tui/src/ink/constants.ts`` byte-copy relax to 4 ms), not to slow
# the provider down. The pacing knobs survive for headless / no-Ink
# callers that still want server-side cadence.
_LLM_STREAM_CHUNK_MAX_CHARS = max(
    1, int(os.environ.get("KOSMOS_LLM_STREAM_CHUNK_MAX_CHARS", "999"))
)
_LLM_STREAM_PACE_S = max(0.0, float(os.environ.get("KOSMOS_LLM_STREAM_PACE_MS", "0")) / 1000.0)


if TYPE_CHECKING:
    from kosmos.observability.event_logger import ObservabilityEventLogger
    from kosmos.observability.metrics import MetricsCollector

logger = logging.getLogger(__name__)
rate_limit_logger = logging.getLogger("kosmos.llm")

_tracer = trace.get_tracer(__name__)


@dataclass(frozen=True)
class RetryPolicy:
    """Rate-limit retry policy (data-model Entity 2).

    Consumed by the Retry-After-first backoff loop landed in T015.
    """

    max_attempts: int = 5
    base_seconds: float = 1.0
    cap_seconds: float = 60.0
    jitter_ratio: float = 0.2
    respect_retry_after: bool = True


def _log_rate_limit_attempt(
    *,
    attempt: int,
    delay: float,
    retry_after_honored: bool,
) -> None:
    """Emit a structured rate-limit retry log line on logger ``kosmos.llm``."""
    rate_limit_logger.info(
        "rate_limit attempt=%d delay=%.3fs retry_after_honored=%s",
        attempt,
        delay,
        retry_after_honored,
        extra={
            "category": "rate_limit",
            "attempt": attempt,
            "delay_seconds": delay,
            "retry_after_honored": retry_after_honored,
        },
    )


_PROMPT_DYNAMIC_BOUNDARY_MARKER = "\nSYSTEM_PROMPT_DYNAMIC_BOUNDARY\n"


def _compute_prompt_hash(system_text: str) -> str:
    """Return SHA-256 of the cacheable prefix of ``system_text``.

    Epic #2152 R4 — when the system message contains the
    ``SYSTEM_PROMPT_DYNAMIC_BOUNDARY`` marker (CC ``prompts.ts:572-575``), hash
    only the bytes UP TO (and including) the marker so the hash captures the
    cacheable static prefix and stays stable across turns even when the
    dynamic suffix grows. Falls back to full-content hashing when the marker
    is absent (transitional path for callers that have not migrated).
    """
    idx = system_text.find(_PROMPT_DYNAMIC_BOUNDARY_MARKER)
    hashed = system_text if idx == -1 else system_text[: idx + len(_PROMPT_DYNAMIC_BOUNDARY_MARKER)]
    return hashlib.sha256(hashed.encode("utf-8")).hexdigest()


class LLMClient:
    """Async LLM client for FriendliAI Serverless endpoint."""

    def __init__(
        self,
        config: LLMClientConfig | None = None,
        metrics: MetricsCollector | None = None,
        event_logger: ObservabilityEventLogger | None = None,
    ) -> None:
        """Initialize with config. Loads from env vars if config is None.

        Args:
            config: LLM client configuration. Loaded from env vars if None.
            metrics: Optional MetricsCollector for recording LLM telemetry.
                When absent, metrics instrumentation is skipped (backward-compatible).
            event_logger: Optional ObservabilityEventLogger for structured events.
                When absent, event emission is skipped (backward-compatible).

        Raises:
            ConfigurationError: If KOSMOS_FRIENDLI_TOKEN is missing or invalid.
        """
        if config is None:
            try:
                config = LLMClientConfig()
            except ValidationError as exc:
                raise ConfigurationError(
                    f"Failed to load LLM client configuration from environment: {exc}"
                ) from exc

        self._config = config
        self._client = httpx.AsyncClient(
            base_url=str(config.base_url),
            headers={"Authorization": f"Bearer {config.token.get_secret_value()}"},
            timeout=httpx.Timeout(config.timeout),
        )
        self._metrics: MetricsCollector | None = metrics
        self._event_logger: ObservabilityEventLogger | None = event_logger
        self._usage = UsageTracker(budget=self._config.session_budget, metrics=metrics)
        # T014: per-session concurrency gate (Entity 3, data-model.md)
        self._semaphore = asyncio.Semaphore(1)
        # T015: rate-limit retry policy (Entity 2, data-model.md).
        # ``max_attempts`` is sourced from config so ``LLMClientConfig.max_retries``
        # still governs total attempts for transient errors (Retry-After + backoff).
        self._rate_limit_policy = RetryPolicy(
            max_attempts=max(1, self._config.max_retries + 1),
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def usage(self) -> UsageTracker:
        """Current session usage tracker."""
        return self._usage

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolDefinition | dict[str, object]] | None = None,
        tool_choice: str | dict[str, object] | None = None,
        temperature: float = 1.0,
        top_p: float = 0.95,
        presence_penalty: float = 0.0,
        max_tokens: int = 1024,
        stop: list[str] | None = None,
    ) -> ChatCompletionResponse:
        """Send a non-streaming chat completion request.

        Args:
            messages: Ordered list of conversation messages.
            tools: Optional tool definitions (ToolDefinition models or raw dicts).
            temperature: Sampling temperature (default 1.0 per K-EXAONE recommendations).
            top_p: Nucleus sampling parameter (default 0.95).
            presence_penalty: Presence penalty (default 0.0).
            max_tokens: Maximum tokens in the completion (default 1024).
            stop: Stop sequences.

        Returns:
            Parsed ChatCompletionResponse.

        Raises:
            BudgetExceededError: If the session token budget is exhausted.
            AuthenticationError: On 401 or 403 responses.
            LLMResponseError: On 400, 404, rate-limit exhaustion, or other errors.
        """
        if not self._usage.can_afford(max_tokens or 1):
            raise BudgetExceededError("Session token budget exhausted")

        payload = self._build_payload(
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            presence_penalty=presence_penalty,
            max_tokens=max_tokens,
            stop=stop,
            tools=tools,
            tool_choice=tool_choice,
            stream=False,
        )

        logger.debug(
            "LLM complete request: model=%s messages=%d",
            self._config.model,
            len(messages),
        )

        _call_start = time.monotonic()

        try:
            result = await self._complete_with_retry(payload)
        except Exception:
            _duration_ms = (time.monotonic() - _call_start) * 1000
            self._metrics_record_call(success=False, duration_ms=_duration_ms)
            raise

        self._usage.debit(result.usage)
        logger.info(
            "Token usage: %d input, %d output",
            result.usage.input_tokens,
            result.usage.output_tokens,
        )
        _duration_ms = (time.monotonic() - _call_start) * 1000
        self._metrics_record_call(success=True, duration_ms=_duration_ms)
        return result

    async def _complete_with_retry(self, payload: dict[str, object]) -> ChatCompletionResponse:
        """Execute complete() with Retry-After-first backoff loop (T015).

        Acquires the session-level concurrency gate (T014) around each provider call.
        """
        policy = self._rate_limit_policy
        last_exc: Exception | None = None

        for attempt in range(policy.max_attempts):
            try:
                async with self._semaphore:
                    response = await self._client.post("/chat/completions", json=payload)

                if response.status_code == 429:
                    delay = self._compute_rate_limit_delay(response, attempt, policy)
                    retry_after_honored = (
                        self._has_retry_after(response) and policy.respect_retry_after
                    )
                    _log_rate_limit_attempt(
                        attempt=attempt,
                        delay=delay,
                        retry_after_honored=retry_after_honored,
                    )
                    last_exc = LLMResponseError(
                        f"Rate limited by LLM API (HTTP 429) on attempt {attempt + 1}",
                        status_code=429,
                    )
                    # Skip the sleep on the final attempt — we are about to raise.
                    if attempt < policy.max_attempts - 1:
                        await asyncio.sleep(delay)
                    continue

                await self._raise_for_status(response)
                return self._parse_completion_response(response.json())

            except (AuthenticationError, BudgetExceededError):
                raise
            except LLMResponseError:
                raise
            except httpx.ConnectError as exc:
                from kosmos.llm.errors import LLMConnectionError  # noqa: PLC0415

                raise LLMConnectionError(f"Connection failed: {exc}") from exc
            except httpx.RequestError as exc:
                # Non-streaming call: surface as a connection/transport failure,
                # not a stream interruption (reviewer feedback, PR #460).
                from kosmos.llm.errors import LLMConnectionError  # noqa: PLC0415

                raise LLMConnectionError(f"Request failed: {exc}") from exc

        # All attempts exhausted
        raise LLMResponseError(
            f"Rate limit retry budget exhausted after {policy.max_attempts} attempts",
            status_code=429,
        ) from last_exc

    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolDefinition | dict[str, object]] | None = None,
        tool_choice: str | dict[str, object] | None = None,
        temperature: float = 1.0,
        top_p: float = 0.95,
        presence_penalty: float = 0.0,
        max_tokens: int = 1024,
        stop: list[str] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Send a streaming chat completion request.

        Yields StreamEvent objects as they arrive from the SSE stream.
        Implements Retry-After-first backoff (T015/T016) and session-level
        concurrency gate (T014) per data-model.md Entities 2 and 3.

        Args:
            messages: Ordered list of conversation messages.
            tools: Optional tool definitions (ToolDefinition models or raw dicts).
            temperature: Sampling temperature (default 1.0 per K-EXAONE recommendations).
            top_p: Nucleus sampling parameter (default 0.95).
            presence_penalty: Presence penalty (default 0.0).
            max_tokens: Maximum tokens in the completion (default 1024).
            stop: Stop sequences.

        Yields:
            StreamEvent for each SSE event received.

        Raises:
            BudgetExceededError: If the session token budget is exhausted.
            StreamInterruptedError: If the connection is lost mid-stream.
            AuthenticationError: On 401 or 403 responses.
            LLMResponseError: On rate-limit exhaustion or non-retryable HTTP errors.
        """
        if not self._usage.can_afford(max_tokens or 1):
            raise BudgetExceededError("Session token budget exhausted")

        payload = self._build_payload(
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            presence_penalty=presence_penalty,
            max_tokens=max_tokens,
            stop=stop,
            tools=tools,
            tool_choice=tool_choice,
            stream=True,
        )

        logger.debug(
            "LLM stream request: model=%s messages=%d",
            self._config.model,
            len(messages),
        )

        # T010: open a single "chat" span for the entire logical streaming call
        # (including all retry attempts — see T020 for per-retry counter).
        # Use start_span + explicit end() so the span stays alive across yield
        # boundaries in the async generator lifetime.
        span = _tracer.start_span("chat")
        span.set_attribute(GEN_AI_OPERATION_NAME, "chat")
        span.set_attribute(GEN_AI_PROVIDER_NAME, "friendliai")
        span.set_attribute(GEN_AI_REQUEST_MODEL, self._config.model)
        # Optional attributes — only when present in this call's payload.
        if temperature is not None:
            span.set_attribute("gen_ai.request.temperature", float(temperature))
        if max_tokens is not None:
            span.set_attribute("gen_ai.request.max_tokens", int(max_tokens))
        if top_p is not None:
            span.set_attribute("gen_ai.request.top_p", float(top_p))

        # T032: kosmos.prompt.hash — SHA-256 of the system-prompt bytes actually
        # sent on the wire. KOSMOS extension namespace per Spec 021; consumed by
        # Epic #501. Satisfies FR-C07 / SC-007.
        if messages and messages[0].role == "system" and messages[0].content is not None:
            span.set_attribute(
                "kosmos.prompt.hash",
                _compute_prompt_hash(messages[0].content),
            )

        # Attach span as the active context for child spans (execute_tool, etc.)
        # while preserving the caller's context on generator close.
        ctx = trace.use_span(span, end_on_exit=False)
        ctx.__enter__()

        # T019: mutable container to collect finalize info from _stream_with_retry().
        # Populated on the success path only; remains empty if an exception is raised.
        _finalize: dict[str, object] = {}

        try:
            async for event in self._stream_with_retry(payload, _finalize):
                yield event
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR))
            span.record_exception(exc)
            span.set_attribute(ERROR_TYPE, exc.__class__.__name__)
            raise
        else:
            # T019: success path — write span attributes exactly once.
            # Guard: only write when _finalize was populated (stream completed normally).
            if _finalize:
                span.set_attributes(
                    {
                        GEN_AI_USAGE_INPUT_TOKENS: int(
                            cast(
                                int,
                                _finalize.get("input_tokens", self._usage.input_tokens_used),
                            )
                        ),
                        GEN_AI_USAGE_OUTPUT_TOKENS: int(
                            cast(
                                int,
                                _finalize.get("output_tokens", self._usage.output_tokens_used),
                            )
                        ),
                        GEN_AI_RESPONSE_MODEL: str(
                            _finalize.get("response_model", self._config.model)
                        ),
                        GEN_AI_RESPONSE_FINISH_REASONS: list(
                            cast(list[str], _finalize.get("finish_reasons", []))
                        ),
                    }
                )
        finally:
            ctx.__exit__(None, None, None)
            span.end()

    async def _stream_with_retry(  # noqa: C901
        self,
        payload: dict[str, object],
        _finalize: dict[str, object],
    ) -> AsyncIterator[StreamEvent]:
        """Execute stream() with Retry-After-first backoff loop (T015/T016).

        Acquires the session-level concurrency gate (T014) around each provider call.
        Pre-stream 429 and mid-stream 429 envelopes both route through the same policy.

        Args:
            payload: The request payload dict.
            _finalize: Mutable container populated on success with keys
                ``input_tokens``, ``output_tokens``, ``response_model``,
                ``finish_reasons`` — consumed by ``stream()`` for T019 span
                attributes.  Must be an empty dict on entry; written at most once.
        """
        policy = self._rate_limit_policy
        _stream_start = time.monotonic()
        _metrics_recorded = False
        last_exc: Exception | None = None

        # T019: per-stream accumulators (reset on each successful attempt).
        _finish_reasons: set[str] = set()
        _response_model: str | None = None
        # Snapshot usage before stream starts so we can compute the delta.
        _usage_input_before = self._usage.input_tokens_used
        _usage_output_before = self._usage.output_tokens_used

        for attempt in range(policy.max_attempts):
            try:
                async with self._semaphore:  # noqa: SIM117
                    async with self._client.stream(
                        "POST", "/chat/completions", json=payload
                    ) as response:
                        # Pre-stream 429 (T016: rate-limit before any chunk)
                        if response.status_code == 429:
                            await response.aread()
                            delay = self._compute_rate_limit_delay(response, attempt, policy)
                            _log_rate_limit_attempt(
                                attempt=attempt,
                                delay=delay,
                                retry_after_honored=(
                                    self._has_retry_after(response) and policy.respect_retry_after
                                ),
                            )
                            last_exc = LLMResponseError(
                                f"Rate limited (HTTP 429) on stream attempt {attempt + 1}",
                                status_code=429,
                            )
                            # T020: increment retry counter before sleeping/retrying.
                            if attempt < policy.max_attempts - 1:
                                if self._metrics is not None:
                                    try:
                                        self._metrics.increment(
                                            "kosmos_llm_rate_limit_retries_total",
                                            labels={
                                                "provider": "friendliai",
                                                "model": self._config.model,
                                            },
                                        )
                                    except Exception:  # noqa: BLE001
                                        logger.debug(
                                            "LLMClient: rate_limit counter increment failed",
                                            exc_info=True,
                                        )
                                await asyncio.sleep(delay)
                            # Reset accumulators for the next attempt.
                            _finish_reasons = set()
                            _response_model = None
                            _usage_input_before = self._usage.input_tokens_used
                            _usage_output_before = self._usage.output_tokens_used
                            continue

                        await self._raise_for_status(response)

                        # Yield events; watch for mid-stream 429 envelopes (T016)
                        rate_limited_mid_stream = False
                        async for line in response.aiter_lines():
                            if self._is_rate_limit_envelope(line):
                                rate_limited_mid_stream = True
                                delay = self._compute_rate_limit_delay(response, attempt, policy)
                                _log_rate_limit_attempt(
                                    attempt=attempt,
                                    delay=delay,
                                    retry_after_honored=(
                                        self._has_retry_after(response)
                                        and policy.respect_retry_after
                                    ),
                                )
                                last_exc = LLMResponseError(
                                    f"Rate limited (mid-stream SSE 429) on stream "
                                    f"attempt {attempt + 1}",
                                    status_code=429,
                                )
                                # T020: increment retry counter before sleeping/retrying.
                                if attempt < policy.max_attempts - 1:
                                    if self._metrics is not None:
                                        try:
                                            self._metrics.increment(
                                                "kosmos_llm_rate_limit_retries_total",
                                                labels={
                                                    "provider": "friendliai",
                                                    "model": self._config.model,
                                                },
                                            )
                                        except Exception:  # noqa: BLE001
                                            logger.debug(
                                                "LLMClient: rate_limit counter increment failed",
                                                exc_info=True,
                                            )
                                    await asyncio.sleep(delay)
                                break

                            # T019: intercept chunk metadata before/after yielding.
                            chunk_info = self._extract_chunk_metadata(line)
                            if chunk_info.get("finish_reason"):
                                _finish_reasons.add(chunk_info["finish_reason"])  # type: ignore[arg-type]
                            if chunk_info.get("model"):
                                _response_model = chunk_info["model"]

                            async for event in self._parse_sse_line(line):
                                yield event
                                if event.type == "done":
                                    _duration_ms = (time.monotonic() - _stream_start) * 1000
                                    self._metrics_record_call(
                                        success=True, duration_ms=_duration_ms
                                    )
                                    _metrics_recorded = True
                                    # T019: populate finalize container on clean EOF.
                                    _finalize["input_tokens"] = (
                                        self._usage.input_tokens_used - _usage_input_before
                                    )
                                    _finalize["output_tokens"] = (
                                        self._usage.output_tokens_used - _usage_output_before
                                    )
                                    _finalize["response_model"] = _response_model or payload.get(
                                        "model", self._config.model
                                    )
                                    _finalize["finish_reasons"] = sorted(_finish_reasons)
                                    return

                        if rate_limited_mid_stream:
                            # Reset accumulators for the next attempt.
                            _finish_reasons = set()
                            _response_model = None
                            _usage_input_before = self._usage.input_tokens_used
                            _usage_output_before = self._usage.output_tokens_used
                            # Outer loop will retry
                            continue

                        # Stream completed without explicit [DONE] — treat as success
                        if not _metrics_recorded:
                            _duration_ms = (time.monotonic() - _stream_start) * 1000
                            self._metrics_record_call(success=True, duration_ms=_duration_ms)
                            _metrics_recorded = True
                        # T019: populate finalize container (no [DONE] path).
                        _finalize["input_tokens"] = (
                            self._usage.input_tokens_used - _usage_input_before
                        )
                        _finalize["output_tokens"] = (
                            self._usage.output_tokens_used - _usage_output_before
                        )
                        _finalize["response_model"] = _response_model or payload.get(
                            "model", self._config.model
                        )
                        _finalize["finish_reasons"] = sorted(_finish_reasons)
                        return

            except (AuthenticationError, BudgetExceededError):
                if not _metrics_recorded:
                    _duration_ms = (time.monotonic() - _stream_start) * 1000
                    self._metrics_record_call(success=False, duration_ms=_duration_ms)
                raise
            except LLMResponseError:
                if not _metrics_recorded:
                    _duration_ms = (time.monotonic() - _stream_start) * 1000
                    self._metrics_record_call(success=False, duration_ms=_duration_ms)
                raise
            except httpx.ConnectError as exc:
                _duration_ms = (time.monotonic() - _stream_start) * 1000
                self._metrics_record_call(success=False, duration_ms=_duration_ms)
                _metrics_recorded = True
                raise StreamInterruptedError(f"Connection lost during streaming: {exc}") from exc
            except httpx.TimeoutException as exc:
                _duration_ms = (time.monotonic() - _stream_start) * 1000
                self._metrics_record_call(success=False, duration_ms=_duration_ms)
                _metrics_recorded = True
                raise StreamInterruptedError(f"Stream timed out: {exc}") from exc
            except httpx.RequestError as exc:
                _duration_ms = (time.monotonic() - _stream_start) * 1000
                self._metrics_record_call(success=False, duration_ms=_duration_ms)
                _metrics_recorded = True
                raise StreamInterruptedError(f"Stream request failed: {exc}") from exc

        # All attempts exhausted
        if not _metrics_recorded:
            _duration_ms = (time.monotonic() - _stream_start) * 1000
            self._metrics_record_call(success=False, duration_ms=_duration_ms)
        raise LLMResponseError(
            f"Rate limit retry budget exhausted after {policy.max_attempts} stream attempts",
            status_code=429,
        ) from last_exc

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> LLMClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Private metrics helpers (fail-safe: never raise)
    # ------------------------------------------------------------------

    def _metrics_record_call(self, *, success: bool, duration_ms: float) -> None:
        """Record a single LLM call to metrics and event logger.

        Wrapped in try/except so metrics failures never propagate (AC-A9).
        """
        try:
            if self._metrics is not None:
                self._metrics.increment("llm.call_count", labels={"model": self._config.model})
                if not success:
                    self._metrics.increment("llm.error_count", labels={"model": self._config.model})
                self._metrics.observe(
                    "llm.call_duration_ms",
                    duration_ms,
                    labels={"model": self._config.model},
                )
        except Exception:  # noqa: BLE001
            logger.debug("LLMClient: metrics record failed", exc_info=True)

        try:
            if self._event_logger is not None:
                from kosmos.observability.events import ObservabilityEvent  # noqa: PLC0415

                self._event_logger.emit(
                    ObservabilityEvent(
                        event_type="llm_call",
                        success=success,
                        duration_ms=duration_ms,
                        metadata={"model": self._config.model},
                    )
                )
        except Exception:  # noqa: BLE001
            logger.debug("LLMClient: event_logger emit failed", exc_info=True)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_chunk_metadata(line: str) -> dict[str, str | None]:
        """Extract ``finish_reason`` and ``model`` from a raw SSE data line.

        Returns a dict with keys ``"finish_reason"`` and ``"model"`` (both may
        be ``None`` when absent or unparseable).  Used by ``_stream_with_retry``
        to accumulate T019 finalize data without duplicating JSON parsing.
        """
        result: dict[str, str | None] = {"finish_reason": None, "model": None}
        if not line or not line.startswith("data: "):
            return result
        payload_text = line[len("data: ") :].strip()
        if not payload_text or payload_text == "[DONE]":
            return result
        try:
            chunk = json.loads(payload_text)
        except json.JSONDecodeError:
            return result
        if not isinstance(chunk, dict):
            return result
        # Extract model field.
        model_val = chunk.get("model")
        if isinstance(model_val, str) and model_val:
            result["model"] = model_val
        # Extract finish_reason from the first choice.
        choices = chunk.get("choices")
        if isinstance(choices, list) and choices:
            fr = choices[0].get("finish_reason")
            if isinstance(fr, str) and fr:
                result["finish_reason"] = fr
        return result

    @staticmethod
    def _is_rate_limit_envelope(line: str) -> bool:
        """Return True when an SSE data line contains a rate-limit error envelope.

        Detects provider error payloads shaped like
        ``{"error": {"status": 429, ...}}`` or variants keyed on ``code`` /
        ``type`` (``"rate_limit"`` / ``"rate_limited"``). Non-error or non-JSON
        lines return False — normal SSE content and ``[DONE]`` flow through.
        """
        if not line or not line.startswith("data: "):
            return False
        payload_text = line[len("data: ") :].strip()
        if not payload_text or payload_text == "[DONE]":
            return False
        try:
            envelope = json.loads(payload_text)
        except json.JSONDecodeError:
            return False
        if not isinstance(envelope, dict):
            return False
        error = envelope.get("error")
        if not isinstance(error, dict):
            return False
        status = error.get("status")
        code = str(error.get("code", "")).lower()
        error_type = str(error.get("type", "")).lower()
        return (
            status == 429
            or code in {"429", "rate_limit", "rate_limited"}
            or error_type in {"rate_limit", "rate_limited"}
        )

    async def _pace_text_chunk(self, text: str, kind: str) -> AsyncIterator[StreamEvent]:
        """Split a paragraph-granular delta into character-paced sub-events.

        Spec 2521 (2026-05-01) — see the ``_LLM_STREAM_*`` module-level
        constants for the rationale + tunables. Disabled when the pace
        is set to zero.
        """
        from collections.abc import Callable as _Callable  # noqa: PLC0415

        def _content_event(s: str) -> StreamEvent:
            return StreamEvent(type="content_delta", content=s)

        def _thinking_event(s: str) -> StreamEvent:
            return StreamEvent(type="thinking_delta", thinking=s)

        kind_to_event: dict[str, _Callable[[str], StreamEvent]] = {
            "content": _content_event,
            "thinking": _thinking_event,
        }
        make_event = kind_to_event[kind]
        n = len(text)
        if _LLM_STREAM_PACE_S <= 0:
            # Pacing disabled — provider cadence passes through verbatim.
            yield make_event(text)
            return
        if n <= _LLM_STREAM_CHUNK_MAX_CHARS:
            # Provider already gave us a small natural chunk (e.g. K-EXAONE
            # emits 3-10 codepoints per SSE line on the content channel).
            # Yield it whole, then sleep so the *next* chunk's effective
            # arrival latency at the frontend is ≥ PACE — guaranteeing it
            # falls outside Ink's FRAME_INTERVAL_MS throttle and gets its
            # own ANSI flush. The post-yield sleep is the entire point;
            # without it K-EXAONE's 13-17 ms inter-chunk latency stays
            # below Ink's 16 ms throttle and chunks fold into one paint.
            yield make_event(text)
            await asyncio.sleep(_LLM_STREAM_PACE_S)
            return
        step = _LLM_STREAM_CHUNK_MAX_CHARS
        for i in range(0, n, step):
            yield make_event(text[i : i + step])
            if i + step < n:
                await asyncio.sleep(_LLM_STREAM_PACE_S)

    async def _parse_sse_line(self, line: str) -> AsyncIterator[StreamEvent]:  # noqa: C901
        """Parse a single SSE line and yield corresponding StreamEvent(s)."""
        if not line or not line.startswith("data: "):
            return

        payload_text = line[len("data: ") :]

        if payload_text == "[DONE]":
            yield StreamEvent(type="done")
            return

        try:
            chunk = json.loads(payload_text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse SSE chunk: %r", payload_text)
            return

        if "usage" in chunk and chunk["usage"] is not None:
            raw_usage = chunk["usage"]
            usage = TokenUsage(
                input_tokens=raw_usage.get("prompt_tokens", 0),
                output_tokens=raw_usage.get("completion_tokens", 0),
            )
            logger.info(
                "LLM stream usage: input=%d output=%d",
                usage.input_tokens,
                usage.output_tokens,
            )
            self._usage.debit(usage)
            yield StreamEvent(type="usage", usage=usage)

        choices = chunk.get("choices")
        if not choices:
            return

        choice = choices[0]
        delta = choice.get("delta", {})

        if "content" in delta and delta["content"] is not None:
            # CC reference: services/api/claude.ts:2113 (text_delta content_block_delta).
            content = delta["content"]
            async for sub in self._pace_text_chunk(content, "content"):
                yield sub
        elif "reasoning_content" in delta and delta["reasoning_content"] is not None:
            # CC reference: services/api/claude.ts:2148-2161 (thinking_delta
            # content_block_delta) — K-EXAONE emits chain-of-thought on a
            # separate ``delta.reasoning_content`` channel. Forwarding the
            # same StreamEvent shape on KOSMOS lets the TUI's
            # ``AssistantThinkingMessage`` component render the reasoning
            # inline instead of swallowing it. Log only the chunk length —
            # never the raw content (CoT may contain user PII or sensitive
            # reasoning about user input).
            reasoning_text = delta["reasoning_content"]
            logger.debug(
                "Forwarding reasoning_content as thinking_delta (len=%d)",
                len(reasoning_text),
            )
            async for sub in self._pace_text_chunk(reasoning_text, "thinking"):
                yield sub

        if "tool_calls" in delta and delta["tool_calls"]:
            # CC reference: services/api/claude.ts:1997 (tool_use content_block_start)
            # + services/api/claude.ts:2087 (input_json_delta content_block_delta).
            # FriendliAI's OpenAI-compatible streaming buffers tool_call argument
            # JSON across multiple deltas (matching OpenAI's incremental parser).
            # KOSMOS mirrors CC's pattern by emitting one StreamEvent per delta;
            # the IPC bridge (stdio.py) accumulates them into the final
            # ToolCallFrame.
            for tc_delta in delta["tool_calls"]:
                func = tc_delta.get("function", {})
                # Log only tool metadata (index/id/name + arg length).
                # Raw `arguments` often carries user-provided location strings
                # or other PII — never log them.
                _args_field = func.get("arguments")
                _args_len = len(_args_field) if isinstance(_args_field, str) else 0
                logger.debug(
                    "tool_call_delta idx=%s id=%s name=%r args_len=%d",
                    tc_delta.get("index"),
                    tc_delta.get("id"),
                    func.get("name"),
                    _args_len,
                )
                yield StreamEvent(
                    type="tool_call_delta",
                    tool_call_index=tc_delta.get("index"),
                    tool_call_id=tc_delta.get("id"),
                    function_name=func.get("name"),
                    function_args_delta=func.get("arguments"),
                )

    def _build_payload(
        self,
        *,
        messages: list[ChatMessage],
        temperature: float,
        top_p: float,
        presence_penalty: float,
        max_tokens: int,
        stop: list[str] | None,
        tools: list[ToolDefinition | dict[str, object]] | None = None,
        tool_choice: str | dict[str, object] | None = None,
        stream: bool,
    ) -> dict[str, object]:
        """Construct the JSON payload for a chat completions request.

        The four sampling/generation parameters (temperature, top_p,
        presence_penalty, max_tokens) are always included so the provider
        uses the caller's values — defaults are set at the call site.

        K-EXAONE specific: ``chat_template_kwargs.enable_thinking`` controls
        the model's reasoning mode. **KOSMOS now defaults this to ``False``**
        (Spec 2521 FriendliAI-cadence migration, 2026-05-01) so the citizen
        gets a sub-10 s first-token answer on the visible content channel
        instead of 1-3 minutes of reasoning trace before the bullet appears.

        Empirical channel behaviour (probe_friendli_channels.py, 2026-05-01):
            enable_thinking=False → answer streams out on ``delta.content`` at
                                     paragraph granularity (one SSE chunk
                                     ≈ one paragraph; verified via
                                     ``/tmp/tdb-thinking-off/raw.cast`` —
                                     117-byte and 617-byte chunks separated
                                     by ~5 s).
            enable_thinking=True  → ~0 bytes content (just newlines), full
                                     reasoning routed to ``reasoning_content``
                                     (separated channel), clean tool_calls.
                                     First-paragraph latency: 60-180 s.

        Why default flipped (Spec 2521 user directive):
            Layer 5 frame-by-frame review proved no frontend / pacing layer
            could dilate K-EXAONE's paragraph-granularity SSE chunks into
            Anthropic-style per-token deltas. The CC-token-streaming UX
            cannot be back-ported, so KOSMOS migrates to the FriendliAI
            cadence as the design baseline: paragraph-shaped reveal with
            inter-paragraph spinner cycling. ``enable_thinking=False``
            puts the answer on the visible channel where that cadence is
            citizen-readable; ``True`` buries it on ``reasoning_content``
            with a 1-3 min wait.

        Override via ``KOSMOS_K_EXAONE_THINKING=true`` to re-enable the
        model-card-recommended reasoning mode for benchmark / evaluation
        runs (τ²-Bench Retail 78.6 / Airline 60.4 / Telecom 73.5 are all
        measured with thinking ON). The ``/effort high`` slash command
        is the planned UX shortcut.
        """
        import os  # noqa: PLC0415 — local import keeps top-level imports thin

        enable_thinking = os.environ.get("KOSMOS_K_EXAONE_THINKING", "true").lower() in (
            "true",
            "1",
            "yes",
        )

        payload: dict[str, object] = {
            "model": self._config.model,
            "messages": [m.model_dump(exclude_none=True) for m in messages],
            "temperature": temperature,
            "top_p": top_p,
            "presence_penalty": presence_penalty,
            "max_tokens": max_tokens,
            # K-EXAONE chat-template hint — FriendliAI / vLLM forward this
            # to the model's tokenizer.apply_chat_template(...) call. With
            # enable_thinking=False the model emits an answer directly
            # without the <think>...</think> trace, dropping first-token
            # latency from ~60-180s to <10s for typical citizen prompts.
            "chat_template_kwargs": {"enable_thinking": enable_thinking},
        }
        if stop is not None:
            payload["stop"] = stop
        if tools is not None:
            tool_payloads = [t.model_dump() if isinstance(t, ToolDefinition) else t for t in tools]
            payload["tools"] = tool_payloads
            if tool_payloads:
                # KOSMOS citizen flows require one observed tool result before
                # the model may request the next tool. FriendliAI's
                # OpenAI-compatible default permits parallel tool calls.
                payload["parallel_tool_calls"] = False
            if tool_choice is not None:
                payload["tool_choice"] = tool_choice
        if stream:
            payload["stream"] = True
            payload["stream_options"] = {"include_usage": True}
        return payload

    # ------------------------------------------------------------------
    # Private retry helpers (T015)
    # ------------------------------------------------------------------

    @staticmethod
    def _has_retry_after(response: httpx.Response) -> bool:
        """Return True when the response carries a parsable Retry-After header.

        A header is considered parsable when it decodes to a non-negative float
        (``Retry-After: <seconds>``). Malformed values log False so the
        rate-limit log line does not overstate honouring behaviour.
        """
        raw = response.headers.get("retry-after")
        if raw is None:
            return False
        try:
            return float(raw) >= 0
        except ValueError:
            return False

    @staticmethod
    def _compute_rate_limit_delay(
        response: httpx.Response,
        attempt: int,
        policy: RetryPolicy,
    ) -> float:
        """Compute sleep duration for a 429 response per the policy.

        If Retry-After header is present and ``respect_retry_after`` is True,
        that value takes precedence.  Otherwise exponential backoff with jitter:
        ``min(cap, base * 2**attempt) * uniform(1-jitter, 1+jitter)``.
        """
        if policy.respect_retry_after and "retry-after" in response.headers:
            try:
                return float(response.headers["retry-after"])
            except ValueError:
                pass  # Fall through to computed backoff
        exp_delay = min(policy.cap_seconds, policy.base_seconds * (2**attempt))
        jitter_factor = random.uniform(  # noqa: S311 — not cryptographic
            1 - policy.jitter_ratio,
            1 + policy.jitter_ratio,
        )
        return float(exp_delay * jitter_factor)

    @staticmethod
    async def _raise_for_status(response: httpx.Response) -> None:
        """Map HTTP error status codes to typed KOSMOS exceptions.

        Reads the response body before accessing text to avoid
        ``httpx.ResponseNotRead`` on streaming responses.
        """
        status = response.status_code
        if status < 400:
            return
        # Read the full body first so .text is safe on streaming responses.
        await response.aread()
        body = response.text[:500]
        if status in (401, 403):
            raise AuthenticationError(
                f"Authentication failed (HTTP {status})",
                status_code=status,
            )
        if status == 429:
            raise LLMResponseError(
                f"Rate limited by LLM API (HTTP 429): {body}",
                status_code=status,
            )
        if status >= 500:
            raise LLMResponseError(
                f"LLM API server error (HTTP {status}): {body}",
                status_code=status,
            )
        if status >= 400:
            raise LLMResponseError(
                f"LLM API returned error (HTTP {status}): {body}",
                status_code=status,
            )

    @staticmethod
    def _parse_completion_response(data: dict[str, object]) -> ChatCompletionResponse:
        """Parse a raw /chat/completions JSON response into ChatCompletionResponse."""
        choice = data["choices"][0]  # type: ignore[index]
        message = choice["message"]

        # Parse tool calls if present
        tool_calls: list[ToolCall] = []
        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                func = tc["function"]
                tool_calls.append(
                    ToolCall(
                        id=tc["id"],
                        type=tc.get("type", "function"),
                        function=FunctionCall(
                            name=func["name"],
                            arguments=func["arguments"],
                        ),
                    )
                )

        # Parse token usage
        raw_usage = data.get("usage") or {}
        usage = TokenUsage(
            input_tokens=raw_usage.get("prompt_tokens", 0),  # type: ignore[attr-defined]
            output_tokens=raw_usage.get("completion_tokens", 0),  # type: ignore[attr-defined]
        )

        logger.info(
            "LLM complete usage: model=%s input=%d output=%d",
            data.get("model"),
            usage.input_tokens,
            usage.output_tokens,
        )

        return ChatCompletionResponse(
            id=data["id"],  # type: ignore[arg-type]
            content=message.get("content"),
            tool_calls=tool_calls,
            usage=usage,
            model=data["model"],  # type: ignore[arg-type]
            finish_reason=choice["finish_reason"],
        )
