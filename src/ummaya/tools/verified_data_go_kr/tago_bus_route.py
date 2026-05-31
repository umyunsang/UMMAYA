# SPDX-License-Identifier: Apache-2.0
"""TAGO bus route search adapter."""

from __future__ import annotations

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


class TagoBusRouteInput(BaseModel):
    """Input for TAGO bus route search."""

    model_config = ConfigDict(extra="forbid")

    city_code: str = Field(..., min_length=1, description=_TAGO_CITY_CODE_DESCRIPTION)
    route_no: str = Field(..., min_length=1, description="Bus route number visible to citizens.")
    page_no: int = Field(default=1, ge=1, description="Page number.")
    num_of_rows: int = Field(default=10, ge=1, le=100, description="Rows per page.")


SPEC = require_spec("tago_bus_route_search")
INPUT_SCHEMA = TagoBusRouteInput
TOOL: GovAPITool = build_tool(SPEC, INPUT_SCHEMA)


async def handle(
    input_model: TagoBusRouteInput,
    *,
    fixture_body: bytes | None = None,
) -> dict[str, object]:
    """Fetch or replay TAGO bus route rows."""

    return await handle_verified_input(input_model, SPEC, fixture_body=fixture_body)


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register this adapter."""

    register_module(registry, executor, tool=TOOL, input_schema=INPUT_SCHEMA, handler=handle)
