# SPDX-License-Identifier: Apache-2.0
"""Model-facing metadata helpers for the UMMAYA tool system.

This module owns adapter metadata shaping that is shared by runtime tool
registration and IPC manifest export. IPC emitters may serialize this metadata,
but the tool system owns the official query-name mapping and schema guidance.
"""

from __future__ import annotations

from ummaya.tools.verified_data_go_kr._models import VerifiedAdapterSpec

_COMMON_FIELD_DESCRIPTIONS: dict[str, str] = {
    "page_no": (
        "1-based result page number for upstream pagination; keep 1 unless the user "
        "explicitly asks for a later page."
    ),
    "num_of_rows": (
        "Maximum number of provider rows to request per page; keep the default unless "
        "the user asks for a broader list."
    ),
    "current_page": (
        "1-based current page number for provider pagination; use 1 for the initial "
        "lookup and increase only for follow-up paging."
    ),
    "per_page": (
        "Maximum provider rows to return for each page; keep the default for ordinary "
        "citizen-facing summaries."
    ),
    "p_index": "1-based public-data page index used by the upstream statistics API.",
    "p_size": "Maximum number of public-data statistics rows to request for one page.",
    "data_type": (
        "Response serialization format requested from the upstream API; use JSON unless "
        "that specific provider operation documents XML only."
    ),
    "return_type": (
        "Response serialization format requested from the upstream provider; use json "
        "unless the endpoint contract says otherwise."
    ),
    "result_type": (
        "Response serialization format requested from the upstream provider; use json "
        "unless the endpoint contract says otherwise."
    ),
    "city_code": (
        "Official TAGO cityCode identifying the municipality for bus route, arrival, "
        "location, or station queries. Use the provider's getCtyCodeList contract; "
        "common metropolitan examples from the TAGO city-code list include "
        "Busan=21, Daegu=22, Incheon=23, Gwangju=24, Daejeon=25, and Ulsan=26."
    ),
    "route_no": "Bus route number visible to citizens, mapped to the provider routeNo filter.",
    "route_id": "Official provider routeId returned by a prior route lookup.",
    "node_id": "Official provider nodeId for a bus stop, usually returned by station lookup.",
    "node_nm": "Bus stop name fragment used by the TAGO station-search provider filter.",
    "node_no": "Bus stop number used by the TAGO station-search provider filter.",
    "sido_name": "Korean province or metropolitan-city name for AirKorea measurements.",
    "q0": "Korean province or metropolitan-city name used by the public-data search API.",
    "q1": "Korean district, county, or city name used by the public-data search API.",
    "year": "Four-digit target year for the provider statistics or utility dataset.",
    "month": "Two-digit or numeric target month for the provider statistics or utility dataset.",
    "search_ym": "Target search year-month in the provider-documented YYYYMM format.",
    "biz_year": "Four-digit business year used by the corporate finance public-data endpoint.",
    "presentn_year": (
        "Disclosure year or year-month value used by the Fair Trade Commission endpoint."
    ),
    "job_se_code": "Fair Trade Commission job-section code from the public-data contract.",
    "schl_div_cd": "University school-division code from the KCUE public-data contract.",
    "inqry_div": (
        "Procurement inquiry division code used by the PPS endpoint. For PPS bid "
        "search-condition operations, use 1 for notice-publication datetime and 2 "
        "for bid-opening datetime."
    ),
    "bid_ntce_no": "Bid notice number used by PPS detail-style procurement endpoints.",
    "inqry_bgn_dt": "PPS search start datetime in official YYYYMMDDHHMM format.",
    "inqry_end_dt": "PPS search end datetime in official YYYYMMDDHHMM format.",
    "bid_ntce_nm": "PPS bid notice-name keyword; partial Korean notice names are allowed.",
    "ntce_instt_nm": "PPS public notice agency-name filter; partial agency names are allowed.",
    "dminstt_nm": "PPS demand agency-name filter; partial agency names are allowed.",
    "prtcpt_lmt_rgn_nm": "PPS participation-limit region-name filter, such as 부산광역시.",
    "indstryty_nm": "PPS industry or license-name filter, such as 전기공사업.",
    "prdct_clsfc_no_nm": (
        "Product classification number or name search term for the PPS shopping endpoint."
    ),
    "indoor_outdoor": "Indoor or outdoor charger-location filter from the provider contract.",
    "station_code": "Marine observation station code from the MOF ocean-water-quality contract.",
    "term": "Financial dictionary term to search in the KSD public-data endpoint.",
    "item_name": "Drug product name to search in the MFDS public-data endpoint.",
    "road_address": "Road-name address fragment used to search emergency call-box locations.",
    "fclts_nm": "Facility name fragment used to search MOIS facility-safety information.",
    "pblanc_ty": "Public job notice-type code from the MPM provider contract.",
    "instt_se": "Institution classification code from the MPM provider contract.",
    "sort_order": "Sort direction requested from the public-job provider contract.",
    "hashtags": "Hashtag or keyword filter for SME and startup support notices.",
    "title": "Publication title search term used by the constitutional-court endpoint.",
    "endstnno": "Destination station number used by the subway segment fare/time endpoint.",
    "strstnno": "Origin station number used by the subway segment fare/time endpoint.",
    "metro_cd": "Metropolitan area code from the KEPCO power-usage provider contract.",
    "city_cd": "City or county code from the KEPCO power-usage provider contract.",
    "cntr_cd": "Contract-type code from the KEPCO power-usage provider contract.",
}


def build_verified_llm_description(spec: VerifiedAdapterSpec) -> str:
    """Build the model-facing description for one verified public-data adapter."""

    query_mapping = ", ".join(
        f"{field_name}->{query_name}"
        for field_name, query_name in sorted(spec.query_param_map.items())
    )
    static_params = ", ".join(
        f"{name}={value}" for name, value in sorted(spec.static_query_params.items())
    )
    static_clause = (
        f" Runtime also sends fixed provider parameters: {static_params}." if static_params else ""
    )
    examples = "; ".join(spec.trigger_examples)
    example_clause = f" Example request: {examples}." if examples else ""

    return (
        f"{spec.name_ko} live public-data adapter. {spec.llm_description} "
        f"Use this tool only when the user needs the official dataset {spec.dataset_id} "
        f"from {spec.ministry}. The UMMAYA runtime supplies {spec.auth_query_param} "
        f"from {spec.env_var}; never ask the user for that credential and never place it "
        "inside params. Fill only the documented input_schema_json fields. "
        f"Input fields map to upstream query parameters as: {query_mapping}.{static_clause} "
        f"The upstream endpoint returns {spec.response_format.upper()} and the adapter "
        "normalizes rows into a collection envelope while preserving provider field names. "
        f"Policy and contract source: {spec.policy_url}. Probe evidence: {spec.evidence_path}."
        f"{example_clause}"
    )


def enrich_input_schema_json(
    tool_id: str,
    schema: dict[str, object],
) -> dict[str, object]:
    """Add official query names and field guidance to manifest input schemas."""

    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return schema

    query_param_map = _verified_query_param_map(tool_id)
    for field_name, property_schema in properties.items():
        if not isinstance(field_name, str) or not isinstance(property_schema, dict):
            continue
        description = str(property_schema.get("description") or "").strip()
        additions: list[str] = []

        official_param = query_param_map.get(field_name)
        if official_param and official_param not in description:
            additions.append(f"Official upstream query parameter name: {official_param}.")

        common_description = _COMMON_FIELD_DESCRIPTIONS.get(field_name)
        if common_description and (len(description) < 24 or common_description not in description):
            additions.append(common_description)

        if len(description) < 24 and not additions:
            additions.append(
                f"Adapter parameter '{field_name}' for {tool_id}; fill it only from "
                "the user request, official codes, or prior tool results."
            )

        if additions:
            property_schema["description"] = " ".join([description, *additions]).strip()

    return schema


def _verified_query_param_map(tool_id: str) -> dict[str, str]:
    """Return public-data official query names for verified adapters."""

    try:
        from ummaya.tools.verified_data_go_kr._manifest import require_spec  # noqa: PLC0415
    except ImportError:
        return {}

    try:
        spec = require_spec(tool_id)
    except KeyError:
        return {}
    return dict(spec.query_param_map)
