# SPDX-License-Identifier: Apache-2.0
"""Factory helpers shared by verified public-data adapter modules."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC

from pydantic import BaseModel

from ummaya.tools.executor import ToolExecutor
from ummaya.tools.models import AdapterRealDomainPolicy, GovAPITool
from ummaya.tools.registry import ToolRegistry
from ummaya.tools.verified_data_go_kr._client import fetch_verified_output
from ummaya.tools.verified_data_go_kr._models import VerifiedAdapterSpec

type AdapterHandle[InputT: BaseModel] = Callable[[InputT], Awaitable[dict[str, object]]]


def build_tool(spec: VerifiedAdapterSpec, input_schema: type[BaseModel]) -> GovAPITool:
    """Build the GovAPITool metadata object for one verified adapter."""

    return GovAPITool(
        id=spec.tool_id,
        name_ko=spec.name_ko,
        ministry=spec.ministry,
        category=spec.category,
        endpoint=str(spec.endpoint),
        auth_type="api_key",
        input_schema=input_schema,
        output_schema=_VerifiedCollectionSchema,
        search_hint=spec.search_hint,
        policy=AdapterRealDomainPolicy(
            real_classification_url=spec.policy_url,
            real_classification_text=spec.policy_text,
            citizen_facing_gate=spec.citizen_facing_gate,
            last_verified=spec.last_verified.astimezone(UTC),
        ),
        is_concurrency_safe=True,
        cache_ttl_seconds=300,
        rate_limit_per_minute=20,
        adapter_mode=spec.adapter_mode,
        primitive=spec.primitive,
        llm_description=spec.llm_description,
        trigger_examples=spec.trigger_examples,
    )


async def handle_verified_input(
    input_model: BaseModel,
    spec: VerifiedAdapterSpec,
    *,
    fixture_body: bytes | None = None,
) -> dict[str, object]:
    """Return an executor-ready dict for one verified adapter call."""

    output = await fetch_verified_output(input_model, spec, fixture_body=fixture_body)
    return output.model_dump(mode="python")


def register_module[InputT: BaseModel](
    registry: ToolRegistry,
    executor: ToolExecutor,
    *,
    tool: GovAPITool,
    input_schema: type[InputT],
    handler: AdapterHandle[InputT],
) -> None:
    """Register one verified module with the central registry and executor."""

    registry.register(tool)

    async def adapter(input_model: BaseModel) -> dict[str, object]:
        validated = input_schema.model_validate(input_model)
        return await handler(validated)

    executor.register_adapter(tool.id, adapter)


class _VerifiedCollectionSchema(BaseModel):
    """Output schema used by legacy ToolExecutor.dispatch validation."""

    kind: str
    items: list[dict[str, object]]
    total_count: int
