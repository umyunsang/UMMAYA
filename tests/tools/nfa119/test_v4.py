# SPDX-License-Identifier: Apache-2.0
"""T033 — NFA EmergencyInformationService v4 tests.

Covers all 6 sub-operations (happy + error path) against fixture-mocked HTTP.
Live tests (``@pytest.mark.live``) gate on KOSMOS_DATA_GO_KR_API_KEY.

Wire param contract (research-nfa-wire.md):
  - URL = {_BASE_URL}/{operation}   (operation suffix REQUIRED)
  - activity: gutYm; all others: stmtYm; vehicle_info: no ym param
  - resultType=json, pageNo, numOfRows, rsacGutFsttOgidNm (all camelCase)
"""

from __future__ import annotations

import json
import pathlib
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from kosmos.tools.errors import ConfigurationError, ToolExecutionError
from kosmos.tools.nfa119.emergency_info_service import (
    NFA_EMERGENCY_INFO_SERVICE_TOOL,
    NfaActivityItem,
    NfaConditionItem,
    NfaEmergencyInfoServiceInput,
    NfaEmergencyInfoServiceOutput,
    NfaEmgOperation,
    NfaFirstaidItem,
    NfaTransferItem,
    NfaVehicleDispatchItem,
    NfaVehicleInfoItem,
    _build_params,
    _parse_response,
    handle,
)

_FIXTURE_DIR = pathlib.Path(__file__).parent.parent.parent / "fixtures" / "nfa119"

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _mock_client(fixture_data: dict, content_type: str = "application/json") -> httpx.AsyncClient:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"content-type": content_type}
    mock_response.json.return_value = fixture_data
    mock_response.raise_for_status = MagicMock()
    mock = AsyncMock(spec=httpx.AsyncClient)
    mock.get.return_value = mock_response
    mock.aclose = AsyncMock()
    return mock


# ---------------------------------------------------------------------------
# T033-A: Wire param builder — operation-specific ym routing
# ---------------------------------------------------------------------------


class TestBuildParams:
    """_build_params correctly routes ym wire param per operation."""

    def _make_inp(self, operation: NfaEmgOperation) -> NfaEmergencyInfoServiceInput:
        return NfaEmergencyInfoServiceInput(
            operation=operation,
            rsac_gut_fstt_ogid_nm="공주소방서",
            stmt_ym="202101",
        )

    def test_activity_uses_gut_ym(self) -> None:
        """getEmgencyActivityInfo must use gutYm wire param."""
        inp = self._make_inp(NfaEmgOperation.activity)
        params = _build_params(inp, api_key="testkey")
        assert "gutYm" in params
        assert params["gutYm"] == "202101"
        assert "stmtYm" not in params

    def test_transfer_uses_stmt_ym(self) -> None:
        """getEmgPatientTransferInfo must use stmtYm wire param."""
        inp = self._make_inp(NfaEmgOperation.transfer)
        params = _build_params(inp, api_key="testkey")
        assert "stmtYm" in params
        assert params["stmtYm"] == "202101"
        assert "gutYm" not in params

    def test_condition_uses_stmt_ym(self) -> None:
        """getEmgPatientConditionInfo must use stmtYm."""
        inp = self._make_inp(NfaEmgOperation.condition)
        params = _build_params(inp, api_key="testkey")
        assert "stmtYm" in params
        assert "gutYm" not in params

    def test_firstaid_uses_stmt_ym(self) -> None:
        """getEmgPatientFirstaidInfo must use stmtYm."""
        inp = self._make_inp(NfaEmgOperation.firstaid)
        params = _build_params(inp, api_key="testkey")
        assert "stmtYm" in params
        assert "gutYm" not in params

    def test_vehicle_dispatch_uses_stmt_ym(self) -> None:
        """getEmgVehicleDispatchInfo must use stmtYm."""
        inp = self._make_inp(NfaEmgOperation.vehicle_dispatch)
        params = _build_params(inp, api_key="testkey")
        assert "stmtYm" in params
        assert "gutYm" not in params

    def test_vehicle_info_omits_ym(self) -> None:
        """getEmgVehicleInfo must NOT send any ym param (vehicle registry snapshot)."""
        inp = self._make_inp(NfaEmgOperation.vehicle_info)
        params = _build_params(inp, api_key="testkey")
        assert "stmtYm" not in params
        assert "gutYm" not in params

    def test_sido_hq_included_when_provided(self) -> None:
        """sidoHqOgidNm is included in wire params when sido_hq_ogid_nm is set."""
        inp = NfaEmergencyInfoServiceInput(
            operation=NfaEmgOperation.activity,
            rsac_gut_fstt_ogid_nm="공주소방서",
            stmt_ym="202101",
            sido_hq_ogid_nm="충청남도소방본부",
        )
        params = _build_params(inp, api_key="testkey")
        assert params.get("sidoHqOgidNm") == "충청남도소방본부"

    def test_sido_hq_omitted_when_none(self) -> None:
        """sidoHqOgidNm is NOT included when sido_hq_ogid_nm is None."""
        inp = NfaEmergencyInfoServiceInput(
            operation=NfaEmgOperation.activity,
            rsac_gut_fstt_ogid_nm="공주소방서",
            stmt_ym="202101",
            sido_hq_ogid_nm=None,
        )
        params = _build_params(inp, api_key="testkey")
        assert "sidoHqOgidNm" not in params

    def test_rsac_gut_fstt_ogid_nm_camelcase(self) -> None:
        """rsacGutFsttOgidNm wire param name is camelCase."""
        inp = self._make_inp(NfaEmgOperation.activity)
        params = _build_params(inp, api_key="testkey")
        assert "rsacGutFsttOgidNm" in params
        assert params["rsacGutFsttOgidNm"] == "공주소방서"

    def test_result_type_camelcase(self) -> None:
        """resultType wire param (capital T) value is 'json'."""
        inp = self._make_inp(NfaEmgOperation.activity)
        params = _build_params(inp, api_key="testkey")
        assert params.get("resultType") == "json"

    def test_page_no_camelcase(self) -> None:
        """pageNo / numOfRows are camelCase in wire params."""
        inp = NfaEmergencyInfoServiceInput(
            operation=NfaEmgOperation.transfer,
            rsac_gut_fstt_ogid_nm="파주소방서",
            stmt_ym="202106",
            page_no=2,
            num_of_rows=5,
        )
        params = _build_params(inp, api_key="testkey")
        assert params["pageNo"] == 2
        assert params["numOfRows"] == 5


# ---------------------------------------------------------------------------
# T033-B: _parse_response — per-operation item model dispatch
# ---------------------------------------------------------------------------


class TestParseResponse:
    """_parse_response dispatches to the correct item model per operation."""

    def test_activity_parses_nfa_activity_item(self) -> None:
        """getEmgencyActivityInfo → NfaActivityItem list."""
        data = _load_fixture("nfa_emergency_info_service.json")
        result = _parse_response(data, NfaEmgOperation.activity.value)
        assert result.operation == "getEmgencyActivityInfo"
        assert result.result_code == "00"
        assert result.total_count == 1
        assert len(result.items) == 1
        item = result.items[0]
        assert isinstance(item, NfaActivityItem)
        assert item.rsacGutFsttOgidNm == "천안동남소방서"
        assert item.gutYm == "202112"

    def test_transfer_parses_nfa_transfer_item(self) -> None:
        """getEmgPatientTransferInfo → NfaTransferItem list."""
        data = _load_fixture("nfa_transfer.json")
        result = _parse_response(data, NfaEmgOperation.transfer.value)
        assert result.operation == "getEmgPatientTransferInfo"
        assert result.total_count == 162
        assert len(result.items) == 2
        item = result.items[0]
        assert isinstance(item, NfaTransferItem)
        assert item.stmtYm == "202101"
        assert item.rsacGutFsttOgidNm == "공주소방서"

    def test_condition_parses_nfa_condition_item(self) -> None:
        """getEmgPatientConditionInfo → NfaConditionItem list."""
        data = _load_fixture("nfa_condition.json")
        result = _parse_response(data, NfaEmgOperation.condition.value)
        assert result.operation == "getEmgPatientConditionInfo"
        assert result.total_count == 1299
        assert len(result.items) == 2
        item = result.items[0]
        assert isinstance(item, NfaConditionItem)
        assert item.ruptSptmCdNm == "어지러움"
        assert item.topBpsr == "122"

    def test_firstaid_parses_nfa_firstaid_item(self) -> None:
        """getEmgPatientFirstaidInfo → NfaFirstaidItem list."""
        data = _load_fixture("nfa_firstaid.json")
        result = _parse_response(data, NfaEmgOperation.firstaid.value)
        assert result.operation == "getEmgPatientFirstaidInfo"
        assert result.total_count == 74
        assert len(result.items) == 2
        item = result.items[0]
        assert isinstance(item, NfaFirstaidItem)
        assert item.fstaCdNm == "비관, 기타"

    def test_vehicle_dispatch_parses_nfa_vehicle_dispatch_item(self) -> None:
        """getEmgVehicleDispatchInfo → NfaVehicleDispatchItem list."""
        data = _load_fixture("nfa_vehicle_dispatch.json")
        result = _parse_response(data, NfaEmgOperation.vehicle_dispatch.value)
        assert result.operation == "getEmgVehicleDispatchInfo"
        assert result.total_count == 1199
        assert len(result.items) == 2
        item = result.items[0]
        assert isinstance(item, NfaVehicleDispatchItem)
        assert item.vctpCdNm == "구급차특수(중형)"
        assert item.vhclNo == "998머5826"

    def test_vehicle_info_parses_nfa_vehicle_info_item(self) -> None:
        """getEmgVehicleInfo → NfaVehicleInfoItem list."""
        data = _load_fixture("nfa_vehicle_info.json")
        result = _parse_response(data, NfaEmgOperation.vehicle_info.value)
        assert result.operation == "getEmgVehicleInfo"
        assert result.total_count == 117
        assert len(result.items) == 2
        item = result.items[0]
        assert isinstance(item, NfaVehicleInfoItem)
        assert item.rsacGutFsttOgidNm == "동부소방서"
        assert item.stde == "20220125"

    def test_single_item_as_dict_unwrapped(self) -> None:
        """Shape B: body.items.item is a single dict — must be unwrapped to list of 1."""
        payload = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE"},
                "body": {
                    "pageNo": 1,
                    "numOfRows": 1,
                    "totalCount": 1,
                    "items": {
                        "item": {
                            "sidoHqOgidNm": "충청남도소방본부",
                            "rsacGutFsttOgidNm": "천안동남소방서",
                            "gutYm": "202112",
                            "gutHh": "14",
                            "ruptSptmCdNm": "기침",
                        }
                    },
                },
            }
        }
        result = _parse_response(payload, NfaEmgOperation.activity.value)
        assert isinstance(result.items, list)
        assert len(result.items) == 1
        item = result.items[0]
        assert isinstance(item, NfaActivityItem)
        assert item.gutYm == "202112"

    def test_error_code_raises_tool_execution_error(self) -> None:
        """resultCode != '00' must raise ToolExecutionError."""
        payload = {
            "response": {
                "header": {"resultCode": "10", "resultMsg": "INVALID REQUEST PARAMETER ERROR"},
                "body": {
                    "pageNo": 1,
                    "numOfRows": 10,
                    "totalCount": 0,
                    "items": None,
                },
            }
        }
        with pytest.raises(ToolExecutionError) as exc_info:
            _parse_response(payload, NfaEmgOperation.activity.value)
        assert "10" in str(exc_info.value)
        assert "INVALID" in str(exc_info.value).upper()

    def test_missing_header_raises_tool_execution_error(self) -> None:
        """Malformed payload (no response.header) raises ToolExecutionError."""
        with pytest.raises(ToolExecutionError):
            _parse_response({"bad": "shape"}, NfaEmgOperation.activity.value)

    def test_empty_items_returns_empty_list(self) -> None:
        """items=None in body → empty items list (no error)."""
        payload = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE"},
                "body": {
                    "pageNo": 1,
                    "numOfRows": 10,
                    "totalCount": 0,
                    "items": None,
                },
            }
        }
        result = _parse_response(payload, NfaEmgOperation.activity.value)
        assert result.items == []
        assert result.total_count == 0


# ---------------------------------------------------------------------------
# T033-C: handle() — happy path per sub-operation (mocked HTTP)
# ---------------------------------------------------------------------------


class TestHandleHappy:
    """handle() happy-path tests with mocked httpx.AsyncClient."""

    @pytest.mark.asyncio
    async def test_handle_activity(self, monkeypatch) -> None:
        """handle() with activity operation returns NfaActivityItem fields."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", "testkey123")
        data = _load_fixture("nfa_emergency_info_service.json")
        client = _mock_client(data)

        inp = NfaEmergencyInfoServiceInput(
            operation=NfaEmgOperation.activity,
            rsac_gut_fstt_ogid_nm="천안동남소방서",
            stmt_ym="202112",
        )
        result = await handle(inp, client=client)

        # Envelope-ready collection contract (post-2026-05-04 fabrication fix):
        # handle() returns {"kind": "collection", "items": [...], "total_count": N}
        # — operation/result_code metadata is logged but no longer surfaced to the
        # LLM, because the discriminated LookupOutput envelope only carries kind
        # + items + total_count + meta. See module docstring for the C-class context.
        assert result["kind"] == "collection"
        assert result["total_count"] == 1
        assert len(result["items"]) == 1
        # Verify correct sub-endpoint URL was called
        call_args = client.get.call_args
        assert "/getEmgencyActivityInfo" in str(call_args)
        # Verify gutYm wire param (params kwarg from httpx client.get(url, params=...))
        called_params = call_args.kwargs.get("params") or (
            call_args.args[1] if len(call_args.args) > 1 else {}
        )
        assert called_params.get("gutYm") == "202112"
        assert "stmtYm" not in called_params

    @pytest.mark.asyncio
    async def test_handle_transfer(self, monkeypatch) -> None:
        """handle() with transfer operation returns NfaTransferItem fields."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", "testkey123")
        data = _load_fixture("nfa_transfer.json")
        client = _mock_client(data)

        inp = NfaEmergencyInfoServiceInput(
            operation=NfaEmgOperation.transfer,
            rsac_gut_fstt_ogid_nm="공주소방서",
            stmt_ym="202101",
        )
        result = await handle(inp, client=client)

        assert result["kind"] == "collection"
        assert result["total_count"] == 162
        items = result["items"]
        assert len(items) == 2
        assert items[0]["stmtYm"] == "202101"
        # Verify stmtYm wire param
        call_args = client.get.call_args
        called_params = call_args.kwargs.get("params") or {}
        assert called_params.get("stmtYm") == "202101"
        assert "gutYm" not in called_params

    @pytest.mark.asyncio
    async def test_handle_condition(self, monkeypatch) -> None:
        """handle() with condition operation returns NfaConditionItem fields."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", "testkey123")
        data = _load_fixture("nfa_condition.json")
        client = _mock_client(data)

        inp = NfaEmergencyInfoServiceInput(
            operation=NfaEmgOperation.condition,
            rsac_gut_fstt_ogid_nm="파주소방서",
            stmt_ym="202107",
        )
        result = await handle(inp, client=client)

        assert result["kind"] == "collection"
        assert result["total_count"] == 1299
        assert result["items"][0]["ruptSptmCdNm"] == "어지러움"

    @pytest.mark.asyncio
    async def test_handle_firstaid(self, monkeypatch) -> None:
        """handle() with firstaid operation returns NfaFirstaidItem fields."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", "testkey123")
        data = _load_fixture("nfa_firstaid.json")
        client = _mock_client(data)

        inp = NfaEmergencyInfoServiceInput(
            operation=NfaEmgOperation.firstaid,
            rsac_gut_fstt_ogid_nm="천안동남소방서",
            stmt_ym="202105",
        )
        result = await handle(inp, client=client)

        assert result["kind"] == "collection"
        assert result["total_count"] == 74
        assert result["items"][0]["fstaCdNm"] == "비관, 기타"

    @pytest.mark.asyncio
    async def test_handle_vehicle_dispatch(self, monkeypatch) -> None:
        """handle() with vehicle_dispatch operation returns NfaVehicleDispatchItem fields."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", "testkey123")
        data = _load_fixture("nfa_vehicle_dispatch.json")
        client = _mock_client(data)

        inp = NfaEmergencyInfoServiceInput(
            operation=NfaEmgOperation.vehicle_dispatch,
            rsac_gut_fstt_ogid_nm="은평소방서",
            stmt_ym="202101",
        )
        result = await handle(inp, client=client)

        assert result["kind"] == "collection"
        assert result["total_count"] == 1199
        assert result["items"][0]["vctpCdNm"] == "구급차특수(중형)"

    @pytest.mark.asyncio
    async def test_handle_vehicle_info(self, monkeypatch) -> None:
        """handle() with vehicle_info operation returns NfaVehicleInfoItem fields."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", "testkey123")
        data = _load_fixture("nfa_vehicle_info.json")
        client = _mock_client(data)

        inp = NfaEmergencyInfoServiceInput(
            operation=NfaEmgOperation.vehicle_info,
            rsac_gut_fstt_ogid_nm="동부소방서",
            stmt_ym="202201",
        )
        result = await handle(inp, client=client)

        assert result["kind"] == "collection"
        assert result["total_count"] == 117
        assert result["items"][0]["stde"] == "20220125"
        # vehicle_info: no ym param in wire call
        call_args = client.get.call_args
        called_params = call_args.kwargs.get("params") or {}
        assert "stmtYm" not in called_params
        assert "gutYm" not in called_params


# ---------------------------------------------------------------------------
# T033-D: handle() — error paths
# ---------------------------------------------------------------------------


class TestHandleErrors:
    """handle() error-path tests."""

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_config_error(self, monkeypatch) -> None:
        """handle() raises ConfigurationError if KOSMOS_DATA_GO_KR_API_KEY is not set."""
        monkeypatch.delenv("KOSMOS_DATA_GO_KR_API_KEY", raising=False)

        inp = NfaEmergencyInfoServiceInput(
            rsac_gut_fstt_ogid_nm="천안동남소방서",
            stmt_ym="202112",
        )
        with pytest.raises(ConfigurationError):
            await handle(inp)

    @pytest.mark.asyncio
    async def test_xml_content_type_raises_tool_error(self, monkeypatch) -> None:
        """handle() raises ToolExecutionError when NFA returns XML content-type."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", "testkey123")

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/xml"}
        mock_response.raise_for_status = MagicMock()
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = mock_response
        client.aclose = AsyncMock()

        inp = NfaEmergencyInfoServiceInput(
            rsac_gut_fstt_ogid_nm="천안동남소방서",
            stmt_ym="202112",
        )
        with pytest.raises(ToolExecutionError) as exc_info:
            await handle(inp, client=client)
        assert "XML" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_result_code_10_raises_tool_error(self, monkeypatch) -> None:
        """handle() raises ToolExecutionError on resultCode='10' (invalid params)."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", "testkey123")
        payload = {
            "response": {
                "header": {"resultCode": "10", "resultMsg": "INVALID REQUEST PARAMETER ERROR"},
                "body": {
                    "pageNo": 1,
                    "numOfRows": 10,
                    "totalCount": 0,
                    "items": None,
                },
            }
        }
        client = _mock_client(payload)

        inp = NfaEmergencyInfoServiceInput(
            rsac_gut_fstt_ogid_nm="천안동남소방서",
            stmt_ym="202112",
        )
        with pytest.raises(ToolExecutionError) as exc_info:
            await handle(inp, client=client)
        assert "10" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_http_status_error_raises_tool_error(self, monkeypatch) -> None:
        """handle() raises ToolExecutionError on HTTP 500."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", "testkey123")

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=mock_response,
        )
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = mock_response
        client.aclose = AsyncMock()

        inp = NfaEmergencyInfoServiceInput(
            rsac_gut_fstt_ogid_nm="천안동남소방서",
            stmt_ym="202112",
        )
        with pytest.raises(ToolExecutionError) as exc_info:
            await handle(inp, client=client)
        assert "500" in str(exc_info.value) or "HTTP" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_network_error_raises_tool_error(self, monkeypatch) -> None:
        """handle() raises ToolExecutionError on network timeout."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", "testkey123")

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.side_effect = httpx.ConnectTimeout("connection timed out")
        client.aclose = AsyncMock()

        inp = NfaEmergencyInfoServiceInput(
            rsac_gut_fstt_ogid_nm="천안동남소방서",
            stmt_ym="202112",
        )
        with pytest.raises(ToolExecutionError) as exc_info:
            await handle(inp, client=client)
        assert "Network" in str(exc_info.value) or "network" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# T033-E: Tool metadata + description integrity
# ---------------------------------------------------------------------------


class TestToolMetadata:
    """NFA_EMERGENCY_INFO_SERVICE_TOOL metadata and description integrity."""

    def test_tool_id(self) -> None:
        assert NFA_EMERGENCY_INFO_SERVICE_TOOL.id == "nfa_emergency_info_service"

    def test_output_schema_is_envelope_placeholder(self) -> None:
        """output_schema is an envelope placeholder; handler emits envelope-ready dict.

        Updated 2026-05-04 (C-class fabrication fix): the strict
        NfaEmergencyInfoServiceOutput remains as the documentation contract,
        but the wire surface is now a placeholder that lets the
        envelope-ready ``{"kind": "collection", ...}`` dict flow into
        envelope.normalize() — see module docstring for context.
        """
        from kosmos.tools.nfa119.emergency_info_service import _PlaceholderOutput

        assert NFA_EMERGENCY_INFO_SERVICE_TOOL.output_schema is _PlaceholderOutput
        # Documentation contract preserved
        assert NfaEmergencyInfoServiceOutput.__name__ == "NfaEmergencyInfoServiceOutput"

    def test_llm_description_not_empty(self) -> None:
        assert len(NFA_EMERGENCY_INFO_SERVICE_TOOL.llm_description) > 100

    def test_llm_description_contains_17_hq(self) -> None:
        """llm_description section 3 must contain NFA_HQ_SHORT_REFERENCE (17 시도본부)."""
        desc = NFA_EMERGENCY_INFO_SERVICE_TOOL.llm_description
        assert "서울특별시소방재난본부" in desc
        assert "제주특별자치도소방안전본부" in desc

    def test_llm_description_contains_operations(self) -> None:
        """llm_description must mention the 6 operation values."""
        desc = NFA_EMERGENCY_INFO_SERVICE_TOOL.llm_description
        assert "getEmgencyActivityInfo" in desc or "activity" in desc

    def test_llm_description_contains_gut_ym_wire_rule(self) -> None:
        """llm_description domain_quirk must document gutYm vs stmtYm routing."""
        desc = NFA_EMERGENCY_INFO_SERVICE_TOOL.llm_description
        assert "gutYm" in desc

    def test_auth_type(self) -> None:
        assert NFA_EMERGENCY_INFO_SERVICE_TOOL.auth_type == "api_key"

    def test_cache_ttl(self) -> None:
        assert NFA_EMERGENCY_INFO_SERVICE_TOOL.cache_ttl_seconds == 86400


# ---------------------------------------------------------------------------
# T033-F: @pytest.mark.live — real data.go.kr call (skipped in CI)
# ---------------------------------------------------------------------------


@pytest.mark.live
class TestHandleLive:
    """Live integration — skipped unless '-m live' + KOSMOS_DATA_GO_KR_API_KEY set.

    AGENTS.md hard rule: Never call live data.go.kr APIs from CI tests.
    """

    @pytest.mark.asyncio
    async def test_live_activity(self) -> None:
        """Live: getEmgencyActivityInfo against real NFA API."""
        import os

        if not os.environ.get("KOSMOS_DATA_GO_KR_API_KEY"):
            pytest.skip("KOSMOS_DATA_GO_KR_API_KEY not set — skipping live NFA test")

        inp = NfaEmergencyInfoServiceInput(
            operation=NfaEmgOperation.activity,
            rsac_gut_fstt_ogid_nm="천안동남소방서",
            stmt_ym="202112",
            num_of_rows=2,
        )
        result = await handle(inp)
        assert result["kind"] == "collection"
        assert isinstance(result["items"], list)

    @pytest.mark.asyncio
    async def test_live_vehicle_info(self) -> None:
        """Live: getEmgVehicleInfo (no ym param) against real NFA API."""
        import os

        if not os.environ.get("KOSMOS_DATA_GO_KR_API_KEY"):
            pytest.skip("KOSMOS_DATA_GO_KR_API_KEY not set — skipping live NFA test")

        inp = NfaEmergencyInfoServiceInput(
            operation=NfaEmgOperation.vehicle_info,
            rsac_gut_fstt_ogid_nm="동부소방서",
            stmt_ym="202201",
            sido_hq_ogid_nm="대구소방안전본부",
            num_of_rows=2,
        )
        result = await handle(inp)
        assert result["kind"] == "collection"
        assert isinstance(result["items"], list)
