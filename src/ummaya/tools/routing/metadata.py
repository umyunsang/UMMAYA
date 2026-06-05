# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import Sequence
from typing import assert_never

from ummaya.tools.models import GovAPITool, MockFidelityGrade
from ummaya.tools.routing.schema import unique
from ummaya.tools.routing.types import (
    AdapterCardError,
    PrimitiveFamily,
    SchemaFieldSummary,
    SideEffectLevel,
    SourceMode,
)


def primitive_family(value: str | None) -> PrimitiveFamily:
    match value:
        case "find":
            return "find"
        case "locate":
            return "locate"
        case "send":
            return "send"
        case "check":
            return "check"
        case "document":
            return "document"
        case None:
            raise AdapterCardError("AdapterCard requires GovAPITool.primitive to be declared")
        case _:
            raise AdapterCardError(f"Unsupported adapter primitive for AdapterCard: {value!r}")


def source_mode_for_tool(tool: GovAPITool) -> SourceMode:
    return "mock" if tool.adapter_mode == "mock" else "live"


def side_effect_level_for_tool(
    tool: GovAPITool,
    primitive: PrimitiveFamily,
) -> SideEffectLevel:
    if tool.policy is not None:
        match tool.policy.citizen_facing_gate:
            case "read-only":
                return "read_only"
            case "login":
                return "login"
            case "action":
                return "action"
            case "sign":
                return "sign"
            case "send":
                return "send"
            case unreachable_gate:
                assert_never(unreachable_gate)
    match primitive:
        case "send":
            return "send"
        case "check":
            return "verify"
        case "find" | "locate" | "document":
            return "read_only"
        case unreachable_primitive:
            assert_never(unreachable_primitive)


def mock_fidelity_grade_for_tool(tool: GovAPITool) -> MockFidelityGrade:
    if tool.adapter_mode != "mock":
        return "not_applicable"
    if tool.mock_fidelity_grade == "not_applicable":
        return "unknown"
    return tool.mock_fidelity_grade


def credential_requirements_for_tool(tool: GovAPITool) -> tuple[str, ...]:
    requirements: list[str] = [tool.auth_type]
    if tool.published_tier_minimum is not None:
        requirements.append(tool.published_tier_minimum)
    if tool.nist_aal_hint is not None:
        requirements.append(tool.nist_aal_hint)
    return tuple(unique(requirements))


def capabilities_for_tool(tool: GovAPITool, primitive: PrimitiveFamily) -> tuple[str, ...]:
    return tuple(unique([primitive, *tool.category, tool.name_ko]))


def entity_types_for_tool(
    input_summary: Sequence[SchemaFieldSummary],
    categories: Sequence[str],
) -> tuple[str, ...]:
    names = [field.name for field in input_summary]
    if names:
        return tuple(names)
    return tuple(unique(categories))


def prerequisite_tools_for_tool(tool: GovAPITool, primitive: PrimitiveFamily) -> tuple[str, ...]:
    description = (tool.llm_description or "").lower()
    if primitive == "send" or "prior check" in description or "delegation" in description:
        return ("check",)
    return ()


def examples_ko_for_tool(tool: GovAPITool) -> tuple[str, ...]:
    if tool.trigger_examples:
        return tuple(tool.trigger_examples)
    return (tool.name_ko,)


def examples_en_for_tool(tool: GovAPITool, primitive: PrimitiveFamily) -> tuple[str, ...]:
    domain = tool.category[0] if tool.category else tool.id
    return (f"Use {tool.id} to {primitive} {domain} information.",)


def limitations_for_tool(
    tool: GovAPITool,
    source_mode: SourceMode,
    policy_authority_url: str | None,
) -> tuple[str, ...]:
    limitations = [f"Requires registry source_mode {source_mode} and auth_type {tool.auth_type}."]
    if source_mode == "mock":
        limitations.append("Mock output may mirror shape without live upstream freshness.")
    if policy_authority_url is None:
        limitations.append("No agency policy citation is registered for this adapter.")
    return tuple(limitations)


def safety_annotations_for_tool(
    tool: GovAPITool,
    side_effect_level: SideEffectLevel,
) -> tuple[str, ...]:
    values = [
        f"side_effect_level:{side_effect_level}",
        f"auth_type:{tool.auth_type}",
        f"concurrency_safe:{str(tool.is_concurrency_safe).lower()}",
    ]
    if tool.policy is not None:
        values.append(f"citizen_gate:{tool.policy.citizen_facing_gate}")
    return tuple(values)


def domain_for_tool(tool: GovAPITool) -> str:
    if tool.category:
        return tool.category[0]
    return tool.id


def routing_text(
    *,
    tool_id: str,
    primitive: PrimitiveFamily,
    agency: str,
    domain: str,
    capabilities: Sequence[str],
    required_slots: Sequence[str],
    examples_ko: Sequence[str],
    limitations: Sequence[str],
) -> str:
    return " | ".join(
        (
            f"tool_id={tool_id}",
            f"primitive={primitive}",
            f"agency={agency}",
            f"domain={domain}",
            f"capabilities={', '.join(capabilities)}",
            f"required_slots={', '.join(required_slots) or 'none'}",
            f"examples_ko={'; '.join(examples_ko)}",
            f"limitations={'; '.join(limitations)}",
        )
    )
