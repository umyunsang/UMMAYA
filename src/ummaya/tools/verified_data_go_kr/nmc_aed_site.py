# SPDX-License-Identifier: Apache-2.0
"""NMC AED site lookup adapter."""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ummaya.tools.executor import ToolExecutor
from ummaya.tools.models import GovAPITool
from ummaya.tools.registry import ToolRegistry
from ummaya.tools.verified_data_go_kr._factory import (
    build_tool,
    handle_verified_input,
    register_module,
)
from ummaya.tools.verified_data_go_kr._manifest import require_spec


class NmcAedSiteInput(BaseModel):
    """Input for NMC AED management records."""

    model_config = ConfigDict(extra="forbid")

    q0: str = Field(..., min_length=1, description="City/province name.")
    q1: str = Field(..., min_length=1, description="District/county name.")
    page_no: int = Field(default=1, ge=1, description="Page number.")
    num_of_rows: int = Field(default=10, ge=1, le=100, description="Rows per page.")
    origin_lat: float | None = Field(
        default=None,
        ge=-90,
        le=90,
        description=(
            "Optional original query latitude for client-side distance sorting. "
            "Not sent to the upstream NMC AED API."
        ),
    )
    origin_lon: float | None = Field(
        default=None,
        ge=-180,
        le=180,
        description=(
            "Optional original query longitude for client-side distance sorting. "
            "Not sent to the upstream NMC AED API."
        ),
    )

    @model_validator(mode="after")
    def _origin_pair_is_complete(self) -> NmcAedSiteInput:
        if (self.origin_lat is None) ^ (self.origin_lon is None):
            raise ValueError("origin_lat and origin_lon must be supplied together")
        return self


SPEC = require_spec("nmc_aed_site_locate")
INPUT_SCHEMA = NmcAedSiteInput
TOOL: GovAPITool = build_tool(SPEC, INPUT_SCHEMA)


async def handle(
    input_model: NmcAedSiteInput,
    *,
    fixture_body: bytes | None = None,
) -> dict[str, object]:
    """Fetch or replay NMC AED rows."""

    output = await handle_verified_input(input_model, SPEC, fixture_body=fixture_body)
    if input_model.origin_lat is None or input_model.origin_lon is None:
        return output
    _sort_items_by_origin_distance(
        output,
        origin_lat=input_model.origin_lat,
        origin_lon=input_model.origin_lon,
    )
    return output


def _sort_items_by_origin_distance(
    output: dict[str, object],
    *,
    origin_lat: float,
    origin_lon: float,
) -> None:
    items = output.get("items")
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        record = item.get("record")
        if not isinstance(record, dict):
            continue
        lat = _as_float(record.get("wgs84Lat"))
        lon = _as_float(record.get("wgs84Lon"))
        if lat is None or lon is None:
            continue
        distance_km = round(
            _haversine_km(
                lat1=origin_lat,
                lon1=origin_lon,
                lat2=lat,
                lon2=lon,
            ),
            3,
        )
        record["distance"] = distance_km
        record["distance_km"] = distance_km
        record["distance_unit"] = "km"
    items.sort(key=_distance_sort_key)


def _distance_sort_key(item: object) -> tuple[int, float]:
    if not isinstance(item, dict):
        return (1, 0.0)
    record = item.get("record")
    if not isinstance(record, dict):
        return (1, 0.0)
    distance = _as_float(record.get("distance_km"))
    if distance is None:
        return (1, 0.0)
    return (0, distance)


def _as_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str):
        return None
    try:
        return float(value.strip())
    except ValueError:
        return None


def _haversine_km(*, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    return radius_km * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register this adapter."""

    register_module(registry, executor, tool=TOOL, input_schema=INPUT_SCHEMA, handler=handle)
