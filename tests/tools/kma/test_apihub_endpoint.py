# SPDX-License-Identifier: Apache-2.0
"""Tests for KMA APIHub endpoint and credential selection."""

from __future__ import annotations

import pytest

from ummaya.tools.errors import ConfigurationError
from ummaya.tools.kma.apihub_catalog import get_operation_by_id
from ummaya.tools.kma.apihub_endpoint import resolve_apihub_endpoint


def test_api_hub_auth_key_selects_api_hub_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "api-hub-key")
    monkeypatch.delenv("UMMAYA_DATA_GO_KR_API_KEY", raising=False)
    operation = get_operation_by_id("AmmIwxxmService/getMetar")

    endpoint = resolve_apihub_endpoint(operation)

    assert endpoint.url == "https://apihub.kma.go.kr/api/typ02/openApi/AmmIwxxmService/getMetar"
    assert endpoint.auth_query_param == "authKey"
    assert endpoint.api_key == "api-hub-key"
    assert endpoint.env_var == "UMMAYA_KMA_API_HUB_AUTH_KEY"


def test_data_go_kr_key_is_not_accepted_for_api_hub_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("UMMAYA_KMA_API_HUB_AUTH_KEY", raising=False)
    monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "data-go-kr-key")
    operation = get_operation_by_id("AmmIwxxmService/getMetar")

    with pytest.raises(ConfigurationError) as exc_info:
        resolve_apihub_endpoint(operation)

    assert "UMMAYA_KMA_API_HUB_AUTH_KEY" in str(exc_info.value)


def test_missing_api_hub_key_raises_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UMMAYA_KMA_API_HUB_AUTH_KEY", raising=False)
    monkeypatch.delenv("UMMAYA_DATA_GO_KR_API_KEY", raising=False)
    operation = get_operation_by_id("AmmIwxxmService/getMetar")

    with pytest.raises(ConfigurationError) as exc_info:
        resolve_apihub_endpoint(operation)

    assert "UMMAYA_KMA_API_HUB_AUTH_KEY" in str(exc_info.value)
