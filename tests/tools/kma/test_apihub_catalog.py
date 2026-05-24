# SPDX-License-Identifier: Apache-2.0
"""Tests for the KMA APIHub structured operation catalog."""

from __future__ import annotations

from collections import Counter

from ummaya.tools.kma.apihub_catalog import (
    KMA_APIHUB_STRUCTURED_OPERATIONS,
    get_operation_by_id,
    get_operation_by_tool_id,
    iter_structured_operations,
)


def test_catalog_contains_all_structured_typ02_operations() -> None:
    assert len(iter_structured_operations(include_retired=True)) == 85
    assert len(iter_structured_operations()) == 78


def test_catalog_tool_ids_are_unique_and_prefixed() -> None:
    tool_ids = [operation.tool_id for operation in KMA_APIHUB_STRUCTURED_OPERATIONS]

    assert len(tool_ids) == len(set(tool_ids))
    assert all(tool_id.startswith("kma_apihub_") for tool_id in tool_ids)


def test_catalog_category_counts_match_captured_apihub_evidence() -> None:
    counts = Counter(operation.category_seq for operation in KMA_APIHUB_STRUCTURED_OPERATIONS)

    assert counts == {
        2: 12,
        3: 14,
        4: 6,
        5: 2,
        6: 20,
        7: 2,
        8: 1,
        9: 8,
        10: 7,
        12: 3,
        14: 10,
    }


def test_approved_operations_match_current_mypage_evidence() -> None:
    approved = {
        operation.operation_id
        for operation in KMA_APIHUB_STRUCTURED_OPERATIONS
        if operation.approval_state == "approved"
    }

    assert len(approved) == 85
    assert approved == {operation.operation_id for operation in KMA_APIHUB_STRUCTURED_OPERATIONS}


def test_disabled_operations_are_kept_in_catalog_but_not_active() -> None:
    disabled = {
        operation.operation_id
        for operation in KMA_APIHUB_STRUCTURED_OPERATIONS
        if operation.availability != "active"
    }

    assert disabled == {
        "GtsInfoService/getBuoy",
        "GtsInfoService/getSynop",
        "GtsInfoService/getTemp",
        "NwpModelInfoService/getLdapsUnisAll",
        "NwpModelInfoService/getLdapsUnisArea",
        "NwpModelInfoService/getRdapsUnisAll",
        "NwpModelInfoService/getRdapsUnisArea",
    }
    assert disabled.isdisjoint(operation.operation_id for operation in iter_structured_operations())

    assert get_operation_by_id("GtsInfoService/getSynop").availability == ("upstream_unavailable")
    assert get_operation_by_id("NwpModelInfoService/getLdapsUnisAll").availability == ("retired")


def test_catalog_lookup_helpers_return_stable_operations() -> None:
    operation = get_operation_by_id("AmmIwxxmService/getMetar")

    assert operation.tool_id == "kma_apihub_amm_iwxxm_service_get_metar"
    assert get_operation_by_tool_id(operation.tool_id) == operation
    assert [param.name for param in operation.request_params] == [
        "pageNo",
        "numOfRows",
        "dataType",
        "icao",
        "authKey",
    ]
    assert [param.field_name for param in operation.non_credential_params] == [
        "page_no",
        "num_of_rows",
        "data_type",
        "icao",
    ]
