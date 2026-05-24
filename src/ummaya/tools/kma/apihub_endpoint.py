# SPDX-License-Identifier: Apache-2.0
"""Endpoint and credential selection for KMA APIHub structured OpenAPI calls."""

from __future__ import annotations

import os
from dataclasses import dataclass

from ummaya.tools.errors import ConfigurationError
from ummaya.tools.kma.apihub_catalog import KmaApiHubOperation

KMA_API_HUB_AUTH_KEY_ENV = "UMMAYA_KMA_API_HUB_AUTH_KEY"
KMA_API_HUB_BASE_URL = "https://apihub.kma.go.kr"


@dataclass(frozen=True)
class KmaApiHubEndpoint:
    """Resolved KMA APIHub endpoint URL and authentication query parameter."""

    url: str
    auth_query_param: str
    api_key: str
    env_var: str


def resolve_apihub_endpoint(operation: KmaApiHubOperation) -> KmaApiHubEndpoint:
    """Resolve the endpoint for a structured KMA APIHub operation.

    KMA APIHub uses ``authKey`` on the agency-owned ``apihub.kma.go.kr``
    surface. The legacy data.go.kr ``serviceKey`` credential is intentionally
    not accepted for this adapter family.
    """
    api_hub_key = os.environ.get(KMA_API_HUB_AUTH_KEY_ENV, "").strip()
    if not api_hub_key:
        raise ConfigurationError(KMA_API_HUB_AUTH_KEY_ENV)

    return KmaApiHubEndpoint(
        url=f"{KMA_API_HUB_BASE_URL}{operation.endpoint_path}",
        auth_query_param="authKey",
        api_key=api_hub_key,
        env_var=KMA_API_HUB_AUTH_KEY_ENV,
    )
