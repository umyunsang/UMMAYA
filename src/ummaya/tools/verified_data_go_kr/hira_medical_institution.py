# SPDX-License-Identifier: Apache-2.0
"""HIRA medical institution detail adapter."""

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


class HiraMedicalInstitutionInput(BaseModel):
    """Input for HIRA medical institution detail."""

    model_config = ConfigDict(extra="forbid")

    ykiho: str = Field(..., min_length=1, description="Encrypted HIRA institution ID.")
    page_no: int = Field(default=1, ge=1, description="Page number.")
    num_of_rows: int = Field(default=5, ge=1, le=100, description="Rows per page.")


SPEC = require_spec("hira_medical_institution_detail")
INPUT_SCHEMA = HiraMedicalInstitutionInput
TOOL: GovAPITool = build_tool(SPEC, INPUT_SCHEMA)


async def handle(
    input_model: HiraMedicalInstitutionInput,
    *,
    fixture_body: bytes | None = None,
) -> dict[str, object]:
    """Fetch or replay HIRA detail rows."""

    return await handle_verified_input(input_model, SPEC, fixture_body=fixture_body)


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register this adapter."""

    register_module(registry, executor, tool=TOOL, input_schema=INPUT_SCHEMA, handler=handle)
