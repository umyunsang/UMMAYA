# SPDX-License-Identifier: Apache-2.0
"""Tests for the output enum mapping invariants in prompts/system_v1.md.

Wave-2 G5 (Spec realuse-audit-2026-05-05) — F-beta-06 regression test.
Citizens were seeing raw KMA enum codes (`강수형태 0`, `sky_code 1`,
`vec 271°`) in answers because the system prompt did not surface the
ministry's enum-to-natural-language mappings. PR #2772 added the VEC
16-direction mapping inline in `kma_current_observation.py:llm_description`
(input-side); this test asserts the *output-side* mappings (PTY / SKY / VEC)
are now also present in the system prompt where the LLM applies them at
answer-formatting time.

Contract: F-known criterion #3 (raw 내부 필드 노출 금지).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kosmos.context.prompt_loader import PromptLoader

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "prompts" / "manifest.yaml"


@pytest.fixture(scope="module")
def system_prompt_text() -> str:
    loader = PromptLoader(manifest_path=MANIFEST)
    return loader.load("system_v1")


def test_pty_full_enum_mapping_present(system_prompt_text: str) -> None:
    """All seven KMA PTY codes (0/1/2/3/5/6/7) map to Korean natural language."""
    text = system_prompt_text
    # Header — establishes that the section exists at all.
    assert "PTY" in text, "system_v1.md missing PTY enum mapping section"
    assert "강수형태" in text, "system_v1.md missing 강수형태 label"

    # Each official KMA code → Korean phrase
    expectations = {
        "pty=0": "강수 없음",
        "pty=1": "비",
        "pty=2": "비/눈",
        "pty=3": "눈",
        "pty=5": "이슬비",
        "pty=6": "이슬비/눈",
        "pty=7": "눈날림",
    }
    for code, label in expectations.items():
        assert code in text, (
            f"system_v1.md PTY mapping missing code '{code}' "
            "(see KMA getUltraSrtNcst spec)"
        )
        assert label in text, (
            f"system_v1.md PTY mapping missing Korean label '{label}' for {code}"
        )


def test_sky_code_mapping_present(system_prompt_text: str) -> None:
    """KMA SKY codes (1/3/4) map to 맑음 / 구름많음 / 흐림."""
    text = system_prompt_text
    assert "SKY" in text, "system_v1.md missing SKY enum mapping"
    assert "맑음" in text
    assert "구름많음" in text
    assert "흐림" in text


def test_vec_16_direction_mapping_present(system_prompt_text: str) -> None:
    """VEC wind direction maps to 16 Korean compass directions.

    PR #2772 added this on the input side; G5 surfaces it on the output
    side so the LLM applies the mapping in citizen-facing answers.
    """
    text = system_prompt_text
    assert "VEC" in text, "system_v1.md missing VEC enum mapping"
    # Key boundaries — pick three around the worst-case "vec=271 → 북서풍"
    # mismatch from F-known.
    assert "0=북" in text, "VEC mapping missing N anchor"
    assert "270=서" in text, "VEC mapping missing W anchor"
    # 16 NSEW abbreviations (must all be present)
    for abbr in (
        "N(",
        "NNE(",
        "NE(",
        "ENE(",
        "E(",
        "ESE(",
        "SE(",
        "SSE(",
        "S(",
        "SSW(",
        "SW(",
        "WSW(",
        "W(",
        "WNW(",
        "NW(",
        "NNW(",
    ):
        assert abbr in text, f"VEC 16-direction mapping missing abbreviation '{abbr}'"
    # Worked example for the F-known criterion #4 mismatch (vec=271 was
    # being narrated as 북서풍, actual NW=315; the example pins it).
    assert "vec=271" in text, "VEC mapping missing the 271° worked example"
    assert "서풍" in text, "VEC mapping missing 서풍 phrase"


def test_critical_directive_to_convert_raw_codes(system_prompt_text: str) -> None:
    """The CRITICAL directive forbids raw enum exposure (`pty: 0`, etc.)."""
    text = system_prompt_text
    assert "raw 코드" in text, (
        "system_v1.md missing the CRITICAL directive that forbids raw "
        "enum exposure in citizen-facing answers"
    )
