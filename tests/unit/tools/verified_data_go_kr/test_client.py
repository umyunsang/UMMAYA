# SPDX-License-Identifier: Apache-2.0
"""Unit tests for verified data.go.kr HTTP client helpers."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from pydantic import BaseModel, ValidationError

from ummaya.tools.verified_data_go_kr import _client as client_module
from ummaya.tools.verified_data_go_kr._client import (
    _raise_for_status_sanitized,
    fetch_verified_output,
)
from ummaya.tools.verified_data_go_kr._models import VerifiedAdapterSpec


class _ClientFixtureInput(BaseModel):
    page_no: int = 1


def _spec(*, endpoint: str = "https://apis.data.go.kr/example") -> VerifiedAdapterSpec:
    return VerifiedAdapterSpec(
        dataset_id="99999999",
        tool_id="example_lookup",
        module_name="example_lookup",
        name_ko="예시 조회",
        ministry="MOIS",
        category=["public-data"],
        endpoint=endpoint,
        env_var="UMMAYA_TEST_DATA_GO_KR_KEY",
        auth_query_param="serviceKey",
        response_format="json",
        query_param_map={"page_no": "pageNo"},
        evidence_path="docs/api/data-go-kr-candidate-docs/example/probes/example.body",
        policy_url="https://www.data.go.kr/data/99999999/openapi.do",
        policy_text="공공데이터포털 인증키 기반 예시 OpenAPI.",
        last_verified=datetime(2026, 5, 16, tzinfo=UTC),
        search_hint="example find",
        llm_description="예시 데이터를 조회한다.",
    )


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
    assert "real-secret" not in str(exc_info.value.request.url)
    assert "real-secret" not in str(exc_info.value.response.request.url)


@pytest.mark.asyncio
async def test_fetch_verified_output_uses_traced_async_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UMMAYA_TEST_DATA_GO_KR_KEY", "fake-key")
    calls: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["serviceKey"] == "fake-key"
        assert request.url.params["pageNo"] == "1"
        return httpx.Response(
            200,
            content=(
                b'{"response":{"header":{"resultCode":"00","resultMsg":"NORMAL_CODE"},'
                b'"body":{"items":{"item":[{"name":"ok"}]},"totalCount":1}}}'
            ),
            request=request,
        )

    def fake_traced_async_client(**kwargs: object) -> httpx.AsyncClient:
        timeout = kwargs["timeout"]
        assert isinstance(timeout, float)
        calls.append(timeout)
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(client_module, "traced_async_client", fake_traced_async_client)

    output = await fetch_verified_output(_ClientFixtureInput(), _spec())

    assert calls == [10.0]
    assert output.total_count == 1
    assert output.items[0].record["name"] == "ok"


def test_verified_adapter_spec_allows_documented_data_go_kr_http_gateway() -> None:
    spec = _spec(endpoint="http://apis.data.go.kr/example")

    assert spec.endpoint == "http://apis.data.go.kr/example"


def test_verified_adapter_spec_rejects_non_gateway_cleartext_endpoint() -> None:
    with pytest.raises(ValidationError):
        _spec(endpoint="http://example.test/openapi")
