# SPDX-License-Identifier: Apache-2.0
"""Gyeryong assistive-device charging place adapter."""

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


class GyeryongAssistiveChargerInput(BaseModel):
    """Input for Gyeryong assistive-device charger locations."""

    model_config = ConfigDict(extra="forbid")

    current_page: int = Field(default=1, ge=1, description="Page number.")
    per_page: int = Field(default=10, ge=1, le=100, description="Rows per page.")
    indoor_outdoor: str | None = Field(
        default=None,
        min_length=1,
        description="Indoor/outdoor filter.",
    )


SPEC = require_spec("gyeryong_assistive_device_charging_place_locate")
INPUT_SCHEMA = GyeryongAssistiveChargerInput
TOOL: GovAPITool = build_tool(SPEC, INPUT_SCHEMA)


async def handle(
    input_model: GyeryongAssistiveChargerInput,
    *,
    fixture_body: bytes | None = None,
) -> dict[str, object]:
    """Fetch or replay Gyeryong charger rows."""

    return await handle_verified_input(input_model, SPEC, fixture_body=fixture_body)


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register this adapter."""

    register_module(registry, executor, tool=TOOL, input_schema=INPUT_SCHEMA, handler=handle)
