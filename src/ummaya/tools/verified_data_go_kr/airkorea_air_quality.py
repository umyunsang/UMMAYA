# SPDX-License-Identifier: Apache-2.0
"""AirKorea city/province real-time air quality adapter."""

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


class AirKoreaAirQualityInput(BaseModel):
    """Input for AirKorea city/province air quality."""

    model_config = ConfigDict(extra="forbid")

    sido_name: str = Field(..., min_length=1, description="Korean province/city name.")
    page_no: int = Field(default=1, ge=1, description="Page number.")
    num_of_rows: int = Field(default=10, ge=1, le=100, description="Rows per page.")
    ver: str = Field(default="1.0", description="AirKorea response version.")


SPEC = require_spec("airkorea_ctprvn_air_quality")
INPUT_SCHEMA = AirKoreaAirQualityInput
TOOL: GovAPITool = build_tool(SPEC, INPUT_SCHEMA)


async def handle(
    input_model: AirKoreaAirQualityInput,
    *,
    fixture_body: bytes | None = None,
) -> dict[str, object]:
    """Fetch or replay AirKorea air quality rows."""

    return await handle_verified_input(input_model, SPEC, fixture_body=fixture_body)


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register this adapter."""

    register_module(registry, executor, tool=TOOL, input_schema=INPUT_SCHEMA, handler=handle)
