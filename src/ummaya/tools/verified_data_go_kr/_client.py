# SPDX-License-Identifier: Apache-2.0
"""HTTP client helpers for verified public-data adapters."""

from __future__ import annotations

import httpx
from pydantic import BaseModel

from ummaya.tools.errors import _require_env
from ummaya.tools.verified_data_go_kr._models import (
    VerifiedAdapterSpec,
    VerifiedPublicDataOutput,
)
from ummaya.tools.verified_data_go_kr._parsing import parse_verified_payload

_TIMEOUT_SECONDS = 10.0


async def fetch_verified_output(
    input_model: BaseModel,
    spec: VerifiedAdapterSpec,
    *,
    fixture_body: bytes | None = None,
) -> VerifiedPublicDataOutput:
    """Fetch or fixture-replay one verified adapter response."""

    if fixture_body is not None:
        return parse_verified_payload(
            fixture_body,
            response_format=spec.response_format,
            record_tag=spec.record_tag,
        )

    params = _build_query_params(input_model, spec)
    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        response = await client.get(str(spec.endpoint), params=params)
        response.raise_for_status()
        return parse_verified_payload(
            response.content,
            response_format=spec.response_format,
            record_tag=spec.record_tag,
        )


def _build_query_params(input_model: BaseModel, spec: VerifiedAdapterSpec) -> dict[str, str]:
    dumped = input_model.model_dump(mode="python", exclude_none=True)
    params = dict(spec.static_query_params)
    params[spec.auth_query_param] = _require_env(spec.env_var)
    for field_name, query_name in spec.query_param_map.items():
        value = dumped.get(field_name)
        if value is not None:
            params[query_name] = str(value)
    return params
