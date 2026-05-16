# SPDX-License-Identifier: Apache-2.0
"""MOJ village lawyer regional status adapter."""

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


class MojVillageLawyerInput(BaseModel):
    """Input for MOJ village lawyer regional assignment rows."""

    model_config = ConfigDict(extra="forbid")

    page_no: int = Field(default=1, ge=1, description="Page number.")
    num_of_rows: int = Field(default=20, ge=1, le=100, description="Rows per page.")


SPEC = require_spec("moj_village_lawyer_lookup")
INPUT_SCHEMA = MojVillageLawyerInput
TOOL: GovAPITool = build_tool(SPEC, INPUT_SCHEMA)


async def handle(
    input_model: MojVillageLawyerInput,
    *,
    fixture_body: bytes | None = None,
) -> dict[str, object]:
    """Fetch or replay MOJ village lawyer rows."""

    return await handle_verified_input(input_model, SPEC, fixture_body=fixture_body)


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register this adapter."""

    register_module(registry, executor, tool=TOOL, input_schema=INPUT_SCHEMA, handler=handle)
