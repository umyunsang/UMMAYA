# SPDX-License-Identifier: Apache-2.0
"""PPS bid public information adapter."""

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


class PpsBidPublicInfoInput(BaseModel):
    """Input for PPS bid public information."""

    model_config = ConfigDict(extra="forbid")

    inqry_div: str = Field(..., min_length=1, description="PPS inquiry division.")
    bid_ntce_no: str | None = Field(default=None, description="Bid notice number.")
    page_no: int = Field(default=1, ge=1, description="Page number.")
    num_of_rows: int = Field(default=10, ge=1, le=100, description="Rows per page.")


SPEC = require_spec("pps_bid_public_info")
INPUT_SCHEMA = PpsBidPublicInfoInput
TOOL: GovAPITool = build_tool(SPEC, INPUT_SCHEMA)


async def handle(
    input_model: PpsBidPublicInfoInput,
    *,
    fixture_body: bytes | None = None,
) -> dict[str, object]:
    """Fetch or replay PPS bid public information rows."""

    return await handle_verified_input(input_model, SPEC, fixture_body=fixture_body)


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register this adapter."""

    register_module(registry, executor, tool=TOOL, input_schema=INPUT_SCHEMA, handler=handle)
