# SPDX-License-Identifier: Apache-2.0
"""Tests for hira_hospital_search adapter — T051.

Covers:
  - Happy path: fixture replay via respx mock → LookupCollection with items.
  - Error path: upstream 500 HTTP status → LookupError(reason="upstream_unavailable").
  - Provider error: upstream returns resultCode=99 → RuntimeError → LookupError.
  - Input validation: xPos="" (empty / zero-length string via fetch params) →
      LookupError(reason="invalid_params") via the executor's validation gate.
  - lookup(mode="fetch") integration via a test-local registry + executor pair.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ummaya.tools.executor import ToolExecutor
from ummaya.tools.hira.hospital_search import (
    HIRA_HOSPITAL_SEARCH_TOOL,
    HiraHospitalSearchInput,
    handle,
    register,
)
from ummaya.tools.lookup import lookup
from ummaya.tools.models import LookupCollection, LookupError, LookupFetchInput  # noqa: A004
from ummaya.tools.registry import ToolRegistry

_FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "hira"


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES_DIR / name).read_text())


def _make_mock_client(
    fixture_data: dict,
    *,
    status_code: int = 200,
) -> httpx.AsyncClient:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = status_code
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = fixture_data
    if status_code >= 400:
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=mock_response,
        )
    else:
        mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response
    return mock_client


@pytest.fixture
def hira_registry_and_executor():
    """Test-local registry + executor with only hira_hospital_search registered."""
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)
    return registry, executor


# ---------------------------------------------------------------------------
# Happy path — fixture replay returns LookupCollection
# ---------------------------------------------------------------------------


class TestHiraHospitalSearchHappy:
    """Happy path: fixture-backed fetch returns LookupCollection."""

    async def test_handle_returns_collection_dict(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """handle() with happy fixture returns a collection-shaped dict."""
        monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "test-key-hira")
        fixture = _load_fixture("hospital_search_happy.json")
        mock_client = _make_mock_client(fixture)

        inp = HiraHospitalSearchInput(xPos=127.028, yPos=37.498, radius=2000)
        result = await handle(inp, client=mock_client)

        assert result["kind"] == "collection"
        assert result["total_count"] == 3
        assert len(result["items"]) == 3

    async def test_handle_items_have_expected_fields(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Items from the happy fixture contain yadmNm, addr, telno, clCd, clCdNm, ykiho."""
        monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "test-key-hira")
        fixture = _load_fixture("hospital_search_happy.json")
        mock_client = _make_mock_client(fixture)

        inp = HiraHospitalSearchInput(xPos=127.028, yPos=37.498, radius=2000)
        result = await handle(inp, client=mock_client)

        for item in result["items"]:
            assert "yadmNm" in item
            assert "addr" in item
            assert "ykiho" in item

    async def test_lookup_fetch_returns_lookup_collection(
        self,
        hira_registry_and_executor,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """lookup(mode='fetch', tool_id='hira_hospital_search') → LookupCollection."""
        registry, executor = hira_registry_and_executor
        fixture = _load_fixture("hospital_search_happy.json")
        mock_client = _make_mock_client(fixture)

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setenv("UMMAYA_DATA_GO_KR_API_KEY", "test-key-hira")
            inp = LookupFetchInput(
                mode="fetch",
                tool_id="hira_hospital_search",
                params={"xPos": 127.028, "yPos": 37.498, "radius": 2000},
            )
            # V6: hira_hospital_search now requires auth_level=AAL1 + requires_auth=True.
            # Provide a test session identity so the executor auth gate passes.
            result = await lookup(inp, executor=executor, session_identity="test-session")

        assert isinstance(result, LookupCollection), f"Expected LookupCollection, got: {result}"
        assert result.kind == "collection"
        assert len(result.items) == 3
        assert result.total_count == 3
        assert result.meta.source == "hira_hospital_search"

    async def test_lookup_fetch_items_populated(
        self,
        hira_registry_and_executor,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Items from lookup fetch have yadmNm and ykiho fields."""
        registry, executor = hira_registry_and_executor
        fixture = _load_fixture("hospital_search_happy.json")
        mock_client = _make_mock_client(fixture)

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setenv("UMMAYA_DATA_GO_KR_API_KEY", "test-key-hira")
            inp = LookupFetchInput(
                mode="fetch",
                tool_id="hira_hospital_search",
                params={"xPos": 127.028, "yPos": 37.498, "radius": 2000},
            )
            # V6: requires_auth=True; provide session identity to pass auth gate.
            result = await lookup(inp, executor=executor, session_identity="test-session")

        assert isinstance(result, LookupCollection)
        for item in result.items:
            assert "yadmNm" in item
            assert "ykiho" in item


# ---------------------------------------------------------------------------
# Error path — upstream 500 → LookupError(reason="upstream_unavailable")
# ---------------------------------------------------------------------------


class TestHiraHospitalSearchErrorPath:
    """Error paths: HTTP 500 and provider resultCode errors."""

    async def test_upstream_500_returns_lookup_error(
        self,
        hira_registry_and_executor,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """HTTP 500 from HIRA → LookupError(reason='upstream_unavailable', retryable=True)."""
        registry, executor = hira_registry_and_executor
        mock_client = _make_mock_client({}, status_code=500)

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setenv("UMMAYA_DATA_GO_KR_API_KEY", "test-key-hira")
            inp = LookupFetchInput(
                mode="fetch",
                tool_id="hira_hospital_search",
                params={"xPos": 127.028, "yPos": 37.498, "radius": 2000},
            )
            # V6: requires_auth=True; provide session identity to pass auth gate.
            result = await lookup(inp, executor=executor, session_identity="test-session")

        assert isinstance(result, LookupError), f"Expected LookupError, got: {result}"
        assert result.reason == "upstream_unavailable"
        assert result.retryable is True

    async def test_provider_error_resultcode_99_returns_lookup_error(
        self,
        hira_registry_and_executor,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """HIRA resultCode=99 (SYSTEM_ERROR) → LookupError(reason='upstream_unavailable')."""
        registry, executor = hira_registry_and_executor
        fixture = _load_fixture("hospital_search_error_provider_error.json")
        mock_client = _make_mock_client(fixture)

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setenv("UMMAYA_DATA_GO_KR_API_KEY", "test-key-hira")
            inp = LookupFetchInput(
                mode="fetch",
                tool_id="hira_hospital_search",
                params={"xPos": 127.028, "yPos": 37.498, "radius": 2000},
            )
            # V6: requires_auth=True; provide session identity to pass auth gate.
            result = await lookup(inp, executor=executor, session_identity="test-session")

        assert isinstance(result, LookupError)
        assert result.reason == "upstream_unavailable"


# ---------------------------------------------------------------------------
# Input validation — invalid params → LookupError(reason="invalid_params")
# ---------------------------------------------------------------------------


class TestHiraHospitalSearchInputValidation:
    """Input validation errors produce LookupError(reason='invalid_params')."""

    async def test_radius_exceeds_max_returns_invalid_params(
        self,
        hira_registry_and_executor,
    ) -> None:
        """radius > 10000 → LookupError(reason='invalid_params')."""
        registry, executor = hira_registry_and_executor
        inp = LookupFetchInput(
            mode="fetch",
            tool_id="hira_hospital_search",
            params={"xPos": 127.028, "yPos": 37.498, "radius": 99999},
        )
        # V6: requires_auth=True; provide session identity so auth gate passes,
        # then the input validation gate runs and returns invalid_params.
        result = await lookup(inp, executor=executor, session_identity="test-session")

        assert isinstance(result, LookupError)
        assert result.reason == "invalid_params"

    async def test_xpos_out_of_korea_range_returns_invalid_params(
        self,
        hira_registry_and_executor,
    ) -> None:
        """xPos outside Korean longitude range (124–132) → LookupError(reason='invalid_params')."""
        registry, executor = hira_registry_and_executor
        inp = LookupFetchInput(
            mode="fetch",
            tool_id="hira_hospital_search",
            params={"xPos": 0.0, "yPos": 37.498, "radius": 2000},
        )
        # V6: requires_auth=True; provide session identity so auth gate passes.
        result = await lookup(inp, executor=executor, session_identity="test-session")

        assert isinstance(result, LookupError)
        assert result.reason == "invalid_params"

    async def test_missing_required_xpos_returns_invalid_params(
        self,
        hira_registry_and_executor,
    ) -> None:
        """Missing required xPos parameter → LookupError(reason='invalid_params')."""
        registry, executor = hira_registry_and_executor
        inp = LookupFetchInput(
            mode="fetch",
            tool_id="hira_hospital_search",
            params={"yPos": 37.498, "radius": 2000},  # xPos omitted
        )
        # V6: requires_auth=True; provide session identity so auth gate passes.
        result = await lookup(inp, executor=executor, session_identity="test-session")

        assert isinstance(result, LookupError)
        assert result.reason == "invalid_params"

    async def test_whole_degree_coordinate_pair_returns_invalid_params(
        self,
        hira_registry_and_executor,
    ) -> None:
        """Rounded xPos/yPos pair is rejected before upstream HIRA call."""
        registry, executor = hira_registry_and_executor
        inp = LookupFetchInput(
            mode="fetch",
            tool_id="hira_hospital_search",
            params={"xPos": 128, "yPos": 35, "radius": 2000},
        )

        result = await lookup(inp, executor=executor, session_identity="test-session")

        assert isinstance(result, LookupError)
        assert result.reason == "invalid_params"
        assert "whole degrees" in result.message


# ---------------------------------------------------------------------------
# Tool definition assertions
# ---------------------------------------------------------------------------


class TestHiraHospitalSearchToolDefinition:
    """HIRA_HOSPITAL_SEARCH_TOOL GovAPITool field assertions."""

    def test_tool_id(self) -> None:
        assert HIRA_HOSPITAL_SEARCH_TOOL.id == "hira_hospital_search"

    # test_requires_auth_true / test_is_personal_data_false removed in Epic δ #2295
    # — requires_auth / is_personal_data deleted from GovAPITool (Constitution § II).

    def test_is_concurrency_safe_true(self) -> None:
        assert HIRA_HOSPITAL_SEARCH_TOOL.is_concurrency_safe is True

    def test_cache_ttl_zero(self) -> None:
        assert HIRA_HOSPITAL_SEARCH_TOOL.cache_ttl_seconds == 0

    def test_input_schema(self) -> None:
        assert HIRA_HOSPITAL_SEARCH_TOOL.input_schema is HiraHospitalSearchInput

    def test_search_hint_bilingual(self) -> None:
        hint = HIRA_HOSPITAL_SEARCH_TOOL.search_hint
        # Must contain both Korean and English terms (FR-021, bilingual requirement)
        assert "병원" in hint
        assert "hospital" in hint.lower()


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


class TestHiraHospitalSearchRegister:
    """register() wires tool into registry and executor."""

    def test_register(self) -> None:
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        register(registry, executor)

        assert "hira_hospital_search" in registry
        tool = registry.lookup("hira_hospital_search")
        assert tool.id == "hira_hospital_search"
        assert "hira_hospital_search" in executor._adapters
        assert callable(executor._adapters["hira_hospital_search"])


# ---------------------------------------------------------------------------
# D + E fix (2026-05-04, snap-009 강남역 내과 lookup regression)
# ---------------------------------------------------------------------------


class TestHiraHospitalSearchDistanceSort:
    """D-fix: HIRA does not sort server-side; UMMAYA sorts by distance ASC.

    Verified live 2026-05-04: baseline call near 강남역 (37.498, 127.028)
    returned d=829, 760, 479, 610, 757 (registration order). Citizens expect
    "근처 X" to mean the actually-closest match.
    """

    @staticmethod
    def _unsorted_fixture() -> dict:
        """Synthesize a HIRA response with intentionally unsorted distances."""
        return {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
                "body": {
                    "totalCount": 5,
                    "pageNo": 1,
                    "numOfRows": 20,
                    "items": {
                        "item": [
                            {
                                "ykiho": "A",
                                "yadmNm": "Far Hospital",
                                "addr": "addr A",
                                "telno": "02-000-0001",
                                "clCd": "31",
                                "clCdNm": "의원",
                                "XPos": "127.030",
                                "YPos": "37.500",
                                "distance": "829.13",
                                "sidoCdNm": "서울",
                                "sgguCdNm": "강남구",
                            },
                            {
                                "ykiho": "B",
                                "yadmNm": "Mid Hospital",
                                "addr": "addr B",
                                "telno": "02-000-0002",
                                "clCd": "31",
                                "clCdNm": "의원",
                                "XPos": "127.029",
                                "YPos": "37.499",
                                "distance": "479.98",
                                "sidoCdNm": "서울",
                                "sgguCdNm": "강남구",
                            },
                            {
                                "ykiho": "C",
                                "yadmNm": "Closest Hospital",
                                "addr": "addr C",
                                "telno": "02-000-0003",
                                "clCd": "31",
                                "clCdNm": "의원",
                                "XPos": "127.0281",
                                "YPos": "37.4982",
                                "distance": "117.99",
                                "sidoCdNm": "서울",
                                "sgguCdNm": "강남구",
                            },
                            {
                                "ykiho": "D",
                                "yadmNm": "Missing Distance",
                                "addr": "addr D",
                                "telno": "02-000-0004",
                                "clCd": "31",
                                "clCdNm": "의원",
                                "XPos": "127.029",
                                "YPos": "37.499",
                                # distance intentionally missing
                                "sidoCdNm": "서울",
                                "sgguCdNm": "강남구",
                            },
                            {
                                "ykiho": "E",
                                "yadmNm": "Second Closest",
                                "addr": "addr E",
                                "telno": "02-000-0005",
                                "clCd": "31",
                                "clCdNm": "의원",
                                "XPos": "127.028",
                                "YPos": "37.498",
                                "distance": "206.35",
                                "sidoCdNm": "서울",
                                "sgguCdNm": "강남구",
                            },
                        ]
                    },
                },
            }
        }

    async def test_handle_sorts_items_by_distance_ascending(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """handle() sorts the response items by distance ASC (closest first)."""
        monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "test-key-hira")
        mock_client = _make_mock_client(self._unsorted_fixture())

        inp = HiraHospitalSearchInput(xPos=127.028, yPos=37.498, radius=2000)
        result = await handle(inp, client=mock_client)

        names = [item["yadmNm"] for item in result["items"]]
        # Expected: 117.99 < 206.35 < 479.98 < 829.13 < (missing → last)
        assert names == [
            "Closest Hospital",
            "Second Closest",
            "Mid Hospital",
            "Far Hospital",
            "Missing Distance",
        ], f"Items not sorted by distance ASC: {names}"

    async def test_handle_handles_string_distance_precision(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """High-precision decimal-string distances (HIRA's actual format) sort correctly."""
        monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "test-key-hira")
        # Use HIRA's actual response format — long decimal strings.
        fixture = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
                "body": {
                    "totalCount": 2,
                    "pageNo": 1,
                    "numOfRows": 20,
                    "items": {
                        "item": [
                            {
                                "ykiho": "A",
                                "yadmNm": "Farther",
                                "addr": "a",
                                "telno": "1",
                                "clCd": "31",
                                "clCdNm": "의원",
                                "XPos": "127.030",
                                "YPos": "37.500",
                                "distance": "829.13139418720577113074191426367837982",
                                "sidoCdNm": "서울",
                                "sgguCdNm": "강남구",
                            },
                            {
                                "ykiho": "B",
                                "yadmNm": "Closer",
                                "addr": "b",
                                "telno": "2",
                                "clCd": "31",
                                "clCdNm": "의원",
                                "XPos": "127.028",
                                "YPos": "37.498",
                                "distance": "117.99528042207281436111062822721148603",
                                "sidoCdNm": "서울",
                                "sgguCdNm": "강남구",
                            },
                        ]
                    },
                },
            }
        }
        mock_client = _make_mock_client(fixture)

        inp = HiraHospitalSearchInput(xPos=127.028, yPos=37.498, radius=2000)
        result = await handle(inp, client=mock_client)

        assert [item["yadmNm"] for item in result["items"]] == ["Closer", "Farther"]


class TestHiraHospitalSearchSpecialtyFilter:
    """E-fix: dgsbjt natural-language input maps to dgsbjtCd and forwards to HIRA.

    Verified live 2026-05-04: dgsbjtCd=01 near 강남역 reduced totalCount
    907 → 118 (only 내과 entries).
    """

    async def test_dgsbjt_korean_maps_to_code_and_forwards(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """dgsbjt='내과' → params['dgsbjtCd']='01' on the outbound HIRA call."""
        monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "test-key-hira")
        fixture = _load_fixture("hospital_search_happy.json")
        mock_client = _make_mock_client(fixture)

        inp = HiraHospitalSearchInput(xPos=127.028, yPos=37.498, radius=2000, dgsbjt="내과")
        await handle(inp, client=mock_client)

        # Inspect the params passed to the mock client's GET call.
        call = mock_client.get.call_args
        params = call.kwargs["params"]
        assert params["dgsbjtCd"] == "01", (
            f"Expected dgsbjtCd='01' for '내과', got {params.get('dgsbjtCd')!r}"
        )

    async def test_dgsbjt_english_alias_maps_to_code(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """dgsbjt='pediatrics' → 11 (English alias mapping)."""
        monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "test-key-hira")
        fixture = _load_fixture("hospital_search_happy.json")
        mock_client = _make_mock_client(fixture)

        inp = HiraHospitalSearchInput(xPos=127.028, yPos=37.498, radius=2000, dgsbjt="pediatrics")
        await handle(inp, client=mock_client)

        params = mock_client.get.call_args.kwargs["params"]
        assert params["dgsbjtCd"] == "11"

    async def test_dgsbjt_already_a_code_passthrough(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """dgsbjt='13' (already a 2-digit code) → passes through unchanged."""
        monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "test-key-hira")
        fixture = _load_fixture("hospital_search_happy.json")
        mock_client = _make_mock_client(fixture)

        inp = HiraHospitalSearchInput(xPos=127.028, yPos=37.498, radius=2000, dgsbjt="13")
        await handle(inp, client=mock_client)

        params = mock_client.get.call_args.kwargs["params"]
        assert params["dgsbjtCd"] == "13"

    async def test_dgsbjt_single_digit_code_is_zero_padded(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """dgsbjt='1' or int 1 maps to the canonical HIRA code '01'."""
        monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "test-key-hira")
        fixture = _load_fixture("hospital_search_happy.json")
        mock_client = _make_mock_client(fixture)

        inp = HiraHospitalSearchInput(xPos=127.028, yPos=37.498, radius=2000, dgsbjt=1)
        await handle(inp, client=mock_client)

        params = mock_client.get.call_args.kwargs["params"]
        assert params["dgsbjtCd"] == "01"

    async def test_dgsbjt_multi_specialty_fans_out_and_merges(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """dgsbjt='피부과,내과' makes one HIRA call per specialty code."""
        monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "test-key-hira")
        fixture = _load_fixture("hospital_search_happy.json")
        mock_client = _make_mock_client(fixture)

        inp = HiraHospitalSearchInput(
            xPos=127.028,
            yPos=37.498,
            radius=2000,
            dgsbjt="피부과,내과",
        )
        result = await handle(inp, client=mock_client)

        call_params = [call.kwargs["params"] for call in mock_client.get.call_args_list]
        assert [params["dgsbjtCd"] for params in call_params] == ["14", "01"]
        assert result["items"], "Merged multi-specialty result should keep fixture rows"
        for item in result["items"]:
            assert item["matchedDgsbjtCds"] == ["14", "01"]
            assert item["matchedDgsbjtNms"] == ["피부과", "내과"]
            assert item["matchedDgsbjtCd"] == "14,01"
            assert item["matchedDgsbjtNm"] == "피부과,내과"

    def test_dgsbjt_unknown_raises_validation_error(self) -> None:
        """Unknown specialty name raises ValueError (→ executor invalid_params)."""
        with pytest.raises(ValueError, match="Unknown medical specialty"):
            HiraHospitalSearchInput(xPos=127.028, yPos=37.498, radius=2000, dgsbjt="존재하지않는과")

    async def test_dgsbjt_omitted_no_param_sent(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When dgsbjt is None the outbound params do NOT include dgsbjtCd."""
        monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "test-key-hira")
        fixture = _load_fixture("hospital_search_happy.json")
        mock_client = _make_mock_client(fixture)

        inp = HiraHospitalSearchInput(xPos=127.028, yPos=37.498, radius=2000)
        await handle(inp, client=mock_client)

        params = mock_client.get.call_args.kwargs["params"]
        assert "dgsbjtCd" not in params


class TestHiraHospitalSearchClcdFilter:
    """E-fix: clCd natural-language input maps to 종별코드 and forwards to HIRA."""

    async def test_clcd_korean_maps_to_code(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """clCd='의원' → '31', clCd='상급종합' → '11'."""
        monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "test-key-hira")
        fixture = _load_fixture("hospital_search_happy.json")
        mock_client = _make_mock_client(fixture)

        inp = HiraHospitalSearchInput(xPos=127.028, yPos=37.498, radius=2000, clCd="의원")
        await handle(inp, client=mock_client)
        assert mock_client.get.call_args.kwargs["params"]["clCd"] == "31"

    async def test_clcd_combined_with_dgsbjt(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Both filters together: 내과 + 의원 = '내과의원' (server-side AND)."""
        monkeypatch.setenv("UMMAYA_DATA_GO_KR_API_KEY", "test-key-hira")
        fixture = _load_fixture("hospital_search_happy.json")
        mock_client = _make_mock_client(fixture)

        inp = HiraHospitalSearchInput(
            xPos=127.028, yPos=37.498, radius=2000, dgsbjt="내과", clCd="의원"
        )
        await handle(inp, client=mock_client)
        params = mock_client.get.call_args.kwargs["params"]
        assert params["dgsbjtCd"] == "01"
        assert params["clCd"] == "31"

    def test_clcd_unknown_raises_validation_error(self) -> None:
        """Unknown institution type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown institution type"):
            HiraHospitalSearchInput(xPos=127.028, yPos=37.498, radius=2000, clCd="없는종별")
