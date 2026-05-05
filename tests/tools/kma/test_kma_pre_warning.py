# SPDX-License-Identifier: Apache-2.0
"""Tests for kosmos.tools.kma.kma_pre_warning."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from pydantic import ValidationError

from kosmos.tools.errors import ConfigurationError, ToolExecutionError
from kosmos.tools.executor import ToolExecutor
from kosmos.tools.kma.kma_pre_warning import (
    KMA_PRE_WARNING_TOOL,
    KmaPreWarningInput,
    KmaPreWarningOutput,
    _call,
    _normalize_items,
    _parse_response,
    register,
)
from kosmos.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURE_DIR / name).read_text())


def _make_mock_client(fixture_data: dict) -> httpx.AsyncClient:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = fixture_data
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response
    return mock_client


# ---------------------------------------------------------------------------
# TestKmaPreWarningInput
# ---------------------------------------------------------------------------


class TestKmaPreWarningInput:
    def test_default_construction(self):
        inp = KmaPreWarningInput()
        assert inp.num_of_rows == 100
        assert inp.page_no == 1
        assert inp.stn_id is None
        assert inp.data_type == "JSON"

    def test_with_stn_id(self):
        inp = KmaPreWarningInput(stn_id="108")
        assert inp.stn_id == "108"

    def test_custom_num_of_rows(self):
        inp = KmaPreWarningInput(num_of_rows=50)
        assert inp.num_of_rows == 50

    def test_num_of_rows_minimum(self):
        with pytest.raises(ValidationError):
            KmaPreWarningInput(num_of_rows=0)

    def test_page_no_minimum(self):
        with pytest.raises(ValidationError):
            KmaPreWarningInput(page_no=0)

    def test_page_no_valid(self):
        inp = KmaPreWarningInput(page_no=3)
        assert inp.page_no == 3


# ---------------------------------------------------------------------------
# TestNormalizeItems
# ---------------------------------------------------------------------------


class TestNormalizeItems:
    def test_list_input_returned_as_is(self):
        items = [{"stnId": "108", "title": "test"}, {"stnId": "159", "title": "test2"}]
        result = _normalize_items(items)
        assert result == items

    def test_dict_input_wrapped_in_list(self):
        """Single-item dict must be wrapped in a list."""
        item = {"stnId": "108", "title": "[예비] 제04-3호"}
        result = _normalize_items(item)
        assert result == [item]

    def test_empty_string_returns_empty_list(self):
        assert _normalize_items("") == []

    def test_none_returns_empty_list(self):
        assert _normalize_items(None) == []

    def test_unexpected_type_returns_empty_list(self):
        assert _normalize_items(42) == []  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TestParseResponse
# ---------------------------------------------------------------------------


class TestParseResponse:
    def test_success(self):
        """Load the success fixture and verify all items are parsed."""
        data = _load_fixture("kma_pre_warning_success.json")
        out = _parse_response(data)
        assert isinstance(out, KmaPreWarningOutput)
        assert out.total_count == 2
        assert len(out.items) == 2

        first = out.items[0]
        assert first.stn_id == "108"
        assert first.title == "[예비] 제04-3호 : 2026.04.14.08:00"
        assert first.tm_fc == "202604140800"
        assert first.tm_seq == 3

    def test_empty_response_code_03(self):
        """resultCode=03 (NO_DATA) must return empty output, not raise."""
        data = _load_fixture("kma_pre_warning_empty.json")
        out = _parse_response(data)
        assert out.total_count == 0
        assert out.items == []

    def test_error_code_raises_tool_execution_error(self):
        """A non-'00' and non-'03' result code must raise ToolExecutionError."""
        error_payload = {
            "response": {
                "header": {"resultCode": "99", "resultMsg": "UNKNOWN_ERROR"},
                "body": None,
            }
        }
        with pytest.raises(ToolExecutionError) as exc_info:
            _parse_response(error_payload)
        assert "99" in str(exc_info.value)

    def test_single_item_normalized(self):
        """A single-item dict must be normalized to a one-element list."""
        single_item_payload = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "NORMAL_CODE"},
                "body": {
                    "totalCount": 1,
                    "items": {
                        "item": {
                            "stnId": "108",
                            "title": "[예비] 제04-1호 : 2026.04.14.06:00",
                            "tmFc": "202604140600",
                            "tmSeq": 1,
                        }
                    },
                },
            }
        }
        out = _parse_response(single_item_payload)
        assert len(out.items) == 1
        assert out.items[0].tm_seq == 1

    def test_empty_items_body(self):
        """An items='' body must return an empty items list."""
        payload = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "NORMAL_CODE"},
                "body": {
                    "totalCount": 0,
                    "items": "",
                },
            }
        }
        out = _parse_response(payload)
        assert out.total_count == 0
        assert out.items == []

    def test_multiple_items(self):
        """Multiple items must all be parsed."""
        data = _load_fixture("kma_pre_warning_success.json")
        out = _parse_response(data)
        stn_ids = [item.stn_id for item in out.items]
        assert "108" in stn_ids
        assert "159" in stn_ids


# ---------------------------------------------------------------------------
# TestCall
# ---------------------------------------------------------------------------


class TestCall:
    @pytest.mark.asyncio
    async def test_success_flow(self, monkeypatch):
        """_call with a mocked httpx client returns a dict matching output schema."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", "test-key-abc")
        fixture_data = _load_fixture("kma_pre_warning_success.json")
        mock_client = _make_mock_client(fixture_data)

        inp = KmaPreWarningInput()
        result = await _call(inp, client=mock_client)

        assert isinstance(result, dict)
        assert result["total_count"] == 2
        assert isinstance(result["items"], list)
        assert len(result["items"]) == 2

    @pytest.mark.asyncio
    async def test_success_with_stn_id_filter(self, monkeypatch):
        """_call with stn_id passes the parameter to the API."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", "test-key-abc")
        fixture_data = _load_fixture("kma_pre_warning_success.json")
        mock_client = _make_mock_client(fixture_data)

        inp = KmaPreWarningInput(stn_id="108")
        _result = await _call(inp, client=mock_client)

        # Verify the stnId was passed in the request
        call_kwargs = mock_client.get.call_args
        params_sent = call_kwargs[1]["params"]
        assert params_sent.get("stnId") == "108"

    @pytest.mark.asyncio
    async def test_no_stn_id_excludes_param(self, monkeypatch):
        """_call without stn_id must NOT include stnId in the request parameters."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", "test-key-abc")
        fixture_data = _load_fixture("kma_pre_warning_empty.json")
        mock_client = _make_mock_client(fixture_data)

        inp = KmaPreWarningInput()
        await _call(inp, client=mock_client)

        call_kwargs = mock_client.get.call_args
        params_sent = call_kwargs[1]["params"]
        assert "stnId" not in params_sent

    @pytest.mark.asyncio
    async def test_empty_response_no_error(self, monkeypatch):
        """A no-data (resultCode=03) response must return empty output without error."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", "test-key-abc")
        fixture_data = _load_fixture("kma_pre_warning_empty.json")
        mock_client = _make_mock_client(fixture_data)

        inp = KmaPreWarningInput()
        result = await _call(inp, client=mock_client)

        assert result["total_count"] == 0
        assert result["items"] == []

    @pytest.mark.asyncio
    async def test_missing_api_key(self, monkeypatch):
        """Absent KOSMOS_DATA_GO_KR_API_KEY raises ConfigurationError."""
        monkeypatch.delenv("KOSMOS_DATA_GO_KR_API_KEY", raising=False)

        inp = KmaPreWarningInput()
        with pytest.raises(ConfigurationError):
            await _call(inp)

    @pytest.mark.asyncio
    async def test_xml_content_type_guard(self, monkeypatch):
        """An XML content-type response must raise ToolExecutionError."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", "test-key-abc")

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/xml; charset=UTF-8"}
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response

        inp = KmaPreWarningInput()
        with pytest.raises(ToolExecutionError) as exc_info:
            await _call(inp, client=mock_client)
        assert "XML" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_http_status_error(self, monkeypatch):
        """An HTTP 500 must raise ToolExecutionError."""
        monkeypatch.setenv("KOSMOS_DATA_GO_KR_API_KEY", "test-key-abc")

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response

        inp = KmaPreWarningInput()
        with pytest.raises(httpx.HTTPStatusError):
            await _call(inp, client=mock_client)


# ---------------------------------------------------------------------------
# TestToolDefinition
# ---------------------------------------------------------------------------


class TestToolDefinition:
    def test_tool_id(self):
        assert KMA_PRE_WARNING_TOOL.id == "kma_pre_warning"

    def test_is_core_true(self):
        assert KMA_PRE_WARNING_TOOL.is_core is True

    def test_provider(self):
        assert KMA_PRE_WARNING_TOOL.ministry == "KMA"

    def test_cache_ttl(self):
        assert KMA_PRE_WARNING_TOOL.cache_ttl_seconds == 300

    # test_not_personal_data removed in Epic δ #2295 (is_personal_data deleted).

    def test_input_schema(self):
        assert KMA_PRE_WARNING_TOOL.input_schema is KmaPreWarningInput

    def test_output_schema(self):
        assert KMA_PRE_WARNING_TOOL.output_schema is KmaPreWarningOutput

    def test_search_hint_bilingual(self):
        hint = KMA_PRE_WARNING_TOOL.search_hint
        assert "예비특보" in hint
        assert "pre-warning" in hint


# ---------------------------------------------------------------------------
# TestRegister
# ---------------------------------------------------------------------------


class TestRegister:
    def test_register_adds_to_registry_and_executor(self):
        """register() wires the tool into both registry and executor."""
        registry = ToolRegistry()
        executor = ToolExecutor(registry)

        register(registry, executor)

        assert "kma_pre_warning" in registry
        assert registry.lookup("kma_pre_warning") is KMA_PRE_WARNING_TOOL
        assert "kma_pre_warning" in executor._adapters

    @pytest.mark.asyncio
    async def test_registered_adapter_wraps_envelope_with_collection_kind(self, monkeypatch):
        """Audit G4 / F-beta-01 — registered adapter MUST return a 5-variant
        LookupOutput-shaped dict so envelope.normalize() can extract the
        ``kind`` discriminator. Pre-fix the adapter returned the raw
        ``KmaPreWarningOutput.model_dump()`` (no ``kind`` field) which surfaced
        in β6 as ``Unable to extract tag using discr``.
        """
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        register(registry, executor)
        adapter = executor._adapters["kma_pre_warning"]

        async def _fake_call(_inp):
            return {
                "total_count": 2,
                "items": [
                    {
                        "stn_id": "108",
                        "title": "[예비] 호우주의보",
                        "tm_fc": "202605051200",
                        "tm_seq": 1,
                    },
                    {
                        "stn_id": "159",
                        "title": "[예비] 강풍주의보",
                        "tm_fc": "202605051300",
                        "tm_seq": 2,
                    },
                ],
            }

        from kosmos.tools.kma import kma_pre_warning as _mod

        monkeypatch.setattr(_mod, "_call", _fake_call)

        result = await adapter(KmaPreWarningInput())

        assert isinstance(result, dict)
        assert result.get("kind") == "collection"  # discriminator MUST be present
        assert isinstance(result.get("items"), list)
        assert len(result["items"]) == 2
        assert result.get("total_count") == 2

    @pytest.mark.asyncio
    async def test_registered_adapter_passes_envelope_normalizer(self, monkeypatch):
        """End-to-end: registered adapter output passes envelope.normalize()."""
        from kosmos.tools.envelope import normalize

        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        register(registry, executor)
        adapter = executor._adapters["kma_pre_warning"]

        async def _fake_call(_inp):
            return {"total_count": 0, "items": []}

        from kosmos.tools.kma import kma_pre_warning as _mod

        monkeypatch.setattr(_mod, "_call", _fake_call)

        raw = await adapter(KmaPreWarningInput())
        validated = normalize(
            output=raw,
            tool=KMA_PRE_WARNING_TOOL,
            request_id="00000000-0000-0000-0000-000000000000",
            elapsed_ms=10,
        )
        # If normalize returned without raising, the discriminator extraction
        # succeeded. Validated object should be a LookupCollection.
        assert getattr(validated, "kind", None) == "collection"
