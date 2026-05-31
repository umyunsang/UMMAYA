# SPDX-License-Identifier: Apache-2.0
"""TAGO bus arrival search adapter."""

from __future__ import annotations

from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from ummaya.tools.executor import ToolExecutor
from ummaya.tools.models import GovAPITool
from ummaya.tools.registry import ToolRegistry
from ummaya.tools.verified_data_go_kr._factory import (
    build_tool,
    handle_verified_input,
    register_module,
)
from ummaya.tools.verified_data_go_kr._manifest import require_spec

_TAGO_CITY_CODE_DESCRIPTION = (
    "Official TAGO cityCode from the provider getCtyCodeList contract. "
    "Common metropolitan examples: Busan=21, Daegu=22, Incheon=23, "
    "Gwangju=24, Daejeon=25, Ulsan=26."
)


class TagoBusArrivalInput(BaseModel):
    """Input for TAGO bus arrival search."""

    model_config = ConfigDict(extra="forbid")

    city_code: str = Field(..., min_length=1, description=_TAGO_CITY_CODE_DESCRIPTION)
    node_id: str = Field(
        ...,
        min_length=1,
        description="Official TAGO nodeId returned by tago_bus_station_search.",
    )
    route_no: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Optional client-side filter against the official TAGO response field routeno. "
            "It is not sent upstream; use it when the citizen names a visible bus route "
            "such as 1001."
        ),
    )
    route_id: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Optional client-side filter against the official TAGO response field routeid. "
            "Get it from tago_bus_route_search when route_no alone is ambiguous."
        ),
    )
    page_no: int = Field(default=1, ge=1, description="Page number.")
    num_of_rows: int = Field(default=10, ge=1, le=100, description="Rows per page.")


SPEC = require_spec("tago_bus_arrival_search")
INPUT_SCHEMA = TagoBusArrivalInput
TOOL: GovAPITool = build_tool(SPEC, INPUT_SCHEMA)


async def handle(
    input_model: TagoBusArrivalInput,
    *,
    fixture_body: bytes | None = None,
) -> dict[str, object]:
    """Fetch or replay TAGO bus arrival rows."""

    output = await handle_verified_input(input_model, SPEC, fixture_body=fixture_body)
    if input_model.route_no is None and input_model.route_id is None:
        return output
    return _filter_arrivals(output, route_no=input_model.route_no, route_id=input_model.route_id)


def _filter_arrivals(
    output: dict[str, object],
    *,
    route_no: str | None,
    route_id: str | None,
) -> dict[str, object]:
    items = output.get("items")
    if not isinstance(items, list):
        return output

    filtered: list[dict[str, object]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        record = item.get("record")
        if not isinstance(record, dict):
            continue
        typed_record = cast(dict[str, object], record)
        if route_no is not None and str(typed_record.get("routeno", "")) != route_no:
            continue
        if route_id is not None and str(typed_record.get("routeid", "")) != route_id:
            continue
        filtered.append(cast(dict[str, object], item))

    filtered_output = dict(output)
    filtered_output["items"] = filtered
    filtered_output["total_count"] = len(filtered)
    filtered_output["next_cursor"] = None
    return filtered_output


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register this adapter."""

    register_module(registry, executor, tool=TOOL, input_schema=INPUT_SCHEMA, handler=handle)
