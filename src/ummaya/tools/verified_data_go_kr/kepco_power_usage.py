# SPDX-License-Identifier: Apache-2.0
"""KEPCO contract-type power usage adapter."""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from ummaya.tools.executor import ToolExecutor
from ummaya.tools.models import GovAPITool
from ummaya.tools.registry import ToolRegistry
from ummaya.tools.verified_data_go_kr._factory import (
    build_tool,
    handle_verified_input,
    register_module,
)
from ummaya.tools.verified_data_go_kr._manifest import require_spec


class KepcoPowerUsageInput(BaseModel):
    """Input for KEPCO contract-type power usage."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    year: str = Field(..., min_length=4, max_length=4, description="Usage year.")
    month: str = Field(..., min_length=1, max_length=2, description="Usage month.")
    metro_cd: str | None = Field(
        default=None,
        validation_alias=AliasChoices("metro_cd", "metroCd"),
        description="Metropolitan code.",
    )
    city_cd: str | None = Field(
        default=None,
        validation_alias=AliasChoices("city_cd", "cityCd"),
        description="City/county/district code.",
    )
    cntr_cd: str | None = Field(
        default=None,
        validation_alias=AliasChoices("cntr_cd", "cntrCd"),
        description="Contract type code.",
    )


SPEC = require_spec("kepco_contract_power_usage")
INPUT_SCHEMA = KepcoPowerUsageInput
TOOL: GovAPITool = build_tool(SPEC, INPUT_SCHEMA)


async def handle(
    input_model: KepcoPowerUsageInput,
    *,
    fixture_body: bytes | None = None,
) -> dict[str, object]:
    """Fetch or replay KEPCO power usage rows."""

    return await handle_verified_input(input_model, SPEC, fixture_body=fixture_body)


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register this adapter."""

    register_module(registry, executor, tool=TOOL, input_schema=INPUT_SCHEMA, handler=handle)
