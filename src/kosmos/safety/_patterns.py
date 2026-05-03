# SPDX-License-Identifier: Apache-2.0
"""Single source of truth for PII detection patterns used across KOSMOS safety layers.

(a) This module is the canonical SoT for ``_PII_PATTERNS`` and
    ``PII_ACCEPTING_PARAMS``.  Both ``step3_params.py`` (permission gate) and
    ``_redactor.py`` (output redaction) import from here so the pattern set
    never drifts between the two callers.

(b) ``_PII_PATTERNS`` is ``_``-prefixed to signal that it is an internal
    constant not intended as part of the public package API.  The underscore
    prefix is a convention only; the dict is still imported by the two modules
    above because they share the same package tree.

(c) ``luhn_valid()`` is used exclusively by the redactor (``_redactor.py``) as
    a post-filter to eliminate false-positive ``credit_card`` regex matches.
    Step 3 (``step3_params.py``) intentionally keeps regex-only behavior and
    does NOT call ``luhn_valid()``.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# PII regex patterns
# ---------------------------------------------------------------------------

# Mapping of PII type label to compiled pattern.
# Patterns use re.search so they catch PII embedded inside longer strings.
_PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "rrn": re.compile(r"\d{6}-[1-4]\d{6}"),
    "phone_kr": re.compile(r"01[016789]-?\d{3,4}-?\d{4}"),
    "email": re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    "passport_kr": re.compile(r"[A-Z]\d{8}"),
    "credit_card": re.compile(r"\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}"),
}

# ---------------------------------------------------------------------------
# PII-accepting parameter names
# ---------------------------------------------------------------------------

# Parameter names that are explicitly declared as PII-accepting.  Tools that
# legitimately take these values (e.g., identity-verification endpoints) list
# the parameter names here so step 3 skips the scan for those keys.
# This set is intentionally conservative and kept small.
PII_ACCEPTING_PARAMS: frozenset[str] = frozenset(
    {
        "citizen_id",  # Citizen identifier field in personal-data tools
        "resident_number",  # RRN parameter for identity verification tools
        "phone_number",  # Explicit phone-number input fields
        "passport_number",  # Passport number for travel/identity APIs
    }
)

# ---------------------------------------------------------------------------
# Injection detection patterns — used exclusively by _injection.py
# ---------------------------------------------------------------------------

# Expected length heuristic constant for tool outputs (median chars in a
# well-formed KOSMOS adapter response).  Used by the length-deviation signal
# in run_detector(); exposed here to keep _patterns.py as the single source
# of truth for all pattern constants.
EXPECTED_LEN: int = 512

# Mapping of injection category label → list of compiled case-insensitive
# regex patterns.  Score = (distinct category hits) / len(_INJECTION_PATTERNS).
# NOTE: this is structural/regex-based detection, NOT a static keyword
# blocklist.  Adding entries must be justified by a concrete attack taxonomy
# reference (arXiv 2504.11168 / OWASP LLM01).
_INJECTION_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "role_assumption": [
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+\w+", re.IGNORECASE),
        re.compile(r"act\s+as\s+(an?\s+)?\w+", re.IGNORECASE),
        # Korean canonical: "이전 지시를 무시" (ignore previous instructions)
        # — direct LLM01 jailbreak phrasing, matches arXiv 2504.11168 taxonomy.
        re.compile(r"\uc774\uc804\s*\uc9c0\uc2dc\ub97c?\s*\ubb34\uc2dc", re.IGNORECASE),
        # Korean variant: "이전 지시를 도모" — role-assumption signal (Edge Case E-2)
        re.compile(r"\uc774\uc804\s*\uc9c0\uc2dc\ub97c?\s*\ub3c4\ubaa8", re.IGNORECASE),
    ],
    "system_override": [
        re.compile(r"</?system>", re.IGNORECASE),
        re.compile(r"\[\s*(INST|SYSTEM)\s*\]", re.IGNORECASE),
        re.compile(r"\[\[/?INST\]\]", re.IGNORECASE),
    ],
    "exfiltration_lure": [
        re.compile(r"print\s+(the\s+)?contents?\s+of", re.IGNORECASE),
        re.compile(r"\.env\b", re.IGNORECASE),
        re.compile(r"~/\.ssh", re.IGNORECASE),
        # Indirect-injection wrapper — an attacker wraps a payload in an
        # opaque encoding (base64/hex) and asks the LLM to "decode and
        # execute" it. Belongs in this category because the wrapper text is
        # the lure that drives the LLM toward acting on otherwise-opaque
        # bytes. Kept inside `exfiltration_lure` (not a new category) so the
        # 3-category denominator stays stable — adding a 4th category would
        # demote a single-category hit from 0.20 (block) to 0.15 (allow).
        # Without these patterns, the integration-verification fix in
        # _injection.py (require `structural > 0` to block) would let ep-001
        # through: base64-encoded "Ignore all previous instructions / DAN /
        # Reveal all secrets" preceded by "Execute the following
        # base64-encoded instruction:". Normal opaque identifier responses
        # (e.g., HIRA `ykiho` field) carry no such wrapper directive and
        # remain in the allow lane.
        re.compile(
            r"(execute|run|decode|interpret|process)\s+(the\s+)?(following|this|below)?\s*(base64|hex|encoded)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(base64|hex|encoded)[\-\s]?(encoded|decoded)?\s+(instruction|command|payload|directive)",
            re.IGNORECASE,
        ),
    ],
}

# ---------------------------------------------------------------------------
# Luhn checksum (ISO/IEC 7812) — used by _redactor.py only
# ---------------------------------------------------------------------------


def luhn_valid(value: str) -> bool:
    """Return True if *value* passes the ISO/IEC 7812 Luhn checksum.

    Non-digit characters are stripped before validation.  Returns False
    immediately when the resulting digit-string is not exactly 16 characters
    long (matching the reach of the ``credit_card`` regex above).

    This function is called by ``_redactor.py`` as a post-filter to discard
    ``credit_card`` regex matches that are not plausible card numbers.
    ``step3_params.py`` (permission gate, Step 3) intentionally does NOT call
    this function — Step 3 keeps regex-only behaviour byte-unchanged.
    """
    digits = re.sub(r"\D", "", value)
    if len(digits) != 16:
        return False

    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:  # every second digit from the right (0-indexed)
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0
