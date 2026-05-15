# SPDX-License-Identifier: Apache-2.0
"""Manifest guards for the verified data.go.kr adapter wave."""

from __future__ import annotations

import json
from pathlib import Path

from ummaya.tools.verified_data_go_kr import VERIFIED_DATA_GO_KR_ADAPTERS

ROOT = Path(__file__).resolve().parents[4]
SCOPED_NEW_30 = ROOT / "docs/api/data-go-kr-candidate-docs/SCOPED-NEW-30-manifest.json"

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
    }
)

EXPECTED_TOOL_IDS = frozenset(
    {
        "fsc_corporate_finance_summary",
        "airkorea_ctprvn_air_quality",
        "ftc_large_group_status",
        "ftc_public_ym_list",
        "tago_bus_route_search",
        "tago_bus_arrival_search",
        "tago_bus_location_search",
        "tago_bus_station_search",
        "kepco_contract_power_usage",
        "pps_bid_public_info",
        "reb_real_estate_stat_table",
        "bfc_funeral_area_fee",
        "kcue_finance_regional_tuition",
        "kcue_student_regional_foreign",
    }
)


def test_manifest_contains_only_live_probe_confirmed_candidates() -> None:
    dataset_ids = frozenset(spec.dataset_id for spec in VERIFIED_DATA_GO_KR_ADAPTERS)
    tool_ids = frozenset(spec.tool_id for spec in VERIFIED_DATA_GO_KR_ADAPTERS)

    assert dataset_ids == EXPECTED_DATASET_IDS
    assert tool_ids == EXPECTED_TOOL_IDS


def test_manifest_excludes_scoped_new_30_candidates_pending_authorization() -> None:
    raw = json.loads(SCOPED_NEW_30.read_text(encoding="utf-8"))
    pending_ids = {str(entry["id"]) for entry in raw}
    included_ids = {spec.dataset_id for spec in VERIFIED_DATA_GO_KR_ADAPTERS}

    assert not included_ids & pending_ids


def test_all_verified_candidates_are_find_live_read_only_adapters() -> None:
    for spec in VERIFIED_DATA_GO_KR_ADAPTERS:
        assert spec.primitive == "find", spec.tool_id
        assert spec.adapter_mode == "live", spec.tool_id
        assert spec.citizen_facing_gate == "read-only", spec.tool_id
        assert spec.env_var, spec.tool_id
        assert spec.evidence_path.endswith((".body.json", ".body.xml")), spec.tool_id


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
