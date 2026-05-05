# SPDX-License-Identifier: Apache-2.0
"""Tests for SystemPromptAssembler (T010, T028).

Covers:
- All four mandatory sections present (FR-009)
- Determinism: same config → identical output
- Determinism stress test: 1000 consecutive calls via SystemPromptAssembler (SC-001)
- Determinism stress test: 1000 consecutive calls via ContextBuilder.build_system_message() (T028)
- personal_data_warning=False omits section 4
"""

from __future__ import annotations

from kosmos.context.builder import ContextBuilder
from kosmos.context.models import SystemPromptConfig
from kosmos.context.system_prompt import SystemPromptAssembler


class TestSystemPromptAssembler:
    def _assembler(self) -> SystemPromptAssembler:
        return SystemPromptAssembler()

    def test_contains_platform_identity(self) -> None:
        cfg = SystemPromptConfig(platform_name="KOSMOS")
        result = self._assembler().assemble(cfg)
        assert "KOSMOS" in result
        # Epic #2152 R1 — citizen-domain framing in Korean prose.
        assert "공공" in result and "시민" in result

    def test_contains_language_policy(self) -> None:
        cfg = SystemPromptConfig(language="ko")
        result = self._assembler().assemble(cfg)
        # Epic #2152 R1 — language rule lives in <core_rules> Korean prose.
        assert "한국어" in result

    def test_contains_tool_use_policy(self) -> None:
        result = self._assembler().assemble(SystemPromptConfig())
        # Epic #2152 R1 — <tool_usage> section enumerates citizen-domain
        # tool triggers; fabrication ban lives in <core_rules>.
        assert "도구" in result
        assert "지어내지" in result or "fabricate" in result.lower()

    def test_contains_personal_data_reminder_when_enabled(self) -> None:
        cfg = SystemPromptConfig(personal_data_warning=True)
        result = self._assembler().assemble(cfg)
        # Epic #2152 R1 — personal-data reminder in <output_style> uses PIPA.
        assert "personal data" in result.lower() or "PIPA" in result or "개인정보" in result

    def test_omits_personal_data_reminder_when_disabled(self) -> None:
        cfg = SystemPromptConfig(personal_data_warning=False)
        result = self._assembler().assemble(cfg)
        # The <output_style> personal-data reminder paragraph must be absent
        # when the config gate disables it.  Use the unique opening sentinel of
        # the <output_style> block as the probe; the heavier <pipa_safety>
        # section (always-on critical directive) also mentions PIPA and
        # "개인정보" so those broad terms can no longer serve as absence probes.
        assert "Handle personal data with care" not in result
        # Also confirm the <output_style>-specific PIPA line is absent.
        assert "시민의 개인정보는 PIPA 에 따라 처리합니다" not in result

    def test_deterministic_same_instance(self) -> None:
        cfg = SystemPromptConfig()
        assembler = self._assembler()
        first = assembler.assemble(cfg)
        second = assembler.assemble(cfg)
        assert first == second

    def test_deterministic_different_instances(self) -> None:
        cfg = SystemPromptConfig()
        first = SystemPromptAssembler().assemble(cfg)
        second = SystemPromptAssembler().assemble(cfg)
        assert first == second

    def test_sections_separated_by_double_newline(self) -> None:
        result = self._assembler().assemble(SystemPromptConfig())
        assert "\n\n" in result

    def test_custom_platform_name(self) -> None:
        cfg = SystemPromptConfig(platform_name="TESTBOT")
        result = self._assembler().assemble(cfg)
        assert "TESTBOT" in result

    def test_custom_language(self) -> None:
        cfg = SystemPromptConfig(language="en")
        result = self._assembler().assemble(cfg)
        assert "en" in result

    def test_nonempty_output(self) -> None:
        result = self._assembler().assemble(SystemPromptConfig())
        assert len(result.strip()) > 0


class TestSystemPromptDeterminismStress:
    """SC-001: 1000 consecutive SystemPromptAssembler calls return identical content."""

    def test_1000_calls_deterministic(self) -> None:
        cfg = SystemPromptConfig()
        assembler = SystemPromptAssembler()
        baseline = assembler.assemble(cfg)
        for _ in range(999):
            result = assembler.assemble(cfg)
            assert result == baseline, "Assemble output changed between calls"


class TestContextBuilderDeterminismStress:
    """SC-001 (T028): 1000 consecutive build_system_message() calls are identical."""

    def test_system_prompt_determinism_stress(self) -> None:
        """SC-001: 1000 consecutive build_system_message() calls produce identical content."""
        builder = ContextBuilder()
        first = builder.build_system_message()

        for _ in range(999):
            msg = builder.build_system_message()
            assert msg.content == first.content
            assert msg.role == first.role
