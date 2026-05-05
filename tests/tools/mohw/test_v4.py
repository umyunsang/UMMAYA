# SPDX-License-Identifier: Apache-2.0
"""Tests for mohw_welfare_eligibility_search US4 — Spec 2522 T028.

Covers:
- lifeArray=007 happy path (@pytest.mark.live, skipped in CI)
- camelCase serialize unit test (_build_params)
- XML parsing unit test (_parse_xml_response)
- callTp=L + srchKeyCode=003 auto-injection verification
"""

from __future__ import annotations

import textwrap

import pytest
import respx

from kosmos.tools.mohw.welfare_eligibility_search import (
    _MOHW_DESCRIPTION,
    MOHW_WELFARE_ELIGIBILITY_SEARCH_TOOL,
    MohwWelfareEligibilitySearchInput,
    MohwWelfareEligibilitySearchOutput,
    SsisWelfareServiceItem,
    _build_params,
    _parse_xml_response,
    handle,
)

# ---------------------------------------------------------------------------
# Minimal fixtures
# ---------------------------------------------------------------------------

_MINIMAL_XML = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <response>
      <resultCode>0</resultCode>
      <resultMessage>정상 처리되었습니다.</resultMessage>
      <totalCount>1</totalCount>
      <pageNo>1</pageNo>
      <numOfRows>10</numOfRows>
      <servList>
        <servList>
          <servId>WLF00000056</servId>
          <servNm>의료급여(요양비)</servNm>
          <jurMnofNm>보건복지부</jurMnofNm>
          <jurOrgNm>기초의료보장과</jurOrgNm>
          <lifeArray>임신 · 출산</lifeArray>
          <intrsThemaArray>신체건강,임신·출산</intrsThemaArray>
          <trgterIndvdlArray>저소득</trgterIndvdlArray>
          <onapPsbltYn>Y</onapPsbltYn>
          <servDtlLink>https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do?wlfareInfoId=WLF00000056</servDtlLink>
          <servDgst>저소득 임산부 요양비 지원</servDgst>
          <sprtCycNm>1회성</sprtCycNm>
          <srvPvsnNm>현금</srvPvsnNm>
          <rprsCtadr>129</rprsCtadr>
        </servList>
      </servList>
    </response>
""").encode("utf-8")

_MULTI_ITEM_XML = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <response>
      <resultCode>0</resultCode>
      <resultMessage>정상 처리되었습니다.</resultMessage>
      <totalCount>2</totalCount>
      <pageNo>1</pageNo>
      <numOfRows>10</numOfRows>
      <servList>
        <servList>
          <servId>WLF00000001</servId>
          <servNm>서비스A</servNm>
          <jurMnofNm>보건복지부</jurMnofNm>
          <onapPsbltYn>Y</onapPsbltYn>
        </servList>
        <servList>
          <servId>WLF00000002</servId>
          <servNm>서비스B</servNm>
          <jurMnofNm>행정안전부</jurMnofNm>
          <onapPsbltYn>N</onapPsbltYn>
        </servList>
      </servList>
    </response>
""").encode("utf-8")

_EMPTY_XML = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <response>
      <resultCode>0</resultCode>
      <resultMessage>정상 처리되었습니다.</resultMessage>
      <totalCount>0</totalCount>
      <pageNo>1</pageNo>
      <numOfRows>10</numOfRows>
      <servList/>
    </response>
""").encode("utf-8")

_FAKE_API_KEY = "TEST_KEY_XXXX"


# ---------------------------------------------------------------------------
# T028 — camelCase serialize unit test
# ---------------------------------------------------------------------------


class TestBuildParamsSnakeToCamel:
    """_build_params correctly maps snake_case pydantic fields to camelCase wire params."""

    def test_minimal_input_has_fixed_params(self) -> None:
        """Minimal input always emits callTp=L and srchKeyCode=003."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({})
        params = _build_params(inp, _FAKE_API_KEY)

        # T026: fixed injections
        assert params["callTp"] == "L", f"Expected callTp='L', got {params['callTp']!r}"
        assert params["srchKeyCode"] == "003", (
            f"Expected srchKeyCode='003', got {params['srchKeyCode']!r}"
        )

    def test_service_key_included(self) -> None:
        """serviceKey is always in params."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({})
        params = _build_params(inp, _FAKE_API_KEY)
        assert params["serviceKey"] == _FAKE_API_KEY

    def test_life_array_mapped_camel_case(self) -> None:
        """life_array='007' → lifeArray='007' in wire params."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({"life_array": "007"})
        params = _build_params(inp, _FAKE_API_KEY)
        assert "lifeArray" in params, f"lifeArray missing from params: {params}"
        assert params["lifeArray"] == "007"

    def test_search_wrd_mapped_camel_case(self) -> None:
        """search_wrd → searchWrd in wire params."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({"search_wrd": "출산"})
        params = _build_params(inp, _FAKE_API_KEY)
        assert "searchWrd" in params, f"searchWrd missing from params: {params}"
        assert params["searchWrd"] == "출산"

    def test_trgter_indvdl_array_mapped_camel_case(self) -> None:
        """trgter_indvdl_array='020' → trgterIndvdlArray='020'."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({"trgter_indvdl_array": "020"})
        params = _build_params(inp, _FAKE_API_KEY)
        assert "trgterIndvdlArray" in params
        assert params["trgterIndvdlArray"] == "020"

    def test_intrs_thema_array_mapped_camel_case(self) -> None:
        """intrs_thema_array='080' → intrsThemaArray='080'."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({"intrs_thema_array": "080"})
        params = _build_params(inp, _FAKE_API_KEY)
        assert "intrsThemaArray" in params
        assert params["intrsThemaArray"] == "080"

    def test_num_of_rows_mapped_camel_case(self) -> None:
        """num_of_rows=20 → numOfRows='20'."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({"num_of_rows": 20})
        params = _build_params(inp, _FAKE_API_KEY)
        assert "numOfRows" in params
        assert params["numOfRows"] == "20"

    def test_page_no_mapped_camel_case(self) -> None:
        """page_no=3 → pageNo='3'."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({"page_no": 3})
        params = _build_params(inp, _FAKE_API_KEY)
        assert "pageNo" in params
        assert params["pageNo"] == "3"

    def test_age_mapped_when_set(self) -> None:
        """age=30 → age='30' in wire params when set."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({"age": 30})
        params = _build_params(inp, _FAKE_API_KEY)
        assert "age" in params
        assert params["age"] == "30"

    def test_age_absent_when_none(self) -> None:
        """age=None → 'age' must not appear in wire params."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({})
        params = _build_params(inp, _FAKE_API_KEY)
        assert "age" not in params

    def test_onap_psblt_yn_mapped_when_set(self) -> None:
        """onap_psblt_yn='Y' → onapPsbltYn='Y'."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({"onap_psblt_yn": "Y"})
        params = _build_params(inp, _FAKE_API_KEY)
        assert "onapPsbltYn" in params
        assert params["onapPsbltYn"] == "Y"

    def test_optional_fields_absent_when_none(self) -> None:
        """Optional camelCase keys absent when pydantic fields are None."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({})
        params = _build_params(inp, _FAKE_API_KEY)
        for absent in (
            "lifeArray",
            "searchWrd",
            "trgterIndvdlArray",
            "intrsThemaArray",
            "age",
            "onapPsbltYn",
        ):
            assert absent not in params, f"{absent!r} should not appear when value is None"


# ---------------------------------------------------------------------------
# T028 — callTp=L auto-injection (T026 contract)
# ---------------------------------------------------------------------------


class TestCallTpAutoInjection:
    """T026: callTp=L + srchKeyCode=003 are always injected regardless of input."""

    def test_calltP_is_always_L(self) -> None:
        """callTp=L is always present in wire params."""
        for life_code in ("001", "007", None):
            raw: dict[str, object] = {}
            if life_code:
                raw["life_array"] = life_code
            inp = MohwWelfareEligibilitySearchInput.model_validate(raw)
            params = _build_params(inp, _FAKE_API_KEY)
            assert params["callTp"] == "L", (
                f"callTp should always be 'L' (life_array={life_code!r}), got {params['callTp']!r}"
            )

    def test_srch_key_code_always_003(self) -> None:
        """srchKeyCode=003 is always present in wire params."""
        inp = MohwWelfareEligibilitySearchInput.model_validate({"search_wrd": "출산"})
        params = _build_params(inp, _FAKE_API_KEY)
        assert params["srchKeyCode"] == "003", (
            f"srchKeyCode should always be '003', got {params['srchKeyCode']!r}"
        )


# ---------------------------------------------------------------------------
# T028 — XML parsing unit test
# ---------------------------------------------------------------------------


class TestParseXmlResponse:
    """_parse_xml_response correctly parses SSIS NationalWelfarelistV001 XML."""

    def test_minimal_xml_result_code(self) -> None:
        """Minimal XML parses resultCode='0' and resultMessage correctly."""
        parsed = _parse_xml_response(_MINIMAL_XML)
        assert parsed["result_code"] == "0"
        assert "정상" in parsed["result_message"]

    def test_minimal_xml_total_count(self) -> None:
        """totalCount=1 parsed as integer."""
        parsed = _parse_xml_response(_MINIMAL_XML)
        assert parsed["total_count"] == 1

    def test_minimal_xml_item_fields(self) -> None:
        """Service item fields mapped correctly from XML."""
        parsed = _parse_xml_response(_MINIMAL_XML)
        items = parsed["items"]
        assert len(items) == 1
        item = items[0]
        assert item["servId"] == "WLF00000056"
        assert item["servNm"] == "의료급여(요양비)"
        assert item["jurMnofNm"] == "보건복지부"
        assert item["onapPsbltYn"] == "Y"
        assert item["lifeArray"] == "임신 · 출산"

    def test_minimal_xml_pydantic_roundtrip(self) -> None:
        """Parsed dict validates through MohwWelfareEligibilitySearchOutput."""
        parsed = _parse_xml_response(_MINIMAL_XML)
        output = MohwWelfareEligibilitySearchOutput.model_validate(parsed)
        assert output.result_code == "0"
        assert output.total_count == 1
        assert len(output.items) == 1
        item: SsisWelfareServiceItem = output.items[0]
        assert item.servId == "WLF00000056"
        assert item.onapPsbltYn == "Y"

    def test_multi_item_xml_parses_all_items(self) -> None:
        """Two servList items parsed into two result items."""
        parsed = _parse_xml_response(_MULTI_ITEM_XML)
        assert parsed["total_count"] == 2
        assert len(parsed["items"]) == 2
        assert parsed["items"][0]["servId"] == "WLF00000001"
        assert parsed["items"][1]["servId"] == "WLF00000002"

    def test_empty_serv_list_returns_no_items(self) -> None:
        """Empty servList element → items=[] with total_count=0."""
        parsed = _parse_xml_response(_EMPTY_XML)
        assert parsed["total_count"] == 0
        assert parsed["items"] == []

    def test_page_no_and_num_of_rows_parsed(self) -> None:
        """pageNo and numOfRows extracted from XML envelope."""
        parsed = _parse_xml_response(_MINIMAL_XML)
        assert parsed["page_no"] == 1
        assert parsed["num_of_rows"] == 10


# ---------------------------------------------------------------------------
# T028 — handle() with respx mock (non-live)
# ---------------------------------------------------------------------------


class TestHandleMocked:
    """handle() with mocked HTTP verifies param injection and XML parsing end-to-end."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_handle_injects_calltP_and_srch_key_code(self, monkeypatch) -> None:
        """handle() sends callTp=L + srchKeyCode=003 in HTTP request."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", _FAKE_API_KEY)

        captured_params: dict[str, str] = {}

        def _capture(request, **kwargs):
            from urllib.parse import parse_qs, urlparse

            qs = parse_qs(urlparse(str(request.url)).query)
            captured_params.update({k: v[0] for k, v in qs.items()})
            return respx.MockResponse(status_code=200, content=_MINIMAL_XML)

        respx.get(url__regex=r".*B554287.*").mock(side_effect=_capture)

        inp = MohwWelfareEligibilitySearchInput.model_validate({"life_array": "007"})
        await handle(inp)

        assert captured_params.get("callTp") == "L", (
            f"callTp not in request params: {captured_params}"
        )
        assert captured_params.get("srchKeyCode") == "003", (
            f"srchKeyCode not in request params: {captured_params}"
        )
        assert captured_params.get("lifeArray") == "007", (
            f"lifeArray not in request params: {captured_params}"
        )

    @pytest.mark.asyncio
    @respx.mock
    async def test_handle_returns_parsed_items(self, monkeypatch) -> None:
        """handle() returns correctly parsed items from mocked XML response."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", _FAKE_API_KEY)
        respx.get(url__regex=r".*B554287.*").respond(200, content=_MINIMAL_XML)

        inp = MohwWelfareEligibilitySearchInput.model_validate({"life_array": "007"})
        result = await handle(inp)

        # Envelope-ready collection contract (post-2026-05-04 fabrication fix):
        # handle() returns {"kind": "collection", "items": [...], "total_count": N}
        # — result_code / result_message / page_no / num_of_rows are still
        # logged by the parser but no longer exposed via the LLM-facing
        # surface, because the discriminated LookupOutput envelope only
        # carries kind + items + total_count + meta.
        assert result["kind"] == "collection"
        assert result["total_count"] == 1
        items = result["items"]
        assert len(items) == 1
        assert items[0]["servId"] == "WLF00000056"
        assert items[0]["jurMnofNm"] == "보건복지부"


# ---------------------------------------------------------------------------
# T028 — live happy path: lifeArray=007 (임신·출산) returns ≥ 5 results
# ---------------------------------------------------------------------------


@pytest.mark.live
class TestMohwV4LifeArray007Live:
    """Live query: lifeArray=007 (임신·출산) → ≥ 5 welfare services returned.

    Skipped in CI by default. Run with:
        uv run pytest -m live tests/tools/mohw/test_v4.py

    Requires KOSMOS_DATA_GO_KR_API_KEY to be set.
    Evidence: /tmp/kosmos-evidence/koroad-mohw-evidence.md (totalCount=21 for lifeArray=007).
    """

    @pytest.mark.asyncio
    async def test_life_array_007_returns_at_least_five_services(self) -> None:
        """Live SSIS call with lifeArray=007 returns ≥ 5 welfare service records."""
        inp = MohwWelfareEligibilitySearchInput.model_validate(
            {"life_array": "007", "num_of_rows": 10}
        )
        result = await handle(inp)

        assert result["result_code"] in ("0", "00"), (
            f"Expected resultCode='0', got {result['result_code']!r}"
        )
        items = result["items"]
        assert len(items) >= 5, (
            f"Expected ≥ 5 items for lifeArray=007 (임신·출산), got {len(items)}. "
            f"total_count={result['total_count']}"
        )
        for item in items:
            assert item.get("servId"), f"Item missing servId: {item}"
            assert item.get("servNm"), f"Item missing servNm: {item}"

    @pytest.mark.asyncio
    async def test_life_array_007_total_count_at_least_ten(self) -> None:
        """Live SSIS call totalCount for lifeArray=007 is at least 10 (evidence: 21)."""
        inp = MohwWelfareEligibilitySearchInput.model_validate(
            {"life_array": "007", "num_of_rows": 1}
        )
        result = await handle(inp)

        assert result["total_count"] >= 10, (
            f"Expected totalCount ≥ 10 for lifeArray=007, got {result['total_count']}. "
            "Evidence file showed 21 services."
        )


# ---------------------------------------------------------------------------
# T028 — llm_description 5-section structure assertions
# ---------------------------------------------------------------------------


class TestMohwV4Description:
    """_MOHW_DESCRIPTION 5-section structural assertions."""

    def test_description_non_empty(self) -> None:
        """_MOHW_DESCRIPTION is a non-empty string."""
        assert isinstance(_MOHW_DESCRIPTION, str)
        assert len(_MOHW_DESCRIPTION) > 50

    def test_description_mentions_ssis(self) -> None:
        """Section 1 purpose: mentions SSIS or bokjiro."""
        desc = _MOHW_DESCRIPTION.lower()
        assert "ssis" in desc or "bokjiro" in desc

    def test_description_mentions_life_array_codes(self) -> None:
        """Section 3 short_reference: contains MOHW_LIFE_STAGE_SHORT_REFERENCE inline."""
        assert "007" in _MOHW_DESCRIPTION
        assert "임신" in _MOHW_DESCRIPTION

    def test_description_mentions_calltP_auto_inject(self) -> None:
        """Section 2 input_quirk: callTp auto-injection noted."""
        assert "callTp" in _MOHW_DESCRIPTION

    def test_description_mentions_xml_response(self) -> None:
        """Section 4 domain_quirk: XML response format noted."""
        assert "XML" in _MOHW_DESCRIPTION or "xml" in _MOHW_DESCRIPTION.lower()

    def test_description_five_sections_by_double_newline(self) -> None:
        """build_description_v4 joins 5 sections with double newline → 4 separators."""
        sections = _MOHW_DESCRIPTION.split("\n\n")
        assert len(sections) >= 4, (
            f"Expected ≥ 4 double-newline separators (5 sections), got {len(sections) - 1}"
        )

    def test_tool_llm_description_matches_built_description(self) -> None:
        """MOHW_WELFARE_ELIGIBILITY_SEARCH_TOOL.llm_description equals _MOHW_DESCRIPTION."""
        assert MOHW_WELFARE_ELIGIBILITY_SEARCH_TOOL.llm_description == _MOHW_DESCRIPTION

    def test_output_schema_is_envelope_placeholder(self) -> None:
        """output_schema is an envelope placeholder; handler emits envelope-ready dict.

        Updated 2026-05-04 (C-class fabrication fix): the strict
        MohwWelfareEligibilitySearchOutput remains as the documentation
        contract, but the wire surface is now ``_MohwPlaceholderOutput``
        so the envelope-ready ``{"kind": "collection", ...}`` dict can
        flow into envelope.normalize() — see module docstring for context.
        """
        from kosmos.tools.mohw.welfare_eligibility_search import _MohwPlaceholderOutput

        assert MOHW_WELFARE_ELIGIBILITY_SEARCH_TOOL.output_schema is _MohwPlaceholderOutput
        # Documentation contract preserved
        assert MohwWelfareEligibilitySearchOutput.__name__ == "MohwWelfareEligibilitySearchOutput"

    def test_citizen_facing_gate_is_read_only(self) -> None:
        """US4 real impl: citizen_facing_gate must be 'read-only' (no auth gate)."""
        policy = MOHW_WELFARE_ELIGIBILITY_SEARCH_TOOL.policy
        assert policy is not None
        assert policy.citizen_facing_gate == "read-only", (
            f"Expected 'read-only' gate, got {policy.citizen_facing_gate!r}"
        )
