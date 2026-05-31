# SPDX-License-Identifier: Apache-2.0
"""Manifest guards for the verified data.go.kr adapter wave."""

from __future__ import annotations

import json
from pathlib import Path

from ummaya.tools.verified_data_go_kr import VERIFIED_DATA_GO_KR_ADAPTERS

ROOT = Path(__file__).resolve().parents[4]
SCOPED_NEW_30 = ROOT / "docs/api/data-go-kr-candidate-docs/SCOPED-NEW-30-manifest.json"
BLOCKED_DATASET_IDS = frozenset({"15038392", "15058923", "15063444"})

EXPECTED_DATASET_IDS = frozenset(
    {
        "15043459",
        "15073861",
        "15091886",
        "15091910",
        "15098529",
        "15098530",
        "15098533",
        "15098534",
        "15101360",
        "15129394",
        "15134761",
        "15157485",
        "15158680",
        "15158684",
        "15121954",
        "15073554",
        "15001699",
        "15155046",
        "15158794",
        "15096040",
        "15000652",
        "15127779",
        "15075057",
        "15156780",
        "15129471",
        "15158905",
        "15157820",
        "15140950",
        "15149906",
        "15074634",
    }
)

EXPECTED_TOOL_IDS = frozenset(
    {
        "fsc_corporate_finance_summary",
        "airkorea_ctprvn_air_quality",
        "ftc_large_group_status",
        "ftc_public_ym_list",
        "tago_bus_route_search",
        "tago_bus_route_station_search",
        "tago_bus_arrival_search",
        "tago_bus_location_search",
        "tago_bus_station_search",
        "kepco_contract_power_usage",
        "pps_bid_public_info",
        "reb_real_estate_stat_table",
        "bfc_funeral_area_fee",
        "kcue_finance_regional_tuition",
        "kcue_student_regional_foreign",
        "moj_village_lawyer_lookup",
        "mois_facility_safety_info_lookup",
        "hira_medical_institution_detail",
        "mois_emergency_call_box_lookup",
        "djtc_subway_segment_fare_time_check",
        "gyeryong_assistive_device_charging_place_locate",
        "nmc_aed_site_locate",
        "mof_ocean_water_quality_check",
        "mfds_easy_drug_info_lookup",
        "mpm_public_job_lookup",
        "pps_shopping_mall_product_lookup",
        "ksd_financial_term_lookup",
        "mss_sme_support_notice_lookup",
        "ccourt_publication_documents",
        "moj_stay_person_counter",
        "msit_business_announcement_lookup",
    }
)


def test_manifest_contains_only_live_probe_confirmed_candidates() -> None:
    dataset_ids = frozenset(spec.dataset_id for spec in VERIFIED_DATA_GO_KR_ADAPTERS)
    tool_ids = frozenset(spec.tool_id for spec in VERIFIED_DATA_GO_KR_ADAPTERS)

    assert dataset_ids == EXPECTED_DATASET_IDS
    assert tool_ids == EXPECTED_TOOL_IDS


def test_manifest_includes_callable_scoped_candidates_and_excludes_blockers() -> None:
    raw = json.loads(SCOPED_NEW_30.read_text(encoding="utf-8"))
    scoped_ids = {str(entry["id"]) for entry in raw}
    included_ids = {spec.dataset_id for spec in VERIFIED_DATA_GO_KR_ADAPTERS}

    assert (included_ids & scoped_ids) - BLOCKED_DATASET_IDS
    assert not included_ids & BLOCKED_DATASET_IDS


def test_all_verified_candidates_are_find_live_read_only_adapters() -> None:
    for spec in VERIFIED_DATA_GO_KR_ADAPTERS:
        assert spec.primitive == "find", spec.tool_id
        assert spec.adapter_mode == "live", spec.tool_id
        assert spec.citizen_facing_gate == "read-only", spec.tool_id
        assert spec.env_var, spec.tool_id
        assert spec.evidence_path.endswith((".body", ".body.json", ".body.xml")), spec.tool_id


def test_special_transport_contracts_are_manifested() -> None:
    by_tool_id = {spec.tool_id: spec for spec in VERIFIED_DATA_GO_KR_ADAPTERS}

    assert by_tool_id["moj_stay_person_counter"].auth_query_param == "ServiceKey"
    assert by_tool_id["moj_stay_person_counter"].endpoint.startswith("http://")
    assert by_tool_id["moj_village_lawyer_lookup"].endpoint.startswith("http://")
    assert "User-Agent" in by_tool_id["msit_business_announcement_lookup"].request_headers


def test_manifest_evidence_paths_exist_and_stay_inside_candidate_docs() -> None:
    evidence_root = ROOT / "docs/api/data-go-kr-candidate-docs"

    for spec in VERIFIED_DATA_GO_KR_ADAPTERS:
        evidence = ROOT / spec.evidence_path
        assert evidence.exists(), spec.tool_id
        assert evidence.is_relative_to(evidence_root), spec.tool_id
        assert f"/{spec.dataset_id}/" in evidence.as_posix(), spec.tool_id


def test_generated_schema_exists_for_each_verified_adapter() -> None:
    schema_root = ROOT / "docs/api/schemas"

    for spec in VERIFIED_DATA_GO_KR_ADAPTERS:
        assert (schema_root / f"{spec.tool_id}.json").exists(), spec.tool_id
