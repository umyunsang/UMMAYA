# SPDX-License-Identifier: Apache-2.0
"""REB real-estate statistic table adapter."""

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


class RebRealEstateStatsInput(BaseModel):
    """Input for REB statistic table search."""

    model_config = ConfigDict(extra="forbid")

    statbl_id: str | None = Field(default=None, description="Optional statistic table ID.")
    p_index: int = Field(default=1, ge=1, description="Page index.")
    p_size: int = Field(default=100, ge=1, le=1000, description="Page size.")


SPEC = require_spec("reb_real_estate_stat_table")
INPUT_SCHEMA = RebRealEstateStatsInput
TOOL: GovAPITool = build_tool(SPEC, INPUT_SCHEMA)


async def handle(
    input_model: RebRealEstateStatsInput,
    *,
    fixture_body: bytes | None = None,
) -> dict[str, object]:
    """Fetch or replay REB real-estate statistic table rows."""

    return await handle_verified_input(input_model, SPEC, fixture_body=fixture_body)


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register this adapter."""

    register_module(registry, executor, tool=TOOL, input_schema=INPUT_SCHEMA, handler=handle)
