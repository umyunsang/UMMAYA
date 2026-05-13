# SPDX-License-Identifier: Apache-2.0
"""E2E test infrastructure for spec 030 Scenario 1 Route Safety (Re-baseline).

Provides:
- Env fixture: monkeypatches UMMAYA_DATA_GO_KR_API_KEY + UMMAYA_KAKAO_REST_KEY
  with dummy values so the startup guard is neutralized without bypass (FR-011/012).
- ToolRegistry + ToolExecutor with both facade tools (resolve_location, lookup)
  and both seed adapters (koroad_accident_hazard_search, kma_forecast_fetch)
  registered through the normal V1-V6 backstop path (FR-009/010).
- httpx.AsyncClient.get AsyncMock seam: URL-pattern routing to JSON tapes under
  tests/fixtures/{kakao,koroad,kma}/. Unmatched URLs raise to fail-close (FR-004).
  Supports per-scenario error-injection tables for degraded-path tests.
- OTelSpanCaptureFixture: installs InMemorySpanExporter, tears down after test,
  exposes ObservabilitySnapshot. Respects OTEL_SDK_DISABLED=true (FR-020).
- MockLLMClient script-loader helpers: one builder per scenario_id literal,
  returning a ScenarioScript with the exact scripted StreamEvent sequence (FR-003).
- scenario_runner fixture: wires QueryEngine.run() + span capture + HTTP mock;
  returns a RunReport aggregate.

All tests use recorded fixtures only; zero live API calls (Constitution §IV).
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from tests.e2e.models import (
    CapturedSpan,
    ObservabilitySnapshot,
    RunReport,
    ScenarioId,
    ScenarioScript,
    ScenarioTurn,
)

# Re-export MockLLMClient from engine test fixtures for reuse
from tests.engine.conftest import MockLLMClient
from ummaya.context.builder import ContextBuilder
from ummaya.engine.config import QueryEngineConfig
from ummaya.engine.engine import QueryEngine
from ummaya.engine.events import QueryEvent, StopReason
from ummaya.llm.client import LLMClient
from ummaya.llm.models import ChatMessage, StreamEvent, TokenUsage
from ummaya.llm.usage import UsageTracker
from ummaya.recovery.executor import RecoveryExecutor
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLMClient-compatible adapter for MockLLMClient
# ---------------------------------------------------------------------------


class _MockLLMClientAdapter(LLMClient):
    """Wrap a MockLLMClient so it satisfies Pydantic's isinstance(LLMClient) check."""

    def __new__(cls, *args: object, **kwargs: object) -> _MockLLMClientAdapter:
        return object.__new__(cls)  # type: ignore[return-value]

    def __init__(self, delegate: MockLLMClient) -> None:
        self._delegate = delegate

    @property
    def usage(self) -> UsageTracker:  # type: ignore[override]
        return self._delegate.usage

    async def stream(  # type: ignore[override]
        self,
        messages: list[ChatMessage],
        **kwargs: object,
    ) -> AsyncIterator[StreamEvent]:
        async for event in self._delegate.stream(messages, **kwargs):
            yield event


# ---------------------------------------------------------------------------
# Fixture file paths
# ---------------------------------------------------------------------------

_FIXTURE_BASE = Path(__file__).resolve().parent.parent / "fixtures"
_KAKAO_FIXTURE_DIR = _FIXTURE_BASE / "kakao"
_KOROAD_FIXTURE_DIR = _FIXTURE_BASE / "koroad"
_KMA_FIXTURE_DIR = _FIXTURE_BASE / "kma"


# ---------------------------------------------------------------------------
# T008: httpx.AsyncClient.get AsyncMock seam with per-scenario error injection
# ---------------------------------------------------------------------------


def _resolve_tape_path(
    adapter_id: str,
    filename: str,
    tape_overrides: dict[str, Path],
) -> Path:
    """Resolve the absolute fixture path for an adapter + filename."""
    if adapter_id in tape_overrides:
        return tape_overrides[adapter_id]
    if adapter_id == "koroad_accident_hazard_search":
        return _KOROAD_FIXTURE_DIR / filename
    if adapter_id == "kma_forecast_fetch":
        return _KMA_FIXTURE_DIR / filename
    if adapter_id.startswith("kakao"):
        return _KAKAO_FIXTURE_DIR / filename
    raise AssertionError(f"No fixture directory for adapter: {adapter_id}")


def _load_tape(
    adapter_id: str,
    filename: str,
    tape_overrides: dict[str, Path],
) -> dict[str, Any]:
    """Load a JSON fixture tape, asserting it exists."""
    path = _resolve_tape_path(adapter_id, filename, tape_overrides)
    if not path.exists():
        raise AssertionError(f"Missing HTTP fixture: {path}")
    return json.loads(path.read_text())


def _koroad_tape_name(url_str: str) -> str:
    """Derive the KOROAD fixture tape filename from the siDo query param."""
    if "siDo=51" in url_str:
        return "accident_hazard_siDo=51_year=2023.json"
    if "siDo=52" in url_str:
        return "accident_hazard_siDo=52_year=2023.json"
    if "siDo=42" in url_str and "year=2022" in url_str:
        return "accident_hazard_siDo=42_year=2022.json"
    if "siDo=45" in url_str and "year=2022" in url_str:
        return "accident_hazard_siDo=45_year=2022.json"
    return "accident_hazard_siDo=11_year=2023.json"


def _kakao_tape_name(url_str: str, params: dict[str, Any] | None) -> str:
    """Derive the Kakao geocoder fixture tape filename from the query string."""
    import urllib.parse

    query_str = ""
    if params:
        query_str = str(params.get("query", ""))
    elif "query=" in url_str:
        parsed = urllib.parse.urlparse(url_str)
        qs = urllib.parse.parse_qs(parsed.query)
        query_str = qs.get("query", [""])[0]

    if "강남구" in query_str or "gangnam" in query_str.lower():
        return "local_search_address_강남구.json"
    if "서울역" in query_str or "seoul_station" in query_str.lower():
        return "local_search_address_서울역.json"
    if "춘천" in query_str or "chuncheon" in query_str.lower():
        return "local_search_address_춘천시.json"
    if "전주" in query_str or "jeonju" in query_str.lower():
        return "local_search_address_전주시.json"
    return "local_search_address_강남구.json"


def _build_httpx_mock(
    tape_overrides: dict[str, Path] | None = None,
    error_table: dict[str, list[str | None]] | None = None,
) -> AsyncMock:
    """Build an AsyncMock for httpx.AsyncClient.get with URL-based routing.

    URL pattern routing (in matching order):
      "getRestFrequentzoneLg" → koroad_accident_hazard_search
      "getVilageFcst"         → kma_forecast_fetch
      "local.kakao.com"       → kakao geocoding (various queries)

    Args:
        tape_overrides: adapter_id → explicit tape Path override.
        error_table: adapter_id → list of error modes per sequential call.
                     Each entry is one of "upstream_down", "retryable", None (success).
                     When the call index exceeds the list, falls back to None (success).

    Returns:
        AsyncMock with side_effect routing to tape files.
    """
    _overrides = tape_overrides or {}
    _errors = error_table or {}
    _counters: dict[str, int] = {}

    def _tape(adapter_id: str, filename: str) -> dict[str, Any]:
        return _load_tape(adapter_id, filename, _overrides)

    def _err_mode(adapter_id: str) -> str | None:
        idx = _counters.get(adapter_id, 0)
        _counters[adapter_id] = idx + 1
        errs = _errors.get(adapter_id, [])
        return errs[idx] if idx < len(errs) else None

    def _resp(url_str: str, data: dict[str, Any]) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json=data,
            request=httpx.Request("GET", url_str),
            headers={"content-type": "application/json"},
        )

    async def _mock_get(
        url: str | httpx.URL,
        *,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        import urllib.parse as _urlparse

        url_str = str(url)
        param_str = "&".join(f"{k}={v}" for k, v in (params or {}).items())
        full_url = f"{url_str}?{param_str}" if params else url_str
        parsed = _urlparse.urlparse(url_str)
        url_host = parsed.netloc or parsed.path
        url_path = parsed.path

        # Route by URL path fragment (API endpoint discriminator)
        if "getRestFrequentzoneLg" in url_path:
            aid = "koroad_accident_hazard_search"
            if _err_mode(aid) == "upstream_down":
                return _resp(url_str, _tape(aid, "accident_hazard_ERROR_upstream_down.json"))
            return _resp(url_str, _tape(aid, _koroad_tape_name(full_url)))

        if "getVilageFcst" in url_path:
            aid = "kma_forecast_fetch"
            if _err_mode(aid) == "upstream_down":
                return _resp(url_str, _tape(aid, "forecast_ERROR_upstream_down.json"))
            kma_tape = "forecast_lat=37.518_lon=127.047_base=20260419_0500.json"
            return _resp(url_str, _tape(aid, kma_tape))

        # Route Kakao geocoder by host suffix (defends against subdomain confusion)
        if url_host.endswith(".kakao.com") or url_host == "kakao.com":
            return _resp(url_str, _tape("kakao", _kakao_tape_name(url_str, params)))

        raise AssertionError(f"Unpatched httpx.get call to URL: {url_str!r}")

    return AsyncMock(side_effect=_mock_get)


# ---------------------------------------------------------------------------
# T009: OTelSpanCaptureFixture helper
# ---------------------------------------------------------------------------


class OTelSpanCaptureFixture:
    """Installs InMemorySpanExporter for the duration of one test.

    Usage::

        capture = OTelSpanCaptureFixture()
        capture.setup()
        # ... run scenario ...
        snapshot = capture.snapshot()  # MUST be called before teardown()
        capture.teardown()

    Strategy: monkeypatch the module-level _tracer in executor.py to a dedicated
    TracerProvider backed by InMemorySpanExporter.  This avoids the OTel SDK
    write-once singleton guard that blocks multiple trace.set_tracer_provider()
    calls across test runs (see tests/observability/test_tool_execute_span.py).

    When OTEL_SDK_DISABLED="true", setup() is a no-op and snapshot() returns
    ObservabilitySnapshot(sdk_disabled=True, spans=()) per FR-020.
    """

    def __init__(self) -> None:
        self._exporter: InMemorySpanExporter | None = None
        self._provider: TracerProvider | None = None
        self._orig_tracer: object = None
        self._sdk_disabled = os.getenv("OTEL_SDK_DISABLED", "").lower() == "true"

    def setup(self) -> None:
        if self._sdk_disabled:
            return
        import ummaya.tools.executor as _executor_mod

        self._exporter = InMemorySpanExporter()
        self._provider = TracerProvider()
        self._provider.add_span_processor(SimpleSpanProcessor(self._exporter))
        # Monkeypatch the module-level _tracer instead of resetting the global
        # provider singleton — consistent with the repo's established pattern.
        self._orig_tracer = _executor_mod._tracer
        _executor_mod._tracer = self._provider.get_tracer("ummaya.tools.executor")

    def teardown(self) -> None:
        if self._sdk_disabled or self._provider is None:
            return
        import ummaya.tools.executor as _executor_mod

        # Restore the original tracer before shutting down the test provider.
        _executor_mod._tracer = self._orig_tracer
        self._provider.force_flush()
        self._provider.shutdown()

    def snapshot(self) -> ObservabilitySnapshot:
        """Return an ObservabilitySnapshot from exported spans."""
        if self._sdk_disabled:
            return ObservabilitySnapshot(sdk_disabled=True, spans=())
        if self._exporter is None:
            return ObservabilitySnapshot(sdk_disabled=False, spans=())

        raw_spans = self._exporter.get_finished_spans()

        captured: list[CapturedSpan] = []
        for span in raw_spans:
            attrs = dict(span.attributes or {})
            tool_name_val = str(attrs.get("gen_ai.tool.name", ""))
            if not tool_name_val:
                continue  # Skip non-tool spans

            outcome_raw = attrs.get("ummaya.tool.outcome")
            if outcome_raw not in ("ok", "error"):
                # FR-017: ummaya.tool.outcome must be "ok" or "error".
                # Missing or invalid value is a contract violation — raise so
                # downstream span tests fail diagnostically rather than being
                # hidden by a dropped or defaulted span.
                raise AssertionError(
                    f"snapshot: span {span.name!r} missing/invalid "
                    f"ummaya.tool.outcome={outcome_raw!r}; expected 'ok' or 'error' — "
                    "executor must set ummaya.tool.outcome before span ends (FR-017)"
                )

            status_code_str: str
            sc = span.status.status_code
            if sc == StatusCode.ERROR:
                status_code_str = "ERROR"
            elif sc == StatusCode.OK:
                status_code_str = "OK"
            else:
                status_code_str = "UNSET"

            error_type_val = str(attrs.get("error.type", "")) or None

            # Prefer gen_ai.operation.name attribute; fall back to name-based inference
            # so existing spans without the attribute still classify correctly.
            op_name_attr = str(attrs.get("gen_ai.operation.name", "")) or None
            if op_name_attr is None and "execute_tool" in span.name:
                op_name_attr = "execute_tool"

            captured_span = CapturedSpan(
                name=span.name,
                operation_name=op_name_attr,  # type: ignore[arg-type]
                tool_name=tool_name_val,
                tool_call_id=str(attrs.get("gen_ai.tool.call.id", "")) or None,
                outcome=outcome_raw,  # type: ignore[arg-type]
                adapter_id=str(attrs.get("ummaya.tool.adapter", "")) or None,
                error_type=error_type_val,
                status_code=status_code_str,  # type: ignore[arg-type]
                attribute_keys=frozenset(attrs.keys()),
            )
            captured.append(captured_span)

        return ObservabilitySnapshot(
            sdk_disabled=False,
            spans=tuple(captured),
        )


# ---------------------------------------------------------------------------
# T010: MockLLMClient script-loader helpers — one builder per scenario_id
# ---------------------------------------------------------------------------

# Canonical trigger query for the happy path
TRIGGER_QUERY = "내일 강남구에서 서울역 가는데 날씨랑 사고다발지역 알려줘"

# Mock args for the scripted turns
_RESOLVE_GANGNAM_ARGS = {"query": "강남구", "want": "coords_and_admcd"}
_RESOLVE_SEOUL_STATION_ARGS = {"query": "서울역", "want": "coords_and_admcd"}
_SEARCH_KOROAD_ARGS = {"mode": "search", "query": "사고다발지역 교통사고"}
_FETCH_KOROAD_ARGS = {
    "mode": "fetch",
    "tool_id": "koroad_accident_hazard_search",
    "params": {"adm_cd": "1168000000", "year": 2023},
}
_SEARCH_KMA_ARGS = {"mode": "search", "query": "날씨 예보 단기예보"}
_FETCH_KMA_ARGS = {
    "mode": "fetch",
    "tool_id": "kma_forecast_fetch",
    "params": {"lat": 37.518, "lon": 127.047, "base_date": "20260419", "base_time": "0500"},
}

_KOREAN_SYNTHESIS = (
    "내일 강남구에서 서울역 가는 경로 안전 정보입니다.\n\n"
    "교통사고 위험지점: 서울특별시 강남구 개포동 일대 (사고 12건), "
    "서울특별시 강남구 삼성동 일대 (사고 9건)이 확인되었습니다.\n\n"
    "날씨 예보: 기온 14°C, 강수확률 10%으로 도로 상태는 양호합니다.\n\n"
    "전반적으로 안전 운행이 가능하나 개포동 일대 사고다발구역을 주의하시기 바랍니다."
)

_DEGRADED_SYNTHESIS = (
    "강남구에서 서울역 가는 경로 일부 정보만 제공 가능합니다.\n\n"
    "날씨 예보: 기온 14°C, 강수확률 10%으로 도로 상태는 양호합니다.\n\n"
    "교통사고 위험지점 데이터를 현재 이용할 수 없습니다. "
    "나중에 다시 시도해 주시기 바랍니다."
)

_BOTH_DOWN_SYNTHESIS = (
    "죄송합니다. 현재 교통사고 위험지점 및 날씨 정보 서비스에 일시적인 "
    "장애가 발생했습니다. 잠시 후 다시 시도해 주시기 바랍니다."
)

_USAGE_TOOL_CALL = TokenUsage(input_tokens=200, output_tokens=50)
_USAGE_SYNTHESIS = TokenUsage(input_tokens=800, output_tokens=150)

# Short alias used in script builders to keep lines under 100 chars.
_U = _USAGE_TOOL_CALL


def _tce(
    tool_name: str,
    args: dict[str, Any],
    call_id: str,
    usage: TokenUsage | None = None,
) -> list[StreamEvent]:
    """Short alias for _make_tool_call_events (script builder line-length)."""
    return _make_tool_call_events(tool_name, args, call_id, usage)


def _make_tool_call_events(
    tool_name: str,
    args: dict[str, Any],
    call_id: str,
    usage: TokenUsage | None = None,
) -> list[StreamEvent]:
    """Build a list of StreamEvents for one scripted tool call."""
    events: list[StreamEvent] = [
        StreamEvent(
            type="tool_call_delta",
            tool_call_index=0,
            tool_call_id=call_id,
            function_name=tool_name,
            function_args_delta=None,
        ),
        StreamEvent(
            type="tool_call_delta",
            tool_call_index=0,
            tool_call_id=None,
            function_name=None,
            function_args_delta=json.dumps(args),
        ),
    ]
    if usage:
        events.append(StreamEvent(type="usage", usage=usage))
    events.append(StreamEvent(type="done"))
    return events


def _make_text_events(content: str, usage: TokenUsage | None = None) -> list[StreamEvent]:
    """Build a list of StreamEvents for the synthesis text."""
    events: list[StreamEvent] = [
        StreamEvent(type="content_delta", content=content),
    ]
    if usage:
        events.append(StreamEvent(type="usage", usage=usage))
    events.append(StreamEvent(type="done"))
    return events


def build_happy_script() -> tuple[list[list[StreamEvent]], ScenarioScript]:
    """Build the 6-turn happy-path script (resolve x2, search x2, fetch x2, synthesize)."""
    turns_events = [
        _tce("locate", _RESOLVE_GANGNAM_ARGS, "call_001", _U),
        _tce("locate", _RESOLVE_SEOUL_STATION_ARGS, "call_002", _U),
        _tce("find", _SEARCH_KOROAD_ARGS, "call_003", _U),
        _tce("find", _FETCH_KOROAD_ARGS, "call_004", _U),
        _tce("find", _SEARCH_KMA_ARGS, "call_005", _U),
        _tce("find", _FETCH_KMA_ARGS, "call_006", _U),
        _make_text_events(_KOREAN_SYNTHESIS, _USAGE_SYNTHESIS),
    ]

    scenario_turns = (
        ScenarioTurn(
            index=0,
            kind="tool_call",
            tool_name="locate",
            tool_arguments=_RESOLVE_GANGNAM_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=1,
            kind="tool_call",
            tool_name="locate",
            tool_arguments=_RESOLVE_SEOUL_STATION_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=2,
            kind="tool_call",
            tool_name="find",
            tool_arguments=_SEARCH_KOROAD_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=3,
            kind="tool_call",
            tool_name="find",
            tool_arguments=_FETCH_KOROAD_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=4,
            kind="tool_call",
            tool_name="find",
            tool_arguments=_SEARCH_KMA_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=5,
            kind="tool_call",
            tool_name="find",
            tool_arguments=_FETCH_KMA_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=6, kind="text_delta", text_content=_KOREAN_SYNTHESIS, token_usage=_USAGE_SYNTHESIS
        ),
    )
    script = ScenarioScript(
        scenario_id="happy",
        turns=scenario_turns,
        expected_stop_reason="end_turn",
    )
    return turns_events, script


def build_degraded_kma_retry_script() -> tuple[list[list[StreamEvent]], ScenarioScript]:
    """KMA first call fails (retryable), second succeeds; KOROAD succeeds."""
    # Simulate: KMA fetch fails first, engine retries, then synthesizes with both data
    turns_events = [
        _tce("locate", _RESOLVE_GANGNAM_ARGS, "call_001", _U),
        _tce("locate", _RESOLVE_SEOUL_STATION_ARGS, "call_002", _U),
        _tce("find", _SEARCH_KOROAD_ARGS, "call_003", _U),
        _tce("find", _FETCH_KOROAD_ARGS, "call_004", _U),
        _tce("find", _SEARCH_KMA_ARGS, "call_005", _U),
        # KMA fetch — first attempt returns error, retry on same tool call
        _tce("find", _FETCH_KMA_ARGS, "call_006", _U),
        _tce("find", _FETCH_KMA_ARGS, "call_007r", _U),
        _make_text_events(_KOREAN_SYNTHESIS, _USAGE_SYNTHESIS),
    ]
    scenario_turns = (
        ScenarioTurn(
            index=0,
            kind="tool_call",
            tool_name="locate",
            tool_arguments=_RESOLVE_GANGNAM_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=1,
            kind="tool_call",
            tool_name="locate",
            tool_arguments=_RESOLVE_SEOUL_STATION_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=2,
            kind="tool_call",
            tool_name="find",
            tool_arguments=_SEARCH_KOROAD_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=3,
            kind="tool_call",
            tool_name="find",
            tool_arguments=_FETCH_KOROAD_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=4,
            kind="tool_call",
            tool_name="find",
            tool_arguments=_SEARCH_KMA_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=5,
            kind="tool_call",
            tool_name="find",
            tool_arguments=_FETCH_KMA_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=6,
            kind="tool_call",
            tool_name="find",
            tool_arguments=_FETCH_KMA_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=7, kind="text_delta", text_content=_KOREAN_SYNTHESIS, token_usage=_USAGE_SYNTHESIS
        ),
    )
    script = ScenarioScript(
        scenario_id="degraded_kma_retry",
        turns=scenario_turns,
        expected_stop_reason="end_turn",
    )
    return turns_events, script


def build_degraded_koroad_no_retry_script() -> tuple[list[list[StreamEvent]], ScenarioScript]:
    """KOROAD fails (no retry); KMA succeeds; synthesis references KMA data + gap note."""
    turns_events = [
        _tce("locate", _RESOLVE_GANGNAM_ARGS, "call_001", _U),
        _tce("locate", _RESOLVE_SEOUL_STATION_ARGS, "call_002", _U),
        _tce("find", _SEARCH_KOROAD_ARGS, "call_003", _U),
        _tce("find", _FETCH_KOROAD_ARGS, "call_004", _U),
        _tce("find", _SEARCH_KMA_ARGS, "call_005", _U),
        _tce("find", _FETCH_KMA_ARGS, "call_006", _U),
        _make_text_events(_DEGRADED_SYNTHESIS, _USAGE_SYNTHESIS),
    ]
    scenario_turns = (
        ScenarioTurn(
            index=0,
            kind="tool_call",
            tool_name="locate",
            tool_arguments=_RESOLVE_GANGNAM_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=1,
            kind="tool_call",
            tool_name="locate",
            tool_arguments=_RESOLVE_SEOUL_STATION_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=2,
            kind="tool_call",
            tool_name="find",
            tool_arguments=_SEARCH_KOROAD_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=3,
            kind="tool_call",
            tool_name="find",
            tool_arguments=_FETCH_KOROAD_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=4,
            kind="tool_call",
            tool_name="find",
            tool_arguments=_SEARCH_KMA_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=5,
            kind="tool_call",
            tool_name="find",
            tool_arguments=_FETCH_KMA_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=6,
            kind="text_delta",
            text_content=_DEGRADED_SYNTHESIS,
            token_usage=_USAGE_SYNTHESIS,
        ),
    )
    script = ScenarioScript(
        scenario_id="degraded_koroad_no_retry",
        turns=scenario_turns,
        expected_stop_reason="end_turn",
    )
    return turns_events, script


def build_both_down_script() -> tuple[list[list[StreamEvent]], ScenarioScript]:
    """Both adapters fail; engine produces graceful Korean error message."""
    turns_events = [
        _tce("locate", _RESOLVE_GANGNAM_ARGS, "call_001", _U),
        _tce("locate", _RESOLVE_SEOUL_STATION_ARGS, "call_002", _U),
        _tce("find", _SEARCH_KOROAD_ARGS, "call_003", _U),
        _tce("find", _FETCH_KOROAD_ARGS, "call_004", _U),
        _tce("find", _SEARCH_KMA_ARGS, "call_005", _U),
        _tce("find", _FETCH_KMA_ARGS, "call_006", _U),
        _make_text_events(_BOTH_DOWN_SYNTHESIS, _USAGE_SYNTHESIS),
    ]
    scenario_turns = (
        ScenarioTurn(
            index=0,
            kind="tool_call",
            tool_name="locate",
            tool_arguments=_RESOLVE_GANGNAM_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=1,
            kind="tool_call",
            tool_name="locate",
            tool_arguments=_RESOLVE_SEOUL_STATION_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=2,
            kind="tool_call",
            tool_name="find",
            tool_arguments=_SEARCH_KOROAD_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=3,
            kind="tool_call",
            tool_name="find",
            tool_arguments=_FETCH_KOROAD_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=4,
            kind="tool_call",
            tool_name="find",
            tool_arguments=_SEARCH_KMA_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=5,
            kind="tool_call",
            tool_name="find",
            tool_arguments=_FETCH_KMA_ARGS,
            token_usage=_USAGE_TOOL_CALL,
        ),
        ScenarioTurn(
            index=6,
            kind="text_delta",
            text_content=_BOTH_DOWN_SYNTHESIS,
            token_usage=_USAGE_SYNTHESIS,
        ),
    )
    script = ScenarioScript(
        scenario_id="both_down",
        turns=scenario_turns,
        expected_stop_reason="end_turn",
    )
    return turns_events, script


def build_quirk_2023_gangwon_script() -> tuple[list[list[StreamEvent]], ScenarioScript]:
    """2023 강원도 quirk: adm_cd prefix 42xxx → siDo=51."""
    gangwon_resolve_args = {"query": "강원도 춘천시", "want": "coords_and_admcd"}
    fetch_gangwon_args = {
        "mode": "fetch",
        "tool_id": "koroad_accident_hazard_search",
        "params": {"adm_cd": "4211000000", "year": 2023},
    }
    korean_response = (
        "강원도 춘천시 2023년 교통사고 위험지점 정보입니다.\n"
        "춘천 중심가 일대에 사고다발구역이 확인되었습니다."
    )
    turns_events = [
        _tce("locate", gangwon_resolve_args, "call_001", _U),
        _tce("find", _SEARCH_KOROAD_ARGS, "call_002", _U),
        _tce("find", fetch_gangwon_args, "call_003", _U),
        _make_text_events(korean_response, _USAGE_SYNTHESIS),
    ]
    scenario_turns = (
        ScenarioTurn(
            index=0,
            kind="tool_call",
            tool_name="locate",
            tool_arguments=gangwon_resolve_args,
            token_usage=_U,
        ),
        ScenarioTurn(
            index=1,
            kind="tool_call",
            tool_name="find",
            tool_arguments=_SEARCH_KOROAD_ARGS,
            token_usage=_U,
        ),
        ScenarioTurn(
            index=2,
            kind="tool_call",
            tool_name="find",
            tool_arguments=fetch_gangwon_args,
            token_usage=_U,
        ),
        ScenarioTurn(
            index=3, kind="text_delta", text_content=korean_response, token_usage=_USAGE_SYNTHESIS
        ),
    )
    script = ScenarioScript(
        scenario_id="quirk_2023_gangwon",
        turns=scenario_turns,
        expected_stop_reason="end_turn",
    )
    return turns_events, script


def build_quirk_2023_jeonbuk_script() -> tuple[list[list[StreamEvent]], ScenarioScript]:
    """2023 전북 quirk: adm_cd prefix 45xxx → siDo=52."""
    jeonbuk_resolve_args = {"query": "전북 전주시", "want": "coords_and_admcd"}
    fetch_jeonbuk_args = {
        "mode": "fetch",
        "tool_id": "koroad_accident_hazard_search",
        "params": {"adm_cd": "4511000000", "year": 2023},
    }
    korean_response = (
        "전북 전주시 2023년 교통사고 위험지점 정보입니다.\n"
        "전주 도심 일대에 사고다발구역이 확인되었습니다."
    )
    turns_events = [
        _tce("locate", jeonbuk_resolve_args, "call_001", _U),
        _tce("find", _SEARCH_KOROAD_ARGS, "call_002", _U),
        _tce("find", fetch_jeonbuk_args, "call_003", _U),
        _make_text_events(korean_response, _USAGE_SYNTHESIS),
    ]
    scenario_turns = (
        ScenarioTurn(
            index=0,
            kind="tool_call",
            tool_name="locate",
            tool_arguments=jeonbuk_resolve_args,
            token_usage=_U,
        ),
        ScenarioTurn(
            index=1,
            kind="tool_call",
            tool_name="find",
            tool_arguments=_SEARCH_KOROAD_ARGS,
            token_usage=_U,
        ),
        ScenarioTurn(
            index=2,
            kind="tool_call",
            tool_name="find",
            tool_arguments=fetch_jeonbuk_args,
            token_usage=_U,
        ),
        ScenarioTurn(
            index=3, kind="text_delta", text_content=korean_response, token_usage=_USAGE_SYNTHESIS
        ),
    )
    script = ScenarioScript(
        scenario_id="quirk_2023_jeonbuk",
        turns=scenario_turns,
        expected_stop_reason="end_turn",
    )
    return turns_events, script


def build_quirk_2022_control_script() -> tuple[list[list[StreamEvent]], ScenarioScript]:
    """2022 control: adm_cd prefix 42xxx → siDo=42 (no substitution for pre-2023)."""
    gangwon_resolve_args = {"query": "강원도 춘천시", "want": "coords_and_admcd"}
    fetch_gangwon_2022_args = {
        "mode": "fetch",
        "tool_id": "koroad_accident_hazard_search",
        "params": {"adm_cd": "4211000000", "year": 2022},
    }
    korean_response = (
        "강원도 춘천시 2022년 교통사고 위험지점 정보입니다.\n"
        "2022년 기준 춘천 지역 사고다발구역이 확인되었습니다."
    )
    turns_events = [
        _tce("locate", gangwon_resolve_args, "call_001", _U),
        _tce("find", _SEARCH_KOROAD_ARGS, "call_002", _U),
        _tce("find", fetch_gangwon_2022_args, "call_003", _U),
        _make_text_events(korean_response, _USAGE_SYNTHESIS),
    ]
    scenario_turns = (
        ScenarioTurn(
            index=0,
            kind="tool_call",
            tool_name="locate",
            tool_arguments=gangwon_resolve_args,
            token_usage=_U,
        ),
        ScenarioTurn(
            index=1,
            kind="tool_call",
            tool_name="find",
            tool_arguments=_SEARCH_KOROAD_ARGS,
            token_usage=_U,
        ),
        ScenarioTurn(
            index=2,
            kind="tool_call",
            tool_name="find",
            tool_arguments=fetch_gangwon_2022_args,
            token_usage=_U,
        ),
        ScenarioTurn(
            index=3, kind="text_delta", text_content=korean_response, token_usage=_USAGE_SYNTHESIS
        ),
    )
    script = ScenarioScript(
        scenario_id="quirk_2022_control",
        turns=scenario_turns,
        expected_stop_reason="end_turn",
    )
    return turns_events, script


_SCRIPT_BUILDERS = {
    "happy": build_happy_script,
    "degraded_kma_retry": build_degraded_kma_retry_script,
    "degraded_koroad_no_retry": build_degraded_koroad_no_retry_script,
    "both_down": build_both_down_script,
    "quirk_2023_gangwon": build_quirk_2023_gangwon_script,
    "quirk_2023_jeonbuk": build_quirk_2023_jeonbuk_script,
    "quirk_2022_control": build_quirk_2022_control_script,
}


def get_script(scenario_id: ScenarioId) -> tuple[list[list[StreamEvent]], ScenarioScript]:
    """Return (event_sequences, ScenarioScript) for the given scenario_id."""
    builder = _SCRIPT_BUILDERS[scenario_id]
    return builder()


# ---------------------------------------------------------------------------
# Env setup (FR-011/012)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def e2e_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required env vars via monkeypatch so startup guard is neutralized (FR-012).

    Uses dummy values — no real keys are committed or exposed (FR-011).
    """
    monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "test-dummy-data-go-kr")
    monkeypatch.setenv("UMMAYA_KAKAO_API_KEY", "test-dummy-kakao")
    monkeypatch.setenv("UMMAYA_FRIENDLI_TOKEN", "test-dummy-friendli")


# ---------------------------------------------------------------------------
# Registry + Executor factory
# ---------------------------------------------------------------------------


def _build_registry_and_executor() -> tuple[ToolRegistry, ToolExecutor]:
    """Create a ToolRegistry and ToolExecutor with all required adapters.

    Registers executor adapters for:
    - resolve_location: wraps resolve_location() coroutine; httpx.AsyncClient.get
      is patched at the class level by run_scenario() so no explicit client arg needed.
    - find: wraps lookup() coroutine; captures registry + executor in closure so
      lookup(mode=search) can use the BM25 index and lookup(mode=fetch) can invoke
      the concrete data adapters via executor.invoke().
    - koroad_accident_hazard_search: KOROAD data adapter (V1-V6 validated).
    - kma_forecast_fetch: KMA forecast adapter (V1-V6 validated).

    All tools are registered through ToolRegistry.register() so V1-V6 backstop
    checks run (FR-009/010). No bypass path.
    """

    from pydantic import BaseModel

    from ummaya.tools.kma.forecast_fetch import (
        KMA_FORECAST_FETCH_TOOL,
        KmaForecastFetchInput,
    )
    from ummaya.tools.kma.forecast_fetch import (
        _fetch as kma_forecast_fetch_fn,
    )
    from ummaya.tools.koroad.accident_hazard_search import register as reg_koroad_hazard
    from ummaya.tools.lookup import lookup as _lookup_fn
    from ummaya.tools.models import LookupFetchInput, LookupSearchInput, ResolveLocationInput
    from ummaya.tools.resolve_location import resolve_location as _resolve_location_fn

    registry = ToolRegistry()
    recovery = RecoveryExecutor()
    executor = ToolExecutor(registry, recovery_executor=recovery)

    # Register MVP LLM-visible surface (locate + find)
    from ummaya.tools.mvp_surface import register_mvp_surface

    register_mvp_surface(registry)

    # Register resolve_location executor adapter.
    # resolve_location() uses httpx.AsyncClient internally; the class-level
    # patch.object(httpx.AsyncClient, "get", httpx_mock) in run_scenario() covers it.
    # Use model_dump(mode="json") so datetime/UUID fields serialize to JSON-safe types.
    async def _resolve_location_adapter(inp: BaseModel) -> dict[str, Any]:
        assert isinstance(inp, ResolveLocationInput)
        result = await _resolve_location_fn(inp)
        return result.model_dump(mode="json")

    executor.register_adapter("locate", _resolve_location_adapter)

    # Register lookup executor adapter.
    # _LookupInput is a RootModel wrapper; inp.root is the actual discriminated input.
    # registry and executor are captured here so lookup() can perform BM25 search
    # (search mode) and executor.invoke() dispatch (fetch mode).
    # Use model_dump(mode="json") so all fields are JSON-safe (no datetime/UUID objects).
    # LookupError is returned as structured data (kind="error") rather than raised as
    # an exception — this preserves the structured error payload so the LLM receives
    # the full context and downstream assertions can check kind=="error" in the result.
    async def _lookup_adapter(inp: BaseModel) -> dict[str, Any]:
        actual_inp = inp.root if hasattr(inp, "root") else inp  # type: ignore[attr-defined]
        assert isinstance(actual_inp, (LookupSearchInput, LookupFetchInput))
        result = await _lookup_fn(actual_inp, registry=registry, executor=executor)
        return result.model_dump(mode="json")

    executor.register_adapter("find", _lookup_adapter)

    # Register KOROAD adapter (with V1-V6 validation)
    reg_koroad_hazard(registry, executor)

    # Register KMA forecast_fetch adapter (with V1-V6 validation)
    registry.register(KMA_FORECAST_FETCH_TOOL)

    async def _kma_adapter(inp: BaseModel) -> dict[str, Any]:
        assert isinstance(inp, KmaForecastFetchInput)
        result = await kma_forecast_fetch_fn(inp)
        return result.model_dump() if hasattr(result, "model_dump") else dict(result)

    executor.register_adapter("kma_forecast_fetch", _kma_adapter)

    return registry, executor


# ---------------------------------------------------------------------------
# scenario_runner fixture
# ---------------------------------------------------------------------------


def _map_stop_reason(events: list[QueryEvent]) -> str:
    """Map raw StopReason from engine events to RunReport stop_reason literal."""
    stop_events = [e for e in events if e.type == "stop"]
    raw = stop_events[-1].stop_reason if stop_events else StopReason.error_unrecoverable
    if raw in (StopReason.end_turn, StopReason.task_complete):
        return "end_turn"
    if raw == StopReason.api_budget_exceeded:
        return "api_budget_exceeded"
    return "error_unrecoverable"


def _extract_fetched_adapters(events: list[QueryEvent]) -> list[str]:
    """Return adapter IDs from actual fetch-only find tool_use events.

    Derived from emitted QueryEvents rather than the scripted ScenarioScript
    so that regressions where find targets the wrong tool_id are caught.
    """
    result: list[str] = []
    for event in events:
        if event.type != "tool_use" or event.tool_name != "find":
            continue
        if not event.arguments:
            continue
        try:
            args = json.loads(event.arguments)
        except (json.JSONDecodeError, TypeError):
            continue
        if args.get("mode") == "fetch":
            tool_id = args.get("tool_id")
            if tool_id:
                result.append(str(tool_id))
    return result


def _extract_usage_totals(events: list[QueryEvent]) -> TokenUsage:
    """Sum all usage_update events into a single TokenUsage aggregate."""
    total_input = 0
    total_output = 0
    for event in events:
        if event.type == "usage_update" and event.usage is not None:
            total_input += event.usage.input_tokens or 0
            total_output += event.usage.output_tokens or 0
    return TokenUsage(input_tokens=total_input, output_tokens=total_output)


def _build_report(
    *,
    scenario_id: ScenarioId,
    tool_call_order: tuple[str, ...],
    fetched_adapters: list[str],
    final_response: str | None,
    stop_reason_str: str,
    usage_totals: TokenUsage,
    obs_snapshot: ObservabilitySnapshot,
    adapter_hits: dict[str, int],
    elapsed_ms: int,
) -> RunReport:
    """Construct a RunReport preserving the real observability snapshot.

    sdk_disabled reflects only OTEL_SDK_DISABLED (set by OTelSpanCaptureFixture).
    I7 enforcement (fetched_adapter_ids == adapter span count) is gated in
    RunReport._check_invariants: when span_adapter_count==0 (executor not yet
    emitting ummaya.tool.adapter), I7 is not triggered.  A warning is emitted
    here so the instrumentation gap is visible in logs.
    """
    if not obs_snapshot.sdk_disabled:
        span_adapter_count = sum(1 for s in obs_snapshot.spans if s.adapter_id is not None)
        if span_adapter_count != len(fetched_adapters):
            logger.warning(
                "_build_report: span adapter count (%d) != fetched adapters (%d); "
                "%d total tool spans — ummaya.tool.adapter not yet emitted by executor",
                span_adapter_count,
                len(fetched_adapters),
                len(obs_snapshot.spans),
            )
    return RunReport(
        scenario_id=scenario_id,
        trigger_query=TRIGGER_QUERY,
        tool_call_order=tool_call_order,
        fetched_adapter_ids=tuple(fetched_adapters),
        final_response=final_response,
        stop_reason=stop_reason_str,  # type: ignore[arg-type]
        usage_totals=usage_totals,
        observability=obs_snapshot,
        adapter_rate_limit_hits=adapter_hits,
        elapsed_ms=elapsed_ms,
    )


async def run_scenario(
    scenario_id: ScenarioId,
    *,
    error_table: dict[str, list[str | None]] | None = None,
    tape_overrides: dict[str, Path] | None = None,
) -> RunReport:
    """Wire QueryEngine.run() + span capture + HTTP mock; return RunReport.

    Args:
        scenario_id: One of the canonical ScenarioId literals.
        error_table: Per-adapter sequential error injection (for degraded tests).
        tape_overrides: Explicit tape Path overrides per adapter.

    Returns:
        A fully populated RunReport.
    """
    import time as _time

    event_sequences, script = get_script(scenario_id)

    registry, executor = _build_registry_and_executor()
    context_builder = ContextBuilder(registry=registry)
    mock_llm = MockLLMClient(responses=event_sequences)
    llm_adapter = _MockLLMClientAdapter(mock_llm)
    config = QueryEngineConfig()
    engine = QueryEngine(
        llm_client=llm_adapter,
        tool_registry=registry,
        tool_executor=executor,
        config=config,
        context_builder=context_builder,
    )

    otel = OTelSpanCaptureFixture()
    otel.setup()
    httpx_mock = _build_httpx_mock(tape_overrides=tape_overrides, error_table=error_table)

    t_start = _time.monotonic()
    events: list[QueryEvent] = []
    try:
        with patch.object(httpx.AsyncClient, "get", httpx_mock):
            async for event in engine.run(TRIGGER_QUERY):
                events.append(event)
    finally:
        # Snapshot MUST be taken before teardown — teardown flushes/shuts provider.
        obs_snapshot = otel.snapshot()
        otel.teardown()

    elapsed_ms = int((_time.monotonic() - t_start) * 1000)
    stop_reason_str = _map_stop_reason(events)
    tool_call_order = tuple(e.tool_name for e in events if e.type == "tool_use")
    fetched_adapters = _extract_fetched_adapters(events)
    text_parts = [e.content for e in events if e.type == "text_delta" and e.content]
    final_response = "".join(text_parts) if text_parts else None
    usage_totals = _extract_usage_totals(events)

    adapter_hits: dict[str, int] = {}
    for aid in fetched_adapters:
        adapter_hits[aid] = adapter_hits.get(aid, 0) + 1

    return _build_report(
        scenario_id=scenario_id,
        tool_call_order=tool_call_order,
        fetched_adapters=fetched_adapters,
        final_response=final_response,
        stop_reason_str=stop_reason_str,
        usage_totals=usage_totals,
        obs_snapshot=obs_snapshot,
        adapter_hits=adapter_hits,
        elapsed_ms=elapsed_ms,
    )


# ---------------------------------------------------------------------------
# meta-block assertion helper (FR-007) — reused by US1 and US2
# ---------------------------------------------------------------------------


def assert_meta_block(data: dict[str, Any], source_hint: str | None = None) -> None:
    """Assert that a LookupOutput dict carries a valid meta block.

    FR-007: meta must contain source, fetched_at (ISO-8601), request_id (UUID4),
    elapsed_ms.
    """
    meta = data.get("meta")
    assert meta is not None, f"meta block missing from output (source_hint={source_hint!r})"
    assert "source" in meta, f"meta.source missing (meta={meta!r})"
    assert "fetched_at" in meta, f"meta.fetched_at missing (meta={meta!r})"
    assert "request_id" in meta, f"meta.request_id missing (meta={meta!r})"
    assert "elapsed_ms" in meta, f"meta.elapsed_ms missing (meta={meta!r})"

    # Validate source is non-empty
    assert meta["source"], "meta.source must be non-empty"

    # Validate fetched_at looks like ISO-8601 (basic check)
    fetched_at = str(meta["fetched_at"])
    assert "T" in fetched_at or len(fetched_at) >= 10, (
        f"meta.fetched_at does not look like ISO-8601: {fetched_at!r}"
    )

    if source_hint:
        assert source_hint in str(meta["source"]), (
            f"meta.source={meta['source']!r} does not contain {source_hint!r}"
        )
