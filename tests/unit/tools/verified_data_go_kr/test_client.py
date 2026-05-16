# SPDX-License-Identifier: Apache-2.0
"""Unit tests for verified data.go.kr HTTP client helpers."""

from __future__ import annotations

import httpx
import pytest

from ummaya.tools.verified_data_go_kr._client import _raise_for_status_sanitized


def test_http_status_error_message_redacts_service_key() -> None:
    """Upstream HTTP errors must not leak auth query params into tool errors."""

    request = httpx.Request(
        "GET",
        "https://apis.data.go.kr/example?serviceKey=real-secret&pageNo=1",
    )
    response = httpx.Response(502, request=request)

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        _raise_for_status_sanitized(response)

    message = str(exc_info.value)
    assert "real-secret" not in message
    assert "serviceKey=***" in message
    assert "pageNo=1" in message
