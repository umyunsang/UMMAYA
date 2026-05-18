# SPDX-License-Identifier: Apache-2.0
"""Opt-in live smoke tests for KB identity check.

These tests require partner-issued KB credentials and network allowlisting.
They are skipped unless both `-m live` and all `UMMAYA_KBCERT_*` variables are
present.
"""

from __future__ import annotations

import os

import pytest

from ummaya.primitives.verify import KbIdentityContext
from ummaya.tools.live.verify_kb_identity import invoke

_REQUIRED_ENV = (
    "UMMAYA_KBCERT_BASE_URL",
    "UMMAYA_KBCERT_API_KEY",
    "UMMAYA_KBCERT_HS_KEY",
    "UMMAYA_KBCERT_COMPANY_CD",
)


def _skip_without_kb_credentials() -> None:
    missing = [name for name in _REQUIRED_ENV if not os.environ.get(name, "").strip()]
    if missing:
        pytest.skip("KB identity live test credentials are not configured: " + ", ".join(missing))


def test_live_kb_identity_credentials_are_explicit() -> None:
    """Default non-live selection has a no-network guard test in this file."""
    assert "UMMAYA_KBCERT_API_KEY" in _REQUIRED_ENV
    assert "UMMAYA_KBCERT_HS_KEY" in _REQUIRED_ENV


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_kb_identity_request_smoke() -> None:
    _skip_without_kb_credentials()

    result = await invoke({"mode": "request", "reqTxId": "ummaya-live-synthetic-req-tx-id"})

    assert isinstance(result, KbIdentityContext)
    assert result.external_session_ref is not None
    assert "CI" not in result.model_dump_json()
    assert "DI" not in result.model_dump_json()
