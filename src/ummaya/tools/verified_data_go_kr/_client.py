# SPDX-License-Identifier: Apache-2.0
"""HTTP client helpers for verified public-data adapters."""

from __future__ import annotations

import httpx
from pydantic import BaseModel

from ummaya.tools._outbound_trace import _redact_url
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
    headers = dict(spec.request_headers) or None
    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        response = await client.get(str(spec.endpoint), params=params, headers=headers)
        _raise_for_status_sanitized(response)
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


def _raise_for_status_sanitized(response: httpx.Response) -> None:
    """Raise HTTPStatusError with auth query params redacted from the message."""

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        reason_phrase = exc.response.reason_phrase
        redacted_url = _redact_url(exc.request.url)
        error_kind = _http_error_kind(status_code)
        message = f"{error_kind} '{status_code} {reason_phrase}' for url '{redacted_url}'"
        if 400 <= status_code < 600:
            message = (
                f"{message}\nFor more information check: "
                f"https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/{status_code}"
            )
        redacted_request = httpx.Request(exc.request.method, redacted_url)
        raise httpx.HTTPStatusError(
            message,
            request=redacted_request,
            response=exc.response,
        ) from None


def _http_error_kind(status_code: int) -> str:
    if 300 <= status_code < 400:
        return "Redirect response"
    if 400 <= status_code < 500:
        return "Client error"
    if 500 <= status_code < 600:
        return "Server error"
    return "HTTP status error"
