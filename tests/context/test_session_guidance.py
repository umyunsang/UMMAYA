# SPDX-License-Identifier: Apache-2.0
"""Tests for the session guidance block appended to the system prompt (T007).

Verifies:
  - The assembled system prompt contains the geocoding-first rule sentence.
  - The assembled system prompt contains the no-memory-fill rule sentence.
  - The pre-existing cache prefix (sections 1–4) is byte-identical before and
    after the session guidance block is present (cache-stability assertion).

No golden file — all assertions are computed in-test from the live assembler
output so the test stays correct as wording evolves within the same invariants.

Spec reference: specs/019-phase1-hardening/data-model.md § Entity 5
"""

from __future__ import annotations

from kosmos.context.builder import ContextBuilder
from kosmos.context.models import SystemPromptConfig
from kosmos.context.system_prompt import SystemPromptAssembler

# ---------------------------------------------------------------------------
# Verbatim rule sentences from Entity 5 (data-model.md § Entity 5)
# ---------------------------------------------------------------------------

_GEOCODING_FIRST_RULE = (
    "When the citizen's message names a physical district, neighborhood, landmark, "
    "address, station, or walk-in office location, invoke the geocoding tool before "
    "any retrieved adapter whose input schema requires coordinates or an administrative code."
)

_NO_MEMORY_FILL_RULE = (
    "Do not fill administrative region codes from memory; "
    "pass them only after a geocoding tool has produced them in this session."
)


# ---------------------------------------------------------------------------
# Helper: compute the prompt that would be emitted WITHOUT the guidance block
# ---------------------------------------------------------------------------


def _prefix_without_guidance(config: SystemPromptConfig) -> str:
    """Return the system prompt text for sections 1–4 only (no guidance block).

    Reconstructed by joining only the non-guidance sections so we can assert
    the cache prefix is byte-identical regardless of whether the guidance block
    is appended.
    """
    assembler = SystemPromptAssembler()
    # Access the section builders directly to get the prefix sections.
    # Section 3a (trust hierarchy) is unconditional per Epic #466 FR-018.
    # Section 3b (turn-order) added by Spec 2521 — also unconditional, sits
    # between trust-hierarchy and the optional personal-data section.
    sections = [
        assembler._platform_identity_section(config),
        assembler._language_policy_section(config),
        assembler._pipa_safety_section(),
        assembler._tool_use_policy_section(),
        assembler._trust_hierarchy_section(),
        assembler._turn_order_section(),
    ]
    if config.personal_data_warning:
        sections.append(assembler._personal_data_reminder_section())
    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSessionGuidanceBlock:
    """The system prompt emitted by SystemPromptAssembler contains both rule sentences."""

    def test_geocoding_first_rule_present(self) -> None:
        """The geocoding-first rule (Entity 5) must appear in the assembled prompt."""
        assembler = SystemPromptAssembler()
        prompt = assembler.assemble(SystemPromptConfig())
        assert _GEOCODING_FIRST_RULE in prompt, (
            f"Geocoding-first rule sentence not found in system prompt.\n"
            f"Expected substring:\n  {_GEOCODING_FIRST_RULE!r}\n"
            f"Assembled prompt (first 500 chars):\n  {prompt[:500]!r}"
        )

    def test_no_memory_fill_rule_present(self) -> None:
        """The no-memory-fill rule (Entity 5) must appear in the assembled prompt."""
        assembler = SystemPromptAssembler()
        prompt = assembler.assemble(SystemPromptConfig())
        assert _NO_MEMORY_FILL_RULE in prompt, (
            f"No-memory-fill rule sentence not found in system prompt.\n"
            f"Expected substring:\n  {_NO_MEMORY_FILL_RULE!r}\n"
            f"Assembled prompt (first 500 chars):\n  {prompt[:500]!r}"
        )

    def test_guidance_block_appended_after_existing_sections(self) -> None:
        """Session guidance block must appear AFTER all other sections (end-of-prompt)."""
        assembler = SystemPromptAssembler()
        prompt = assembler.assemble(SystemPromptConfig())
        geocoding_pos = prompt.find(_GEOCODING_FIRST_RULE)
        no_memory_pos = prompt.find(_NO_MEMORY_FILL_RULE)

        assert geocoding_pos != -1, "Geocoding-first rule not found in prompt"
        assert no_memory_pos != -1, "No-memory-fill rule not found in prompt"

        # The session guidance block must be appended last (after sections 1-3 and
        # the optional personal-data section). Verify by checking that the geocoding
        # rule appears AFTER the tool-use policy section's distinctive phrase.
        tool_policy_marker = "Use available tools"
        tool_policy_pos = prompt.find(tool_policy_marker)
        assert tool_policy_pos != -1, "Tool-use policy section not found"
        assert geocoding_pos > tool_policy_pos, (
            f"Geocoding-first rule found at position {geocoding_pos}, "
            f"expected it after the tool-use policy section at {tool_policy_pos}. "
            f"The guidance block must be appended last."
        )

    def test_rules_present_with_personal_data_warning(self) -> None:
        """Both rules appear even when the optional personal-data section is included."""
        assembler = SystemPromptAssembler()
        config = SystemPromptConfig(personal_data_warning=True)
        prompt = assembler.assemble(config)
        assert _GEOCODING_FIRST_RULE in prompt
        assert _NO_MEMORY_FILL_RULE in prompt


class TestCacheStability:
    """The pre-existing prompt prefix (sections 1–4) is byte-identical after T006.

    Appending the session guidance block at the END must not mutate any byte
    of the prefix — that invariant ensures the FriendliAI prompt-cache key
    for the existing sections is never invalidated between turns or deploys.
    """

    def test_prefix_byte_identical(self) -> None:
        """Sections 1–4 text is unchanged; guidance is strictly a suffix."""
        config = SystemPromptConfig()
        assembler = SystemPromptAssembler()

        full_prompt = assembler.assemble(config)
        prefix_only = _prefix_without_guidance(config)

        # The full prompt must START with the prefix, byte-identically.
        assert full_prompt.startswith(prefix_only), (
            f"Assembled prompt does not start with the expected prefix.\n"
            f"Expected prefix (last 100 chars): ...{prefix_only[-100:]!r}\n"
            f"Full prompt (first {len(prefix_only) + 50} chars): "
            f"{full_prompt[: len(prefix_only) + 50]!r}"
        )

    def test_prefix_byte_identical_with_personal_data_section(self) -> None:
        """Cache-stability holds even when the personal-data section is included."""
        config = SystemPromptConfig(personal_data_warning=True)
        assembler = SystemPromptAssembler()

        full_prompt = assembler.assemble(config)
        prefix_only = _prefix_without_guidance(config)

        assert full_prompt.startswith(prefix_only), (
            f"Assembled prompt (personal_data_warning=True) does not start with "
            f"the expected prefix.\n"
            f"Expected prefix ends with: ...{prefix_only[-100:]!r}\n"
            f"Full prompt starts with: {full_prompt[: len(prefix_only) + 50]!r}"
        )

    def test_guidance_suffix_separated_by_double_newline(self) -> None:
        """The guidance block must be separated from the prefix by a double newline."""
        config = SystemPromptConfig()
        assembler = SystemPromptAssembler()

        full_prompt = assembler.assemble(config)
        prefix_only = _prefix_without_guidance(config)

        # After the prefix, there must be exactly "\n\n" before the guidance block.
        remainder = full_prompt[len(prefix_only) :]
        assert remainder.startswith("\n\n"), (
            f"Expected '\\n\\n' separator between prefix and guidance block, "
            f"got: {remainder[:20]!r}"
        )

    def test_builder_system_message_contains_rules(self) -> None:
        """ContextBuilder.build_system_message() emits both rule sentences."""
        builder = ContextBuilder()
        msg = builder.build_system_message()
        content = msg.content or ""
        assert _GEOCODING_FIRST_RULE in content, (
            "Geocoding-first rule missing from ContextBuilder.build_system_message()"
        )
        assert _NO_MEMORY_FILL_RULE in content, (
            "No-memory-fill rule missing from ContextBuilder.build_system_message()"
        )
