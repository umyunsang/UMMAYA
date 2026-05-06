# SPDX-License-Identifier: Apache-2.0
"""Unit tests for mock_koroad_driver_fitness_reservation_v1."""

from __future__ import annotations

import pytest

from kosmos.primitives.submit import SubmitStatus

_TRANSPARENCY_FIELDS = (
    "_mode",
    "_reference_implementation",
    "_actual_endpoint_when_live",
    "_security_wrapping_pattern",
    "_policy_authority",
    "_international_reference",
)


@pytest.mark.asyncio
async def test_koroad_driver_fitness_reservation_happy_path() -> None:
    from kosmos.tools.mock.koroad.driver_fitness_reservation import invoke

    result = await invoke(
        {
            "reservation_type": "fitness_test",
            "applicant_id": "mock-applicant",
            "preferred_center": "부산남부운전면허시험장",
            "preferred_date": "next_available",
            "contact_channel": "sms",
        }
    )

    assert result.status == SubmitStatus.succeeded
    receipt = result.adapter_receipt
    assert str(receipt["receipt_id"]).startswith("koroad-resv-")
    assert receipt["reservation_status"] == "reserved"
    assert receipt["reservation_type"] == "fitness_test"


@pytest.mark.asyncio
async def test_koroad_driver_fitness_reservation_transparency_fields_present() -> None:
    from kosmos.tools.mock.koroad.driver_fitness_reservation import invoke

    result = await invoke({"applicant_id": "mock-applicant"})

    receipt = result.adapter_receipt
    for field in _TRANSPARENCY_FIELDS:
        value = receipt.get(field)
        assert isinstance(value, str) and value.strip(), (
            f"Missing or empty {field!r} in adapter_receipt"
        )
    assert receipt["_mode"] == "mock"
    assert receipt["_policy_authority"].startswith("https://www.safedriving.or.kr/")
    assert receipt["_mock_fidelity_grade"] == (
        "C-official-flow-documented-private-submit-api-inferred"
    )
