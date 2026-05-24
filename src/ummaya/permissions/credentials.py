# SPDX-License-Identifier: Apache-2.0
"""Tool-specific credential resolution for UMMAYA government API adapters.

Central helper that maps a tool identifier to its expected provider and the
environment variable that carries that provider's credential. Used by:

- :mod:`ummaya.permissions.steps.step1_config` to check that the credential
  required by the tool's :class:`~ummaya.permissions.models.AccessTier` is
  actually configured *for that tool's provider* (rather than accepting any
  ``UMMAYA_*_API_KEY``).
- :mod:`ummaya.recovery.auth_refresh` to resolve the correct credential when
  refreshing after an HTTP 401.

Lookup order for a given tool id:

1. ``UMMAYA_<TOOL_ID_UPPER>_API_KEY`` — tool-specific override.
2. Provider-level key such as ``UMMAYA_KAKAO_API_KEY``,
   ``UMMAYA_KMA_API_HUB_AUTH_KEY``, or ``UMMAYA_DATA_GO_KR_API_KEY``.
3. ``UMMAYA_API_KEY`` — legacy global fallback.

The mapping is intentionally explicit (no heuristic prefix matching) so that
adding a new provider is a deliberate change reviewed via code search.
"""

from __future__ import annotations

import logging
import os
from enum import StrEnum

logger = logging.getLogger(__name__)


class CredentialProvider(StrEnum):
    """Provider of the API credential expected by a tool adapter."""

    kakao = "kakao"
    """Kakao Local API; credential is ``UMMAYA_KAKAO_API_KEY``."""

    data_go_kr = "data_go_kr"
    """data.go.kr federated APIs (KMA, KOROAD, etc.); shared key
    ``UMMAYA_DATA_GO_KR_API_KEY``."""

    kma_api_hub = "kma_api_hub"
    """KMA API Hub; credential is ``UMMAYA_KMA_API_HUB_AUTH_KEY``."""


# Primary env var per provider.
_PROVIDER_ENV_VAR: dict[CredentialProvider, str] = {
    CredentialProvider.kakao: "UMMAYA_KAKAO_API_KEY",
    CredentialProvider.data_go_kr: "UMMAYA_DATA_GO_KR_API_KEY",
    CredentialProvider.kma_api_hub: "UMMAYA_KMA_API_HUB_AUTH_KEY",
}

# Tool-id → provider mapping.  Static adapters that require a credential appear
# here. Catalog-generated families may add a checked dynamic mapping in
# provider_for() when the catalog itself owns the canonical id list.
_TOOL_PROVIDERS: dict[str, CredentialProvider] = {
    # Kakao Local API
    "address_to_region": CredentialProvider.kakao,
    "address_to_grid": CredentialProvider.kakao,
    # KOROAD (data.go.kr)
    "koroad_accident_search": CredentialProvider.data_go_kr,
    "koroad_accident_hazard_search": CredentialProvider.data_go_kr,
    # KMA API Hub VilageFcstInfoService_2.0
    "kma_forecast_fetch": CredentialProvider.kma_api_hub,
    "kma_current_observation": CredentialProvider.kma_api_hub,
    "kma_short_term_forecast": CredentialProvider.kma_api_hub,
    "kma_ultra_short_term_forecast": CredentialProvider.kma_api_hub,
    # KMA warning adapters still mirror the data.go.kr WthrWrnInfoService shape.
    "kma_weather_alert_status": CredentialProvider.data_go_kr,
    "kma_pre_warning": CredentialProvider.data_go_kr,
    # HIRA / NMC / NFA / MOHW (data.go.kr)
    "hira_hospital_search": CredentialProvider.data_go_kr,
    "nmc_emergency_search": CredentialProvider.data_go_kr,
    "nfa_emergency_info_service": CredentialProvider.data_go_kr,
    "mohw_welfare_eligibility_search": CredentialProvider.data_go_kr,
}

# Global legacy fallback tried last when no provider-specific or
# tool-specific var is configured.
_GLOBAL_KEY_VAR: str = "UMMAYA_API_KEY"


def _tool_specific_var(tool_id: str) -> str:
    """Return the canonical per-tool env var name.

    ``koroad_accident_search`` → ``UMMAYA_KOROAD_ACCIDENT_SEARCH_API_KEY``.
    """
    return f"UMMAYA_{tool_id.upper()}_API_KEY"


def provider_for(tool_id: str) -> CredentialProvider | None:
    """Return the :class:`CredentialProvider` for *tool_id* or ``None``.

    A ``None`` return means the tool is not registered in the provider map;
    callers should treat this as "no provider credential known" and rely on
    the tool-specific override or global fallback only.
    """
    provider = _TOOL_PROVIDERS.get(tool_id)
    if provider is not None:
        return provider

    if tool_id.startswith("kma_apihub_"):
        try:
            from ummaya.tools.kma.apihub_catalog import get_operation_by_tool_id

            get_operation_by_tool_id(tool_id)
        except KeyError:
            return None
        return CredentialProvider.kma_api_hub

    return None


def expected_env_var(tool_id: str) -> str | None:
    """Return the primary env var name expected for *tool_id*'s provider.

    Returns ``None`` when the tool has no registered provider.
    """
    provider = provider_for(tool_id)
    if provider is None:
        return None
    return _PROVIDER_ENV_VAR[provider]


def resolve_credential(tool_id: str) -> str | None:
    """Resolve a non-empty credential string for *tool_id* or ``None``.

    Lookup order:

    1. ``UMMAYA_<TOOL_ID_UPPER>_API_KEY`` (per-tool override).
    2. Provider-specific env var (e.g. ``UMMAYA_KAKAO_API_KEY``).
    3. ``UMMAYA_API_KEY`` (legacy global fallback).
    """
    specific_var = _tool_specific_var(tool_id)
    value = os.environ.get(specific_var, "").strip()
    if value:
        return value

    provider_var = expected_env_var(tool_id)
    if provider_var is not None:
        provider_value = os.environ.get(provider_var, "").strip()
        if provider_value:
            return provider_value

    global_value = os.environ.get(_GLOBAL_KEY_VAR, "").strip()
    return global_value or None


def has_credential(tool_id: str) -> bool:
    """Return ``True`` iff :func:`resolve_credential` would find a credential."""
    return resolve_credential(tool_id) is not None


def candidate_env_vars(tool_id: str) -> tuple[str, ...]:
    """Return the env var names consulted by :func:`resolve_credential`.

    Useful for diagnostic log messages (e.g. "no credential found; checked
    ``X``, ``Y``, ``Z``").
    """
    names: list[str] = [_tool_specific_var(tool_id)]
    provider_var = expected_env_var(tool_id)
    if provider_var is not None:
        names.append(provider_var)
    names.append(_GLOBAL_KEY_VAR)
    return tuple(names)
