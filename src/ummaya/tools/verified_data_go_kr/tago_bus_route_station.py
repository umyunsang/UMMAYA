# SPDX-License-Identifier: Apache-2.0
"""TAGO bus route-station search adapter."""

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


class TagoBusRouteStationInput(BaseModel):
    """Input for TAGO route-station search."""

    model_config = ConfigDict(extra="forbid")

    city_code: str = Field(..., min_length=1, description=_TAGO_CITY_CODE_DESCRIPTION)
    route_id: str = Field(
        ...,
        min_length=1,
        description="Official TAGO routeId returned by tago_bus_route_search.",
    )
    node_nm: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Optional client-side filter against the official TAGO response field nodenm. "
            "Use it to narrow a route's passing stops to a citizen-named place such as 부산역."
        ),
    )
    updown_cd: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Optional client-side filter against the official TAGO response field updowncd "
            "when a direction is already known."
        ),
    )
    page_no: int = Field(default=1, ge=1, description="Page number.")
    num_of_rows: int = Field(default=100, ge=1, le=100, description="Rows per page.")


SPEC = require_spec("tago_bus_route_station_search")
INPUT_SCHEMA = TagoBusRouteStationInput
TOOL: GovAPITool = build_tool(SPEC, INPUT_SCHEMA)


async def handle(
    input_model: TagoBusRouteStationInput,
    *,
    fixture_body: bytes | None = None,
) -> dict[str, object]:
    """Fetch or replay TAGO route-station rows."""

    output = await handle_verified_input(input_model, SPEC, fixture_body=fixture_body)
    if input_model.node_nm is None and input_model.updown_cd is None:
        return output
    return _filter_route_stations(
        output,
        node_nm=input_model.node_nm,
        updown_cd=input_model.updown_cd,
    )


def _filter_route_stations(
    output: dict[str, object],
    *,
    node_nm: str | None,
    updown_cd: str | None,
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
        if node_nm is not None and node_nm not in str(typed_record.get("nodenm", "")):
            continue
        if updown_cd is not None and str(typed_record.get("updowncd", "")) != updown_cd:
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
