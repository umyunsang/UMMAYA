# SPDX-License-Identifier: Apache-2.0
"""Operator-managed gateway client for release live adapter calls.

The public CLI must not ship Kakao/data.go.kr credentials. In packaged
executions the live public-API adapters route through this gateway, where
operator-managed credentials live server-side. Source-tree and test executions
can still use the direct adapter route by setting ``UMMAYA_LIVE_ADAPTER_MODE``.
"""

from __future__ import annotations

import os
from typing import Any, Literal
from urllib.parse import quote, urlparse

import httpx

from ummaya._version import get_version
from ummaya.tools.errors import ToolExecutionError, UmmayaToolError
from ummaya.tools.models import GovAPITool

_PROXYABLE_HOSTS = frozenset(
    {
        "apis.data.go.kr",
        "openapi.data.go.kr",
        "dapi.kakao.com",
        "business.juso.go.kr",
        "sgisapi.kostat.go.kr",
        "sgisapi.mods.go.kr",
    }
)
_PROXYABLE_PRIMITIVES = frozenset({"find", "locate"})
_VALID_MODES = frozenset({"auto", "proxy", "direct"})


class LiveAdapterProxyConfigurationError(UmmayaToolError):
    """The release live-adapter proxy route is misconfigured."""


def is_proxyable_live_adapter(tool: GovAPITool) -> bool:
    """Return whether *tool* is eligible for the operator gateway route."""
    if tool.adapter_mode != "live":
        return False
    if tool.auth_type != "api_key":
        return False
    if tool.primitive not in _PROXYABLE_PRIMITIVES:
        return False

    host = (urlparse(tool.endpoint).hostname or "").lower()
    return host in _PROXYABLE_HOSTS or host.endswith(".data.go.kr")


def should_use_live_adapter_proxy(
    tool: GovAPITool,
    *,
    mode_override: Literal["auto", "proxy", "direct"] | None = None,
) -> bool:
    """Decide whether this invocation should use the operator gateway.

    ``auto`` is release-aware: the npm/Homebrew wrapper sets
    ``UMMAYA_PACKAGE_ROOT`` for packaged executions, while source-tree Python
    entry points normally do not. This keeps local development direct without
    asking public release users for operator credentials.
    """
    if not is_proxyable_live_adapter(tool):
        return False

    mode = _configured_mode(mode_override)
    if mode == "direct":
        return False
    if mode == "proxy":
        return True
    return bool(os.environ.get("UMMAYA_PACKAGE_ROOT", "").strip())


async def invoke_live_adapter_proxy(
    *,
    tool: GovAPITool,
    params: dict[str, object],
    request_id: str,
    session_identity: object | None,
) -> dict[str, Any]:
    """Invoke the operator-managed live adapter gateway.

    The gateway returns the same adapter output envelope that the local handler
    would have returned. The caller still runs ingress safety and normalization.
    """
    from ummaya.settings import settings  # noqa: PLC0415

    base_url = (
        os.environ.get("UMMAYA_LIVE_ADAPTER_PROXY_URL", settings.live_adapter_proxy_url)
        .strip()
        .rstrip("/")
    )
    if not base_url:
        raise LiveAdapterProxyConfigurationError(
            "UMMAYA_LIVE_ADAPTER_PROXY_URL is required when live adapter proxy mode is active."
        )

    timeout = _configured_timeout(settings.live_adapter_proxy_timeout_seconds)
    token = os.environ.get("UMMAYA_LIVE_ADAPTER_PROXY_TOKEN", settings.live_adapter_proxy_token)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": f"UMMAYA/{get_version()} live-adapter-client",
    }
    if token.strip():
        headers["Authorization"] = f"Bearer {token.strip()}"

    payload: dict[str, object] = {
        "schema_version": "ummaya.live_adapter.v1",
        "tool_id": tool.id,
        "primitive": tool.primitive,
        "request_id": request_id,
        "params": params,
    }
    if session_identity is not None:
        payload["session_identity"] = str(session_identity)

    url = f"{base_url}/{quote(tool.id, safe='')}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()

    data = response.json()
    if not isinstance(data, dict):
        raise ToolExecutionError(tool.id, "Live adapter proxy returned a non-object JSON payload.")

    result = data.get("result") if data.get("ok") is True and "result" in data else data
    if not isinstance(result, dict):
        raise ToolExecutionError(tool.id, "Live adapter proxy returned an invalid result payload.")
    return result


def _configured_mode(
    mode_override: Literal["auto", "proxy", "direct"] | None = None,
) -> Literal["auto", "proxy", "direct"]:
    raw = mode_override or os.environ.get("UMMAYA_LIVE_ADAPTER_MODE", "auto")
    mode = raw.strip().lower()
    if mode not in _VALID_MODES:
        raise LiveAdapterProxyConfigurationError(
            "UMMAYA_LIVE_ADAPTER_MODE must be one of: auto, proxy, direct."
        )
    return mode  # type: ignore[return-value]


def _configured_timeout(default_seconds: float) -> float:
    raw = os.environ.get("UMMAYA_LIVE_ADAPTER_PROXY_TIMEOUT_SECONDS", "")
    if not raw.strip():
        return default_seconds
    try:
        parsed = float(raw)
    except ValueError as exc:
        raise LiveAdapterProxyConfigurationError(
            "UMMAYA_LIVE_ADAPTER_PROXY_TIMEOUT_SECONDS must be a positive number."
        ) from exc
    if parsed <= 0:
        raise LiveAdapterProxyConfigurationError(
            "UMMAYA_LIVE_ADAPTER_PROXY_TIMEOUT_SECONDS must be a positive number."
        )
    return parsed
