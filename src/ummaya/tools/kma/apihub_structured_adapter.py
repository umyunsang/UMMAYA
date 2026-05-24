# SPDX-License-Identifier: Apache-2.0
"""Generic wrappers for KMA APIHub structured ``typ02/openApi`` operations."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from functools import cache
from typing import Literal, cast

import httpx
from pydantic import BaseModel, ConfigDict, Field, create_model

from ummaya.tools._outbound_trace import traced_async_client
from ummaya.tools.errors import ConfigurationError, ToolExecutionError
from ummaya.tools.executor import AdapterFn, ToolExecutor
from ummaya.tools.kma.apihub_catalog import (
    KmaApiHubOperation,
    iter_structured_operations,
)
from ummaya.tools.kma.apihub_endpoint import KMA_API_HUB_BASE_URL, resolve_apihub_endpoint
from ummaya.tools.kma.response_payload import (
    KmaPayloadDecodeError,
    decode_response_payload,
    summarize_http_status_error,
)
from ummaya.tools.models import AdapterRealDomainPolicy, GovAPITool
from ummaya.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

type KmaApiHubQueryValue = str | int | float | bool


class KmaApiHubStructuredOutput(BaseModel):
    """Normalized output from one KMA APIHub structured operation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    operation_id: str
    service: str
    operation: str
    result_code: str | None = None
    result_msg: str | None = None
    page_no: int | None = None
    num_of_rows: int | None = None
    total_count: int | None = None
    items: list[dict[str, object]]
    raw_format: Literal["json", "xml", "text_error"]


def _field_type(param_type: str) -> type[str] | type[int] | type[float] | type[bool]:
    if param_type == "integer":
        return int
    if param_type == "number":
        return float
    if param_type == "boolean":
        return bool
    return str


def _model_name(operation: KmaApiHubOperation) -> str:
    parts = [
        part
        for part in operation.tool_id.removeprefix("kma_apihub_").split("_")
        if part and part != "2" and part != "0"
    ]
    return "KmaApiHub" + "".join(part.title() for part in parts) + "Input"


@cache
def input_schema_for(operation_id: str) -> type[BaseModel]:
    """Build the Pydantic input model for ``<service>/<operation>``."""
    operation = next(op for op in iter_structured_operations() if op.operation_id == operation_id)
    fields: dict[str, tuple[object, object]] = {}
    for param in operation.non_credential_params:
        default: object = param.default if param.default is not None else ...
        fields[param.field_name] = (
            _field_type(param.value_type),
            Field(
                default,
                description=f"KMA APIHub request parameter {param.name}.",
            ),
        )

    model = create_model(  # type: ignore[call-overload]
        _model_name(operation),
        __config__=ConfigDict(frozen=True, extra="forbid"),
        **fields,
    )
    return cast(type[BaseModel], model)


def _response_format(response: httpx.Response) -> Literal["json", "xml", "text_error"]:
    content_type = response.headers.get("content-type", "").lower()
    if "json" in content_type:
        return "json"
    if "xml" in content_type or response.text.lstrip().startswith("<"):
        return "xml"
    return "text_error"


def _dict_or_empty(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): val for key, val in value.items()}


def _normalize_items(value: object) -> list[dict[str, object]]:
    if not value:
        return []
    if isinstance(value, dict):
        return [_dict_or_empty(value)]
    if isinstance(value, list):
        return [_dict_or_empty(item) for item in value if isinstance(item, dict)]
    return [{"value": value}]


def _int_or_none(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value))
    except ValueError:
        return None


def _parse_response(
    operation: KmaApiHubOperation,
    payload: dict[str, object],
    *,
    raw_format: Literal["json", "xml", "text_error"],
) -> KmaApiHubStructuredOutput:
    try:
        response = _dict_or_empty(payload["response"])
    except KeyError as exc:
        raise ToolExecutionError(
            tool_id=operation.tool_id,
            message=f"Unexpected KMA APIHub response structure: missing {exc}",
            cause=exc,
        ) from exc

    header = _dict_or_empty(response.get("header"))
    result_code = str(header.get("resultCode", "")) or None
    result_msg = str(header.get("resultMsg", "")) or None
    if result_code and result_code != "00":
        raise ToolExecutionError(
            tool_id=operation.tool_id,
            message=(
                "KMA APIHub error: "
                f"operation={operation.operation_id!r} "
                f"resultCode={result_code!r} resultMsg={result_msg!r}"
            ),
        )

    body = _dict_or_empty(response.get("body"))
    items_container = _dict_or_empty(body.get("items"))
    raw_items = items_container.get("item")
    items = _normalize_items(raw_items)

    return KmaApiHubStructuredOutput(
        operation_id=operation.operation_id,
        service=operation.service,
        operation=operation.operation,
        result_code=result_code,
        result_msg=result_msg,
        page_no=_int_or_none(body.get("pageNo")),
        num_of_rows=_int_or_none(body.get("numOfRows")),
        total_count=_int_or_none(body.get("totalCount")),
        items=items,
        raw_format=raw_format,
    )


def _query_params(
    operation: KmaApiHubOperation,
    params: BaseModel,
) -> dict[str, KmaApiHubQueryValue]:
    values = params.model_dump(mode="python")
    query: dict[str, KmaApiHubQueryValue] = {}
    for param in operation.non_credential_params:
        value = values.get(param.field_name)
        if value is None:
            continue
        if not isinstance(value, (str, int, float, bool)):
            value = str(value)
        query[param.name] = value
    return query


def _status_error_message(operation: KmaApiHubOperation, exc: httpx.HTTPStatusError) -> str:
    base = f"HTTP error from KMA APIHub: {summarize_http_status_error(exc)}"
    if exc.response.status_code not in {401, 403}:
        return base
    if operation.approval_state != "approval_pending":
        return base
    return (
        f"{base}. APIHub utilization approval for {operation.operation_id!r} "
        "was not observed in the approved-app evidence captured on 2026-05-24."
    )


async def call_operation(
    operation: KmaApiHubOperation,
    params: BaseModel,
    *,
    client: httpx.AsyncClient | None = None,
) -> KmaApiHubStructuredOutput:
    """Call one structured KMA APIHub operation and normalize its envelope."""
    endpoint = resolve_apihub_endpoint(operation)
    query_params = _query_params(operation, params)
    query_params[endpoint.auth_query_param] = endpoint.api_key

    own_client = client is None
    if own_client:
        client = traced_async_client(timeout=30.0)

    try:
        assert client is not None  # noqa: S101
        response = await client.get(endpoint.url, params=query_params)
        response.raise_for_status()
        raw_format = _response_format(response)
        payload = decode_response_payload(response)
        return _parse_response(operation, payload, raw_format=raw_format)
    except (ToolExecutionError, ConfigurationError):
        raise
    except httpx.HTTPStatusError as exc:
        raise ToolExecutionError(
            tool_id=operation.tool_id,
            message=_status_error_message(operation, exc),
            cause=exc,
        ) from exc
    except httpx.RequestError as exc:
        raise ToolExecutionError(
            tool_id=operation.tool_id,
            message=f"Network error reaching KMA APIHub: {exc}",
            cause=exc,
        ) from exc
    except KmaPayloadDecodeError as exc:
        raise ToolExecutionError(
            tool_id=operation.tool_id,
            message=f"Unable to decode KMA APIHub response: {exc}",
            cause=exc,
        ) from exc
    finally:
        if own_client and client is not None:
            await client.aclose()


def build_tool(operation: KmaApiHubOperation) -> GovAPITool:
    """Build the GovAPITool definition for a catalog operation."""
    return GovAPITool(
        id=operation.tool_id,
        name_ko=f"KMA APIHub {operation.category_name_ko} {operation.operation}",
        ministry="KMA",
        category=["기상청", "APIHub", operation.category_name_ko, operation.service],
        endpoint=f"{KMA_API_HUB_BASE_URL}{operation.endpoint_path}",
        auth_type="api_key",
        input_schema=input_schema_for(operation.operation_id),
        output_schema=KmaApiHubStructuredOutput,
        search_hint=(
            f"KMA APIHub 기상청 {operation.category_name_ko} {operation.service} "
            f"{operation.operation} {operation.operation_id} weather meteorological data"
        ),
        llm_description=(
            f"KMA APIHub structured OpenAPI operation {operation.operation_id}. "
            "Use this for direct agency weather data lookup only when the user's "
            "request matches this specific API family. Authentication uses "
            "UMMAYA_KMA_API_HUB_AUTH_KEY via the APIHub authKey parameter."
        ),
        policy=AdapterRealDomainPolicy(
            real_classification_url="https://apihub.kma.go.kr/",
            real_classification_text=(
                "KMA APIHub structured OpenAPI surface; read-only weather and "
                "meteorological data access."
            ),
            citizen_facing_gate="read-only",
            last_verified=datetime(2026, 5, 24, tzinfo=UTC),
        ),
        is_concurrency_safe=True,
        cache_ttl_seconds=600,
        rate_limit_per_minute=10,
        is_core=False,
        primitive="find",
    )


def _adapter_for(operation: KmaApiHubOperation) -> AdapterFn:
    async def _adapter(inp: BaseModel) -> dict[str, object]:
        output = await call_operation(operation, inp)
        return {"kind": "record", "item": output.model_dump(mode="python")}

    return cast(AdapterFn, _adapter)


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register every cataloged structured KMA APIHub operation."""
    count = 0
    for operation in iter_structured_operations():
        tool = build_tool(operation)
        registry.register(tool)
        executor.register_adapter(tool.id, _adapter_for(operation))
        count += 1
    logger.info("Registered %d KMA APIHub structured OpenAPI tools", count)
