# SPDX-License-Identifier: Apache-2.0
"""MPM public job notice lookup adapter."""

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


class MpmPublicJobInput(BaseModel):
    """Input for MPM public job notices."""

    model_config = ConfigDict(extra="forbid")

    pblanc_ty: str = Field(default="e01", min_length=1, description="Notice type code.")
    instt_se: str = Field(default="g01", min_length=1, description="Institution class code.")
    sort_order: str = Field(default="내림차순", min_length=1, description="Sort order.")
    page_no: int = Field(default=1, ge=1, description="Page number.")
    num_of_rows: int = Field(default=10, ge=1, le=100, description="Rows per page.")


SPEC = require_spec("mpm_public_job_lookup")
INPUT_SCHEMA = MpmPublicJobInput
TOOL: GovAPITool = build_tool(SPEC, INPUT_SCHEMA)


async def handle(
    input_model: MpmPublicJobInput,
    *,
    fixture_body: bytes | None = None,
) -> dict[str, object]:
    """Fetch or replay MPM public job rows."""

    return await handle_verified_input(input_model, SPEC, fixture_body=fixture_body)


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register this adapter."""

    register_module(registry, executor, tool=TOOL, input_schema=INPUT_SCHEMA, handler=handle)
