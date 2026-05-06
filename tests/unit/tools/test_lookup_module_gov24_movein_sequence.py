# SPDX-License-Identifier: Apache-2.0
"""Unit tests for mock_lookup_module_gov24_movein_sequence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from kosmos.primitives.delegation import DelegationContext, DelegationToken
from kosmos.tools.mock.lookup_module_gov24_movein_sequence import (
    MOCK_LOOKUP_MODULE_GOV24_MOVEIN_SEQUENCE_TOOL,
    Gov24MoveInSequenceInput,
    handle,
    register,
)

_VALID_INPUT = Gov24MoveInSequenceInput(
    adm_cd="2638000000",
    address="부산광역시 사하구 다대1동",
)

_TRANSPARENCY_FIELDS = (
    "_mode",
    "_reference_implementation",
    "_actual_endpoint_when_live",
    "_security_wrapping_pattern",
    "_policy_authority",
    "_international_reference",
)


def _make_delegation_context(scope: str) -> DelegationContext:
    token = DelegationToken(
        vp_jwt=(
            "eyJhbGciOiJub25lIiwidHlwIjoidnArand0In0."
            "eyJzdWIiOiJtb2NrIn0.mock-signature-not-cryptographic"
        ),
        delegation_token="del_" + "v" * 24,
        scope=scope,
        issuer_did="did:web:mobileid.go.kr",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        **{"_mode": "mock"},
    )
    return DelegationContext(
        token=token,
        purpose_ko="전입신고 연계절차 조회",
        purpose_en="Gov24 move-in sequence lookup",
    )


@pytest.mark.asyncio
async def test_handle_happy_path_carries_sequence_and_transparency() -> None:
    result = await handle(
        _VALID_INPUT,
        delegation_context=_make_delegation_context("lookup:gov24.movein"),
    )

    assert result["kind"] == "record"
    item = result["item"]
    assert item["workflow_kind"] == "gov24_movein_dependent_sequence"
    assert item["required_sequence"][0]["minwon_type"] == "전입신고"
    assert item["required_sequence"][1]["minwon_type"] == "주소변경"
    update_ids = {row["update_id"] for row in item["dependent_records"]}
    assert {"vehicle_address", "health_insurance", "school_assignment"} <= update_ids
    for field in _TRANSPARENCY_FIELDS:
        assert item.get(field)


@pytest.mark.asyncio
async def test_handle_without_delegation_context_fails_closed() -> None:
    result = await handle(_VALID_INPUT, delegation_context=None)

    assert result["kind"] == "error"
    assert result["reason"] == "auth_required"
    assert "lookup:gov24.movein" in result["message"]


@pytest.mark.asyncio
async def test_handle_with_wrong_scope_fails_closed() -> None:
    result = await handle(
        _VALID_INPUT,
        delegation_context=_make_delegation_context("submit:gov24.minwon"),
    )

    assert result["kind"] == "error"
    assert result["reason"] == "auth_required"
    assert "lookup:gov24.movein" in result["message"]


def test_input_normalizes_korean_requested_updates() -> None:
    inp = Gov24MoveInSequenceInput(
        adm_cd="2638000000",
        requested_updates=["자동차 주소", "건강보험", "학교 관련 주소"],
    )

    assert inp.requested_updates == [
        "vehicle_address",
        "health_insurance",
        "school_assignment",
    ]


def test_registration_adds_tool_to_registry_and_executor() -> None:
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)

    assert "mock_lookup_module_gov24_movein_sequence" in registry._tools
    assert "mock_lookup_module_gov24_movein_sequence" in executor._adapters


@pytest.mark.asyncio
async def test_executor_validation_names_root_location_error() -> None:
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)

    result = await executor.invoke(
        tool_id="mock_lookup_module_gov24_movein_sequence",
        params={},
        request_id="test-request",
        session_identity="test-session",
    )

    assert result.kind == "error"
    assert "__root__" in result.message
    assert "Either adm_cd or address must be provided" in result.message


def test_bm25_discovery_surfaces_movein_sequence() -> None:
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)

    results = registry.search("이사 전입신고 자동차 건강보험 학교 주소 변경")
    tool_ids = [r.tool.id for r in results]
    assert "mock_lookup_module_gov24_movein_sequence" in tool_ids


def test_tool_definition_declares_ganpyeon_delegation_source() -> None:
    assert MOCK_LOOKUP_MODULE_GOV24_MOVEIN_SEQUENCE_TOOL.primitive == "lookup"
    assert MOCK_LOOKUP_MODULE_GOV24_MOVEIN_SEQUENCE_TOOL.adapter_mode == "mock"
    assert (
        MOCK_LOOKUP_MODULE_GOV24_MOVEIN_SEQUENCE_TOOL.delegation_source_tool_id
        == "mock_verify_ganpyeon_injeung"
    )
    assert MOCK_LOOKUP_MODULE_GOV24_MOVEIN_SEQUENCE_TOOL.policy is not None
    assert (
        MOCK_LOOKUP_MODULE_GOV24_MOVEIN_SEQUENCE_TOOL.policy.citizen_facing_gate
        == "login"
    )
