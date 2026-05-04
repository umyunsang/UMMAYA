# SPDX-License-Identifier: Apache-2.0
"""Unit tests for envelope normalization — T022.

Tests:
- Wrong ``kind`` discriminator raises ``EnvelopeNormalizationError`` (FR-015).
- Handler exceptions are converted to ``LookupError`` (FR-017).
- ``normalize()`` injects full meta block (FR-014).
- ``make_error_envelope()`` builds a valid ``LookupError`` with meta.

No live API calls are made.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from kosmos.tools.envelope import make_error_envelope, normalize
from kosmos.tools.errors import EnvelopeNormalizationError
from kosmos.tools.models import (
    GovAPITool,
    LookupCollection,
    LookupError,  # noqa: A004
    LookupRecord,
)

# ---------------------------------------------------------------------------
# Helpers: minimal GovAPITool fixture
# ---------------------------------------------------------------------------


class _MinInput(BaseModel):
    q: str


class _MinOutput(BaseModel):
    result: str


def _make_tool(tool_id: str = "test_tool") -> GovAPITool:
    return GovAPITool(
        id=tool_id,
        name_ko="테스트도구",
        ministry="OTHER",
        category=["test"],
        endpoint="https://apis.data.go.kr/test",
        auth_type="api_key",
        input_schema=_MinInput,
        output_schema=_MinOutput,
        search_hint="test 테스트",
        auth_level="AAL1",
        pipa_class="non_personal",
        is_irreversible=False,
        dpa_reference=None,
        requires_auth=True,
        is_personal_data=False,
    )


_REQUEST_ID = str(uuid.uuid4())
_TOOL = _make_tool()


# ---------------------------------------------------------------------------
# Tests: normalize() — happy paths
# ---------------------------------------------------------------------------


class TestNormalizeHappyPath:
    def test_collection_dict_injects_meta(self):
        """A raw dict with kind='collection' gets meta injected and validated."""
        raw = {
            "kind": "collection",
            "items": [{"spot_nm": "강남구 개포동", "occrrnc_cnt": 12}],
            "total_count": 1,
        }
        result = normalize(raw, tool=_TOOL, request_id=_REQUEST_ID, elapsed_ms=100)
        assert isinstance(result, LookupCollection)
        assert result.kind == "collection"
        assert result.meta.source == _TOOL.id
        assert result.meta.request_id == _REQUEST_ID
        assert result.meta.elapsed_ms == 100
        assert isinstance(result.meta.fetched_at, datetime)
        # Citizen-facing meta MUST stamp Asia/Seoul (KST, UTC+09:00).
        # Regression guard for Epic #2766 issue A — prior behavior stamped UTC
        # which made timestamps appear as the previous day in the morning.
        # Pydantic v2 deserializes ZoneInfo into a fixed-offset TzInfo; assert
        # by UTC offset (9h) rather than identity.
        from datetime import timedelta

        assert result.meta.fetched_at.utcoffset() == timedelta(hours=9)

    def test_record_dict_injects_meta(self):
        """A raw dict with kind='record' gets meta injected and validated."""
        raw = {
            "kind": "record",
            "item": {"temperature": 22.5},
        }
        result = normalize(raw, tool=_TOOL, request_id=_REQUEST_ID, elapsed_ms=50)
        assert isinstance(result, LookupRecord)
        assert result.meta.elapsed_ms == 50

    def test_pydantic_model_input_works(self):
        """A Pydantic model input is converted via model_dump() before validation."""
        collection = LookupCollection(
            kind="collection",
            items=[{"x": 1}],
            total_count=1,
            meta={
                "source": "other_tool",
                "fetched_at": datetime.now(tz=UTC),
                "request_id": _REQUEST_ID,
                "elapsed_ms": 10,
            },
        )
        # normalize() always overwrites meta with the current request's meta
        result = normalize(collection, tool=_TOOL, request_id=_REQUEST_ID, elapsed_ms=75)
        assert isinstance(result, LookupCollection)
        assert result.meta is not None

    def test_elapsed_ms_clamped_to_zero_minimum(self):
        """Negative elapsed_ms is clamped to 0 in the meta block."""
        raw = {
            "kind": "collection",
            "items": [],
            "total_count": 0,
        }
        result = normalize(raw, tool=_TOOL, request_id=_REQUEST_ID, elapsed_ms=-99)
        assert isinstance(result, LookupCollection)
        assert result.meta.elapsed_ms == 0


# ---------------------------------------------------------------------------
# Tests: normalize() — discriminator mismatch raises EnvelopeNormalizationError
# ---------------------------------------------------------------------------


class TestNormalizeDiscriminatorMismatch:
    def test_unknown_kind_raises_envelope_error(self):
        """A dict with an unknown kind must raise EnvelopeNormalizationError (FR-015)."""
        raw = {"kind": "unknown_kind", "data": "x"}
        with pytest.raises(EnvelopeNormalizationError):
            normalize(raw, tool=_TOOL, request_id=_REQUEST_ID, elapsed_ms=0)

    def test_timeseries_invalid_interval_raises(self):
        """Invalid interval value in timeseries fails validation."""
        raw = {
            "kind": "timeseries",
            "points": [],
            "interval": "month",  # not in enum: minute|hour|day
        }
        with pytest.raises(EnvelopeNormalizationError):
            normalize(raw, tool=_TOOL, request_id=_REQUEST_ID, elapsed_ms=0)

    def test_non_dict_non_model_raises_envelope_error(self):
        """A handler returning a plain list or string raises EnvelopeNormalizationError."""
        with pytest.raises(EnvelopeNormalizationError):
            normalize(["item1", "item2"], tool=_TOOL, request_id=_REQUEST_ID, elapsed_ms=0)

        with pytest.raises(EnvelopeNormalizationError):
            normalize("raw string output", tool=_TOOL, request_id=_REQUEST_ID, elapsed_ms=0)

    def test_missing_required_field_raises(self):
        """Missing 'items' in a collection dict raises EnvelopeNormalizationError."""
        raw = {"kind": "collection", "total_count": 1}  # no 'items'
        with pytest.raises(EnvelopeNormalizationError):
            normalize(raw, tool=_TOOL, request_id=_REQUEST_ID, elapsed_ms=0)


# ---------------------------------------------------------------------------
# Tests: make_error_envelope()
# ---------------------------------------------------------------------------


class TestMakeErrorEnvelope:
    def test_basic_error_envelope(self):
        """make_error_envelope returns LookupError with full meta block."""
        result = make_error_envelope(
            tool_id="koroad_accident_hazard_search",
            reason="unknown_tool",
            message="No tool registered with id 'koroad_accident_hazard_search'.",
            request_id=_REQUEST_ID,
            elapsed_ms=5,
        )
        assert isinstance(result, LookupError)
        assert result.kind == "error"
        assert result.reason == "unknown_tool"
        assert result.retryable is False
        assert result.meta is not None
        assert result.meta.source == "koroad_accident_hazard_search"
        assert result.meta.elapsed_ms == 5
        assert result.meta.request_id == _REQUEST_ID

    def test_retryable_error_with_upstream_info(self):
        """Retryable error with upstream_code and upstream_message is valid."""
        result = make_error_envelope(
            tool_id="some_tool",
            reason="timeout",
            message="Upstream timed out.",
            request_id=_REQUEST_ID,
            elapsed_ms=30000,
            retryable=True,
            upstream_code="504",
            upstream_message="Gateway Timeout",
        )
        assert result.retryable is True
        assert result.upstream_code == "504"
        assert result.upstream_message == "Gateway Timeout"

    def test_elapsed_ms_clamped(self):
        """Negative elapsed_ms is clamped to 0."""
        result = make_error_envelope(
            tool_id="some_tool",
            reason="timeout",
            message="test",
            request_id=_REQUEST_ID,
            elapsed_ms=-1,
        )
        assert result.meta is not None
        assert result.meta.elapsed_ms == 0

    def test_auth_required_error(self):
        """Auth required error is built correctly."""
        result = make_error_envelope(
            tool_id="secure_tool",
            reason="auth_required",
            message="Tool requires authentication.",
            request_id=_REQUEST_ID,
            elapsed_ms=0,
            retryable=False,
        )
        assert result.reason == "auth_required"
        assert result.meta.source == "secure_tool"
