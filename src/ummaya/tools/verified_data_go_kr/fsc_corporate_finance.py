# SPDX-License-Identifier: Apache-2.0
"""FSC corporate finance summary adapter."""

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


class FscCorporateFinanceInput(BaseModel):
    """Input for FSC corporate finance summary."""

    model_config = ConfigDict(extra="forbid")

    crno: str = Field(..., min_length=1, description="Corporate registration number.")
    biz_year: str = Field(..., min_length=4, max_length=4, description="Business year.")
    page_no: int = Field(default=1, ge=1, description="Page number.")
    num_of_rows: int = Field(default=10, ge=1, le=100, description="Rows per page.")


SPEC = require_spec("fsc_corporate_finance_summary")
INPUT_SCHEMA = FscCorporateFinanceInput
TOOL: GovAPITool = build_tool(SPEC, INPUT_SCHEMA)


async def handle(
    input_model: FscCorporateFinanceInput,
    *,
    fixture_body: bytes | None = None,
) -> dict[str, object]:
    """Fetch or replay FSC corporate finance summary."""

    return await handle_verified_input(input_model, SPEC, fixture_body=fixture_body)


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register this adapter."""

    register_module(registry, executor, tool=TOOL, input_schema=INPUT_SCHEMA, handler=handle)
