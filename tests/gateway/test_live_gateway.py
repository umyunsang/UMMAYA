# SPDX-License-Identifier: Apache-2.0
"""Tests for the operator-hosted live adapter gateway."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from ummaya.gateway.app import _missing_gateway_operator_keys, create_app  # noqa: E402
from ummaya.tools.executor import ToolExecutor  # noqa: E402
from ummaya.tools.models import AdapterRealDomainPolicy, GovAPITool  # noqa: E402
from ummaya.tools.registry import ToolRegistry  # noqa: E402


class _QueryInput(BaseModel):
    q: str


class _FindOutput(BaseModel):
    value: str


class _LocateInput(BaseModel):
    query: str


_KMA_API_HUB_ENDPOINT = (
    "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getUltraSrtNcst"
)


def _policy() -> AdapterRealDomainPolicy:
    return AdapterRealDomainPolicy(
        real_classification_url="https://www.data.go.kr/",
        real_classification_text="Public data read-only API.",
        citizen_facing_gate="read-only",
        last_verified=datetime(2026, 6, 20, tzinfo=UTC),
    )


def _find_tool(
    adapter_mode: str = "live",
    endpoint: str = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst",
) -> GovAPITool:
    return GovAPITool(
        id="kma_current_observation",
        name_ko="기상청 현재 관측",
        ministry="KMA",
        category=["weather"],
        endpoint=endpoint,
        auth_type="api_key",
        input_schema=_QueryInput,
        output_schema=_FindOutput,
        search_hint="weather current observation",
        adapter_mode=adapter_mode,
        primitive="find",
        policy=_policy(),
    )


def _locate_tool() -> GovAPITool:
    return GovAPITool(
        id="kakao_keyword_search",
        name_ko="카카오 장소 키워드 검색",
        ministry="UMMAYA",
        category=["locate"],
        endpoint="https://dapi.kakao.com/v2/local/search/keyword.json",
        auth_type="api_key",
        input_schema=_LocateInput,
        output_schema=_FindOutput,
        search_hint="locate keyword",
        adapter_mode="live",
        primitive="locate",
        policy=_policy(),
    )


def _client(registry: ToolRegistry, executor: ToolExecutor) -> TestClient:
    return TestClient(create_app(registry=registry, executor=executor))


def test_healthz_reports_proxyable_live_adapter_count() -> None:
    registry = ToolRegistry()
    tool = _find_tool()
    registry.register(tool)
    executor = ToolExecutor(registry=registry, live_adapter_mode="direct")
    executor.register_adapter(tool.id, _unused_adapter)

    with _client(registry, executor) as client:
        response = client.get("/healthz")
        ready = client.get("/readyz")

    assert response.status_code == 200
    assert response.json()["proxyable_live_adapter_count"] == 1
    assert ready.status_code == 200
    assert ready.json()["proxyable_live_adapter_count"] == 1


def test_healthz_counts_kma_api_hub_adapter_as_proxyable() -> None:
    registry = ToolRegistry()
    tool = _find_tool(endpoint=_KMA_API_HUB_ENDPOINT)
    registry.register(tool)
    executor = ToolExecutor(registry=registry, live_adapter_mode="direct")
    executor.register_adapter(tool.id, _unused_adapter)

    with _client(registry, executor) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["proxyable_live_adapter_count"] == 1


def test_manifest_endpoint_exposes_registry_without_operator_secrets() -> None:
    registry = ToolRegistry()
    tool = _find_tool()
    registry.register(tool)
    executor = ToolExecutor(registry=registry, live_adapter_mode="direct")
    executor.register_adapter(tool.id, _unused_adapter)

    with _client(registry, executor) as client:
        response = client.get("/v1/manifest")

    body = response.json()
    assert response.status_code == 200
    assert body["kind"] == "adapter_manifest_sync"
    assert body["role"] == "backend"
    manifest_entry = next(entry for entry in body["entries"] if entry["tool_id"] == tool.id)
    assert manifest_entry["policy_authority_url"] == "https://www.data.go.kr/"
    assert "UMMAYA_DATA_GO_KR_API_KEY" not in response.text
    assert "serviceKey" not in response.text


def test_gateway_requires_token_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UMMAYA_LIVE_ADAPTER_GATEWAY_TOKEN", "server-token")
    registry = ToolRegistry()
    tool = _find_tool()
    registry.register(tool)
    executor = ToolExecutor(registry=registry, live_adapter_mode="direct")
    executor.register_adapter(tool.id, _find_adapter)

    payload = {
        "schema_version": "ummaya.live_adapter.v1",
        "tool_id": tool.id,
        "primitive": "find",
        "params": {"q": "다대1동"},
        "request_id": "req-auth",
    }

    with _client(registry, executor) as client:
        missing = client.post(f"/v1/adapters/{tool.id}", json=payload)
        ok = client.post(
            f"/v1/adapters/{tool.id}",
            json=payload,
            headers={"Authorization": "Bearer server-token"},
        )

    assert missing.status_code == 401
    assert ok.status_code == 200


def test_gateway_invokes_find_adapter_direct_even_if_process_env_forces_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UMMAYA_LIVE_ADAPTER_MODE", "proxy")
    registry = ToolRegistry()
    tool = _find_tool()
    registry.register(tool)
    executor = ToolExecutor(registry=registry, live_adapter_mode="direct")
    executor.register_adapter(tool.id, _find_adapter)

    with _client(registry, executor) as client:
        response = client.post(
            f"/v1/adapters/{tool.id}",
            json={
                "schema_version": "ummaya.live_adapter.v1",
                "tool_id": tool.id,
                "primitive": "find",
                "params": {"q": "동아대학교"},
                "request_id": "req-find",
                "session_identity": "session-1",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["result"]["kind"] == "record"
    assert body["result"]["item"] == {"value": "live:동아대학교"}


def test_gateway_invokes_kma_api_hub_adapter_direct_even_if_process_env_forces_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UMMAYA_LIVE_ADAPTER_MODE", "proxy")
    registry = ToolRegistry()
    tool = _find_tool(endpoint=_KMA_API_HUB_ENDPOINT)
    registry.register(tool)
    executor = ToolExecutor(registry=registry, live_adapter_mode="direct")
    executor.register_adapter(tool.id, _find_adapter)

    with _client(registry, executor) as client:
        response = client.post(
            f"/v1/adapters/{tool.id}",
            json={
                "schema_version": "ummaya.live_adapter.v1",
                "tool_id": tool.id,
                "primitive": "find",
                "params": {"q": "동아대학교"},
                "request_id": "req-find-api-hub",
                "session_identity": "session-1",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["result"]["kind"] == "record"
    assert body["result"]["item"] == {"value": "live:동아대학교"}


def test_gateway_rate_limits_by_client_and_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UMMAYA_LIVE_ADAPTER_GATEWAY_RATE_LIMIT_PER_MINUTE", "2")
    registry = ToolRegistry()
    tool = _find_tool()
    registry.register(tool)
    executor = ToolExecutor(registry=registry, live_adapter_mode="direct")
    executor.register_adapter(tool.id, _find_adapter)

    payload = {
        "schema_version": "ummaya.live_adapter.v1",
        "tool_id": tool.id,
        "primitive": "find",
        "params": {"q": "다대1동"},
        "request_id": "req-rate",
    }

    with _client(registry, executor) as client:
        first = client.post(f"/v1/adapters/{tool.id}", json=payload)
        second = client.post(f"/v1/adapters/{tool.id}", json=payload)
        third = client.post(f"/v1/adapters/{tool.id}", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429


def test_gateway_rejects_oversized_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UMMAYA_LIVE_ADAPTER_GATEWAY_MAX_BODY_BYTES", "1024")
    registry = ToolRegistry()
    tool = _find_tool()
    registry.register(tool)
    executor = ToolExecutor(registry=registry, live_adapter_mode="direct")
    executor.register_adapter(tool.id, _find_adapter)

    with _client(registry, executor) as client:
        response = client.post(
            f"/v1/adapters/{tool.id}",
            content=b"x" * 2048,
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 413


def test_gateway_invokes_locate_adapter_via_raw_path() -> None:
    registry = ToolRegistry()
    tool = _locate_tool()
    registry.register(tool)
    executor = ToolExecutor(registry=registry, live_adapter_mode="direct")
    executor.register_adapter(tool.id, _locate_adapter)

    with _client(registry, executor) as client:
        response = client.post(
            f"/v1/adapters/{tool.id}",
            json={
                "schema_version": "ummaya.live_adapter.v1",
                "tool_id": tool.id,
                "primitive": "locate",
                "params": {"query": "동아대학교 승학캠퍼스"},
                "request_id": "req-locate",
                "session_identity": "session-1",
            },
        )

    assert response.status_code == 200
    assert response.json()["result"]["kind"] == "poi"
    assert response.json()["result"]["name"] == "동아대학교 승학캠퍼스"


def test_gateway_rejects_non_live_or_mock_adapter() -> None:
    registry = ToolRegistry()
    tool = _find_tool(adapter_mode="mock")
    registry.register(tool)
    executor = ToolExecutor(registry=registry, live_adapter_mode="direct")
    executor.register_adapter(tool.id, _find_adapter)

    with _client(registry, executor) as client:
        response = client.post(
            f"/v1/adapters/{tool.id}",
            json={
                "schema_version": "ummaya.live_adapter.v1",
                "tool_id": tool.id,
                "primitive": "find",
                "params": {"q": "다대1동"},
            },
        )

    assert response.status_code == 403


def test_gateway_operator_key_check_requires_complete_provider_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "UMMAYA_DATA_GO_KR_API_KEY",
        "UMMAYA_KEPCO_POWER_DATA_API_KEY",
        "UMMAYA_KMA_API_HUB_AUTH_KEY",
        "UMMAYA_KAKAO_API_KEY",
        "UMMAYA_JUSO_CONFM_KEY",
        "UMMAYA_SGIS_KEY",
        "UMMAYA_SGIS_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "data-go-kr")
    monkeypatch.setenv("UMMAYA_KAKAO_API_KEY", "kakao")
    monkeypatch.setenv("UMMAYA_JUSO_CONFM_KEY", "juso")
    monkeypatch.setenv("UMMAYA_SGIS_KEY", "sgis-key")

    assert _missing_gateway_operator_keys() == (
        "UMMAYA_KEPCO_POWER_DATA_API_KEY",
        "UMMAYA_KMA_API_HUB_AUTH_KEY",
        "UMMAYA_SGIS_SECRET",
    )

    monkeypatch.setenv("UMMAYA_KEPCO_POWER_DATA_API_KEY", "kepco")
    monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "kma-api-hub")

    assert _missing_gateway_operator_keys() == ("UMMAYA_SGIS_SECRET",)


async def _find_adapter(inp: BaseModel) -> dict[str, object]:
    assert isinstance(inp, _QueryInput)
    return {"kind": "record", "item": {"value": f"live:{inp.q}"}}


async def _locate_adapter(inp: BaseModel) -> dict[str, object]:
    assert isinstance(inp, _LocateInput)
    return {
        "kind": "poi",
        "name": inp.query,
        "lat": 35.115,
        "lon": 128.968,
        "source": "kakao",
    }


async def _unused_adapter(_: BaseModel) -> dict[str, object]:
    raise AssertionError("adapter should not be called")
