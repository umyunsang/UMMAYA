# SPDX-License-Identifier: Apache-2.0
"""AirKorea city/province real-time air quality adapter."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ummaya.tools.executor import ToolExecutor
from ummaya.tools.models import GovAPITool
from ummaya.tools.registry import ToolRegistry
from ummaya.tools.verified_data_go_kr._factory import (
    build_tool,
    handle_verified_input,
    register_module,
)
from ummaya.tools.verified_data_go_kr._manifest import require_spec


class AirKoreaAirQualityInput(BaseModel):
    """Input for AirKorea city/province air quality."""

    model_config = ConfigDict(extra="forbid")

    sido_name: str = Field(
        ...,
        min_length=1,
        description="AirKorea short province/city name, e.g. 서울, 부산, 경기.",
    )
    page_no: int = Field(default=1, ge=1, description="Page number.")
    num_of_rows: int = Field(
        default=100,
        ge=1,
        le=100,
        description="Rows per page; 100 captures all city/province stations in normal use.",
    )
    ver: str = Field(default="1.0", description="AirKorea response version.")

    @field_validator("sido_name", mode="before")
    @classmethod
    def normalize_sido_name(cls, value: object) -> object:
        """AirKorea returns rows for short 시도 names, not full 행정명 names."""

        if not isinstance(value, str):
            return value
        return _normalize_airkorea_sido_name(value)


SPEC = require_spec("airkorea_ctprvn_air_quality")
INPUT_SCHEMA = AirKoreaAirQualityInput
TOOL: GovAPITool = build_tool(SPEC, INPUT_SCHEMA)


async def handle(
    input_model: AirKoreaAirQualityInput,
    *,
    fixture_body: bytes | None = None,
) -> dict[str, object]:
    """Fetch or replay AirKorea air quality rows."""

    output = await handle_verified_input(input_model, SPEC, fixture_body=fixture_body)
    return _enrich_air_quality_grades(output)


_AIRKOREA_GRADE_LABELS: dict[str, str] = {
    "1": "좋음",
    "2": "보통",
    "3": "나쁨",
    "4": "매우나쁨",
}

_AIRKOREA_ITEM_NAMES: dict[str, str] = {
    "khai": "통합대기환경지수(CAI)",
    "pm10": "미세먼지(PM10)",
    "pm25": "초미세먼지(PM2.5)",
    "o3": "오존(O3)",
    "no2": "이산화질소(NO2)",
    "co": "일산화탄소(CO)",
    "so2": "아황산가스(SO2)",
}

_AIRKOREA_SIDO_ALIASES: dict[str, str] = {
    "서울특별시": "서울",
    "부산광역시": "부산",
    "대구광역시": "대구",
    "인천광역시": "인천",
    "광주광역시": "광주",
    "대전광역시": "대전",
    "울산광역시": "울산",
    "세종특별자치시": "세종",
    "경기도": "경기",
    "강원특별자치도": "강원",
    "강원도": "강원",
    "충청북도": "충북",
    "충청남도": "충남",
    "전북특별자치도": "전북",
    "전라북도": "전북",
    "전라남도": "전남",
    "경상북도": "경북",
    "경상남도": "경남",
    "제주특별자치도": "제주",
    "제주도": "제주",
}


def _normalize_airkorea_sido_name(value: str) -> str:
    normalized = value.strip()
    return _AIRKOREA_SIDO_ALIASES.get(normalized, normalized)


def _enrich_air_quality_grades(output: dict[str, object]) -> dict[str, object]:
    items = output.get("items")
    if not isinstance(items, list):
        return output
    enriched_items: list[dict[str, object]] = []
    changed = False
    for item in items:
        if not isinstance(item, dict):
            continue
        record_raw = item.get("record")
        if not isinstance(record_raw, dict):
            enriched_items.append(item)
            continue
        record = dict(record_raw)
        for prefix, name_ko in _AIRKOREA_ITEM_NAMES.items():
            name_key = f"{prefix}NameKo"
            if name_key not in record:
                record[name_key] = name_ko
                changed = True
            grade_value = record.get(f"{prefix}Grade")
            label = _airkorea_grade_label(grade_value)
            if label is not None:
                record[f"{prefix}GradeLabelKo"] = label
                changed = True
        next_item = dict(item)
        next_item["record"] = record
        enriched_items.append(next_item)
    if not changed:
        return output
    enriched_output = dict(output)
    enriched_output["items"] = enriched_items
    return enriched_output


def _airkorea_grade_label(value: object) -> str | None:
    if value is None:
        return None
    return _AIRKOREA_GRADE_LABELS.get(str(value).strip())


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register this adapter."""

    register_module(registry, executor, tool=TOOL, input_schema=INPUT_SCHEMA, handler=handle)
