# SPDX-License-Identifier: Apache-2.0
"""Opt-in live validation for the BaroCert Toss identity check adapter."""

from __future__ import annotations

import os

import pytest

from ummaya.primitives.verify import GanpyeonInjeungContext, verify

pytestmark = pytest.mark.live

_REQUIRED_ENV = (
    "UMMAYA_BAROCERT_LINK_ID",
    "UMMAYA_BAROCERT_SECRET_KEY",
    "UMMAYA_BAROCERT_CLIENT_CODE",
    "UMMAYA_BAROCERT_TEST_RECEIPT_ID",
)


def _missing_env() -> list[str]:
    return [name for name in _REQUIRED_ENV if not os.environ.get(name, "").strip()]


@pytest.mark.skipif(bool(_missing_env()), reason="BaroCert live credentials are not configured")
@pytest.mark.asyncio
async def test_live_barocert_toss_receipt_verifies_without_identity_payload() -> None:
    import ummaya.tools.live.verify_barocert_identity  # noqa: F401

    result = await verify(
        "ganpyeon_injeung",
        {
            "_tool_id": "live_verify_ganpyeon_injeung",
            "provider": "toss",
            "receiptID": os.environ["UMMAYA_BAROCERT_TEST_RECEIPT_ID"],
        },
    )

    assert isinstance(result, GanpyeonInjeungContext)
    assert result.provider == "toss"
    dumped = result.model_dump_json()
    assert "ci" not in dumped.lower()
    assert "di" not in dumped.lower()
    assert "signedData" not in dumped
