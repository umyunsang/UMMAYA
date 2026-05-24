# SPDX-License-Identifier: Apache-2.0
"""Endpoint and credential selection for KMA VilageFcstInfoService_2.0."""

from __future__ import annotations

import os
from dataclasses import dataclass

from ummaya.tools.errors import ConfigurationError

KMA_API_HUB_AUTH_KEY_ENV = "UMMAYA_KMA_API_HUB_AUTH_KEY"

KMA_API_HUB_VILAGE_FCST_BASE_URL = (
    "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0"
)


@dataclass(frozen=True)
class KmaVilageFcstEndpoint:
    """Resolved KMA VilageFcst endpoint URL and auth query parameter."""

    url: str
    auth_query_param: str
    api_key: str
    env_var: str


def resolve_vilage_fcst_endpoint(operation: str) -> KmaVilageFcstEndpoint:
    """Resolve the KMA VilageFcst endpoint for *operation*.

    KMA API Hub is the agency-owned surface for
    ``VilageFcstInfoService_2.0``. It uses ``authKey`` on the
    ``apihub.kma.go.kr/api/typ02/openApi`` host. The data.go.kr
    ``serviceKey`` credential is intentionally not accepted for this KMA
    API Hub adapter family.
    """
    api_hub_key = os.environ.get(KMA_API_HUB_AUTH_KEY_ENV, "").strip()
    if api_hub_key:
        return KmaVilageFcstEndpoint(
            url=f"{KMA_API_HUB_VILAGE_FCST_BASE_URL}/{operation}",
            auth_query_param="authKey",
            api_key=api_hub_key,
            env_var=KMA_API_HUB_AUTH_KEY_ENV,
        )

    raise ConfigurationError(KMA_API_HUB_AUTH_KEY_ENV)
