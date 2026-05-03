# SPDX-License-Identifier: Apache-2.0
"""Tests for mohw_welfare_eligibility_search adapter — spec 029 US2 + US3.

Covers:
- Input schema happy-path and error-path validation (T024)
- Layer3GateViolation raised when handle() is called directly (T024)
- Executor returns LookupError(reason="auth_required") with zero HTTP calls (T024)
- BM25 search returns mohw_welfare_eligibility_search in top-5 (T024)
- Scenario 3 contract freeze: auth_required shape is exact (T026)
"""

from __future__ import annotations

import json
import pathlib

import pytest
import respx
from pydantic import ValidationError

from kosmos.tools.errors import Layer3GateViolation
from kosmos.tools.executor import ToolExecutor
from kosmos.tools.lookup import lookup
from kosmos.tools.models import (
    LookupError,  # noqa: A004
    LookupFetchInput,
    LookupSearchInput,
    LookupSearchResult,
)
from kosmos.tools.registry import ToolRegistry
from kosmos.tools.ssis.codes import (
    CallType,
    IntrsThemaCode,
    LifeArrayCode,
    OrderBy,
    SrchKeyCode,
)
from kosmos.tools.ssis.welfare_eligibility_search import (
    MOHW_WELFARE_ELIGIBILITY_SEARCH_TOOL,
    MohwWelfareEligibilitySearchInput,
    SsisWelfareServiceItem,
    handle,
    register,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_PATH = (
    pathlib.Path(__file__).parent.parent.parent
    / "fixtures"
    / "ssis"
    / "mohw_welfare_eligibility_search.json"
)


@pytest.fixture(scope="module")
def mohw_reg_exec():
    """Module-scope registry + executor with only MOHW registered."""
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)
    return registry, executor


# ---------------------------------------------------------------------------
# Input schema — happy-path tests
# ---------------------------------------------------------------------------


class TestMohwInputSchemaHappy:
    """MohwWelfareEligibilitySearchInput valid construction tests."""

    def test_minimal_default_input(self) -> None:
        """All-defaults input: only enum defaults applied."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({})
        assert inp.srch_key_code == SrchKeyCode.all_fields
        assert inp.order_by == OrderBy.popular
        assert inp.call_tp == CallType.list_
        assert inp.page_no == 1
        assert inp.num_of_rows == 10
        assert inp.search_wrd is None

    def test_search_wrd_string(self) -> None:
        """search_wrd keyword accepted."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({"search_wrd": "출산"})
        assert inp.search_wrd == "출산"

    def test_life_array_by_enum_value(self) -> None:
        """life_array accepts enum value '007' for 임신·출산."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({"life_array": "007"})
        assert inp.life_array == LifeArrayCode.pregnancy_birth

    def test_intrs_thema_array_080(self) -> None:
        """intrs_thema_array '080' is authoritative 임신·출산 code (not '010')."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({"intrs_thema_array": "080"})
        assert inp.intrs_thema_array == IntrsThemaCode.pregnancy_birth

    def test_combined_codes(self) -> None:
        """life_array + intrs_thema_array together accepted."""
        inp = MohwWelfareEligibilitySearchInput.model_validate(
            {
                "life_array": "007",
                "intrs_thema_array": "080",
            }
        )
        assert inp.life_array == LifeArrayCode.pregnancy_birth
        assert inp.intrs_thema_array == IntrsThemaCode.pregnancy_birth

    def test_age_zero_is_valid(self) -> None:
        """age=0 is within ge=0 bound."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({"age": 0})
        assert inp.age == 0

    def test_age_max_boundary(self) -> None:
        """age=150 is within le=150 bound."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({"age": 150})
        assert inp.age == 150

    def test_num_of_rows_max_boundary(self) -> None:
        """num_of_rows=500 is allowed (SSIS API contract max)."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({"num_of_rows": 500})
        assert inp.num_of_rows == 500

    def test_page_no_max_boundary(self) -> None:
        """page_no=1000 is allowed (SSIS cap)."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({"page_no": 1000})
        assert inp.page_no == 1000

    def test_onap_psblt_yn_y(self) -> None:
        """onap_psblt_yn='Y' is accepted."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({"onap_psblt_yn": "Y"})
        assert inp.onap_psblt_yn == "Y"

    def test_onap_psblt_yn_n(self) -> None:
        """onap_psblt_yn='N' is accepted."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({"onap_psblt_yn": "N"})
        assert inp.onap_psblt_yn == "N"


# ---------------------------------------------------------------------------
# Input schema — error-path tests
# ---------------------------------------------------------------------------


class TestMohwInputSchemaErrors:
    """MohwWelfareEligibilitySearchInput rejection tests."""

    def test_life_array_invalid_code(self) -> None:
        """life_array='999' is not a valid LifeArrayCode enum value."""
        with pytest.raises(ValidationError):
            MohwWelfareEligibilitySearchInput.model_validate({"life_array": "999"})

    def test_age_exceeds_max(self) -> None:
        """age=200 violates le=150."""
        with pytest.raises(ValidationError):
            MohwWelfareEligibilitySearchInput.model_validate({"age": 200})

    def test_age_below_min(self) -> None:
        """age=-1 violates ge=0."""
        with pytest.raises(ValidationError):
            MohwWelfareEligibilitySearchInput.model_validate({"age": -1})

    def test_extra_field_forbidden(self) -> None:
        """extra='forbid' must reject unknown fields."""
        with pytest.raises(ValidationError):
            MohwWelfareEligibilitySearchInput.model_validate(
                {
                    "search_wrd": "x",
                    "unknown_field": "y",
                }
            )

    def test_num_of_rows_exceeds_max(self) -> None:
        """num_of_rows=501 exceeds le=500."""
        with pytest.raises(ValidationError):
            MohwWelfareEligibilitySearchInput.model_validate({"num_of_rows": 501})

    def test_num_of_rows_below_min(self) -> None:
        """num_of_rows=0 violates ge=1."""
        with pytest.raises(ValidationError):
            MohwWelfareEligibilitySearchInput.model_validate({"num_of_rows": 0})

    def test_page_no_below_min(self) -> None:
        """page_no=0 violates ge=1."""
        with pytest.raises(ValidationError):
            MohwWelfareEligibilitySearchInput.model_validate({"page_no": 0})

    def test_page_no_exceeds_max(self) -> None:
        """page_no=1001 exceeds le=1000."""
        with pytest.raises(ValidationError):
            MohwWelfareEligibilitySearchInput.model_validate({"page_no": 1001})

    def test_intrs_thema_array_invalid_code(self) -> None:
        """intrs_thema_array='999' is not a valid IntrsThemaCode."""
        with pytest.raises(ValidationError):
            MohwWelfareEligibilitySearchInput.model_validate({"intrs_thema_array": "999"})

    def test_onap_psblt_yn_invalid(self) -> None:
        """onap_psblt_yn='X' is not Literal['Y','N']."""
        with pytest.raises(ValidationError):
            MohwWelfareEligibilitySearchInput.model_validate({"onap_psblt_yn": "X"})


# ---------------------------------------------------------------------------
# Layer 3 gate — handle() must raise Layer3GateViolation
# ---------------------------------------------------------------------------


class TestMohwLayer3Gate:
    """Verify handle() raises Layer3GateViolation (defence-in-depth)."""

    @pytest.mark.asyncio
    async def test_handle_raises_layer3_gate_violation(self) -> None:
        """handle() with valid input must always raise Layer3GateViolation."""
        inp = MohwWelfareEligibilitySearchInput.model_validate(
            {
                "search_wrd": "출산",
            }
        )
        with pytest.raises(Layer3GateViolation) as exc_info:
            await handle(inp)

        assert "mohw_welfare_eligibility_search" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Executor auth-gate — zero upstream HTTP calls
# ---------------------------------------------------------------------------


class TestMohwExecutorAuthGate:
    """SC-006 (pre-US4 stub): auth gate tests — superseded by Spec 2522 US4.

    Spec 2522 US4 changed citizen_facing_gate from "login" to "read-only"
    (live evidence: NationalWelfarelistV001 is a public API-key-only catalog).
    The two auth_required tests below are skipped; new behavior is tested in
    tests/tools/mohw/test_v4.py::TestMohwV4Description::test_citizen_facing_gate_is_read_only.
    """

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Spec 2522 US4: citizen_facing_gate changed to 'read-only'; auth_required gate no longer applies. See tests/tools/mohw/test_v4.py.")
    @respx.mock
    async def test_executor_returns_auth_required(self, mohw_reg_exec) -> None:
        """[SKIPPED — Spec 2522 US4 supersedes] lookup(mode='fetch') with session_identity=None returns LookupError(auth_required)."""
        _registry, executor = mohw_reg_exec

        respx.get(url__regex=r".*apis\.data\.go\.kr.*").respond(200, text="<response/>")

        inp = LookupFetchInput(
            mode="fetch",
            tool_id="mohw_welfare_eligibility_search",
            params={"search_wrd": "출산"},
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
    async def test_zero_upstream_calls(self, mohw_reg_exec) -> None:
        """No HTTP calls must be made to SSIS endpoint when auth gate fires."""
        _registry, executor = mohw_reg_exec

        ssis_route = respx.get(url__regex=r".*B554287.*").respond(200, text="<response/>")

        inp = LookupFetchInput(
            mode="fetch",
            tool_id="mohw_welfare_eligibility_search",
            params={"search_wrd": "출산"},
        )
        await lookup(inp, executor=executor)

        assert ssis_route.call_count == 0, (
            f"Expected 0 SSIS upstream calls, got {ssis_route.call_count}"
        )


# ---------------------------------------------------------------------------
# T026 — Scenario 3 contract freeze
# ---------------------------------------------------------------------------


class TestMohwScenario3Contract:
    """T026 (pre-US4 stub): Scenario 3 contract — superseded by Spec 2522 US4.

    Spec 2522 US4 replaced the auth_required gate with a real handle() implementation
    (citizen_facing_gate="read-only"). The auth_required LookupError shape is no longer
    the Scenario 3 contract. Kept as historical reference; test is skipped.
    """

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Spec 2522 US4: citizen_facing_gate='read-only'; auth_required scenario no longer valid. Epic #19 must update E2E contract.")
    @respx.mock
    async def test_executor_auth_required_matches_scenario3_contract(self, mohw_reg_exec) -> None:
        """[SKIPPED — Spec 2522 US4 supersedes] LookupError shape for unauthenticated MOHW fetch."""
        _registry, executor = mohw_reg_exec

        respx.route().respond(200, json={})

        inp = LookupFetchInput(
            mode="fetch",
            tool_id="mohw_welfare_eligibility_search",
            params={"search_wrd": "출산"},
        )
        result = await lookup(inp, executor=executor)

        # Shape contract for Scenario 3 E2E replay (pre-US4):
        assert isinstance(result, LookupError)
        assert result.reason == "auth_required", (
            f"Scenario 3 contract violation: expected reason='auth_required', got {result.reason!r}"
        )
        assert result.retryable is False, (
            f"Scenario 3 contract violation: expected retryable=False, got {result.retryable!r}"
        )
        assert result.kind == "error", (
            f"Scenario 3 contract violation: expected kind='error', got {result.kind!r}"
        )


# ---------------------------------------------------------------------------
# BM25 search discoverability
# ---------------------------------------------------------------------------


class TestMohwBm25Discoverability:
    """T024: BM25 lookup(mode='search') must return mohw_welfare_eligibility_search in top-5."""

    @pytest.mark.asyncio
    async def test_korean_query_top5(self, mohw_reg_exec) -> None:
        """Korean query returns mohw_welfare_eligibility_search in top-5 candidates."""
        registry, _executor = mohw_reg_exec

        inp = LookupSearchInput(mode="search", query="출산 보조금 복지 혜택")
        result = await lookup(inp, registry=registry)

        assert isinstance(result, LookupSearchResult)
        tool_ids = [c.tool_id for c in result.candidates[:5]]
        assert "mohw_welfare_eligibility_search" in tool_ids, (
            f"mohw_welfare_eligibility_search not in top-5 for Korean query: {tool_ids}"
        )

    @pytest.mark.asyncio
    async def test_english_query_top5(self, mohw_reg_exec) -> None:
        """English query returns mohw_welfare_eligibility_search in top-5 candidates."""
        registry, _executor = mohw_reg_exec

        inp = LookupSearchInput(mode="search", query="welfare benefit eligibility SSIS childbirth")
        result = await lookup(inp, registry=registry)

        assert isinstance(result, LookupSearchResult)
        tool_ids = [c.tool_id for c in result.candidates[:5]]
        assert "mohw_welfare_eligibility_search" in tool_ids, (
            f"mohw_welfare_eligibility_search not in top-5 for English query: {tool_ids}"
        )


# ---------------------------------------------------------------------------
# Tool metadata integrity
# ---------------------------------------------------------------------------


class TestMohwToolMetadata:
    """Verify MOHW_WELFARE_ELIGIBILITY_SEARCH_TOOL metadata matches spec 029 §4.2."""

    def test_tool_constants(self) -> None:
        # KOSMOS-invented Spec 033/024/025 fields removed in Epic δ #2295:
        # requires_auth, is_personal_data, auth_level, pipa_class, is_irreversible,
        # dpa_reference — deleted from GovAPITool (Constitution § II).
        assert MOHW_WELFARE_ELIGIBILITY_SEARCH_TOOL.id == "mohw_welfare_eligibility_search"
        assert MOHW_WELFARE_ELIGIBILITY_SEARCH_TOOL.cache_ttl_seconds == 0
        assert MOHW_WELFARE_ELIGIBILITY_SEARCH_TOOL.auth_type == "api_key"
        assert MOHW_WELFARE_ELIGIBILITY_SEARCH_TOOL.is_core is False

    def test_fixture_is_valid_json(self) -> None:
        """Synthetic fixture file is valid JSON with expected welfare service fields."""
        data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        assert data["result_code"] == "0"
        assert data["total_count"] == 1
        item = data["items"][0]
        assert item["servId"] == "WLF0000001188"
        assert item["servNm"] == "출산가정 방문서비스"
        assert item["jurMnofNm"] == "보건복지부"

    def test_welfare_item_model(self) -> None:
        """SsisWelfareServiceItem parses fixture item correctly."""
        data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        item_data = data["items"][0]
        item = SsisWelfareServiceItem.model_validate(item_data)
        assert item.servId == "WLF0000001188"
        assert item.servNm == "출산가정 방문서비스"
        assert item.jurMnofNm == "보건복지부"
        assert item.onapPsbltYn == "Y"
