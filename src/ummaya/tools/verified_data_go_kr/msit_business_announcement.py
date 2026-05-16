# SPDX-License-Identifier: Apache-2.0
"""MSIT business announcement adapter."""

from __future__ import annotations

from typing import Literal

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


class MsitBusinessAnnouncementInput(BaseModel):
    """Input for MSIT business announcements."""

    model_config = ConfigDict(extra="forbid")

    page_no: int = Field(default=1, ge=1, description="Page number.")
    num_of_rows: int = Field(default=10, ge=1, le=100, description="Rows per page.")
    return_type: Literal["xml"] = Field(
        default="xml",
        description="Response format pinned to XML for the recorded live contract.",
    )


SPEC = require_spec("msit_business_announcement_lookup")
INPUT_SCHEMA = MsitBusinessAnnouncementInput
TOOL: GovAPITool = build_tool(SPEC, INPUT_SCHEMA)


async def handle(
    input_model: MsitBusinessAnnouncementInput,
    *,
    fixture_body: bytes | None = None,
) -> dict[str, object]:
    """Fetch or replay MSIT business announcement rows."""

    return await handle_verified_input(input_model, SPEC, fixture_body=fixture_body)


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register this adapter."""

    register_module(registry, executor, tool=TOOL, input_schema=INPUT_SCHEMA, handler=handle)
