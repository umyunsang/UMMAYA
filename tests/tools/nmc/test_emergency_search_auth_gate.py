# SPDX-License-Identifier: Apache-2.0
"""Read-only gate tests for nmc_emergency_search.

The coordinate-based NMC endpoint used by this adapter returns public emergency
medical institution location metadata. It uses a KOSMOS service credential and
must not require a citizen session identity or open a permission modal.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import Mock, patch

import pytest
import respx

from kosmos.tools.executor import ToolExecutor
from kosmos.tools.lookup import lookup
from kosmos.tools.models import LookupCollection, LookupError, LookupFetchInput  # noqa: A004
from kosmos.tools.nmc.emergency_search import NMC_EMERGENCY_SEARCH_TOOL, register
from kosmos.tools.registry import ToolRegistry


@pytest.fixture()
def nmc_reg_exec() -> tuple[ToolRegistry, ToolExecutor]:
    """Function-scope registry + executor pair for isolation tests."""
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)
    return registry, executor


def _location_payload() -> dict[str, object]:
    """Minimal data.go.kr B552657 location payload with no hvidate field."""
    return {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
            "body": {
                "items": {
                    "item": [
                        {
                            "dutyName": "테스트응급의료기관",
                            "dutyAddr": "부산광역시 사하구 다대로 1",
                            "distance": 0.42,
                            "hpid": "A0000001",
                            "latitude": 35.059,
                            "longitude": 128.971,
                            "dutyTel1": "051-000-0000",
                            "dutyDivName": "종합병원",
                            "startTime": "0830",
                            "endTime": 1700,
                        }
                    ]
                },
                "totalCount": 1,
            },
        }
    }


class TestNmcReadOnlyGate:
    """Verify that NMC fetches work without citizen authentication."""

    def test_policy_is_read_only(self) -> None:
        """The adapter policy must not force the lookup permission modal."""
        assert NMC_EMERGENCY_SEARCH_TOOL.policy is not None
        assert NMC_EMERGENCY_SEARCH_TOOL.policy.citizen_facing_gate == "read-only"

    @pytest.mark.asyncio
    @respx.mock
    @patch("kosmos.settings.settings")
    async def test_fetch_without_session_identity_calls_public_endpoint(
        self,
        mock_settings: Mock,
        nmc_reg_exec: tuple[ToolRegistry, ToolExecutor],
    ) -> None:
        """Unauthenticated lookup(fetch) reaches upstream and returns a collection."""
        mock_settings.data_go_kr_api_key = "test-key"
        mock_settings.nmc_freshness_minutes = 30
        _, executor = nmc_reg_exec

        route = respx.get(url__regex=r".*apis\.data\.go\.kr.*").respond(
            200,
            json=_location_payload(),
        )

        result = await lookup(
            LookupFetchInput(
                mode="fetch",
                tool_id="nmc_emergency_search",
                params={"lat": 35.059, "lon": 128.971, "limit": 5},
            ),
            executor=executor,
        )

        assert isinstance(result, LookupCollection)
        assert route.call_count == 1
        assert result.kind == "collection"
        assert result.total_count == 1
        assert result.meta.freshness_status == "not_applicable"
        assert result.items[0]["er_24h_operating"] is True

    @pytest.mark.asyncio
    @respx.mock
    @patch("kosmos.settings.settings")
    async def test_missing_service_key_is_upstream_unavailable_not_auth_required(
        self,
        mock_settings: Mock,
        nmc_reg_exec: tuple[ToolRegistry, ToolExecutor],
    ) -> None:
        """Missing service API key is an ops/config error, not a citizen auth gate."""
        mock_settings.data_go_kr_api_key = ""
        mock_settings.nmc_freshness_minutes = 30
        _, executor = nmc_reg_exec

        result = await lookup(
            LookupFetchInput(
                mode="fetch",
                tool_id="nmc_emergency_search",
                params={"lat": 35.059, "lon": 128.971, "limit": 5},
            ),
            executor=executor,
        )

        error = cast(LookupError, result)
        assert isinstance(error, LookupError)
        assert error.reason == "upstream_unavailable"
        assert error.reason != "auth_required"
        assert respx.calls.call_count == 0
