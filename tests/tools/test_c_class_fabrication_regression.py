# SPDX-License-Identifier: Apache-2.0
"""C-class citizen mis-info regression tests.

Anchors the four 2026-05-04 fabrication-trigger fixes against future drift:

1. **NFA `sptMvmnDtc` float drift** — the live data.go.kr endpoint returns
   ``0.5`` (JSON float) but the strict ``str``-only model raised
   ValidationError. The executor masked the error as "Tool execution
   failed." and K-EXAONE fabricated 강남소방서 119 statistics from prior
   knowledge. The fix loosens vital-sign / distance fields to
   ``str | float | int | None`` and skips malformed rows individually
   instead of failing the whole call.

2. **MOHW XML envelope mismatch** — the live SSIS endpoint emits
   ``<wantedList>`` as the root with ``<servList>`` siblings, but the
   parser assumed the legacy ``<response><servList><servList>...`` nested
   shape and extracted zero items. The empty list flowed through output
   validation, the executor raised ``EnvelopeNormalizationError`` masked
   as "Response processing failed.", and K-EXAONE fabricated 12 welfare
   services with stale ``wlfareInfoId`` values pointing at wrong bokjiro
   service detail pages. The fix supports both envelopes.

3. **Envelope-ready handler contract** — both NFA and MOHW handlers were
   returning the raw API response shape (no ``kind`` discriminator),
   which made ``envelope.normalize()`` raise EnvelopeNormalizationError.
   The fix mirrors the working HIRA / KOROAD / NMC pattern by emitting
   ``{"kind": "collection", "items": [...], "total_count": N}``.

4. **Generic error masking violates Anthropic tool-use guidance** —
   "Tool execution failed." and "Response processing failed." are exactly
   the kind of opaque error message that
   https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls
   warns against. The fix replaces them with instructive envelope.message
   strings that name the tool, name the exception class + first 240
   chars of detail, and explicitly forbid prior-knowledge fabrication.
"""

from __future__ import annotations

import asyncio
import textwrap
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from kosmos.tools.errors import LookupErrorReason
from kosmos.tools.mohw.welfare_eligibility_search import (
    MohwWelfareEligibilitySearchInput,
    _parse_xml_response,
)
from kosmos.tools.mohw.welfare_eligibility_search import handle as mohw_handle
from kosmos.tools.nfa119.emergency_info_service import (
    NfaActivityItem,
    NfaConditionItem,
    NfaEmergencyInfoServiceInput,
    NfaEmgOperation,
    _parse_response,
)
from kosmos.tools.nfa119.emergency_info_service import handle as nfa_handle


# ---------------------------------------------------------------------------
# Fix #1: NFA sptMvmnDtc float drift
# ---------------------------------------------------------------------------


class TestNfaFloatDrift:
    """Regression: NFA item models accept JSON float for distance / vitals."""

    def test_sptMvmnDtc_accepts_float(self) -> None:
        """0.5 (float) was the exact value that triggered the 2026-05-04 fab."""
        item = NfaActivityItem(
            sidoHqOgidNm="서울소방재난본부",
            rsacGutFsttOgidNm="강남소방서",
            gutYm="202504",
            sptMvmnDtc=0.5,
        )
        assert item.sptMvmnDtc == 0.5

    def test_sptMvmnDtc_accepts_int(self) -> None:
        item = NfaActivityItem(
            sidoHqOgidNm="서울소방재난본부",
            rsacGutFsttOgidNm="강남소방서",
            gutYm="202504",
            sptMvmnDtc=2,
        )
        assert item.sptMvmnDtc == 2

    def test_sptMvmnDtc_accepts_string(self) -> None:
        item = NfaActivityItem(
            sidoHqOgidNm="서울소방재난본부",
            rsacGutFsttOgidNm="강남소방서",
            gutYm="202504",
            sptMvmnDtc="0.5",
        )
        assert item.sptMvmnDtc == "0.5"

    def test_sptMvmnDtc_accepts_none(self) -> None:
        item = NfaActivityItem(
            sidoHqOgidNm="서울소방재난본부",
            rsacGutFsttOgidNm="강남소방서",
            gutYm="202504",
        )
        assert item.sptMvmnDtc is None

    def test_vital_signs_accept_floats(self) -> None:
        """Blood pressure / heart rate / oxygen / temperature can be JSON floats."""
        item = NfaConditionItem(
            ruptSptmCdNm="어지러움",
            sidoHqOgidNm="서울소방재난본부",
            rsacGutFsttOgidNm="강남소방서",
            stmtYm="202504",
            lwsBpsr=70,
            topBpsr=120,
            ptntHbco=85,
            ptntBfco=18,
            ptntOsv=98.5,
            ptntBht=36.6,
        )
        assert item.ptntOsv == 98.5
        assert item.ptntBht == 36.6

    def test_per_item_failure_does_not_kill_entire_call(self, monkeypatch) -> None:
        """A single malformed row drops that row only, not the whole response.

        2026-05-04 incident: one corrupt ``sptMvmnDtc`` field in the middle of
        a 2,461-row response failed the entire call → "Tool execution failed."
        → fabrication. Now corrupt rows are logged + skipped, citizen still
        sees the rest of the data.
        """
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", "x")
        payload = {
            "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE"},
            "pageNo": 1,
            "numOfRows": 3,
            "totalCount": 3,
            "body": {
                "items": [
                    {
                        "sidoHqOgidNm": "서울소방재난본부",
                        "rsacGutFsttOgidNm": "강남소방서",
                        "gutYm": "202504",
                        "sptMvmnDtc": 0.5,
                    },
                    # Corrupt row — required field missing
                    {"some_unrelated_field": "garbage"},
                    {
                        "sidoHqOgidNm": "서울소방재난본부",
                        "rsacGutFsttOgidNm": "강남소방서",
                        "gutYm": "202504",
                        "sptMvmnDtc": "1.2",
                    },
                ]
            },
        }
        out = _parse_response(payload, NfaEmgOperation.activity.value)
        assert len(out.items) == 2  # corrupt row dropped, two survivors


# ---------------------------------------------------------------------------
# Fix #2: MOHW XML envelope drift
# ---------------------------------------------------------------------------


class TestMohwEnvelopeDrift:
    """Regression: parser handles BOTH wantedList (live) and response-nested (legacy)."""

    LIVE_WANTEDLIST_XML = textwrap.dedent(
        """\
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <wantedList>
          <totalCount>15</totalCount>
          <pageNo>1</pageNo>
          <numOfRows>3</numOfRows>
          <resultCode>0</resultCode>
          <resultMessage>SUCCESS</resultMessage>
          <servList>
            <servId>WLF00000061</servId>
            <servNm>의료급여임신.출산진료비지원</servNm>
            <jurMnofNm>보건복지부</jurMnofNm>
            <servDtlLink>https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do?wlfareInfoId=WLF00000061</servDtlLink>
          </servList>
          <servList>
            <servId>WLF00001088</servId>
            <servNm>고위험 임산부 의료비 지원</servNm>
            <jurMnofNm>보건복지부</jurMnofNm>
          </servList>
          <servList>
            <servId>WLF00000056</servId>
            <servNm>의료급여(요양비)</servNm>
            <jurMnofNm>보건복지부</jurMnofNm>
          </servList>
        </wantedList>
        """
    ).encode("utf-8")

    LEGACY_RESPONSE_XML = textwrap.dedent(
        """\
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
            </servList>
          </servList>
        </response>
        """
    ).encode("utf-8")

    def test_live_wantedList_envelope_extracts_all_items(self) -> None:
        """The exact 2026-05-04 incident shape — must extract 3 items, not 0."""
        parsed = _parse_xml_response(self.LIVE_WANTEDLIST_XML)
        assert parsed["result_code"] == "0"
        assert parsed["total_count"] == 15
        assert len(parsed["items"]) == 3
        ids = [item["servId"] for item in parsed["items"]]
        assert ids == ["WLF00000061", "WLF00001088", "WLF00000056"]

    def test_legacy_response_envelope_still_works(self) -> None:
        """Backward compat — older fixtures and the NIA-IFT v2.2 doc shape."""
        parsed = _parse_xml_response(self.LEGACY_RESPONSE_XML)
        assert parsed["result_code"] == "0"
        assert parsed["total_count"] == 1
        assert len(parsed["items"]) == 1
        assert parsed["items"][0]["servId"] == "WLF00000056"

    def test_zero_items_returns_empty_list_not_crash(self) -> None:
        """Empty result is empty — never raises, never silently fabricates."""
        empty_xml = textwrap.dedent(
            """\
            <?xml version="1.0" encoding="UTF-8"?>
            <wantedList>
              <totalCount>0</totalCount>
              <pageNo>1</pageNo>
              <numOfRows>10</numOfRows>
              <resultCode>0</resultCode>
              <resultMessage>SUCCESS</resultMessage>
            </wantedList>
            """
        ).encode("utf-8")
        parsed = _parse_xml_response(empty_xml)
        assert parsed["total_count"] == 0
        assert parsed["items"] == []


# ---------------------------------------------------------------------------
# Fix #3: Envelope-ready handler contract (kind discriminator)
# ---------------------------------------------------------------------------


class TestEnvelopeReadyHandlers:
    """Regression: NFA + MOHW handlers emit kind='collection' for envelope.normalize."""

    @pytest.mark.asyncio
    async def test_nfa_handle_emits_kind_collection(self, monkeypatch) -> None:
        """Without ``kind``, envelope.normalize raises and triggers fabrication."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", "x")
        # Mock the http response
        client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "application/json;charset=UTF-8"}
        mock_response.json.return_value = {
            "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE"},
            "pageNo": 1,
            "numOfRows": 1,
            "totalCount": 1,
            "body": {
                "items": [
                    {
                        "sidoHqOgidNm": "서울소방재난본부",
                        "rsacGutFsttOgidNm": "강남소방서",
                        "gutYm": "202504",
                        "sptMvmnDtc": 0.5,
                        "ruptOccrPlcCdNm": "집",
                    }
                ]
            },
        }
        mock_response.raise_for_status = MagicMock()
        client.get = AsyncMock(return_value=mock_response)

        inp = NfaEmergencyInfoServiceInput(
            sido_hq_ogid_nm="서울소방재난본부",
            rsac_gut_fstt_ogid_nm="강남소방서",
            stmt_ym="202504",
            operation="getEmgencyActivityInfo",
            num_of_rows=1,
        )
        result = await nfa_handle(inp, client=client)
        assert result["kind"] == "collection"
        assert result["total_count"] == 1
        assert len(result["items"]) == 1
        # Must NOT contain raw API metadata that breaks envelope discrimination
        assert "result_code" not in result
        assert "operation" not in result

    @pytest.mark.asyncio
    async def test_mohw_handle_emits_kind_collection(self, monkeypatch) -> None:
        """Without ``kind``, envelope.normalize raises EnvelopeNormalizationError."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", "x")
        client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.content = TestMohwEnvelopeDrift.LIVE_WANTEDLIST_XML
        mock_response.raise_for_status = MagicMock()
        client.get = AsyncMock(return_value=mock_response)

        inp = MohwWelfareEligibilitySearchInput(life_array="007", num_of_rows=3)
        result = await mohw_handle(inp, client=client)
        assert result["kind"] == "collection"
        assert result["total_count"] == 15
        assert len(result["items"]) == 3
        assert "result_code" not in result


# ---------------------------------------------------------------------------
# Fix #4: Executor instructive error messages (Anthropic tool-use guidance)
# ---------------------------------------------------------------------------


class TestInstructiveErrorMessages:
    """Regression: executor.invoke emits instructive envelope.message strings.

    Anthropic guidance:
        "Write instructive error messages. Instead of generic errors like
         'failed', include what went wrong and what Claude should try next."
        — https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls

    The opaque "Tool execution failed." / "Response processing failed."
    strings were the documented citizen-mis-info trigger.
    """

    @pytest.mark.asyncio
    async def test_adapter_exception_includes_class_and_detail(self, monkeypatch) -> None:
        """envelope.message should name the exception class + first 240 chars."""
        from kosmos.tools.executor import ToolExecutor
        from kosmos.tools.registry import ToolRegistry

        # Use any real registered tool; the Layer-3 gate must allow it.
        registry = ToolRegistry()
        executor = ToolExecutor(registry)

        from kosmos.tools.register_all import register_all_tools

        register_all_tools(registry, executor)

        # Replace HIRA adapter with a failing one
        async def _failing(_inp):
            raise httpx.ConnectError("simulated upstream timeout")

        executor.register_adapter("hira_hospital_search", _failing)

        result = await executor.invoke(
            tool_id="hira_hospital_search",
            params={"xPos": 127.0, "yPos": 37.5, "radius": 1500},
            request_id="rid-test-1",
            session_identity="anon",
        )
        # Should be a LookupError envelope
        assert getattr(result, "kind", None) == "error"
        msg = getattr(result, "message", "")
        # Must NOT be the old opaque string
        assert msg != "Tool execution failed."
        # Must NAME the tool, the exception class, and the fabrication directive
        assert "hira_hospital_search" in msg
        assert "ConnectError" in msg
        assert "fabricate" in msg.lower() or "official" in msg.lower()

    @pytest.mark.asyncio
    async def test_envelope_mismatch_includes_detail(self, monkeypatch) -> None:
        """envelope.message for normalization failure also forbids fabrication."""
        from kosmos.tools.executor import ToolExecutor
        from kosmos.tools.registry import ToolRegistry

        registry = ToolRegistry()
        executor = ToolExecutor(registry)

        from kosmos.tools.register_all import register_all_tools

        register_all_tools(registry, executor)

        # Adapter returns a dict that is NOT envelope-shaped (no `kind`)
        async def _bad_envelope(_inp):
            return {"unexpected_field": "no_kind_discriminator"}

        executor.register_adapter("hira_hospital_search", _bad_envelope)

        result = await executor.invoke(
            tool_id="hira_hospital_search",
            params={"xPos": 127.0, "yPos": 37.5, "radius": 1500},
            request_id="rid-test-2",
            session_identity="anon",
        )
        assert getattr(result, "kind", None) == "error"
        msg = getattr(result, "message", "")
        assert msg != "Response processing failed."
        assert "hira_hospital_search" in msg
        assert "envelope schema" in msg
        assert "fabricate" in msg.lower() or "official" in msg.lower()


# ---------------------------------------------------------------------------
# Fix #4 + system prompt: directive integrity check
# ---------------------------------------------------------------------------


class TestSystemPromptFabricationDirective:
    """Regression: prompts/system_v1.md carries the strengthened directive."""

    def test_critical_directive_present(self) -> None:
        from pathlib import Path

        prompt_path = (
            Path(__file__).parent.parent.parent / "prompts" / "system_v1.md"
        )
        prompt = prompt_path.read_text(encoding="utf-8")
        # The strengthened directive heading
        assert "시민 안전 directive" in prompt
        # The 4-part response format must be enforceable
        assert "필수 응답 형식" in prompt
        # Must list at least the safety-critical agency channels
        assert "복지로" in prompt or "bokjiro" in prompt
        assert "E-Gen" in prompt or "e-gen" in prompt
        assert "119" in prompt
        # Must explicitly forbid the fabrication patterns observed on 2026-05-04
        assert "fabricate" in prompt.lower() or "fabrication" in prompt.lower()
        assert "기존 정보로는" in prompt or "일반적으로" in prompt

    def test_manifest_sha_matches_current_prompt(self) -> None:
        """Spec 026 PromptLoader fail-closed at boot — manifest SHA must match."""
        import hashlib
        from pathlib import Path

        import yaml

        prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        manifest_path = prompts_dir / "manifest.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        sys_entry = next(
            e for e in manifest["entries"] if e["prompt_id"] == "system_v1"
        )
        actual_sha = hashlib.sha256(
            (prompts_dir / sys_entry["path"]).read_bytes()
        ).hexdigest()
        assert sys_entry["sha256"] == actual_sha


if __name__ == "__main__":
    asyncio.run(asyncio.sleep(0))  # smoke
