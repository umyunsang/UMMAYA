# SPDX-License-Identifier: Apache-2.0
"""Opt-in live checks for the MobileID verification daemon."""

from __future__ import annotations

import json
import os

import pytest

from ummaya.tools.live.mobileid_client import MobileIdClient
from ummaya.tools.live.verify_mobile_id import LiveMobileIdCheckInput, handle_live_mobile_id_check

pytestmark = pytest.mark.live

_REQUIRED_ENV = (
    "UMMAYA_MOBILEID_BASE_URL",
    "UMMAYA_MOBILEID_CLIENT_ID",
    "UMMAYA_MOBILEID_TEST_TRXCODE",
)


def _mobileid_env_or_skip() -> tuple[str, str, str]:
    values = {name: os.environ.get(name, "").strip() for name in _REQUIRED_ENV}
    missing = [name for name, value in values.items() if not value]
    if missing:
        pytest.skip(
            "set "
            + ", ".join(_REQUIRED_ENV)
            + " to run live MobileID tests; skipping before network access"
        )
    return (
        values["UMMAYA_MOBILEID_BASE_URL"],
        values["UMMAYA_MOBILEID_CLIENT_ID"],
        values["UMMAYA_MOBILEID_TEST_TRXCODE"],
    )


@pytest.mark.asyncio
async def test_live_mobileid_transaction_status_returns_sanitized_context() -> None:
    base_url, client_id, trxcode = _mobileid_env_or_skip()
    client = MobileIdClient(base_url=base_url, client_id=client_id)

    output = await handle_live_mobile_id_check(
        LiveMobileIdCheckInput(trxcode=trxcode),
        client=client,
    )

    serialized = json.dumps(output.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    assert output.family == "mobile_id"
    assert output.external_session_ref == f"mobileid:{trxcode}"
    forbidden_fragments = (
        "residentRegistrationNumber",
        "phoneNumber",
        "birthDate",
        "RAW-VP",
        "ci",
        "di",
    )
    for fragment in forbidden_fragments:
        assert fragment not in serialized
