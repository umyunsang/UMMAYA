# SPDX-License-Identifier: Apache-2.0
"""Daejeon metro segment fare/time adapter."""

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


class DjtcSubwaySegmentInput(BaseModel):
    """Input for Daejeon subway segment fare and time."""

    model_config = ConfigDict(extra="forbid")

    strstnno: str = Field(..., min_length=1, description="Starting station number.")
    endstnno: str = Field(..., min_length=1, description="Ending station number.")


SPEC = require_spec("djtc_subway_segment_fare_time_check")
INPUT_SCHEMA = DjtcSubwaySegmentInput
TOOL: GovAPITool = build_tool(SPEC, INPUT_SCHEMA)


async def handle(
    input_model: DjtcSubwaySegmentInput,
    *,
    fixture_body: bytes | None = None,
) -> dict[str, object]:
    """Fetch or replay Daejeon subway segment rows."""

    return await handle_verified_input(input_model, SPEC, fixture_body=fixture_body)


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register this adapter."""

    register_module(registry, executor, tool=TOOL, input_schema=INPUT_SCHEMA, handler=handle)
