# SPDX-License-Identifier: Apache-2.0
"""PPS bid public information adapter."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

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

_PPS_DATETIME_FORMAT = "%Y%m%d%H%M"
_PPS_MAX_SEARCH_WINDOW = timedelta(days=31)


class PpsBidPublicInfoInput(BaseModel):
    """Input for PPS bid public information."""

    model_config = ConfigDict(extra="forbid")

    inqry_div: Literal["1", "2"] = Field(
        default="1",
        description=(
            "Official PPS inqryDiv. Use '1' for bid notice publication datetime "
            "(pblancDate) searches such as 'this week posted notices'; use '2' "
            "for bid opening datetime (opengDt) searches."
        ),
    )
    inqry_bgn_dt: str = Field(
        ...,
        pattern=r"^\d{12}$",
        description=(
            "Official PPS inqryBgnDt search start datetime in YYYYMMDDHHMM. "
            "Required when inqry_div is '1' or '2'. Keep each PPS request window "
            "within 31 days."
        ),
    )
    inqry_end_dt: str = Field(
        ...,
        pattern=r"^\d{12}$",
        description=(
            "Official PPS inqryEndDt search end datetime in YYYYMMDDHHMM. "
            "Required when inqry_div is '1' or '2'. Keep each PPS request window "
            "within 31 days."
        ),
    )
    bid_ntce_nm: str | None = Field(
        default=None,
        max_length=1000,
        description=(
            "Official PPS bidNtceNm notice-name keyword. Partial names are allowed; "
            "use this for citizen keywords such as 전기공사."
        ),
    )
    ntce_instt_nm: str | None = Field(
        default=None,
        max_length=400,
        description=(
            "Official PPS ntceInsttNm public notice agency name filter. "
            "Partial agency names are allowed."
        ),
    )
    dminstt_nm: str | None = Field(
        default=None,
        max_length=400,
        description=(
            "Official PPS dminsttNm demand agency name filter. Partial agency names are allowed."
        ),
    )
    region_name: str | None = Field(
        default=None,
        max_length=100,
        description=(
            "UMMAYA client-side region relevance filter copied from citizen wording. "
            "This is not sent to PPS upstream; after the official response, UMMAYA "
            "keeps rows whose documented region/agency fields such as cnstrtsiteRgnNm, "
            "prtcptLmtRgnNm, ntceInsttNm, or dminsttNm match this value."
        ),
    )
    prtcpt_lmt_rgn_nm: str | None = Field(
        default=None,
        max_length=100,
        description=(
            "Official PPS prtcptLmtRgnNm participation-limit region name. "
            "For Busan-region notices use 부산광역시 when the citizen says 부산시."
        ),
    )
    indstryty_nm: str | None = Field(
        default=None,
        max_length=100,
        description=(
            "Official PPS indstrytyNm industry/license name. Use 전기공사업 "
            "for electrical-construction qualification searches when requested."
        ),
    )
    page_no: int = Field(default=1, ge=1, description="Page number.")
    num_of_rows: int = Field(default=10, ge=1, le=100, description="Rows per page.")

    @model_validator(mode="after")
    def validate_official_search_window(self) -> PpsBidPublicInfoInput:
        """Keep PPS searches inside the observed upstream contract window."""

        try:
            start = datetime.strptime(self.inqry_bgn_dt, _PPS_DATETIME_FORMAT)
            end = datetime.strptime(self.inqry_end_dt, _PPS_DATETIME_FORMAT)
        except ValueError as exc:
            raise ValueError(
                "PPS inqry_bgn_dt and inqry_end_dt must be valid YYYYMMDDHHMM datetimes."
            ) from exc
        if end < start:
            raise ValueError("PPS inqry_end_dt must be greater than or equal to inqry_bgn_dt.")
        if end - start > _PPS_MAX_SEARCH_WINDOW:
            raise ValueError(
                "PPS Nara Market bid searches must be split into 31-day-or-smaller "
                "inqry_bgn_dt/inqry_end_dt windows before calling the upstream API."
            )
        return self


SPEC = require_spec("pps_bid_public_info")
INPUT_SCHEMA = PpsBidPublicInfoInput
TOOL: GovAPITool = build_tool(SPEC, INPUT_SCHEMA)


async def handle(
    input_model: PpsBidPublicInfoInput,
    *,
    fixture_body: bytes | None = None,
) -> dict[str, object]:
    """Fetch or replay PPS bid public information rows."""

    output = await handle_verified_input(input_model, SPEC, fixture_body=fixture_body)
    return _filter_output_by_region_name(output, input_model.region_name)


_REGION_RELEVANCE_FIELDS: tuple[str, ...] = (
    "cnstrtsiteRgnNm",
    "prtcptLmtRgnNm",
    "ntceInsttNm",
    "dminsttNm",
    "jntcontrctDutyRgnNm1",
    "jntcontrctDutyRgnNm2",
    "jntcontrctDutyRgnNm3",
)


def _filter_output_by_region_name(
    output: dict[str, object],
    region_name: str | None,
) -> dict[str, object]:
    """Filter PPS rows by documented region-bearing response fields."""

    terms = _region_terms(region_name)
    if not terms:
        return output

    raw_items = output.get("items")
    if not isinstance(raw_items, list):
        return output

    filtered: list[dict[str, object]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        if _item_matches_region(raw_item, terms):
            filtered.append(raw_item)

    next_output = dict(output)
    next_output["items"] = filtered
    next_output["total_count"] = len(filtered)
    raw_meta = output.get("meta")
    meta = dict(raw_meta) if isinstance(raw_meta, dict) else {}
    meta["upstream_total_count"] = output.get("total_count")
    meta["client_filter"] = {
        "field": "region_name",
        "value": region_name,
        "matched_count": len(filtered),
    }
    next_output["meta"] = meta
    return next_output


def _region_terms(region_name: str | None) -> tuple[str, ...]:
    if region_name is None:
        return ()
    normalized = " ".join(region_name.split())
    if not normalized:
        return ()
    terms = [normalized]
    for suffix in ("특별자치시", "특별자치도", "특별시", "광역시", "도"):
        if normalized.endswith(suffix):
            short = normalized[: -len(suffix)]
            if short:
                terms.append(short)
            break
    return tuple(dict.fromkeys(terms))


def _item_matches_region(item: dict[str, object], terms: tuple[str, ...]) -> bool:
    raw_record = item.get("record")
    record = raw_record if isinstance(raw_record, dict) else item
    for field_name in _REGION_RELEVANCE_FIELDS:
        value = record.get(field_name)
        if not isinstance(value, str):
            continue
        compact_value = value.replace(" ", "")
        for term in terms:
            if term in value or term.replace(" ", "") in compact_value:
                return True
    return False


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register this adapter."""

    register_module(registry, executor, tool=TOOL, input_schema=INPUT_SCHEMA, handler=handle)
