# SPDX-License-Identifier: Apache-2.0
"""Tests for the live BaroCert verify adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ummaya.primitives.verify import GanpyeonInjeungContext, VerifyMismatchError, verify

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "barocert"


def _fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_explicit_live_tool_returns_redacted_ganpyeon_context() -> None:
    import ummaya.tools.live.verify_barocert_identity  # noqa: F401

    result = await verify(
        "ganpyeon_injeung",
        {
            "_tool_id": "live_verify_ganpyeon_injeung",
            "provider": "toss",
            "receiptID": "TOSS_RECEIPT_SANITIZED_001",
            "_fixture_status": _fixture("toss_status_complete.json"),
            "_fixture_verify": _fixture("toss_verify_complete.json"),
        },
    )

    assert isinstance(result, GanpyeonInjeungContext)
    assert result.family == "ganpyeon_injeung"
    assert result.provider == "toss"
    assert result.published_tier == "ganpyeon_injeung_toss_aal2"
    assert result.nist_aal_hint == "AAL2"
    assert result.external_session_ref == "barocert:toss:TOSS_RECEIPT_SANITIZED_001"
    assert result.transparency_mode is None
    assert "SYNTHETIC_CI_PLACEHOLDER" not in result.model_dump_json()
    assert "SYNTHETIC_DI_PLACEHOLDER" not in result.model_dump_json()
    assert "SYNTHETIC_SIGNED_DATA_PLACEHOLDER" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_non_live_ganpyeon_selection_still_uses_existing_mock() -> None:
    import ummaya.tools.live.verify_barocert_identity  # noqa: F401

    result = await verify("ganpyeon_injeung", {"_tool_id": "mock_verify_ganpyeon_injeung"})

    assert isinstance(result, GanpyeonInjeungContext)
    assert result.provider == "kakao"
    assert result.external_session_ref == "mock-ganpyeon-ref-001"
    assert result.transparency_mode == "mock"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("session_context", "expected_fragment"),
    [
        ({"provider": "toss"}, "missing_receipt_id"),
        (
            {
                "provider": "toss",
                "receiptID": "TOSS_RECEIPT_SANITIZED_001",
                "_fixture_status": _fixture("toss_status_expired.json"),
                "_fixture_verify": _fixture("toss_verify_complete.json"),
            },
            "expired",
        ),
        (
            {
                "provider": "toss",
                "receiptID": "TOSS_RECEIPT_SANITIZED_001",
                "_fixture_status": _fixture("toss_status_complete.json"),
                "_fixture_verify": _fixture("toss_verify_repeated.json"),
            },
            "upstream_error",
        ),
        (
            {
                "provider": "toss",
                "receiptID": "TOSS_RECEIPT_SANITIZED_001",
                "_fixture_status": _fixture("toss_status_complete.json"),
                "_fixture_verify": {
                    "provider": "naver",
                    "receiptID": "TOSS_RECEIPT_SANITIZED_001",
                    "state": 1,
                },
            },
            "provider_mismatch",
        ),
    ],
)
async def test_live_adapter_negative_paths_fail_closed(
    session_context: dict[str, object],
    expected_fragment: str,
) -> None:
    import ummaya.tools.live.verify_barocert_identity  # noqa: F401

    result = await verify(
        "ganpyeon_injeung",
        {"_tool_id": "live_verify_ganpyeon_injeung", **session_context},
    )

    assert isinstance(result, VerifyMismatchError)
    assert result.expected_family == "ganpyeon_injeung"
    assert result.observed_family.startswith("barocert_identity:")
    assert expected_fragment in result.message
