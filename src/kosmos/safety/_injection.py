# SPDX-License-Identifier: Apache-2.0
"""Indirect prompt-injection detector for KOSMOS tool outputs.

Implements ``run_detector(text) -> InjectionSignalSet`` — the Layer C
detection function described in specs/026-safety-rails/spec.md § Layer C.

Three-signal model
------------------
1. **Structural score** — regex-family match against ``_INJECTION_PATTERNS``
   (defined in ``_patterns.py``, the single source of truth).  Score is the
   fraction of distinct categories that match at least one pattern (max 1.0).
2. **Entropy score** — Shannon entropy of the longest base64/hex-like
   substrings (≥ 32 chars).  High entropy signals encoded payloads.
3. **Length deviation** — ``abs(log10(len(text) / EXPECTED_LEN)) / 2.0``
   clamped to [0, 1].  Unusually short or long inputs are suspicious.

Combined score = 0.6 × structural + 0.25 × entropy + 0.15 × length_deviation.
Decision: ``"block"`` if combined ≥ ``_BLOCK_THRESHOLD`` (currently 0.20 —
tuned down from the 0.50 spec seed after the SC-004 audit; see the weights
block below for rationale), else ``"allow"``.

# SC-004: False-positive audit (T025) on the recorded adapter corpus confirmed
# weights [0.6, 0.25, 0.15] produce zero false positives.  Do NOT change the
# weights without re-running the SC-004 audit and updating fp_audit.json.
"""

from __future__ import annotations

import math
import re

from kosmos.safety._models import InjectionSignalSet
from kosmos.safety._patterns import _INJECTION_PATTERNS, EXPECTED_LEN

# ---------------------------------------------------------------------------
# Signal weights — SC-004: audit verified zero FP on recorded corpus
# Threshold tuned down to 0.20 from the initial 0.50 spec seed because:
#   - single-category structural hit contributes 0.6 × (1/3) ≈ 0.20
#   - max clean-corpus score observed was 0.035 (pure length deviation)
# This creates a safe margin of ~0.17 between the lowest injections block
# score and the highest clean-corpus allow score.
# ---------------------------------------------------------------------------

_W_STRUCTURAL: float = 0.6
_W_ENTROPY: float = 0.25
_W_LENGTH: float = 0.15
_BLOCK_THRESHOLD: float = 0.20  # SC-004: tuned from 0.5; see fp_audit.json

# Float-edge tolerance for the block comparison.
# Rationale: a single-category structural hit computes `0.6 * (1/3)` which
# evaluates to `0.19999999999999998` under IEEE-754 — just below the nominal
# 0.20 threshold.  Subtracting a small epsilon from the threshold keeps the
# intended decision boundary (single-category hit ⇒ block) stable without
# widening the allow-side margin.  Value chosen to be well below the observed
# clean-corpus max score (0.035) per the SC-004 audit.
_BLOCK_EPS: float = 1e-9

# Substrings of at least this many characters are examined for entropy.
_MIN_ENCODED_LEN: int = 32

# Typical Shannon entropy ceilings for normalisation:
#   base64 alphabet: ~4.5 bits/char
#   hex alphabet:    ~3.8 bits/char
_BASE64_ENTROPY_CEIL: float = 4.5
_HEX_ENTROPY_CEIL: float = 3.8

# Regex for candidate encoded substrings (compiled once at module load).
_RE_BASE64_CANDIDATE: re.Pattern[str] = re.compile(r"[A-Za-z0-9+/=]{32,}")
_RE_HEX_CANDIDATE: re.Pattern[str] = re.compile(r"[0-9a-fA-F]{32,}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _shannon_entropy(s: str) -> float:
    """Compute per-character Shannon entropy (bits) of string *s*."""
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    total = len(s)
    entropy = 0.0
    for count in freq.values():
        p = count / total
        entropy -= p * math.log2(p)
    return entropy


def _compute_structural_score(text: str) -> float:
    """Return fraction of injection categories that match at least once."""
    hit_categories: set[str] = set()
    for category, patterns in _INJECTION_PATTERNS.items():
        for pat in patterns:
            if pat.search(text):
                hit_categories.add(category)
                break  # one hit per category is enough
    n_categories = len(_INJECTION_PATTERNS)
    return len(hit_categories) / n_categories if n_categories > 0 else 0.0


def _compute_entropy_score(text: str) -> float:
    """Return normalised entropy score over base64/hex candidate substrings."""
    max_score = 0.0

    # Base64 candidates (broader alphabet including '/')
    for match in _RE_BASE64_CANDIDATE.finditer(text):
        candidate = match.group()
        if len(candidate) >= _MIN_ENCODED_LEN:
            ent = _shannon_entropy(candidate)
            score = min(ent / _BASE64_ENTROPY_CEIL, 1.0)
            max_score = max(max_score, score)

    # Pure hex candidates — scanned independently (hex is a strict subset of
    # the base64 alphabet, so these ranges overlap, but we keep the per-
    # candidate ``max_score`` so the stronger of the two ceilings wins).
    for match in _RE_HEX_CANDIDATE.finditer(text):
        candidate = match.group()
        if len(candidate) >= _MIN_ENCODED_LEN:
            ent = _shannon_entropy(candidate)
            score = min(ent / _HEX_ENTROPY_CEIL, 1.0)
            max_score = max(max_score, score)

    return max_score


def _compute_length_deviation(text: str) -> float:
    """Return normalised length-deviation score in [0, 1]."""
    length = max(len(text), 1)
    deviation = abs(math.log10(length / EXPECTED_LEN))
    return min(deviation / 2.0, 1.0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_detector(text: str) -> InjectionSignalSet:
    """Analyse *text* for indirect-prompt-injection signals.

    Returns an :class:`~kosmos.safety._models.InjectionSignalSet` with the
    individual signal scores and a combined ``decision`` of ``"block"`` or
    ``"allow"``.

    The combined score is:

        combined = 0.6 × structural + 0.25 × entropy + 0.15 × length_deviation

    Decision is ``"block"`` when ``combined ≥ _BLOCK_THRESHOLD`` (see the
    module-level constant, currently ``0.20``).
    """
    structural = _compute_structural_score(text)
    entropy = _compute_entropy_score(text)
    length_dev = _compute_length_deviation(text)

    combined = _W_STRUCTURAL * structural + _W_ENTROPY * entropy + _W_LENGTH * length_dev

    # Block decision (integration-verification follow-up — 2026-05-03):
    # require ≥ 1 structural-pattern category hit AS WELL AS the combined
    # score crossing _BLOCK_THRESHOLD. Pure entropy or pure length-deviation
    # signals are treated as auxiliary — they amplify a structural hit but
    # never trigger a block on their own.
    #
    # Rationale: the 0.20 threshold was tuned around "single-category
    # structural hit ≈ 0.20" (see _BLOCK_EPS comment) under the assumption
    # that legitimate corpora cap out around 0.035. The Layer-5 verification
    # pass disproved that assumption — HIRA's `ykiho` field carries an
    # 80-char base64-like opaque identifier (entropy ~4.17 → normalized ~0.93
    # → weighted ~0.23) that crosses the threshold without any LLM01-style
    # structural pattern present. The result was a 100% false-positive block
    # for the medical hospital adapter (verified at integration-verification
    # frame 09-tool-hospital). True indirect-prompt-injection attacks
    # essentially always carry at least one structural-pattern signal
    # (role assumption, system override, or exfiltration lure) — requiring
    # `structural > 0` preserves Layer-C protection on real attacks while
    # eliminating the opaque-identifier false positive.
    #
    # Use float-tolerant comparison so a single-category structural hit
    # (0.6 × 1/3 = 0.19999…) still trips the 0.20 threshold; see _BLOCK_EPS.
    decision: str = (
        "block" if structural > 0 and combined >= _BLOCK_THRESHOLD - _BLOCK_EPS else "allow"
    )

    return InjectionSignalSet(
        structural_score=structural,
        entropy_score=entropy,
        length_deviation=length_dev,
        decision=decision,  # type: ignore[arg-type]
    )
