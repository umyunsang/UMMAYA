# SPDX-License-Identifier: Apache-2.0
"""Tool description 5-section string template helper for v4 GovAPITool.llm_description.

Implements the DescriptionSection 5-section skeleton from data-model.md.
Token budget: ≤ 500 tokens per tool, ≤ 100 tokens per section.

Token counting: stdlib-only approximation.
  - ASCII word ≈ 1 token per word
  - Korean character ≈ 1 token per character (UTF-8: ~3 bytes, roughly 1 BPE token)
  - Mixed: count Korean chars + non-Korean words separately
  Formula: len(korean_chars) + len(non_korean_text.split())
"""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)

# Token budget constants (data-model.md Constraints)
_MAX_TOKENS_PER_TOOL: int = 500
_MAX_TOKENS_PER_SECTION: int = 100


def _estimate_tokens(text: str) -> int:
    """Estimate token count for mixed Korean/English text without external deps.

    Approximation (stdlib-only):
    - Korean characters (Hangul syllables U+AC00-U+D7A3) each ≈ 1 token
    - Remaining text split on whitespace: each word ≈ 1 token
    This is conservative but consistent with tiktoken BPE behaviour on Korean.
    """
    korean_chars = [c for c in text if "가" <= c <= "힣"]
    non_korean = "".join(c if "가" > c or c > "힣" else " " for c in text)
    non_korean_words = [w for w in non_korean.split() if w.strip()]
    return len(korean_chars) + len(non_korean_words)


def _validate_section(name: str, text: str) -> None:
    """Raise ValueError if a single section exceeds the per-section token budget."""
    count = _estimate_tokens(text)
    if count > _MAX_TOKENS_PER_SECTION:
        raise ValueError(
            f"Description section '{name}' exceeds {_MAX_TOKENS_PER_SECTION}-token budget "
            f"(estimated {count} tokens). Shorten to ≤ {_MAX_TOKENS_PER_SECTION} tokens."
        )


def build_description_v4(
    purpose: str,
    input_quirk: str,
    short_reference: str,
    domain_quirk: str,
    self_contained_decl: str,
) -> str:
    """Assemble a 5-section llm_description string for a GovAPITool (v4 skeleton).

    Each positional argument maps to one DescriptionSection (data-model.md):
      1. ``purpose``            — 목적 (1-2 문장)
      2. ``input_quirk``        — 입력 quirk (param 명, encoding, 필수/선택)
      3. ``short_reference``    — 17 광역시도 short reference inline (≤ 200 tokens)
      4. ``domain_quirk``       — domain-specific quirk (base_time, _type=json, …)
      5. ``self_contained_decl``— self-contained + autonomous chain 권장

    Token budget (enforced at call time):
      - Each section:  ≤ 100 tokens (estimated via _estimate_tokens)
      - Full combined: ≤ 500 tokens

    Args:
        purpose: Section 1 — what this tool does.
        input_quirk: Section 2 — key input parameter notes.
        short_reference: Section 3 — 17 metropolitan region reference table.
        domain_quirk: Section 4 — agency-specific timing, encoding, or code quirks.
        self_contained_decl: Section 5 — self-contained declaration + LLM chain guidance.

    Returns:
        A plain-text string suitable for ``GovAPITool.llm_description``.

    Raises:
        ValueError: If any section or the combined total exceeds the token budget.
    """
    sections = {
        "purpose": purpose,
        "input_quirk": input_quirk,
        "short_reference": short_reference,
        "domain_quirk": domain_quirk,
        "self_contained_decl": self_contained_decl,
    }

    for name, text in sections.items():
        _validate_section(name, text)

    combined = "\n\n".join(
        [purpose, input_quirk, short_reference, domain_quirk, self_contained_decl]
    )

    total = _estimate_tokens(combined)
    if total > _MAX_TOKENS_PER_TOOL:
        raise ValueError(
            f"Combined description exceeds {_MAX_TOKENS_PER_TOOL}-token budget "
            f"(estimated {total} tokens). Reduce section lengths."
        )

    _log.debug(
        "build_description_v4: %d estimated tokens (budget %d)",
        total,
        _MAX_TOKENS_PER_TOOL,
    )
    return combined
