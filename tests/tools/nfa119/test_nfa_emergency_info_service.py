# SPDX-License-Identifier: Apache-2.0
"""Tests for nfa_emergency_info_service adapter — spec 029 US1.

Covers:
- Input schema happy-path and error-path validation (T016)
- Layer3GateViolation raised when handle() is called directly (T016)
- Executor returns LookupError(reason="auth_required") with zero HTTP calls (T016)
- BM25 search returns nfa_emergency_info_service in top-5 for Korean/English queries (T016)
"""

from __future__ import annotations

import json
import pathlib

import pytest
import respx
from pydantic import ValidationError

from kosmos.tools.executor import ToolExecutor
from kosmos.tools.lookup import lookup
from kosmos.tools.models import (
    LookupError,  # noqa: A004
    LookupFetchInput,
    LookupSearchInput,
    LookupSearchResult,
)
from kosmos.tools.nfa119.emergency_info_service import (
    NFA_EMERGENCY_INFO_SERVICE_TOOL,
    NfaActivityItem,
    NfaEmergencyInfoServiceInput,
    NfaEmgOperation,
    handle,
    register,
)
from kosmos.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_PATH = (
    pathlib.Path(__file__).parent.parent.parent
    / "fixtures"
    / "nfa119"
    / "nfa_emergency_info_service.json"
)


@pytest.fixture(scope="module")
def nfa_reg_exec():
    """Module-scope registry + executor with only NFA registered."""
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)
    return registry, executor


# ---------------------------------------------------------------------------
# Input schema — happy-path tests
# ---------------------------------------------------------------------------


class TestNfaInputSchemaHappy:
    """NfaEmergencyInfoServiceInput valid construction tests."""

    def test_minimal_required_fields(self) -> None:
        """Minimal valid input: rsac_gut_fstt_ogid_nm + stmt_ym, rest default."""
        inp = NfaEmergencyInfoServiceInput.model_validate(
            {
                "rsac_gut_fstt_ogid_nm": "천안동남소방서",
                "stmt_ym": "202112",
            }
        )
        assert inp.operation == NfaEmgOperation.activity
        assert inp.rsac_gut_fstt_ogid_nm == "천안동남소방서"
        assert inp.stmt_ym == "202112"
        assert inp.page_no == 1
        assert inp.num_of_rows == 10
        assert inp.result_type == "json"

    def test_all_operations_are_valid(self) -> None:
        """All 6 NfaEmgOperation enum values produce valid inputs."""
        for op in NfaEmgOperation:
            inp = NfaEmergencyInfoServiceInput.model_validate(
                {
                    "rsac_gut_fstt_ogid_nm": "공주소방서",
                    "stmt_ym": "202201",
                    "operation": op.value,
                }
            )
            assert inp.operation == op

    def test_optional_sido_field(self) -> None:
        """sido_hq_ogid_nm is optional and defaults to None."""
        inp = NfaEmergencyInfoServiceInput.model_validate(
            {
                "rsac_gut_fstt_ogid_nm": "은평소방서",
                "stmt_ym": "202101",
            }
        )
        assert inp.sido_hq_ogid_nm is None

    def test_sido_field_with_value(self) -> None:
        """sido_hq_ogid_nm accepts valid string."""
        inp = NfaEmergencyInfoServiceInput.model_validate(
            {
                "rsac_gut_fstt_ogid_nm": "은평소방서",
                "stmt_ym": "202101",
                "sido_hq_ogid_nm": "서울소방재난본부",
            }
        )
        assert inp.sido_hq_ogid_nm == "서울소방재난본부"

    def test_custom_pagination(self) -> None:
        """Custom page_no and num_of_rows within bounds."""
        inp = NfaEmergencyInfoServiceInput.model_validate(
            {
                "rsac_gut_fstt_ogid_nm": "파주소방서",
                "stmt_ym": "202106",
                "page_no": 3,
                "num_of_rows": 50,
            }
        )
        assert inp.page_no == 3
        assert inp.num_of_rows == 50

    def test_num_of_rows_max_boundary(self) -> None:
        """num_of_rows=100 is allowed (max per NFA API contract)."""
        inp = NfaEmergencyInfoServiceInput.model_validate(
            {
                "rsac_gut_fstt_ogid_nm": "파주소방서",
                "stmt_ym": "202106",
                "num_of_rows": 100,
            }
        )
        assert inp.num_of_rows == 100


# ---------------------------------------------------------------------------
# Input schema — error-path tests
# ---------------------------------------------------------------------------


class TestNfaInputSchemaErrors:
    """NfaEmergencyInfoServiceInput rejection tests."""

    def test_stmt_ym_too_short(self) -> None:
        r"""stmt_ym='2021' (4 digits) must fail regex ^\d{6}$."""
        with pytest.raises(ValidationError):
            NfaEmergencyInfoServiceInput.model_validate(
                {
                    "rsac_gut_fstt_ogid_nm": "천안동남소방서",
                    "stmt_ym": "2021",
                }
            )

    def test_stmt_ym_too_long(self) -> None:
        """stmt_ym='20211201' (8 digits) must fail regex."""
        with pytest.raises(ValidationError):
            NfaEmergencyInfoServiceInput.model_validate(
                {
                    "rsac_gut_fstt_ogid_nm": "천안동남소방서",
                    "stmt_ym": "20211201",
                }
            )

    def test_stmt_ym_non_digits(self) -> None:
        """stmt_ym with letters must fail regex."""
        with pytest.raises(ValidationError):
            NfaEmergencyInfoServiceInput.model_validate(
                {
                    "rsac_gut_fstt_ogid_nm": "천안동남소방서",
                    "stmt_ym": "2021AB",
                }
            )

    def test_extra_field_forbidden(self) -> None:
        """extra='forbid' must reject unknown fields."""
        with pytest.raises(ValidationError):
            NfaEmergencyInfoServiceInput.model_validate(
                {
                    "rsac_gut_fstt_ogid_nm": "천안동남소방서",
                    "stmt_ym": "202112",
                    "unknown_field": "value",
                }
            )

    def test_missing_required_rsac_gut_fstt_ogid_nm(self) -> None:
        """rsac_gut_fstt_ogid_nm is required; missing must fail."""
        with pytest.raises(ValidationError):
            NfaEmergencyInfoServiceInput.model_validate(
                {
                    "stmt_ym": "202112",
                }
            )

    def test_missing_required_stmt_ym(self) -> None:
        """stmt_ym is required; missing must fail."""
        with pytest.raises(ValidationError):
            NfaEmergencyInfoServiceInput.model_validate(
                {
                    "rsac_gut_fstt_ogid_nm": "천안동남소방서",
                }
            )

    def test_num_of_rows_exceeds_max(self) -> None:
        """num_of_rows=101 exceeds le=100 bound."""
        with pytest.raises(ValidationError):
            NfaEmergencyInfoServiceInput.model_validate(
                {
                    "rsac_gut_fstt_ogid_nm": "천안동남소방서",
                    "stmt_ym": "202112",
                    "num_of_rows": 101,
                }
            )

    def test_num_of_rows_below_min(self) -> None:
        """num_of_rows=0 violates ge=1."""
        with pytest.raises(ValidationError):
            NfaEmergencyInfoServiceInput.model_validate(
                {
                    "rsac_gut_fstt_ogid_nm": "천안동남소방서",
                    "stmt_ym": "202112",
                    "num_of_rows": 0,
                }
            )

    def test_page_no_below_min(self) -> None:
        """page_no=0 violates ge=1."""
        with pytest.raises(ValidationError):
            NfaEmergencyInfoServiceInput.model_validate(
                {
                    "rsac_gut_fstt_ogid_nm": "천안동남소방서",
                    "stmt_ym": "202112",
                    "page_no": 0,
                }
            )


# ---------------------------------------------------------------------------
# Layer 3 gate — handle() must raise Layer3GateViolation
# ---------------------------------------------------------------------------


class TestNfaLayer3Gate:
    """Verify handle() guard behaviour (T031: live handler replaces stub).

    handle() is now a live HTTP handler. The defence-in-depth backstop is no
    longer Layer3GateViolation — instead, handle() raises ConfigurationError
    when KOSMOS_DATA_GO_KR_API_KEY is absent (which is the CI equivalent).
    Layer3GateViolation is still raised by the executor auth gate *before*
    handle() is ever called (FR-025, FR-026, SC-006 via executor.invoke()).
    """

    @pytest.mark.asyncio
    async def test_handle_raises_config_error_without_api_key(
        self, monkeypatch
    ) -> None:
        """handle() raises ConfigurationError if KOSMOS_DATA_GO_KR_API_KEY is not set."""
        from kosmos.tools.errors import ConfigurationError

        monkeypatch.delenv("KOSMOS_DATA_GO_KR_API_KEY", raising=False)

        inp = NfaEmergencyInfoServiceInput.model_validate(
            {
                "rsac_gut_fstt_ogid_nm": "천안동남소방서",
                "stmt_ym": "202112",
            }
        )
        with pytest.raises(ConfigurationError):
            await handle(inp)


# ---------------------------------------------------------------------------
# Executor auth-gate — zero upstream HTTP calls
# ---------------------------------------------------------------------------


class TestNfaExecutorAuthGate:
    """SC-006: Layer 3 gate short-circuits with zero upstream calls."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_executor_returns_auth_required(self, nfa_reg_exec) -> None:
        """lookup(mode='fetch') with session_identity=None returns LookupError(auth_required)."""
        _registry, executor = nfa_reg_exec

        respx.get(url__regex=r".*apis\.data\.go\.kr.*").respond(200, json={})

        inp = LookupFetchInput(
            mode="fetch",
            tool_id="nfa_emergency_info_service",
            params={
                "rsac_gut_fstt_ogid_nm": "천안동남소방서",
                "stmt_ym": "202112",
            },
        )
        result = await lookup(inp, executor=executor)

        assert isinstance(result, LookupError), (
            f"Expected LookupError, got {type(result).__name__}: {result!r}"
        )
        assert result.kind == "error"
        assert result.reason == "auth_required"
        assert result.retryable is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_zero_upstream_calls(self, nfa_reg_exec) -> None:
        """No HTTP calls must be made to data.go.kr when auth gate fires."""
        _registry, executor = nfa_reg_exec

        nfa_route = respx.get(url__regex=r".*1661000.*").respond(200, json={})

        inp = LookupFetchInput(
            mode="fetch",
            tool_id="nfa_emergency_info_service",
            params={
                "rsac_gut_fstt_ogid_nm": "천안동남소방서",
                "stmt_ym": "202112",
            },
        )
        await lookup(inp, executor=executor)

        assert nfa_route.call_count == 0, (
            f"Expected 0 NFA upstream calls, got {nfa_route.call_count}"
        )

    @pytest.mark.asyncio
    @respx.mock
    async def test_auth_required_shape_matches_scenario2_contract(self, nfa_reg_exec) -> None:
        """LookupError shape is the exact stub contract for Scenario 2 (Epic #18)."""
        _registry, executor = nfa_reg_exec

        respx.route().respond(200, json={})

        inp = LookupFetchInput(
            mode="fetch",
            tool_id="nfa_emergency_info_service",
            params={
                "rsac_gut_fstt_ogid_nm": "천안동남소방서",
                "stmt_ym": "202112",
            },
        )
        result = await lookup(inp, executor=executor)

        assert isinstance(result, LookupError)
        assert result.reason == "auth_required"
        assert result.retryable is False


# ---------------------------------------------------------------------------
# BM25 search discoverability
# ---------------------------------------------------------------------------


class TestNfaBm25Discoverability:
    """T016: BM25 lookup(mode='search') must return nfa_emergency_info_service in top-5."""

    @pytest.mark.asyncio
    async def test_korean_query_top5(self, nfa_reg_exec) -> None:
        """Korean query returns nfa_emergency_info_service in top-5 candidates."""
        registry, _executor = nfa_reg_exec

        inp = LookupSearchInput(mode="search", query="119 구급 출동 소방 통계 현황")
        result = await lookup(inp, registry=registry)

        assert isinstance(result, LookupSearchResult)
        tool_ids = [c.tool_id for c in result.candidates[:5]]
        assert "nfa_emergency_info_service" in tool_ids, (
            f"nfa_emergency_info_service not in top-5 for Korean query: {tool_ids}"
        )

    @pytest.mark.asyncio
    async def test_english_query_top5(self, nfa_reg_exec) -> None:
        """English query returns nfa_emergency_info_service in top-5 candidates."""
        registry, _executor = nfa_reg_exec

        inp = LookupSearchInput(
            mode="search", query="NFA emergency dispatch statistics fire station"
        )
        result = await lookup(inp, registry=registry)

        assert isinstance(result, LookupSearchResult)
        tool_ids = [c.tool_id for c in result.candidates[:5]]
        assert "nfa_emergency_info_service" in tool_ids, (
            f"nfa_emergency_info_service not in top-5 for English query: {tool_ids}"
        )


# ---------------------------------------------------------------------------
# Tool metadata integrity
# ---------------------------------------------------------------------------


class TestNfaToolMetadata:
    """Verify NFA_EMERGENCY_INFO_SERVICE_TOOL metadata matches spec 029 §4.1."""

    def test_tool_constants(self) -> None:
        # KOSMOS-invented Spec 033/024/025 fields removed in Epic δ #2295:
        # requires_auth, is_personal_data, auth_level, pipa_class, is_irreversible,
        # dpa_reference — deleted from GovAPITool (Constitution § II).
        assert NFA_EMERGENCY_INFO_SERVICE_TOOL.id == "nfa_emergency_info_service"
        assert NFA_EMERGENCY_INFO_SERVICE_TOOL.cache_ttl_seconds == 86400
        assert NFA_EMERGENCY_INFO_SERVICE_TOOL.auth_type == "api_key"
        assert NFA_EMERGENCY_INFO_SERVICE_TOOL.is_core is False

    def test_fixture_is_valid_json(self) -> None:
        """Synthetic fixture file is valid JSON and has expected keys."""
        data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        body = data["response"]["body"]
        assert body["totalCount"] == 1
        item = body["items"][0]
        assert item["sidoHqOgidNm"] == "충청남도소방본부"
        assert item["rsacGutFsttOgidNm"] == "천안동남소방서"
        assert item["gutYm"] == "202112"

    def test_activity_item_model(self) -> None:
        """NfaActivityItem parses fixture item correctly."""
        data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        item_data = data["response"]["body"]["items"][0]
        item = NfaActivityItem.model_validate(item_data)
        assert item.sidoHqOgidNm == "충청남도소방본부"
        assert item.rsacGutFsttOgidNm == "천안동남소방서"
        assert item.gutYm == "202112"
        assert item.ruptSptmCdNm == "기침"
        assert item.ptntAge == "60~69세"
