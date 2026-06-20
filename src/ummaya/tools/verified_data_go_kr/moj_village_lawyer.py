# SPDX-License-Identifier: Apache-2.0
"""MOJ village lawyer regional status adapter."""

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

_SCAN_PAGE_SIZE = 100
_MAX_FILTER_SCAN_PAGES = 40
_FILTER_FIELD_MAP = {
    "state": "State",
    "city": "City",
    "village": "Village",
}


class MojVillageLawyerInput(BaseModel):
    """Input for MOJ village lawyer regional assignment rows."""

    model_config = ConfigDict(extra="forbid")

    page_no: int = Field(default=1, ge=1, description="Page number.")
    num_of_rows: int = Field(default=20, ge=1, le=100, description="Rows per page.")
    state: str | None = Field(
        default=None,
        min_length=1,
        description="Optional provider State filter, e.g. 부산 or 강원.",
    )
    city: str | None = Field(
        default=None,
        min_length=1,
        description="Optional provider City filter, e.g. 사하구 or 고성군.",
    )
    village: str | None = Field(
        default=None,
        min_length=1,
        description="Optional provider Village filter, e.g. 하단동.",
    )


SPEC = require_spec("moj_village_lawyer_lookup")
INPUT_SCHEMA = MojVillageLawyerInput
TOOL: GovAPITool = build_tool(SPEC, INPUT_SCHEMA)


async def handle(
    input_model: MojVillageLawyerInput,
    *,
    fixture_body: bytes | None = None,
) -> dict[str, object]:
    """Fetch or replay MOJ village lawyer rows."""

    if not _has_region_filter(input_model):
        return await handle_verified_input(input_model, SPEC, fixture_body=fixture_body)

    if fixture_body is not None:
        output = await handle_verified_input(input_model, SPEC, fixture_body=fixture_body)
        return _filter_output(output, input_model)

    filtered_items: list[dict[str, object]] = []
    provider_total_count = 0
    target_rows = input_model.num_of_rows
    first_page = max(input_model.page_no, 1)

    for page_no in range(first_page, first_page + _MAX_FILTER_SCAN_PAGES):
        page_input = input_model.model_copy(
            update={"page_no": page_no, "num_of_rows": _SCAN_PAGE_SIZE}
        )
        page_output = await handle_verified_input(page_input, SPEC)
        provider_total_count = max(
            provider_total_count,
            _int_value(page_output.get("total_count")),
        )
        filtered_items.extend(_filtered_items(page_output, input_model))
        if len(filtered_items) >= target_rows:
            break
        if provider_total_count <= 0:
            break
        total_pages = (provider_total_count + _SCAN_PAGE_SIZE - 1) // _SCAN_PAGE_SIZE
        if page_no >= total_pages:
            break

    return {
        "kind": "collection",
        "items": filtered_items[:target_rows],
        "total_count": min(len(filtered_items), target_rows),
    }


def _has_region_filter(input_model: MojVillageLawyerInput) -> bool:
    return any(_filter_value(input_model, field) for field in _FILTER_FIELD_MAP)


def _filter_output(
    output: dict[str, object],
    input_model: MojVillageLawyerInput,
) -> dict[str, object]:
    filtered_items = _filtered_items(output, input_model)
    return {
        "kind": "collection",
        "items": filtered_items[: input_model.num_of_rows],
        "total_count": min(len(filtered_items), input_model.num_of_rows),
    }


def _filtered_items(
    output: dict[str, object],
    input_model: MojVillageLawyerInput,
) -> list[dict[str, object]]:
    raw_items = output.get("items")
    if not isinstance(raw_items, list):
        return []
    return [
        item
        for item in raw_items
        if isinstance(item, dict) and _record_matches_region_filter(item, input_model)
    ]


def _record_matches_region_filter(
    item: dict[str, object],
    input_model: MojVillageLawyerInput,
) -> bool:
    raw_record = item.get("record")
    if not isinstance(raw_record, dict):
        return False
    record = {str(key): value for key, value in raw_record.items()}
    for input_field, record_field in _FILTER_FIELD_MAP.items():
        expected = _filter_value(input_model, input_field)
        if expected and not _field_matches(record.get(record_field), expected):
            return False
    return True


def _field_matches(actual: object, expected: str) -> bool:
    actual_text = str(actual or "").strip()
    expected_text = expected.strip()
    if not actual_text:
        return False
    return expected_text in actual_text or actual_text in expected_text


def _filter_value(input_model: MojVillageLawyerInput, field: str) -> str:
    value = getattr(input_model, field)
    return value.strip() if isinstance(value, str) else ""


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return 0


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register this adapter."""

    register_module(registry, executor, tool=TOOL, input_schema=INPUT_SCHEMA, handler=handle)
