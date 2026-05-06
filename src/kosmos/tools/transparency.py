# SPDX-License-Identifier: Apache-2.0
"""Shared transparency-field stamper for all Mock adapter responses.

Epic ε #2296 — FR-005 / FR-006 / FR-024 / FR-025 / SC-005.

Contract: specs/2296-ax-mock-adapters/contracts/mock-adapter-response-shape.md § 1

Every Mock adapter MUST call ``stamp_mock_response()`` to produce its final
response dict.  Live adapters MUST NOT call this function.

Canonical usage pattern (per-adapter module)::

    _REFERENCE_IMPL: Final = "ax-infrastructure-callable-channel"
    _ACTUAL_ENDPOINT: Final = "https://api.gateway.kosmos.gov.kr/v1/verify/modid"
    _SECURITY_WRAPPING: Final = "OID4VP + DID-resolved RP + DPoP"
    _POLICY_AUTHORITY: Final = "https://www.mois.go.kr/.../mobile-id-policy.do"
    _INTERNATIONAL_REF: Final = "EU EUDI Wallet"

    def invoke(session_context: dict[str, Any]) -> dict[str, Any]:
        domain_payload = {...}
        return stamp_mock_response(
            domain_payload,
            reference_implementation=_REFERENCE_IMPL,
            actual_endpoint_when_live=_ACTUAL_ENDPOINT,
            security_wrapping_pattern=_SECURITY_WRAPPING,
            policy_authority=_POLICY_AUTHORITY,
            international_reference=_INTERNATIONAL_REF,
        )
"""

from __future__ import annotations

from typing import Any, Final

__all__ = ["stamp_mock_response"]

# ---------------------------------------------------------------------------
# Module-level constant — never changes in Epic ε
# ---------------------------------------------------------------------------

_MODE_VALUE: Final = "mock"


# ---------------------------------------------------------------------------
# stamp_mock_response
# ---------------------------------------------------------------------------


def stamp_mock_response(
    payload: dict[str, Any],
    *,
    reference_implementation: str,
    actual_endpoint_when_live: str,
    security_wrapping_pattern: str,
    policy_authority: str,
    international_reference: str,
    mock_fidelity_grade: str | None = None,
    mock_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Stamp the six transparency fields onto a Mock adapter response payload.

    Pure function — caller passes a dict, receives a new dict.  The original
    ``payload`` is NOT mutated; the six transparency fields are merged on top.
    Adapters may also attach evidence-grade metadata when their private-domain
    shape is inferred from official flow documentation rather than a public
    callable API schema.

    Args:
        payload: Domain-specific response payload from the Mock adapter.
        reference_implementation: Non-empty; the AX-channel reference family
            this adapter mirrors.  Recommended values:
            ``"ax-infrastructure-callable-channel"`` (Singapore-APEX-style
            verify/submit), ``"public-mydata-action-extension"`` (마이데이터 write
            extension), ``"public-mydata-read-v240930"`` (마이데이터 read existing).
        actual_endpoint_when_live: Non-empty; URL the agency is expected to expose
            when the policy mandate ships.
        security_wrapping_pattern: Non-empty; security stack the channel is
            expected to use, e.g. ``"OAuth2.1 + mTLS + scope-bound bearer"``.
        policy_authority: Non-empty; URL of the agency-published policy.
        international_reference: Non-empty; closest international-analog system,
            e.g. ``"Singapore APEX"``, ``"Estonia X-Road"``, ``"EU EUDI Wallet"``.
        mock_fidelity_grade: Optional non-empty evidence grade for the mock shape.
        mock_evidence: Optional non-empty evidence object. Intended keys include
            ``credential_status``, ``basis_urls``, ``inference_boundary``, and
            ``live_swap_requirements``.

    Returns:
        New dict with ``payload`` keys plus the six transparency fields.

    Raises:
        ValueError: If any of the five caller-supplied values is empty or
            whitespace-only.
    """
    caller_values: tuple[str, ...] = (
        reference_implementation,
        actual_endpoint_when_live,
        security_wrapping_pattern,
        policy_authority,
        international_reference,
    )
    if not all(s.strip() for s in caller_values):
        raise ValueError(
            "stamp_mock_response: all five transparency-field values must be "
            "non-empty, non-whitespace strings.  "
            f"Got: reference_implementation={reference_implementation!r}, "
            f"actual_endpoint_when_live={actual_endpoint_when_live!r}, "
            f"security_wrapping_pattern={security_wrapping_pattern!r}, "
            f"policy_authority={policy_authority!r}, "
            f"international_reference={international_reference!r}."
        )
    if mock_fidelity_grade is not None and not mock_fidelity_grade.strip():
        raise ValueError("stamp_mock_response: mock_fidelity_grade must be non-empty.")
    if mock_evidence is not None and not mock_evidence:
        raise ValueError("stamp_mock_response: mock_evidence must be a non-empty dict.")

    stamped: dict[str, Any] = {
        **payload,
        "_mode": _MODE_VALUE,
        "_reference_implementation": reference_implementation,
        "_actual_endpoint_when_live": actual_endpoint_when_live,
        "_security_wrapping_pattern": security_wrapping_pattern,
        "_policy_authority": policy_authority,
        "_international_reference": international_reference,
    }
    if mock_fidelity_grade is not None:
        stamped["_mock_fidelity_grade"] = mock_fidelity_grade
    if mock_evidence is not None:
        stamped["_mock_evidence"] = mock_evidence
    return stamped
