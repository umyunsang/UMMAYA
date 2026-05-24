# SPDX-License-Identifier: Apache-2.0
"""Tests for KMA VilageFcst endpoint and credential selection."""

from __future__ import annotations

import pytest

from ummaya.tools.errors import ConfigurationError
from ummaya.tools.kma.vilage_fcst_endpoint import resolve_vilage_fcst_endpoint


def test_api_hub_auth_key_selects_api_hub_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "api-hub-key")
    monkeypatch.delenv("UMMAYA_DATA_GO_KR_API_KEY", raising=False)

    endpoint = resolve_vilage_fcst_endpoint("getUltraSrtNcst")

    assert endpoint.url == (
        "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getUltraSrtNcst"
    )
    assert endpoint.auth_query_param == "authKey"
    assert endpoint.api_key == "api-hub-key"
    assert endpoint.env_var == "UMMAYA_KMA_API_HUB_AUTH_KEY"


def test_data_go_kr_key_is_not_accepted_for_api_hub_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("UMMAYA_KMA_API_HUB_AUTH_KEY", raising=False)
    monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "data-go-kr-key")

    with pytest.raises(ConfigurationError) as exc_info:
        resolve_vilage_fcst_endpoint("getVilageFcst")

    assert "UMMAYA_KMA_API_HUB_AUTH_KEY" in str(exc_info.value)


def test_api_hub_key_is_used_when_both_keys_are_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "api-hub-key")
    monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "data-go-kr-key")

    endpoint = resolve_vilage_fcst_endpoint("getUltraSrtFcst")

    assert endpoint.auth_query_param == "authKey"
    assert endpoint.api_key == "api-hub-key"
    assert endpoint.url.startswith("https://apihub.kma.go.kr/api/typ02/openApi/")


def test_missing_both_keys_raises_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UMMAYA_KMA_API_HUB_AUTH_KEY", raising=False)
    monkeypatch.delenv("UMMAYA_DATA_GO_KR_API_KEY", raising=False)

    with pytest.raises(ConfigurationError) as exc_info:
        resolve_vilage_fcst_endpoint("getVilageFcst")

    message = str(exc_info.value)
    assert "UMMAYA_KMA_API_HUB_AUTH_KEY" in message
