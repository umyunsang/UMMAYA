# SPDX-License-Identifier: Apache-2.0
"""KMA v4 unit tests — description token budget + 5-section structure + ORDERING absence.

Tests:
  1. All 6 KMA tools have descriptions ≤ 500 tokens (data-model.md Constraint).
  2. Each description has exactly 5 sections (split on double-newline).
  3. Section 3 of every tool contains a 17 광역시도 reference table (서울=... 형식).
  4. Section 5 of every tool contains "chain" guidance (autonomous, cross-domain, etc.).
  5. kma_grid_short_reference() output is inlined in grid-based tools (S3 check).
  6. ORDERING block is NOT emitted for tools that lack nx/ny required fields.
     (T010 verification: _build_available_adapters_suffix emits ORDERING only for
     tools with nx+ny in required — kma_weather_alert_status has neither.)
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Token estimation helper (mirrored from _description_template for isolation)
# ---------------------------------------------------------------------------


def _estimate_tokens(text: str) -> int:
    """Estimate token count for mixed Korean/English text (stdlib-only).

    Mirrors the formula from kosmos.tools._description_template._estimate_tokens:
      Korean syllables (가-힣) → 1 token each
      Non-Korean text split on whitespace → 1 token per word
    """
    korean_chars = [c for c in text if "가" <= c <= "힣"]
    non_korean = "".join(c if c < "가" or c > "힣" else " " for c in text)
    non_korean_words = [w for w in non_korean.split() if w.strip()]
    return len(korean_chars) + len(non_korean_words)


# ---------------------------------------------------------------------------
# KMA tool description fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def kma_tools() -> dict[str, Any]:
    """Return a dict of tool_id → GovAPITool for the 6 KMA tools."""
    from kosmos.tools.kma.forecast_fetch import KMA_FORECAST_FETCH_TOOL
    from kosmos.tools.kma.kma_current_observation import KMA_CURRENT_OBSERVATION_TOOL
    from kosmos.tools.kma.kma_pre_warning import KMA_PRE_WARNING_TOOL
    from kosmos.tools.kma.kma_short_term_forecast import KMA_SHORT_TERM_FORECAST_TOOL
    from kosmos.tools.kma.kma_ultra_short_term_forecast import KMA_ULTRA_SHORT_TERM_FORECAST_TOOL
    from kosmos.tools.kma.kma_weather_alert_status import KMA_WEATHER_ALERT_STATUS_TOOL

    return {
        "kma_current_observation": KMA_CURRENT_OBSERVATION_TOOL,
        "kma_short_term_forecast": KMA_SHORT_TERM_FORECAST_TOOL,
        "kma_ultra_short_term_forecast": KMA_ULTRA_SHORT_TERM_FORECAST_TOOL,
        "kma_forecast_fetch": KMA_FORECAST_FETCH_TOOL,
        "kma_pre_warning": KMA_PRE_WARNING_TOOL,
        "kma_weather_alert_status": KMA_WEATHER_ALERT_STATUS_TOOL,
    }


# ---------------------------------------------------------------------------
# 1. Token budget tests (≤ 500 tokens per tool)
# ---------------------------------------------------------------------------


class TestDescriptionTokenBudget:
    """Each KMA tool description must stay within the 500-token budget."""

    _BUDGET = 500

    def _check_tool(self, tool_id: str, tool: Any) -> None:
        desc = tool.llm_description
        assert desc, f"{tool_id}: llm_description is empty"
        tokens = _estimate_tokens(desc)
        assert tokens <= self._BUDGET, (
            f"{tool_id}: llm_description exceeds {self._BUDGET}-token budget "
            f"(estimated {tokens} tokens). Shorten the description."
        )

    def test_kma_current_observation_budget(self, kma_tools) -> None:
        self._check_tool("kma_current_observation", kma_tools["kma_current_observation"])

    def test_kma_short_term_forecast_budget(self, kma_tools) -> None:
        self._check_tool("kma_short_term_forecast", kma_tools["kma_short_term_forecast"])

    def test_kma_ultra_short_term_forecast_budget(self, kma_tools) -> None:
        self._check_tool(
            "kma_ultra_short_term_forecast", kma_tools["kma_ultra_short_term_forecast"]
        )

    def test_kma_forecast_fetch_budget(self, kma_tools) -> None:
        self._check_tool("kma_forecast_fetch", kma_tools["kma_forecast_fetch"])

    def test_kma_pre_warning_budget(self, kma_tools) -> None:
        self._check_tool("kma_pre_warning", kma_tools["kma_pre_warning"])

    def test_kma_weather_alert_status_budget(self, kma_tools) -> None:
        self._check_tool("kma_weather_alert_status", kma_tools["kma_weather_alert_status"])


# ---------------------------------------------------------------------------
# 2. Five-section structure tests
# ---------------------------------------------------------------------------


class TestDescriptionFiveSections:
    """Each KMA tool description must have exactly 5 sections (split on \\n\\n)."""

    def _check_tool(self, tool_id: str, tool: Any) -> None:
        desc = tool.llm_description
        sections = desc.split("\n\n")
        assert len(sections) == 5, (
            f"{tool_id}: expected 5 sections separated by \\n\\n, "
            f"got {len(sections)}. Sections: {[s[:40] for s in sections]}"
        )
        # All sections must be non-empty
        for i, section in enumerate(sections):
            assert section.strip(), (
                f"{tool_id}: section {i + 1} is empty. All 5 sections must have content."
            )

    def test_kma_current_observation_five_sections(self, kma_tools) -> None:
        self._check_tool("kma_current_observation", kma_tools["kma_current_observation"])

    def test_kma_short_term_forecast_five_sections(self, kma_tools) -> None:
        self._check_tool("kma_short_term_forecast", kma_tools["kma_short_term_forecast"])

    def test_kma_ultra_short_term_forecast_five_sections(self, kma_tools) -> None:
        self._check_tool(
            "kma_ultra_short_term_forecast", kma_tools["kma_ultra_short_term_forecast"]
        )

    def test_kma_forecast_fetch_five_sections(self, kma_tools) -> None:
        self._check_tool("kma_forecast_fetch", kma_tools["kma_forecast_fetch"])

    def test_kma_pre_warning_five_sections(self, kma_tools) -> None:
        self._check_tool("kma_pre_warning", kma_tools["kma_pre_warning"])

    def test_kma_weather_alert_status_five_sections(self, kma_tools) -> None:
        self._check_tool("kma_weather_alert_status", kma_tools["kma_weather_alert_status"])


# ---------------------------------------------------------------------------
# 3. Section 3 — 17 광역시도 reference table presence
# ---------------------------------------------------------------------------


class TestDescriptionSection3Reference:
    """Section 3 of each tool must contain a 17 광역시도 reference (서울=... 형식)."""

    # Pattern: "서울=<something>" — matches grid coords (서울=(61,126)) and
    # station codes (서울=108) and lat/lon refs (서울=(37.57,126.98)).
    _SIDO_PATTERN = re.compile(r"서울=")

    def _check_tool(self, tool_id: str, tool: Any) -> None:
        desc = tool.llm_description
        sections = desc.split("\n\n")
        assert len(sections) >= 3, f"{tool_id}: expected ≥3 sections, got {len(sections)}"
        section3 = sections[2]
        assert self._SIDO_PATTERN.search(section3), (
            f"{tool_id}: Section 3 (short_reference) must contain '서울=...' "
            f"for 17 광역시도 reference. Got: {section3[:100]!r}"
        )

    def test_kma_current_observation_section3(self, kma_tools) -> None:
        self._check_tool("kma_current_observation", kma_tools["kma_current_observation"])

    def test_kma_short_term_forecast_section3(self, kma_tools) -> None:
        self._check_tool("kma_short_term_forecast", kma_tools["kma_short_term_forecast"])

    def test_kma_ultra_short_term_forecast_section3(self, kma_tools) -> None:
        self._check_tool(
            "kma_ultra_short_term_forecast", kma_tools["kma_ultra_short_term_forecast"]
        )

    def test_kma_forecast_fetch_section3(self, kma_tools) -> None:
        self._check_tool("kma_forecast_fetch", kma_tools["kma_forecast_fetch"])

    def test_kma_pre_warning_section3(self, kma_tools) -> None:
        self._check_tool("kma_pre_warning", kma_tools["kma_pre_warning"])

    def test_kma_weather_alert_status_section3(self, kma_tools) -> None:
        self._check_tool("kma_weather_alert_status", kma_tools["kma_weather_alert_status"])


# ---------------------------------------------------------------------------
# 4. kma_grid_short_reference() output in grid-based tools
# ---------------------------------------------------------------------------


class TestGridShortReferenceInline:
    """Tools that use KMA grid coords (nx/ny) must embed kma_grid_short_reference() output."""

    def test_kma_grid_short_reference_is_string(self) -> None:
        """kma_grid_short_reference() returns a non-empty string."""
        from kosmos.tools.kma.grid_coords import kma_grid_short_reference

        ref = kma_grid_short_reference()
        assert isinstance(ref, str)
        assert len(ref) > 0

    def test_kma_grid_short_reference_contains_17_regions(self) -> None:
        """The output must contain all 17 광역시도 short names."""
        from kosmos.tools.kma.grid_coords import kma_grid_short_reference

        ref = kma_grid_short_reference()
        expected_regions = [
            "서울",
            "부산",
            "대구",
            "인천",
            "광주",
            "대전",
            "울산",
            "세종",
            "경기",
            "강원",
            "충북",
            "충남",
            "전북",
            "전남",
            "경북",
            "경남",
            "제주",
        ]
        for region in expected_regions:
            assert region in ref, (
                f"kma_grid_short_reference() missing region '{region}'. Output: {ref[:100]!r}"
            )

    def test_grid_tools_embed_seoul_nx_ny(self, kma_tools) -> None:
        """kma_current_observation / kma_short_term_forecast / kma_ultra_short use nx/ny ref."""
        # These tools use Lambert grid coords — their S3 should contain nx/ny notation
        grid_tools = [
            "kma_current_observation",
            "kma_short_term_forecast",
            "kma_ultra_short_term_forecast",
        ]
        # Pattern: 서울=(61,126) or similar grid coord
        nx_ny_pattern = re.compile(r"서울=\(\d+,\d+\)")
        for tool_id in grid_tools:
            tool = kma_tools[tool_id]
            sections = tool.llm_description.split("\n\n")
            section3 = sections[2]
            assert nx_ny_pattern.search(section3), (
                f"{tool_id}: Section 3 should contain Seoul grid coords like '서울=(61,126)'. "
                f"Got: {section3[:100]!r}"
            )


# ---------------------------------------------------------------------------
# 5. Section 5 — self-contained / chain guidance
# ---------------------------------------------------------------------------


class TestDescriptionSection5ChainGuidance:
    """Section 5 must declare the tool's chain ordering requirement.

    The previous variant of this test asserted that section 5 contained one of
    ['chain', 'cross', '단독', 'autonomous', 'self'] — a wording that included
    the anti-pattern "단독 호출로 완결" / "self-contained". KMA / HIRA / NMC
    coordinate-input tools are NOT self-contained: they REQUIRE a prior
    resolve_location turn to obtain nx/ny or lat/lon. Asserting "self-contained"
    encouraged tool descriptions to lie to the LLM ("이 도구 단독 호출로 완결"
    contradicting "시민이 좌표 모르면 turn 1 = resolve_location"), and K-EXAONE
    picked the first half — refusing to call resolve_location and hallucinating
    coordinates ("동아대학교 → 부산 동래구 hospitals" frame, 2026-05-04).

    The corrected assertion: section 5 MUST mention ``resolve_location`` AND
    a turn-ordering signal so the LLM gets unambiguous chain guidance.
    """

    _ORDERING_TOKENS = ("turn1", "turn 1", "ORDERING", "ordering", "first", "FIRST")
    _SELF_CONTAINED_TOKENS = ("단독", "self-contained")

    def _check_tool(self, tool_id: str, tool: Any) -> None:
        desc = tool.llm_description
        sections = desc.split("\n\n")
        assert len(sections) == 5, f"{tool_id}: expected 5 sections"
        section5 = sections[4]
        # Two valid shapes: (a) chain-required tool — must reference
        # resolve_location AND a turn-ordering signal; (b) chain-free tool —
        # must explicitly declare self-contained (단독 / self-contained) so
        # the LLM knows it can be invoked without prior steps. Tools that
        # take no coordinate input (e.g. kma_pre_warning, which queries by
        # 관서코드 stn_id) fall into shape (b); tools that need lat/lon or
        # nx/ny (kma_current_observation, _short_term, _ultra, forecast_fetch)
        # fall into shape (a). Asserting one OR the other prevents the
        # 2026-05-04 anti-pattern where a chain-required tool also claimed
        # to be self-contained, contradicting itself in the same paragraph.
        is_chain_required = "resolve_location" in section5 and any(
            tok in section5 for tok in self._ORDERING_TOKENS
        )
        is_chain_free = any(tok in section5 for tok in self._SELF_CONTAINED_TOKENS)
        assert is_chain_required or is_chain_free, (
            f"{tool_id}: Section 5 must EITHER (a) reference resolve_location + an "
            f"ordering token {self._ORDERING_TOKENS} for chain-required tools, "
            f"OR (b) contain a self-contained marker {self._SELF_CONTAINED_TOKENS} "
            f"for chain-free tools. Section 5 text: {section5[:200]!r}"
        )
        # Forbid the contradictory shape: a tool that claims BOTH "단독 호출" /
        # "self-contained" AND "resolve_location" in the same section. That
        # combination is what K-EXAONE picked the wrong half of in the
        # donga-univ-poi-bug frame.
        contradictory = (
            "resolve_location" in section5
            and any(tok in section5 for tok in self._SELF_CONTAINED_TOKENS)
        )
        assert not contradictory, (
            f"{tool_id}: Section 5 mixes self-contained markers "
            f"{self._SELF_CONTAINED_TOKENS} with a resolve_location reference. "
            f"Pick one shape — see the 2026-05-04 donga-univ-poi-bug for the "
            f"failure mode this guard prevents. Section 5 text: {section5[:200]!r}"
        )

    def test_kma_current_observation_section5(self, kma_tools) -> None:
        self._check_tool("kma_current_observation", kma_tools["kma_current_observation"])

    def test_kma_short_term_forecast_section5(self, kma_tools) -> None:
        self._check_tool("kma_short_term_forecast", kma_tools["kma_short_term_forecast"])

    def test_kma_ultra_short_term_forecast_section5(self, kma_tools) -> None:
        self._check_tool(
            "kma_ultra_short_term_forecast", kma_tools["kma_ultra_short_term_forecast"]
        )

    def test_kma_forecast_fetch_section5(self, kma_tools) -> None:
        self._check_tool("kma_forecast_fetch", kma_tools["kma_forecast_fetch"])

    def test_kma_pre_warning_section5(self, kma_tools) -> None:
        self._check_tool("kma_pre_warning", kma_tools["kma_pre_warning"])

    def test_kma_weather_alert_status_section5_autonomous_chain(self, kma_tools) -> None:
        """kma_weather_alert_status S5 mentions autonomous chain with kma_pre_warning."""
        tool = kma_tools["kma_weather_alert_status"]
        sections = tool.llm_description.split("\n\n")
        section5 = sections[4]
        # Must mention the recommended prior tool
        assert "kma_pre_warning" in section5, (
            f"kma_weather_alert_status: Section 5 should reference kma_pre_warning as "
            f"recommended turn 1. Got: {section5!r}"
        )
        # Must state chain is not forced
        assert "강제 X" in section5 or "강제하지 않" in section5 or "chain 강제 X" in section5, (
            f"kma_weather_alert_status: Section 5 must state chain is not forced. Got: {section5!r}"
        )


# ---------------------------------------------------------------------------
# 6. ORDERING block absence — T010 verification
# ---------------------------------------------------------------------------


class TestOrderingBlockAbsence:
    """Verify ORDERING logic: only tools with nx+ny required emit [ORDERING] block.

    T010 task: tools with 5-section descriptions should NOT receive extra ORDERING
    directives from stdio.py when their schema does not have nx+ny required fields.

    The ORDERING trigger in _build_available_adapters_suffix checks:
        needs_kma_grid = "nx" in required and "ny" in required

    kma_weather_alert_status has stn_id/tmFc — no nx/ny → ORDERING must NOT fire.
    kma_pre_warning has optional stn_id only — no nx/ny → ORDERING must NOT fire.
    kma_current_observation HAS nx/ny required → ORDERING fires (positive case).
    """

    def _needs_ordering(self, input_class: type) -> bool:
        """Mirror the ORDERING decision logic from stdio.py _build_available_adapters_suffix.

        Returns True if [ORDERING] block would be emitted for this tool's input schema.
        """
        schema = input_class.model_json_schema()
        raw_required = schema.get("required", [])
        required: set[str] = {str(r) for r in raw_required if isinstance(r, str)}
        return "nx" in required and "ny" in required

    def test_weather_alert_status_no_ordering(self) -> None:
        """kma_weather_alert_status lacks nx/ny → ORDERING block must NOT be emitted."""
        from kosmos.tools.kma.kma_weather_alert_status import KmaWeatherAlertStatusInput

        assert not self._needs_ordering(KmaWeatherAlertStatusInput), (
            "kma_weather_alert_status should NOT trigger [ORDERING] block — "
            "it has stn_id/tmFc, not nx/ny required fields."
        )

    def test_pre_warning_no_ordering(self) -> None:
        """kma_pre_warning lacks nx/ny → ORDERING block must NOT be emitted."""
        from kosmos.tools.kma.kma_pre_warning import KmaPreWarningInput

        assert not self._needs_ordering(KmaPreWarningInput), (
            "kma_pre_warning should NOT trigger [ORDERING] block — "
            "it has optional stn_id, not nx/ny required fields."
        )

    def test_current_observation_triggers_ordering(self) -> None:
        """kma_current_observation has nx+ny required → ORDERING block IS emitted."""
        from kosmos.tools.kma.kma_current_observation import KmaCurrentObservationInput

        assert self._needs_ordering(KmaCurrentObservationInput), (
            "kma_current_observation HAS nx/ny required — [ORDERING] block must be "
            "emitted by _build_available_adapters_suffix."
        )

    def test_short_term_forecast_triggers_ordering(self) -> None:
        """kma_short_term_forecast has nx+ny required → ORDERING triggers."""
        from kosmos.tools.kma.kma_short_term_forecast import KmaShortTermForecastInput

        assert self._needs_ordering(KmaShortTermForecastInput)

    def test_ultra_short_forecast_triggers_ordering(self) -> None:
        """kma_ultra_short_term_forecast has nx+ny required → ORDERING triggers."""
        from kosmos.tools.kma.kma_ultra_short_term_forecast import KmaUltraShortTermForecastInput

        assert self._needs_ordering(KmaUltraShortTermForecastInput)

    def test_weather_alert_status_schema_lacks_nx_ny(self) -> None:
        """Schema-level: kma_weather_alert_status input does not have nx or ny fields."""
        from kosmos.tools.kma.kma_weather_alert_status import KmaWeatherAlertStatusInput

        schema = KmaWeatherAlertStatusInput.model_json_schema()
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))

        assert "nx" not in properties, "kma_weather_alert_status must not have nx field"
        assert "ny" not in properties, "kma_weather_alert_status must not have ny field"
        assert "nx" not in required, "nx must not be in required fields"
        assert "ny" not in required, "ny must not be in required fields"

    def test_kma_current_observation_schema_has_nx_ny_required(self) -> None:
        """Schema-level: kma_current_observation input has nx and ny as required fields."""
        from kosmos.tools.kma.kma_current_observation import KmaCurrentObservationInput

        schema = KmaCurrentObservationInput.model_json_schema()
        required = set(schema.get("required", []))

        assert "nx" in required, "kma_current_observation must have nx in required"
        assert "ny" in required, "kma_current_observation must have ny in required"


# ---------------------------------------------------------------------------
# 7. KmaWeatherAlertStatusInput model_validator
# ---------------------------------------------------------------------------


class TestKmaWeatherAlertStatusInputValidator:
    """model_validator(mode='after') requires stn_id or tmFc — not both None."""

    def test_stn_id_only_is_valid(self) -> None:
        from kosmos.tools.kma.kma_weather_alert_status import KmaWeatherAlertStatusInput

        inp = KmaWeatherAlertStatusInput(stn_id="108")
        assert inp.stn_id == "108"
        assert inp.tmFc is None

    def test_tmfc_only_is_valid(self) -> None:
        from kosmos.tools.kma.kma_weather_alert_status import KmaWeatherAlertStatusInput

        inp = KmaWeatherAlertStatusInput(tmFc="202605031100")
        assert inp.stn_id is None
        assert inp.tmFc == "202605031100"

    def test_both_provided_is_valid(self) -> None:
        from kosmos.tools.kma.kma_weather_alert_status import KmaWeatherAlertStatusInput

        inp = KmaWeatherAlertStatusInput(stn_id="184", tmFc="202605031100")
        assert inp.stn_id == "184"
        assert inp.tmFc == "202605031100"

    def test_both_none_raises_validation_error(self) -> None:
        """Both stn_id and tmFc = None must raise ValidationError."""
        from kosmos.tools.kma.kma_weather_alert_status import KmaWeatherAlertStatusInput

        with pytest.raises(ValidationError) as exc_info:
            KmaWeatherAlertStatusInput()  # defaults: stn_id=None, tmFc=None

        error_str = str(exc_info.value)
        # Must mention at least one of the fields or the error message
        assert "stn_id" in error_str or "tmFc" in error_str or "mandatory" in error_str.lower()

    def test_default_num_of_rows(self) -> None:
        from kosmos.tools.kma.kma_weather_alert_status import KmaWeatherAlertStatusInput

        inp = KmaWeatherAlertStatusInput(stn_id="108")
        assert inp.num_of_rows == 100

    def test_num_of_rows_ge1(self) -> None:
        from kosmos.tools.kma.kma_weather_alert_status import KmaWeatherAlertStatusInput

        with pytest.raises(ValidationError):
            KmaWeatherAlertStatusInput(stn_id="108", num_of_rows=0)
