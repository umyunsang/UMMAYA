# SPDX-License-Identifier: Apache-2.0
"""Tests for 401 auth-refresh logic."""

from __future__ import annotations

import httpx
import pytest
from pydantic import BaseModel

from ummaya.recovery.auth_refresh import attempt_auth_refresh, get_credential
from ummaya.recovery.circuit_breaker import CircuitBreakerConfig
from ummaya.recovery.classifier import ErrorClass
from ummaya.recovery.executor import RecoveryExecutor
from ummaya.recovery.retry import ToolRetryPolicy
from ummaya.tools.models import GovAPITool

# ---------------------------------------------------------------------------
# attempt_auth_refresh — env var behaviour
# ---------------------------------------------------------------------------


async def test_attempt_auth_refresh_returns_true_when_specific_var_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Returns True when the tool-specific env var is present."""
    monkeypatch.setenv("UMMAYA_MY_TOOL_API_KEY", "secret_key_value")
    result = await attempt_auth_refresh("my_tool")
    assert result is True


async def test_attempt_auth_refresh_returns_true_when_global_var_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Returns True when only the global UMMAYA_API_KEY is set."""
    monkeypatch.delenv("UMMAYA_MY_TOOL_API_KEY", raising=False)
    monkeypatch.delenv("UMMAYA_DATA_GO_KR_API_KEY", raising=False)
    monkeypatch.setenv("UMMAYA_API_KEY", "global_key")
    result = await attempt_auth_refresh("my_tool")
    assert result is True


async def test_attempt_auth_refresh_returns_false_when_no_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Returns False when neither the specific nor global env var is present."""
    monkeypatch.delenv("UMMAYA_MY_TOOL_API_KEY", raising=False)
    monkeypatch.delenv("UMMAYA_DATA_GO_KR_API_KEY", raising=False)
    monkeypatch.delenv("UMMAYA_API_KEY", raising=False)
    result = await attempt_auth_refresh("my_tool")
    assert result is False


async def test_attempt_auth_refresh_returns_false_for_empty_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Returns False when the env var is set to an empty string."""
    monkeypatch.setenv("UMMAYA_MY_TOOL_API_KEY", "")
    monkeypatch.delenv("UMMAYA_DATA_GO_KR_API_KEY", raising=False)
    monkeypatch.delenv("UMMAYA_API_KEY", raising=False)
    result = await attempt_auth_refresh("my_tool")
    assert result is False


async def test_attempt_auth_refresh_prefers_specific_over_global(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tool-specific key takes precedence over the global fallback."""
    monkeypatch.setenv("UMMAYA_SPECIFIC_TOOL_API_KEY", "specific_val")
    monkeypatch.setenv("UMMAYA_API_KEY", "global_val")
    result = await attempt_auth_refresh("specific_tool")
    assert result is True


# ---------------------------------------------------------------------------
# get_credential helper
# ---------------------------------------------------------------------------


def test_get_credential_returns_specific_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UMMAYA_MYAPI_API_KEY", "the_key")
    assert get_credential("myapi") == "the_key"


def test_get_credential_falls_back_to_global(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UMMAYA_MYAPI_API_KEY", raising=False)
    monkeypatch.delenv("UMMAYA_DATA_GO_KR_API_KEY", raising=False)
    monkeypatch.setenv("UMMAYA_API_KEY", "global_key")
    assert get_credential("myapi") == "global_key"


def test_get_credential_returns_none_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UMMAYA_MYAPI_API_KEY", raising=False)
    monkeypatch.delenv("UMMAYA_DATA_GO_KR_API_KEY", raising=False)
    monkeypatch.delenv("UMMAYA_API_KEY", raising=False)
    assert get_credential("myapi") is None


# ---------------------------------------------------------------------------
# 401 handling in RecoveryExecutor — integration-style
# ---------------------------------------------------------------------------


class _DummyInput(BaseModel):
    query: str


class _DummyOutput(BaseModel):
    result: str


@pytest.fixture()
def auth_tool() -> GovAPITool:
    # Spec-024 V5: requires_auth=True ⇒ auth_level must be at least AAL1 (not
    # 'public'). This tool exercises 401-refresh flow, so it is correctly
    # authenticated.
    return GovAPITool(
        id="auth_test_tool",
        name_ko="인증 테스트 도구",
        ministry="OTHER",
        category=["test"],
        endpoint="https://api.example.com/",
        auth_type="api_key",
        input_schema=_DummyInput,
        output_schema=_DummyOutput,
        search_hint="auth test",
        auth_level="AAL1",
        pipa_class="non_personal",
        is_irreversible=False,
        dpa_reference=None,
        requires_auth=True,
        is_concurrency_safe=False,
        is_personal_data=False,
        cache_ttl_seconds=0,
        rate_limit_per_minute=60,
    )


@pytest.fixture()
def fast_executor() -> RecoveryExecutor:
    return RecoveryExecutor(
        retry_policy=ToolRetryPolicy(
            max_retries=0,  # no retries — 401 should still get one extra attempt
            base_delay=0.0,
            multiplier=1.0,
            max_delay=0.0,
        ),
        circuit_config=CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=60.0,
        ),
    )


async def test_401_triggers_auth_refresh_and_succeeds_on_retry(
    fast_executor: RecoveryExecutor,
    auth_tool: GovAPITool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After a 401, auth refresh succeeds (env var present) and retry succeeds."""
    monkeypatch.setenv("UMMAYA_AUTH_TEST_TOOL_API_KEY", "refreshed_key")

    call_count = 0
    request = httpx.Request("GET", "https://api.example.com/")
    response_401 = httpx.Response(401, request=request)
    exc_401 = httpx.HTTPStatusError("401", request=request, response=response_401)

    async def adapter(args: object) -> dict[str, object]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise exc_401
        return {"result": "ok"}

    result = await fast_executor.execute(auth_tool, adapter, _DummyInput(query="test"))
    assert result.tool_result.success is True
    assert result.tool_result.data == {"result": "ok"}
    assert call_count == 2  # initial + post-refresh retry


async def test_401_without_credentials_returns_auth_expired(
    fast_executor: RecoveryExecutor,
    auth_tool: GovAPITool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """401 with no credentials available results in auth_expired error."""
    monkeypatch.delenv("UMMAYA_AUTH_TEST_TOOL_API_KEY", raising=False)
    monkeypatch.delenv("UMMAYA_DATA_GO_KR_API_KEY", raising=False)
    monkeypatch.delenv("UMMAYA_API_KEY", raising=False)

    request = httpx.Request("GET", "https://api.example.com/")
    response_401 = httpx.Response(401, request=request)
    exc_401 = httpx.HTTPStatusError("401", request=request, response=response_401)

    async def always_401(args: object) -> dict[str, object]:
        raise exc_401

    result = await fast_executor.execute(auth_tool, always_401, _DummyInput(query="x"))
    assert result.tool_result.success is False
    assert result.tool_result.error_type == "auth_expired"


async def test_401_with_refresh_but_still_fails_returns_error(
    fast_executor: RecoveryExecutor,
    auth_tool: GovAPITool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """401 even after credential refresh results in auth_expired."""
    monkeypatch.setenv("UMMAYA_AUTH_TEST_TOOL_API_KEY", "some_key")

    request = httpx.Request("GET", "https://api.example.com/")
    response_401 = httpx.Response(401, request=request)
    exc_401 = httpx.HTTPStatusError("401", request=request, response=response_401)

    async def always_401(args: object) -> dict[str, object]:
        raise exc_401

    result = await fast_executor.execute(auth_tool, always_401, _DummyInput(query="x"))
    assert result.tool_result.success is False
    assert result.tool_result.error_type == "auth_expired"


async def test_401_classification_in_classifier() -> None:
    """DataGoKrErrorClassifier maps HTTP 401 to AUTH_EXPIRED."""
    from ummaya.recovery.classifier import DataGoKrErrorClassifier

    clf = DataGoKrErrorClassifier()
    result = clf.classify_response(401, "Unauthorized")
    assert result.error_class == ErrorClass.AUTH_EXPIRED
    # AUTH_EXPIRED is not in the retryable set — handled separately
    assert result.is_retryable is False


async def test_403_still_maps_to_auth_failure() -> None:
    """HTTP 403 maps to AUTH_FAILURE (not AUTH_EXPIRED)."""
    from ummaya.recovery.classifier import DataGoKrErrorClassifier

    clf = DataGoKrErrorClassifier()
    result = clf.classify_response(403, "Forbidden")
    assert result.error_class == ErrorClass.AUTH_FAILURE


# ---------------------------------------------------------------------------
# Provider-aware credential resolution regressions
# ---------------------------------------------------------------------------


async def test_kakao_tool_refresh_uses_kakao_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: Kakao-backed tools must discover UMMAYA_KAKAO_API_KEY."""
    monkeypatch.delenv("UMMAYA_ADDRESS_TO_REGION_API_KEY", raising=False)
    monkeypatch.delenv("UMMAYA_DATA_GO_KR_API_KEY", raising=False)
    monkeypatch.delenv("UMMAYA_API_KEY", raising=False)
    monkeypatch.setenv("UMMAYA_KAKAO_API_KEY", "kakao-key")

    assert await attempt_auth_refresh("address_to_region") is True
    assert get_credential("address_to_region") == "kakao-key"


async def test_data_go_kr_tool_refresh_uses_data_go_kr_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: data.go.kr tools discover UMMAYA_DATA_GO_KR_API_KEY."""
    monkeypatch.delenv("UMMAYA_KOROAD_ACCIDENT_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("UMMAYA_KAKAO_API_KEY", raising=False)
    monkeypatch.delenv("UMMAYA_API_KEY", raising=False)
    monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "data-key")

    assert await attempt_auth_refresh("koroad_accident_search") is True
    assert get_credential("koroad_accident_search") == "data-key"


async def test_all_live_data_go_kr_adapters_use_shared_data_go_kr_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every live data.go.kr adapter should share the provider credential."""
    monkeypatch.delenv("UMMAYA_API_KEY", raising=False)
    monkeypatch.delenv("UMMAYA_KAKAO_API_KEY", raising=False)
    monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "data-key")

    tool_ids = [
        "koroad_accident_search",
        "koroad_accident_hazard_search",
        "kma_weather_alert_status",
        "kma_pre_warning",
        "hira_hospital_search",
        "nmc_emergency_search",
        "nfa_emergency_info_service",
        "mohw_welfare_eligibility_search",
    ]
    for tool_id in tool_ids:
        monkeypatch.delenv(f"UMMAYA_{tool_id.upper()}_API_KEY", raising=False)
        assert await attempt_auth_refresh(tool_id) is True
        assert get_credential(tool_id) == "data-key"


async def test_kma_vilage_fcst_adapters_use_api_hub_auth_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """KMA VilageFcst API Hub adapters discover UMMAYA_KMA_API_HUB_AUTH_KEY."""
    monkeypatch.delenv("UMMAYA_API_KEY", raising=False)
    monkeypatch.delenv("UMMAYA_DATA_GO_KR_API_KEY", raising=False)
    monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "api-hub-key")

    tool_ids = [
        "kma_forecast_fetch",
        "kma_current_observation",
        "kma_short_term_forecast",
        "kma_ultra_short_term_forecast",
    ]
    for tool_id in tool_ids:
        monkeypatch.delenv(f"UMMAYA_{tool_id.upper()}_API_KEY", raising=False)
        assert await attempt_auth_refresh(tool_id) is True
        assert get_credential(tool_id) == "api-hub-key"


async def test_kakao_tool_rejects_data_go_kr_only_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: Kakao tool must NOT be satisfied by data.go.kr-only env.

    Without a Kakao, per-tool, or legacy global key, the refresh has to
    fail closed so the caller surfaces ``needs_authentication``.
    """
    monkeypatch.delenv("UMMAYA_ADDRESS_TO_REGION_API_KEY", raising=False)
    monkeypatch.delenv("UMMAYA_KAKAO_API_KEY", raising=False)
    monkeypatch.delenv("UMMAYA_API_KEY", raising=False)
    monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "data-only")

    assert await attempt_auth_refresh("address_to_region") is False
    assert get_credential("address_to_region") is None


async def test_per_tool_override_wins_over_provider_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per-tool override env var beats the provider-level key."""
    monkeypatch.setenv("UMMAYA_ADDRESS_TO_REGION_API_KEY", "override")
    monkeypatch.setenv("UMMAYA_KAKAO_API_KEY", "provider")
    monkeypatch.delenv("UMMAYA_API_KEY", raising=False)

    assert get_credential("address_to_region") == "override"
