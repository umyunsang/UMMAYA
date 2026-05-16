# SPDX-License-Identifier: Apache-2.0
"""Registration tests for verified data.go.kr adapters."""

from __future__ import annotations

from ummaya.tools.executor import ToolExecutor
from ummaya.tools.registry import ToolRegistry
from ummaya.tools.verified_data_go_kr import (
    VERIFIED_DATA_GO_KR_ADAPTERS,
)
from ummaya.tools.verified_data_go_kr import (
    register as register_verified_data_go_kr,
)

NEW_TOOL_IDS = frozenset(
    {
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


def test_register_verified_data_go_kr_tools_adds_all_adapters() -> None:
    registry = ToolRegistry()
    executor = ToolExecutor(registry)

    register_verified_data_go_kr(registry, executor)

    expected_ids = {spec.tool_id for spec in VERIFIED_DATA_GO_KR_ADAPTERS}
    assert set(registry._tools) == expected_ids
    assert set(executor._adapters) == expected_ids
    assert expected_ids >= NEW_TOOL_IDS


def test_registered_tools_are_find_live_read_only_with_policy_citations() -> None:
    registry = ToolRegistry()
    executor = ToolExecutor(registry)

    register_verified_data_go_kr(registry, executor)

    for spec in VERIFIED_DATA_GO_KR_ADAPTERS:
        tool = registry.find(spec.tool_id)
        assert tool.primitive == "find"
        assert tool.adapter_mode == "live"
        assert tool.policy is not None
        assert tool.policy.citizen_facing_gate == "read-only"
        assert tool.policy.real_classification_url == spec.policy_url
        assert spec.dataset_id in tool.search_hint
