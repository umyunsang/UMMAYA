# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import Iterable

from ummaya.tools.models import GovAPITool
from ummaya.tools.routing.metadata import (
    capabilities_for_tool,
    credential_requirements_for_tool,
    domain_for_tool,
    entity_types_for_tool,
    examples_en_for_tool,
    examples_ko_for_tool,
    limitations_for_tool,
    mock_fidelity_grade_for_tool,
    prerequisite_tools_for_tool,
    primitive_family,
    routing_text,
    safety_annotations_for_tool,
    side_effect_level_for_tool,
    source_mode_for_tool,
)
from ummaya.tools.routing.schema import model_json_schema, schema_summary, sha256
from ummaya.tools.routing.types import (
    INTENT_VERBS,
    LEGACY_ALIASES,
    AdapterCard,
)


def build_adapter_cards(tools: Iterable[GovAPITool]) -> tuple[AdapterCard, ...]:
    return tuple(build_adapter_card(tool) for tool in sorted(tools, key=lambda item: item.id))


def build_adapter_card(tool: GovAPITool) -> AdapterCard:
    primitive = primitive_family(tool.primitive)
    input_schema = model_json_schema(tool.input_schema)
    output_schema = model_json_schema(tool.output_schema)
    input_summary = schema_summary(input_schema)
    output_summary = schema_summary(output_schema)
    required_slots = tuple(field.name for field in input_summary if field.required)
    optional_slots = tuple(field.name for field in input_summary if not field.required)
    source_mode = source_mode_for_tool(tool)
    policy_authority_url = tool.policy.real_classification_url if tool.policy is not None else None
    side_effect_level = side_effect_level_for_tool(tool, primitive)
    credential_requirements = credential_requirements_for_tool(tool)
    capabilities = capabilities_for_tool(tool, primitive)
    entity_types = entity_types_for_tool(input_summary, tool.category)
    prerequisite_tools = prerequisite_tools_for_tool(tool, primitive)
    input_schema_hash = sha256(input_schema)
    manifest_hash = sha256(
        {
            "tool_id": tool.id,
            "primitive_family": primitive,
            "agency": str(tool.ministry),
            "source_mode": source_mode,
            "policy_authority_url": policy_authority_url,
            "input_schema_hash": input_schema_hash,
            "output_schema_hash": sha256(output_schema),
        }
    )
    examples_ko = examples_ko_for_tool(tool)
    examples_en = examples_en_for_tool(tool, primitive)
    negative_examples = (f"Do not use for requests outside primitive {primitive}.",)
    limitations = limitations_for_tool(tool, source_mode, policy_authority_url)
    safety_annotations = safety_annotations_for_tool(tool, side_effect_level)

    return AdapterCard(
        tool_id=tool.id,
        primitive_family=primitive,
        legacy_primitive_aliases=LEGACY_ALIASES[primitive],
        domain=domain_for_tool(tool),
        agency=str(tool.ministry),
        source_mode=source_mode,
        capabilities=capabilities,
        intent_verbs=INTENT_VERBS[primitive],
        entity_types=entity_types,
        required_slots=required_slots,
        optional_slots=optional_slots,
        prerequisite_tools=prerequisite_tools,
        input_schema_hash=input_schema_hash,
        input_schema_summary=input_summary,
        output_schema_summary=output_summary,
        policy_authority_url=policy_authority_url,
        safety_annotations=safety_annotations,
        side_effect_level=side_effect_level,
        credential_requirements=credential_requirements,
        mock_fidelity_grade=mock_fidelity_grade_for_tool(tool),
        examples_ko=examples_ko,
        examples_en=examples_en,
        negative_examples=negative_examples,
        limitations=limitations,
        manifest_hash=manifest_hash,
        routing_text=routing_text(
            tool_id=tool.id,
            primitive=primitive,
            agency=str(tool.ministry),
            domain=domain_for_tool(tool),
            capabilities=capabilities,
            required_slots=required_slots,
            examples_ko=examples_ko,
            limitations=limitations,
        ),
    )
