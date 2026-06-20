# SPDX-License-Identifier: Apache-2.0
"""Tests for release live-adapter proxy routing."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from pydantic import BaseModel

from ummaya.tools.executor import ToolExecutor
from ummaya.tools.live_proxy import invoke_live_adapter_proxy, should_use_live_adapter_proxy
from ummaya.tools.models import GovAPITool, LookupRecord
from ummaya.tools.registry import ToolRegistry


class _ProxyInput(BaseModel):
    q: str


class _ProxyOutput(BaseModel):
    value: str


def _make_proxyable_tool(
    endpoint: str = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst",
) -> GovAPITool:
    return GovAPITool(
        id="kma_current_observation",
        name_ko="기상청 현재 관측",
        ministry="KMA",
        category=["weather"],
        endpoint=endpoint,
        auth_type="api_key",
        input_schema=_ProxyInput,
        output_schema=_ProxyOutput,
        search_hint="weather current observation",
        adapter_mode="live",
        primitive="find",
    )


def test_auto_mode_routes_packaged_proxyable_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UMMAYA_LIVE_ADAPTER_MODE", raising=False)
    monkeypatch.setenv("UMMAYA_PACKAGE_ROOT", "/opt/homebrew/Caskroom/ummaya/0.1.1/package")

    assert should_use_live_adapter_proxy(_make_proxyable_tool()) is True


def test_auto_mode_routes_packaged_kma_api_hub_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("UMMAYA_LIVE_ADAPTER_MODE", raising=False)
    monkeypatch.setenv("UMMAYA_PACKAGE_ROOT", "/opt/homebrew/Caskroom/ummaya/0.1.1/package")

    assert (
        should_use_live_adapter_proxy(
            _make_proxyable_tool(
                endpoint=(
                    "https://apihub.kma.go.kr/api/typ02/openApi/"
                    "VilageFcstInfoService_2.0/getUltraSrtNcst"
                )
            )
        )
        is True
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://bigdata.kepco.co.kr/openapi/v1/powerUsage/contractType.do",
        "https://www.reb.or.kr/r-one/openapi/SttsApiTbl.do",
    ],
)
def test_auto_mode_routes_packaged_verified_non_data_go_hosts(
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
) -> None:
    monkeypatch.delenv("UMMAYA_LIVE_ADAPTER_MODE", raising=False)
    monkeypatch.setenv("UMMAYA_PACKAGE_ROOT", "/opt/homebrew/Caskroom/ummaya/0.1.1/package")

    assert should_use_live_adapter_proxy(_make_proxyable_tool(endpoint=endpoint)) is True


def test_auto_mode_keeps_source_tree_direct(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UMMAYA_LIVE_ADAPTER_MODE", raising=False)
    monkeypatch.delenv("UMMAYA_PACKAGE_ROOT", raising=False)

    assert should_use_live_adapter_proxy(_make_proxyable_tool()) is False


def test_auto_mode_keeps_git_checkout_package_root_direct(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    package_root = tmp_path
    git_dir = package_root / ".git"
    git_dir.mkdir()
    monkeypatch.delenv("UMMAYA_LIVE_ADAPTER_MODE", raising=False)
    monkeypatch.setenv("UMMAYA_PACKAGE_ROOT", str(package_root))

    assert should_use_live_adapter_proxy(_make_proxyable_tool()) is False


@pytest.mark.asyncio
async def test_executor_proxy_route_does_not_call_local_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UMMAYA_LIVE_ADAPTER_MODE", "proxy")
    monkeypatch.setenv("UMMAYA_LIVE_ADAPTER_PROXY_URL", "https://gateway.example/v1/adapters")

    registry = ToolRegistry()
    tool = _make_proxyable_tool()
    registry.register(tool)
    executor = ToolExecutor(registry)

    async def _local_adapter(_: BaseModel) -> dict[str, object]:
        raise AssertionError("local adapter must not run in proxy mode")

    async def _proxy_adapter(**kwargs: object) -> dict[str, object]:
        assert kwargs["tool"] == tool
        assert kwargs["params"] == {"q": "동아대학교"}
        assert kwargs["request_id"] == "req-proxy"
        return {"kind": "record", "item": {"value": "proxied"}}

    monkeypatch.setattr("ummaya.tools.live_proxy.invoke_live_adapter_proxy", _proxy_adapter)
    executor.register_adapter(tool.id, _local_adapter)

    result = await executor.invoke(
        tool.id,
        {"q": "동아대학교"},
        "req-proxy",
        session_identity="session-1",
    )

    assert isinstance(result, LookupRecord)
    assert result.item == {"value": "proxied"}
    assert result.meta.source == tool.id


@pytest.mark.asyncio
async def test_executor_direct_mode_calls_local_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UMMAYA_LIVE_ADAPTER_MODE", "direct")
    monkeypatch.setenv("UMMAYA_PACKAGE_ROOT", "/opt/homebrew/Caskroom/ummaya/0.1.1/package")

    registry = ToolRegistry()
    tool = _make_proxyable_tool()
    registry.register(tool)
    executor = ToolExecutor(registry)

    async def _local_adapter(_: BaseModel) -> dict[str, object]:
        return {"kind": "record", "item": {"value": "direct"}}

    executor.register_adapter(tool.id, _local_adapter)

    result = await executor.invoke(
        tool.id,
        {"q": "다대1동"},
        "req-direct",
        session_identity="session-1",
    )

    assert isinstance(result, LookupRecord)
    assert result.item == {"value": "direct"}


@pytest.mark.asyncio
@respx.mock
async def test_invoke_live_adapter_proxy_retries_retryable_gateway_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UMMAYA_LIVE_ADAPTER_PROXY_URL", "https://gateway.example/v1/adapters")
    monkeypatch.setenv("UMMAYA_LIVE_ADAPTER_PROXY_MAX_ATTEMPTS", "2")
    monkeypatch.setattr("ummaya.tools.live_proxy.asyncio.sleep", _noop_sleep)

    tool = _make_proxyable_tool()
    route = respx.post("https://gateway.example/v1/adapters/kma_current_observation").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": {
                        "kind": "error",
                        "reason": "timeout",
                        "message": "Adapter timed out.",
                        "retryable": True,
                    },
                },
            ),
            httpx.Response(
                200,
                json={"ok": True, "result": {"kind": "record", "item": {"value": "proxied"}}},
            ),
        ],
    )

    result = await invoke_live_adapter_proxy(
        tool=tool,
        params={"q": "다대포"},
        request_id="req-proxy-retry",
        session_identity="session-1",
    )

    assert result == {"kind": "record", "item": {"value": "proxied"}}
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_invoke_live_adapter_proxy_omits_authorization_when_legacy_proxy_token_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a packaged client still has the retired proxy-token env var.
    monkeypatch.setenv("UMMAYA_LIVE_ADAPTER_PROXY_URL", "https://gateway.example/v1/adapters")
    monkeypatch.setenv("UMMAYA_LIVE_ADAPTER_PROXY_TOKEN", "legacy-client-token")

    tool = _make_proxyable_tool()
    route = respx.post("https://gateway.example/v1/adapters/kma_current_observation").mock(
        return_value=httpx.Response(
            200,
            json={"ok": True, "result": {"kind": "record", "item": {"value": "proxied"}}},
        )
    )

    # When: the public client invokes the hosted gateway.
    result = await invoke_live_adapter_proxy(
        tool=tool,
        params={"q": "다대포"},
        request_id="req-no-client-secret",
        session_identity="session-1",
    )

    # Then: no client-side bearer secret is sent to the gateway.
    assert result == {"kind": "record", "item": {"value": "proxied"}}
    assert route.call_count == 1
    assert "authorization" not in route.calls[0].request.headers


async def _noop_sleep(_: float) -> None:
    return None
