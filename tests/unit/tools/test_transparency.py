# SPDX-License-Identifier: Apache-2.0
"""T004 — stamp_mock_response() unit tests.

Covers:
- Happy path: six fields stamped onto the payload dict.
- Empty-string rejection: any of the five caller-supplied values being empty
  or whitespace-only raises ValueError.

Contract: specs/2296-ax-mock-adapters/contracts/mock-adapter-response-shape.md § 1
"""

from __future__ import annotations

import pytest

from kosmos.tools.transparency import stamp_mock_response

# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

_VALID_KWARGS = {
    "reference_implementation": "ax-infrastructure-callable-channel",
    "actual_endpoint_when_live": "https://api.gateway.kosmos.gov.kr/v1/verify/modid",
    "security_wrapping_pattern": "OID4VP + DID-resolved RP + DPoP",
    "policy_authority": "https://www.mois.go.kr/frt/bbs/type001/commonSelectBoardArticle.do",
    "international_reference": "EU EUDI Wallet",
}


def test_stamp_mock_response_happy_path() -> None:
    """stamp_mock_response stamps all six fields and preserves original payload."""
    payload = {"citizen_id": "citizen-abc", "verified": True}
    result = stamp_mock_response(payload, **_VALID_KWARGS)

    # Original keys preserved.
    assert result["citizen_id"] == "citizen-abc"
    assert result["verified"] is True

    # Six transparency fields added.
    assert result["_mode"] == "mock"
    assert result["_reference_implementation"] == "ax-infrastructure-callable-channel"
    assert result["_actual_endpoint_when_live"] == (
        "https://api.gateway.kosmos.gov.kr/v1/verify/modid"
    )
    assert result["_security_wrapping_pattern"] == "OID4VP + DID-resolved RP + DPoP"
    assert result["_policy_authority"].startswith("https://")
    assert result["_international_reference"] == "EU EUDI Wallet"


def test_stamp_mock_response_returns_new_dict() -> None:
    """stamp_mock_response does not mutate the original payload dict."""
    payload: dict = {"key": "value"}
    result = stamp_mock_response(payload, **_VALID_KWARGS)
    assert result is not payload
    assert "_mode" not in payload


def test_stamp_mock_response_empty_payload_works() -> None:
    """Stamping an empty payload dict is valid."""
    result = stamp_mock_response({}, **_VALID_KWARGS)
    assert result["_mode"] == "mock"
    assert len(result) == 6  # exactly 6 transparency fields


def test_stamp_mock_response_optional_evidence_fields() -> None:
    """Adapters may attach evidence-grade metadata for privileged mocks."""
    evidence = {
        "credential_status": "student_no_live_authority",
        "basis_urls": ["https://example.gov.test/spec"],
        "inference_boundary": "Private payload is inferred.",
        "live_swap_requirements": ["official approval"],
    }
    result = stamp_mock_response(
        {"receipt_id": "mock-001"},
        **_VALID_KWARGS,
        mock_fidelity_grade="B-official-flow-private-spec-inferred",
        mock_evidence=evidence,
    )

    assert result["_mock_fidelity_grade"] == "B-official-flow-private-spec-inferred"
    assert result["_mock_evidence"] == evidence


# ---------------------------------------------------------------------------
# Empty-string / whitespace rejection paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field_name, bad_value",
    [
        ("reference_implementation", ""),
        ("reference_implementation", "   "),
        ("actual_endpoint_when_live", ""),
        ("actual_endpoint_when_live", "\t"),
        ("security_wrapping_pattern", ""),
        ("policy_authority", ""),
        ("international_reference", ""),
    ],
)
def test_stamp_mock_response_rejects_empty(field_name: str, bad_value: str) -> None:
    """Any empty or whitespace-only caller-supplied value must raise ValueError."""
    kwargs = {**_VALID_KWARGS, field_name: bad_value}
    with pytest.raises(ValueError, match="non-empty"):
        stamp_mock_response({"key": "value"}, **kwargs)


def test_stamp_mock_response_rejects_empty_evidence_grade() -> None:
    """Evidence grade is optional, but if provided it must be non-empty."""
    with pytest.raises(ValueError, match="mock_fidelity_grade"):
        stamp_mock_response(
            {"key": "value"},
            **_VALID_KWARGS,
            mock_fidelity_grade=" ",
        )


def test_stamp_mock_response_rejects_empty_evidence_object() -> None:
    """Evidence object is optional, but if provided it must not be empty."""
    with pytest.raises(ValueError, match="mock_evidence"):
        stamp_mock_response(
            {"key": "value"},
            **_VALID_KWARGS,
            mock_evidence={},
        )
