# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from ummaya.tools.errors import ToolNotFoundError
from ummaya.tools.models import GovAPITool
from ummaya.tools.routing.decision_types import RouteCandidate, RouteDecision, SchemaProjectionLevel
from ummaya.tools.routing.schema import model_json_schema

if TYPE_CHECKING:
    from ummaya.tools.registry import ToolRegistry


class AvailableAdaptersProjection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    content: str | None
    tool_ids: tuple[str, ...]
    schema_projection_level: SchemaProjectionLevel


def build_available_adapters_projection(
    decision: RouteDecision,
    registry: ToolRegistry,
    *,
    query: str,
    projection_level: SchemaProjectionLevel | None = None,
    max_visible: int = 5,
    visible_tool_ids: Iterable[str] | None = None,
    exclude_tool_ids: Iterable[str] = (),
) -> AvailableAdaptersProjection:
    level = projection_level or decision.schema_projection_level
    if level == "none":
        return AvailableAdaptersProjection(
            content=None,
            tool_ids=(),
            schema_projection_level=level,
        )

    visible = _selected_candidates(
        decision,
        max_visible=max_visible,
        visible_tool_ids=visible_tool_ids,
        exclude_tool_ids=exclude_tool_ids,
    )
    if not visible:
        return AvailableAdaptersProjection(
            content=None,
            tool_ids=(),
            schema_projection_level="none",
        )

    tool_ids = tuple(candidate.tool_id for candidate in visible)
    lines: list[str] = [
        (
            f'<available_adapters query="{_xml_attr(query[:120])}" '
            f'decision_id="{decision.decision_id}" '
            f'backend="{_xml_attr(decision.backend_label)}" '
            f'schema_projection="{level}">'
        ),
        (
            f"RouteDecision candidates (top {len(visible)}, backend={decision.backend_label}, "
            f"manifest_hash={decision.manifest_hash[:12]})."
        ),
        "Use concrete adapter function names when they are present in tools[].",
    ]
    if decision.degradation_reason:
        lines.append(f"degradation_reason: {decision.degradation_reason}")
    if decision.permission_gate:
        lines.append("permission_gate: true")
    if level == "name_only":
        lines.extend(f"- {candidate.tool_id}" for candidate in visible)
        lines.append("</available_adapters>")
        return AvailableAdaptersProjection(
            content="\n".join(lines),
            tool_ids=tool_ids,
            schema_projection_level=level,
        )

    for candidate in visible:
        lines.extend(_candidate_lines(candidate, registry, projection_level=level))
    lines.extend(_route_rules(visible))
    lines.append("</available_adapters>")
    return AvailableAdaptersProjection(
        content="\n".join(lines),
        tool_ids=tool_ids,
        schema_projection_level=level,
    )


def selected_concrete_adapter_tools(
    decision: RouteDecision,
    registry: ToolRegistry,
    *,
    exclude_tool_ids: Iterable[str] = (),
    max_tools: int = 5,
) -> tuple[GovAPITool, ...]:
    excluded = frozenset(exclude_tool_ids)
    tools: list[GovAPITool] = []
    for tool_id in _decision_tool_ids(decision):
        if tool_id in excluded:
            continue
        try:
            tools.append(registry.find(tool_id))
        except ToolNotFoundError:
            continue
        if len(tools) >= max_tools:
            break
    return tuple(tools)


def _selected_candidates(
    decision: RouteDecision,
    *,
    max_visible: int,
    visible_tool_ids: Iterable[str] | None = None,
    exclude_tool_ids: Iterable[str] = (),
) -> tuple[RouteCandidate, ...]:
    excluded = frozenset(exclude_tool_ids)
    selected = (
        tuple(tool_id for tool_id in visible_tool_ids if tool_id not in excluded)
        if visible_tool_ids is not None
        else tuple(tool_id for tool_id in _decision_tool_ids(decision) if tool_id not in excluded)
    )
    selected_rank = {tool_id: index for index, tool_id in enumerate(selected)}
    candidates_by_id = {
        candidate.tool_id: candidate
        for candidate in decision.candidate_set
        if candidate.tool_id in selected_rank
    }
    ordered = tuple(
        candidates_by_id[tool_id] for tool_id in selected if tool_id in candidates_by_id
    )
    return ordered[: max(0, max_visible)]


def _decision_tool_ids(decision: RouteDecision) -> tuple[str, ...]:
    if decision.selected_tools:
        return decision.selected_tools
    if (
        decision.clarification is not None
        and decision.clarification.reason == "side_effect_confirmation"
    ):
        return ()
    return tuple(candidate.tool_id for candidate in decision.candidate_set)


def _candidate_lines(
    candidate: RouteCandidate,
    registry: ToolRegistry,
    *,
    projection_level: SchemaProjectionLevel,
) -> list[str]:
    card = candidate.card
    lines = [
        f"- tool_id: {card.tool_id}",
        f"  primitive: {card.primitive_family}",
        f"  source_mode: {card.source_mode}",
        f"  agency: {card.agency}",
        f"  domain: {card.domain}",
        f"  score: {candidate.retrieval_score:.4f}",
        f"  description: {_one_line(card.routing_text)}",
        f"  required_params: {list(card.required_slots)}",
        f"  optional_params: {list(card.optional_slots)}",
        f"  call_hint: {card.tool_id}({{...schema fields...}})",
        f"  policy_url: {card.policy_authority_url or ''}",
    ]
    llm_description = _tool_llm_description(card.tool_id, registry)
    if llm_description:
        lines.append(f"  usage: {_one_line(llm_description)}")
    if projection_level in {"summary", "full_schema"}:
        lines.append("  input_schema_summary:")
        lines.extend(_schema_summary_lines(candidate, registry))
    if projection_level == "full_schema":
        try:
            tool = registry.find(card.tool_id)
            schema_json = json.dumps(
                model_json_schema(tool.input_schema),
                ensure_ascii=False,
                sort_keys=True,
            )
        except ToolNotFoundError:
            schema_json = "{}"
        lines.append(f"  input_schema_json: {schema_json}")
    return lines


def _tool_llm_description(tool_id: str, registry: ToolRegistry) -> str | None:
    try:
        value = registry.find(tool_id).llm_description
    except ToolNotFoundError:
        return None
    return value if isinstance(value, str) and value.strip() else None


def _schema_summary_lines(candidate: RouteCandidate, registry: ToolRegistry) -> list[str]:
    card = candidate.card
    try:
        schema = model_json_schema(registry.find(card.tool_id).input_schema)
    except ToolNotFoundError:
        schema = {}
    properties = _mapping(schema.get("properties"))
    defs = _mapping(schema.get("$defs"))
    required = frozenset(card.required_slots)
    lines: list[str] = []
    for field in card.input_schema_summary:
        flag = "required" if field.required else "optional"
        description = f" - {_one_line(field.description)}" if field.description else ""
        lines.append(f"    - {field.name} ({field.type}, {flag}){description}")
        field_schema = _mapping(properties.get(field.name))
        for nested_name, nested_schema in _nested_properties(field.name, field_schema, defs):
            nested_description = _description(nested_schema)
            nested_suffix = f" - {_one_line(nested_description)}" if nested_description else ""
            nested_required = _nested_required(field.name, nested_name, field_schema, defs)
            nested_flag = "required" if field.name in required and nested_required else "optional"
            lines.append(
                f"      - {nested_name} ({_schema_type(nested_schema)}, {nested_flag})"
                f"{nested_suffix}"
            )
    return lines


def _route_rules(candidates: tuple[RouteCandidate, ...]) -> tuple[str, ...]:
    primitives = frozenset(candidate.card.primitive_family for candidate in candidates)
    lines = [
        "Rules:",
        (
            "  - Concrete adapter functions accept only their own schema fields; "
            "do not wrap tool_id/params inside concrete adapter calls."
        ),
        (
            "  - Use root primitives find/locate/check/send only when the concrete "
            "adapter function is not loaded."
        ),
        (
            "  - Preserve explicit citizen constraints such as count, radius, date, "
            "time, category, institution type, and administrative region when a "
            "selected schema exposes the matching field."
        ),
    ]
    if primitives == {"find"}:
        lines.append(
            "  - All selected adapters are read/fetch candidates; do not switch to "
            "check/send unless the citizen explicitly asks for authentication, "
            "consent, submission, payment, report, or filing."
        )
    return tuple(lines)


def _one_line(value: str | None, *, limit: int = 900) -> str:
    compact = " ".join((value or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def _xml_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _nested_properties(
    parent_name: str,
    field_schema: Mapping[str, object],
    defs: Mapping[str, object],
) -> tuple[tuple[str, Mapping[str, object]], ...]:
    target = _resolve_ref(field_schema, defs)
    if target:
        return _properties_with_prefix(parent_name, target)
    raw_items = field_schema.get("items")
    item_schema = _mapping(raw_items)
    item_target = _resolve_ref(item_schema, defs)
    if item_target:
        return _properties_with_prefix(f"{parent_name}[]", item_target)
    return ()


def _properties_with_prefix(
    prefix: str, schema: Mapping[str, object]
) -> tuple[tuple[str, Mapping[str, object]], ...]:
    properties = _mapping(schema.get("properties"))
    return tuple(
        (f"{prefix}.{name}", _mapping(spec)) for name, spec in properties.items() if str(name)
    )


def _nested_required(
    parent_name: str,
    nested_name: str,
    field_schema: Mapping[str, object],
    defs: Mapping[str, object],
) -> bool:
    target = _resolve_ref(field_schema, defs)
    nested_key = nested_name.removeprefix(f"{parent_name}.")
    if not target:
        item_schema = _mapping(field_schema.get("items"))
        target = _resolve_ref(item_schema, defs)
        nested_key = nested_name.removeprefix(f"{parent_name}[].")
    raw_required = target.get("required") if target else None
    if not isinstance(raw_required, list):
        return False
    return nested_key in {str(item) for item in raw_required if isinstance(item, str)}


def _resolve_ref(schema: Mapping[str, object], defs: Mapping[str, object]) -> Mapping[str, object]:
    ref = schema.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
        return {}
    return _mapping(defs.get(ref.removeprefix("#/$defs/")))


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _description(schema: Mapping[str, object]) -> str | None:
    value = schema.get("description")
    return value if isinstance(value, str) and value.strip() else None


def _schema_type(schema: Mapping[str, object]) -> str:
    raw_type = schema.get("type")
    if isinstance(raw_type, str):
        return raw_type
    if isinstance(raw_type, list):
        return "|".join(str(item) for item in raw_type)
    if "$ref" in schema:
        return "ref"
    if "anyOf" in schema:
        return "anyOf"
    if "oneOf" in schema:
        return "oneOf"
    return "unknown"
