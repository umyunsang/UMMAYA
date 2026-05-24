# SPDX-License-Identifier: Apache-2.0
"""Tests for provider credential routing."""

from __future__ import annotations

from ummaya.permissions.credentials import (
    CredentialProvider,
    candidate_env_vars,
    expected_env_var,
    provider_for,
    resolve_credential,
)


def test_kma_apihub_catalog_tool_uses_api_hub_provider() -> None:
    tool_id = "kma_apihub_amm_iwxxm_service_get_metar"

    assert provider_for(tool_id) == CredentialProvider.kma_api_hub
    assert expected_env_var(tool_id) == "UMMAYA_KMA_API_HUB_AUTH_KEY"
    assert candidate_env_vars(tool_id) == (
        "UMMAYA_KMA_APIHUB_AMM_IWXXM_SERVICE_GET_METAR_API_KEY",
        "UMMAYA_KMA_API_HUB_AUTH_KEY",
        "UMMAYA_API_KEY",
    )


def test_unknown_kma_apihub_prefix_does_not_guess_provider() -> None:
    assert provider_for("kma_apihub_not_a_catalog_operation") is None


def test_kma_apihub_provider_key_resolves_without_data_go_kr(
    monkeypatch,
) -> None:
    monkeypatch.delenv("UMMAYA_KMA_APIHUB_AMM_IWXXM_SERVICE_GET_METAR_API_KEY", raising=False)
    monkeypatch.setenv("UMMAYA_KMA_API_HUB_AUTH_KEY", "api-hub-key")
    monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "data-go-kr-key")

    assert resolve_credential("kma_apihub_amm_iwxxm_service_get_metar") == "api-hub-key"
