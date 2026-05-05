# SPDX-License-Identifier: Apache-2.0
"""Tests for KST date/time injection into the chat-request system prompt.

KOSMOS hotfix (2026-05-04, KMA base_time hallucination 차단):
The previous dynamic-suffix block emitted only ``오늘 날짜 (UTC)`` — which
let K-EXAONE guess KMA ``base_time`` (KST HHMM publication slots:
0200/0500/0800/1100/1400/1700/2000/2300). A wrong base_time produces a
4-9-hour-off forecast — a citizen safety violation under the system prompt
fabrication directive.

These tests assert the system prompt the LLM actually sees contains:

  1. ``오늘 날짜 (KST): YYYY-MM-DD`` derived from Asia/Seoul, NOT UTC.
  2. ``현재 시각 (KST): HH:MM (HHMM)`` — both display and concatenated forms.
  3. The eight-slot KMA base_time enumeration.
  4. The ``직전 발표`` hint pre-computed by the backend (so the LLM can
     copy-paste rather than guess).

We reuse the in-process pipe harness from ``test_stdio.py`` so the full
augmented_system path runs end-to-end, including the SHA-locked
PromptLoader fallback and the BM25 ``<available_adapters>`` suffix.
"""

from __future__ import annotations

import importlib
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from tests.ipc.test_stdio import (  # type: ignore[import-not-found]
    _FakeLLMClientNoTools,
    _make_chat_request,
    _run_with_frame,
)


def _extract_system_content(fake_client: type) -> str:
    """Pull the system message content the LLM was actually called with."""
    assert fake_client.recorded_calls, "LLMClient.stream() never invoked"
    messages = fake_client.recorded_calls[0].get("messages", [])
    for msg in messages:
        if getattr(msg, "role", None) == "system":
            content = getattr(msg, "content", None)
            assert isinstance(content, str) and content, "Empty system message"
            return content
    raise AssertionError("No role='system' message found in LLM call")


# ---------------------------------------------------------------------------
# T1 — KST date format invariant (timezone='Asia/Seoul', not UTC)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_prompt_includes_kst_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """System prompt dynamic suffix must contain '오늘 날짜 (KST): YYYY-MM-DD'.

    The KST date may differ from the UTC date by ±1 day around midnight UTC;
    we accept either today-KST or tomorrow-KST as long as the literal '(KST)'
    label is present (so the LLM cannot interpret it as UTC).
    """
    frame = _make_chat_request(tools=[])
    _, fake_client = await _run_with_frame(frame, _FakeLLMClientNoTools, monkeypatch=monkeypatch)
    system_content = _extract_system_content(fake_client)

    # Date label must be KST, NOT UTC (the regression we are guarding against).
    assert "오늘 날짜 (KST):" in system_content, (
        "Expected '오늘 날짜 (KST):' in dynamic suffix; the previous version "
        "incorrectly emitted '(UTC)' which let the LLM offset the date by 9h. "
        f"Suffix preview: ...{system_content[-800:]!r}"
    )
    assert "(UTC)" not in system_content.split("## Current session context", 1)[-1], (
        "Dynamic suffix must NOT mention UTC for the citizen-facing date — "
        "all wall-clock references must be KST so KMA base_time stays consistent."
    )

    # The injected date must match an actual KST date computed in the test.
    expected_kst = datetime.now(tz=ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")
    assert expected_kst in system_content, (
        f"Injected KST date does not match expected {expected_kst!r}. "
        f"Suffix preview: ...{system_content[-800:]!r}"
    )


# ---------------------------------------------------------------------------
# T2 — KST current time HH:MM and HHMM both present
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_prompt_includes_kst_current_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Suffix must contain '현재 시각 (KST): HH:MM (HHMM).'.

    Both formats are required:
      - HH:MM is the human-readable display the LLM cites in its answer.
      - HHMM is the KMA ``base_time`` argument format (validator-accepted).
    """
    frame = _make_chat_request(tools=[])
    _, fake_client = await _run_with_frame(frame, _FakeLLMClientNoTools, monkeypatch=monkeypatch)
    system_content = _extract_system_content(fake_client)

    # Anchor on the KST label and the HH:MM (HHMM) pattern.
    pattern = re.compile(r"현재 시각 \(KST\): \d{2}:\d{2} \(\d{4}\)")
    match = pattern.search(system_content)
    assert match is not None, (
        "Expected '현재 시각 (KST): HH:MM (HHMM)' in dynamic suffix. "
        f"Suffix preview: ...{system_content[-800:]!r}"
    )

    # Quick sanity: the HH:MM and HHMM substrings inside the match must be
    # consistent (e.g. '07:35 (0735)', not '07:35 (0700)').
    rendered = match.group(0)
    hm = rendered.split(": ", 1)[1].split(" ", 1)[0]  # '07:35'
    hhmm_inside = rendered.rsplit("(", 1)[1].rstrip(")")  # '0735'
    assert hm.replace(":", "") == hhmm_inside, (
        f"HH:MM and HHMM forms disagree inside the same render: {rendered!r}"
    )


# ---------------------------------------------------------------------------
# T3 — KMA base_time slot enumeration + pre-computed 직전 발표 hint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_prompt_includes_kma_base_time_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Suffix must enumerate the 8 KMA base_time slots and emit the precomputed
    '직전 발표' hint (base_date + base_time) for the current KST hour.
    """
    frame = _make_chat_request(tools=[])
    _, fake_client = await _run_with_frame(frame, _FakeLLMClientNoTools, monkeypatch=monkeypatch)
    system_content = _extract_system_content(fake_client)

    # All 8 publication slots must appear (one block, separated by '/').
    assert "0200/0500/0800/1100/1400/1700/2000/2300" in system_content, (
        "KMA 8-slot base_time enumeration missing from dynamic suffix. "
        f"Suffix preview: ...{system_content[-800:]!r}"
    )

    # Pre-computed hint: 'base_date=YYYYMMDD, base_time=HHMM'.
    hint_pattern = re.compile(r"base_date=\d{8}, base_time=\d{4}")
    assert hint_pattern.search(system_content) is not None, (
        "Pre-computed '직전 발표' base_date/base_time hint missing — the LLM "
        "is forced to compute it itself, defeating the hallucination guard. "
        f"Suffix preview: ...{system_content[-800:]!r}"
    )

    # Anti-hallucination phrasing: 'base_time 추측 금지' must be present.
    assert "base_time 추측 금지" in system_content, (
        "Anti-hallucination directive 'base_time 추측 금지' missing from suffix."
    )


# ---------------------------------------------------------------------------
# T4 — Spec 026 fail-closed boot invariant (PromptLoader still gates)
# ---------------------------------------------------------------------------


def test_prompt_loader_still_loads_system_v1_after_kst_injection() -> None:
    """The dynamic KST injection lives OUTSIDE the SHA-locked prompt files.

    Spec 026 requires that ``prompts/system_v1.md`` and
    ``prompts/session_guidance_v1.md`` boot via PromptLoader with their
    manifest SHA-256 verified at startup (R1/R2/R3 fail-closed). This test
    asserts that the manifest still validates after our hotfix — i.e. we
    did NOT modify the byte-locked files.
    """
    # Re-import to force a fresh PromptLoader construction; the import will
    # raise PromptRegistryError on any R1/R2/R3 violation.
    from kosmos.context.prompt_loader import PromptLoader, default_manifest_path

    loader = PromptLoader(manifest_path=default_manifest_path())
    text = loader.load("system_v1")

    # Sanity — the citizen system prompt is non-empty and Korean-primary.
    assert len(text) > 100, "system_v1.md text suspiciously short"
    assert "시민" in text, "system_v1.md missing citizen-facing framing"


# ---------------------------------------------------------------------------
# T5 — System prompt cache prefix invariant (paragraph stability)
# ---------------------------------------------------------------------------


def test_kst_injection_does_not_mutate_static_prefix() -> None:
    """SystemPromptAssembler output must remain deterministic across calls.

    The KST/time injection happens in ``stdio.py`` AFTER
    ``_DYNAMIC_BOUNDARY_MARKER`` — the static cache prefix served by
    SystemPromptAssembler must remain byte-identical (NFR-003 / SC-001).
    """
    from kosmos.context.models import SystemPromptConfig
    from kosmos.context.system_prompt import SystemPromptAssembler

    cfg = SystemPromptConfig()
    a = SystemPromptAssembler().assemble(cfg)
    b = SystemPromptAssembler().assemble(cfg)
    assert a == b, "SystemPromptAssembler is non-deterministic"

    # The assembled static prefix must NOT contain the dynamic-suffix
    # KST literal — that lives downstream in stdio.py only.
    assert "현재 시각 (KST):" not in a, (
        "KST current-time literal leaked into the static cache prefix; "
        "this would invalidate the FriendliAI prompt-cache key every minute. "
        "Move the injection back to the dynamic suffix in stdio.py."
    )


# ---------------------------------------------------------------------------
# T6 — KMA adapter llm_descriptions cite the prompt rule
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module_path",
    [
        "kosmos.tools.kma.kma_short_term_forecast",
        "kosmos.tools.kma.kma_ultra_short_term_forecast",
        "kosmos.tools.kma.kma_current_observation",
        "kosmos.tools.kma.forecast_fetch",
    ],
)
def test_kma_adapter_cites_kst_time_rule(module_path: str) -> None:
    """Every KMA adapter that takes ``base_time`` must reference the
    '현재 KST 시각' system-prompt hint in its llm_description input_quirk
    so the LLM knows to copy-paste from the dynamic suffix instead of guessing.
    """
    mod = importlib.import_module(module_path)

    # Locate the GovAPITool definition exported from the module.
    tool = None
    for attr in dir(mod):
        candidate = getattr(mod, attr)
        if hasattr(candidate, "id") and getattr(candidate, "id", "").startswith("kma_"):
            tool = candidate
            break
    assert tool is not None, f"No GovAPITool exported from {module_path}"

    desc = getattr(tool, "llm_description", "") or ""
    assert "현재 KST 시각" in desc, (
        f"{module_path} llm_description missing '현재 KST 시각' anchor — "
        "the LLM has no link between its input parameter and the system "
        "prompt's dynamic time hint. Description was:\n" + desc[:500]
    )
    assert "추측 금지" in desc, (
        f"{module_path} llm_description missing 'base_time 추측 금지' directive."
    )
