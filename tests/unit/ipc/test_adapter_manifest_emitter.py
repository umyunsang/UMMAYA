# SPDX-License-Identifier: Apache-2.0
"""T008 — adapter_manifest_emitter unit tests.

Covers:
1. Happy emission — frame is written to stdout_writer; all fields are valid.
2. Sort ordering — entries are sorted by tool_id (ascending lexicographic).
3. Hash matches canonical JSON — I3 invariant preserved end-to-end.
4. Extra registry priority — register_manifest_entry() entries take precedence.
5. Empty extra registry + empty main registry → SystemExit(78).

Contract: specs/2296-ax-mock-adapters/contracts/ipc-adapter-manifest-frame.md § 5.1
"""

from __future__ import annotations

import hashlib
import io
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, ConfigDict, Field

from ummaya.ipc.adapter_manifest_emitter import (
    _EXTRA_REGISTRY,
    _build_entries,
    _canonical_json,
    emit_manifest,
    register_manifest_entry,
)
from ummaya.ipc.frame_schema import AdapterManifestEntry, AdapterManifestSyncFrame
from ummaya.tools.models import AdapterRealDomainPolicy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _ProbeInput(BaseModel):
    """Small OpenAPI-shaped input model used to prove manifest schema export."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    icao: str = Field(description="KMA APIHub request parameter icao.")
    page_no: int = Field(default=1, description="KMA APIHub request parameter pageNo.")


class _ProbeOutput(BaseModel):
    """Small OpenAPI-shaped output model used to prove manifest schema export."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    items: list[dict[str, object]]


def _make_entry(
    tool_id: str,
    primitive: str = "find",
    source_mode: str = "live",
    policy_url: str | None = None,
) -> AdapterManifestEntry:
    if source_mode in ("live", "mock") and policy_url is None:
        policy_url = f"https://example.gov.kr/{tool_id}/policy.do"
    return AdapterManifestEntry(
        tool_id=tool_id,
        name=tool_id.replace("_", " ").title(),
        primitive=primitive,  # type: ignore[arg-type]
        policy_authority_url=policy_url,
        source_mode=source_mode,  # type: ignore[arg-type]
    )


def _empty_registry() -> object:
    """Return a mock ToolRegistry with no tools."""
    mock = MagicMock()
    mock._tools = {}
    return mock


def _registry_tool(
    tool_id: str,
    *,
    primitive: str = "find",
    is_core: bool = False,
    input_schema: type[BaseModel] = _ProbeInput,
    output_schema: type[BaseModel] = _ProbeOutput,
    search_hint: str | None = None,
    llm_description: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=tool_id,
        name_ko=tool_id.replace("_", " "),
        primitive=primitive,
        adapter_mode="live",
        is_core=is_core,
        input_schema=input_schema,
        output_schema=output_schema,
        search_hint=search_hint or f"{tool_id} APIHub OpenAPI schema probe",
        llm_description=llm_description
        or (
            f"{tool_id} OpenAPI operation. Use the concrete backend input schema; "
            "credential parameters are supplied by UMMAYA runtime, not by the user."
        ),
        policy=AdapterRealDomainPolicy(
            real_classification_url=f"https://example.gov.kr/{tool_id}/policy.do",
            real_classification_text=f"{tool_id} policy",
            citizen_facing_gate="read-only",
            last_verified=datetime(2026, 5, 24, tzinfo=UTC),
        ),
    )


# ---------------------------------------------------------------------------
# Test 1: Happy emission
# ---------------------------------------------------------------------------


def test_emit_manifest_happy_path() -> None:
    """emit_manifest writes a valid JSON-encoded AdapterManifestSyncFrame."""
    # Seed the extra registry with two known adapters.
    _EXTRA_REGISTRY.clear()
    _EXTRA_REGISTRY["alpha_tool"] = _make_entry("alpha_tool", "send")
    _EXTRA_REGISTRY["beta_tool"] = _make_entry("beta_tool", "check")

    buf = io.StringIO()
    registry = _empty_registry()

    emit_manifest(buf, registry, pid=99999)

    raw = buf.getvalue().strip()
    assert raw, "Output buffer must be non-empty"

    parsed = json.loads(raw)
    assert parsed["kind"] == "adapter_manifest_sync"
    assert parsed["role"] == "backend"
    assert parsed["emitter_pid"] == 99999
    assert isinstance(parsed["entries"], list)
    assert len(parsed["entries"]) >= 2  # alpha_tool + beta_tool + internal entries

    # Validate it round-trips through the Pydantic model.
    frame = AdapterManifestSyncFrame.model_validate(parsed)
    assert frame.kind == "adapter_manifest_sync"
    assert frame.emitter_pid == 99999

    _EXTRA_REGISTRY.clear()


# ---------------------------------------------------------------------------
# Test 2: Sort ordering
# ---------------------------------------------------------------------------


def test_build_entries_sort_order() -> None:
    """Entries returned by _build_entries are sorted by tool_id (ascending)."""
    _EXTRA_REGISTRY.clear()
    _EXTRA_REGISTRY["zebra_tool"] = _make_entry("zebra_tool", "send")
    _EXTRA_REGISTRY["apple_tool"] = _make_entry("apple_tool", "find")
    _EXTRA_REGISTRY["mango_tool"] = _make_entry("mango_tool", "check")

    registry = _empty_registry()
    entries = _build_entries(registry)

    tool_ids = [e.tool_id for e in entries]
    assert tool_ids == sorted(tool_ids), f"Entries not sorted: {tool_ids}"

    _EXTRA_REGISTRY.clear()


# ---------------------------------------------------------------------------
# Test 3: Hash matches canonical JSON (I3 invariant)
# ---------------------------------------------------------------------------


def test_hash_matches_canonical_json() -> None:
    """manifest_hash in the emitted frame matches SHA-256 of canonical JSON."""
    _EXTRA_REGISTRY.clear()
    _EXTRA_REGISTRY["gamma_tool"] = _make_entry("gamma_tool", "find")

    buf = io.StringIO()
    emit_manifest(buf, _empty_registry(), pid=1)

    parsed = json.loads(buf.getvalue().strip())
    emitted_hash: str = parsed["manifest_hash"]

    # Recompute independently from the entries in the frame.
    entries = [AdapterManifestEntry.model_validate(e) for e in parsed["entries"]]
    sorted_entries = sorted(entries, key=lambda e: e.tool_id)
    recomputed_hash = hashlib.sha256(_canonical_json(sorted_entries).encode("utf-8")).hexdigest()

    assert emitted_hash == recomputed_hash, (
        f"manifest_hash mismatch: {emitted_hash!r} != {recomputed_hash!r}"
    )

    _EXTRA_REGISTRY.clear()


# ---------------------------------------------------------------------------
# Test 4: Extra registry takes precedence
# ---------------------------------------------------------------------------


def test_extra_registry_takes_precedence_over_main_registry() -> None:
    """Entries registered via register_manifest_entry() override ToolRegistry entries."""
    _EXTRA_REGISTRY.clear()


def test_core_primitives_are_not_adapter_manifest_entries() -> None:
    """Only root primitives are hidden; concrete adapters may still be is_core."""
    _EXTRA_REGISTRY.clear()

    registry = _empty_registry()
    registry._tools = {
        "find": _registry_tool("find", primitive="find", is_core=True),
        "locate": _registry_tool("locate", primitive="locate", is_core=True),
        "kma_current_observation": _registry_tool(
            "kma_current_observation",
            primitive="find",
            is_core=True,
        ),
    }

    entries = _build_entries(registry)
    by_id = {entry.tool_id: entry for entry in entries}

    assert "kma_current_observation" in by_id
    assert "find" not in by_id
    assert "locate" not in by_id

    _EXTRA_REGISTRY.clear()

    # Register an entry for "conflict_tool" in the extra registry.
    extra_entry = AdapterManifestEntry(
        tool_id="conflict_tool",
        name="Extra Version",
        primitive="check",
        policy_authority_url="https://extra.gov.kr/policy.do",
        source_mode="mock",
    )
    register_manifest_entry(extra_entry)

    # Simulate a main ToolRegistry tool with the same tool_id.
    mock_tool = MagicMock()
    mock_tool.id = "conflict_tool"
    mock_tool.name_ko = "Registry Version"
    mock_tool.primitive = "find"
    mock_tool.adapter_mode = "live"
    mock_tool.policy = None

    registry = _empty_registry()
    registry._tools = {"conflict_tool": mock_tool}

    entries = _build_entries(registry)
    conflict_entries = [e for e in entries if e.tool_id == "conflict_tool"]
    assert len(conflict_entries) == 1
    assert conflict_entries[0].name == "Extra Version", (
        "Extra registry entry must win over ToolRegistry entry"
    )

    _EXTRA_REGISTRY.clear()


def test_build_entries_exports_backend_tool_schema_and_description() -> None:
    """Concrete adapter manifest entries carry the backend OpenAPI schema."""
    _EXTRA_REGISTRY.clear()

    registry = _empty_registry()
    registry._tools = {
        "kma_apihub_amm_iwxxm_service_get_metar": _registry_tool(
            "kma_apihub_amm_iwxxm_service_get_metar",
            search_hint="KMA APIHub AmmIwxxmService getMetar METAR icao",
            llm_description=(
                "KMA APIHub AmmIwxxmService/getMetar. Provide ICAO station code "
                "as icao; authKey is supplied by UMMAYA runtime."
            ),
        ),
    }

    entries = _build_entries(registry)
    entry = next(e for e in entries if e.tool_id == "kma_apihub_amm_iwxxm_service_get_metar")

    assert entry.search_hint == "KMA APIHub AmmIwxxmService getMetar METAR icao"
    assert entry.llm_description is not None
    assert "AmmIwxxmService/getMetar" in entry.llm_description

    properties = entry.input_schema_json["properties"]
    assert isinstance(properties, dict)
    assert properties["icao"]["description"] == "KMA APIHub request parameter icao."
    assert properties["page_no"]["default"] == 1
    assert "authKey" not in properties
    assert entry.input_schema_json["additionalProperties"] is False

    output_properties = entry.output_schema_json["properties"]
    assert isinstance(output_properties, dict)
    assert "items" in output_properties

    _EXTRA_REGISTRY.clear()


def test_full_runtime_manifest_exports_model_facing_tool_metadata() -> None:
    """Every runtime adapter exposes enough metadata for LLM tool selection."""
    from ummaya.tools.executor import ToolExecutor
    from ummaya.tools.register_all import register_all_tools
    from ummaya.tools.registry import ToolRegistry

    _EXTRA_REGISTRY.clear()

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)

    entries = _build_entries(registry)
    issues: list[str] = []

    for entry in entries:
        search_hint = (entry.search_hint or "").strip()
        if len(search_hint) < 30:
            issues.append(f"{entry.tool_id}: search_hint too short or missing")

        llm_description = (entry.llm_description or "").strip()
        if len(llm_description) < 80:
            issues.append(f"{entry.tool_id}: llm_description too short or missing")

        properties = entry.input_schema_json.get("properties")
        if not isinstance(properties, dict) or not properties:
            issues.append(f"{entry.tool_id}: input_schema_json.properties missing")
            continue

        for property_name, property_schema in properties.items():
            if not isinstance(property_schema, dict):
                issues.append(f"{entry.tool_id}.{property_name}: property schema is not an object")
                continue
            description = str(property_schema.get("description") or "").strip()
            if len(description) < 24:
                issues.append(f"{entry.tool_id}.{property_name}: description too short")

    assert issues == []

    by_id = {entry.tool_id: entry for entry in entries}

    assert "cityCode" in _property_description(by_id["tago_bus_route_search"], "city_code")
    assert "Busan=21" in _property_description(by_id["tago_bus_route_search"], "city_code")
    arrival_description = str(by_id["tago_bus_arrival_search"].llm_description)
    assert "tago_bus_station_search first" in arrival_description
    assert "route_no" in arrival_description
    assert "routeno" in _property_description(by_id["tago_bus_arrival_search"], "route_no")
    assert "routeid" in _property_description(by_id["tago_bus_arrival_search"], "route_id")
    route_station_description = str(by_id["tago_bus_route_station_search"].llm_description)
    assert "route_id" in route_station_description
    assert "node_nm" in route_station_description
    assert "nodenm" in _property_description(by_id["tago_bus_route_station_search"], "node_nm")
    assert "sidoName" in _property_description(by_id["airkorea_ctprvn_air_quality"], "sido_name")
    assert "cntrCd" in _property_description(by_id["kepco_contract_power_usage"], "cntr_cd")
    assert "presentnYear" in _property_description(by_id["ftc_large_group_status"], "presentn_year")

    mobile_id = by_id["mobile_id"]
    assert mobile_id.source_mode == "internal"
    assert "scope_list" in mobile_id.input_schema_json["properties"]
    assert "check:mobile_id.identity" in str(mobile_id.llm_description)
    assert "mobile ID" in str(mobile_id.search_hint)

    _EXTRA_REGISTRY.clear()


def _property_description(entry: AdapterManifestEntry, property_name: str) -> str:
    properties = entry.input_schema_json["properties"]
    assert isinstance(properties, dict)
    property_schema = properties[property_name]
    assert isinstance(property_schema, dict)
    return str(property_schema["description"])


# ---------------------------------------------------------------------------
# Test 5: Empty registries → SystemExit(78) (boot-validation fail-closed)
# ---------------------------------------------------------------------------


def test_emit_manifest_exits_78_when_no_entries() -> None:
    """When no entries can be built, emit_manifest exits with SystemExit(78)."""
    # Clear all sources
    _EXTRA_REGISTRY.clear()

    buf = io.StringIO()
    registry = _empty_registry()

    # Patch _build_entries to return empty list simulating total failure.
    with patch("ummaya.ipc.adapter_manifest_emitter._build_entries", return_value=[]):
        with pytest.raises(SystemExit) as exc_info:
            emit_manifest(buf, registry, pid=1)
        assert exc_info.value.code == 78, (
            f"Expected SystemExit(78), got SystemExit({exc_info.value.code})"
        )


# ---------------------------------------------------------------------------
# Audit-4 P0-9 — every Mock submit adapter now emits a non-null
# policy_authority_url; manifest emitter logs ZERO "policy_authority_url is
# required" warnings for the full registry walk.
# ---------------------------------------------------------------------------


def test_audit4_p0_9_mock_submits_have_policy_url(caplog: pytest.LogCaptureFixture) -> None:
    """Pre-Audit-4: Mock submit adapters lacked an AdapterRealDomainPolicy
    citation, dropping them from the manifest with 10 warnings on every boot.
    Post-Audit-4: each REGISTRATION carries a populated ``policy=`` block, so
    the emitter walks them cleanly and emits zero ``policy_authority_url is
    required`` warnings."""
    import logging

    # Eager-import the Mock tree so submit adapters self-register.
    import ummaya.tools.mock  # noqa: F401
    from ummaya.ipc.adapter_manifest_emitter import _build_entries
    from ummaya.tools.executor import ToolExecutor
    from ummaya.tools.register_all import register_all_tools
    from ummaya.tools.registry import ToolRegistry

    reg = ToolRegistry()
    register_all_tools(reg, ToolExecutor(registry=reg))

    with caplog.at_level(logging.WARNING, logger="ummaya.ipc.adapter_manifest_emitter"):
        entries = _build_entries(reg, warn_on_missing=True)

    # Mock submit adapters MUST surface with policy_authority_url populated.
    expected_mock_submits = {
        "mock_kftc_opengiro_bill_send_v1",
        "mock_kftc_opengiro_payment_send_v1",
        "mock_submit_module_gov24_minwon",
        "mock_submit_module_hometax_taxreturn",
        "mock_submit_module_public_mydata_action",
        "mock_traffic_fine_pay_v1",
        "mock_welfare_application_submit_v1",
    }
    by_id = {e.tool_id: e for e in entries}

    for mock_id in expected_mock_submits:
        assert mock_id in by_id, f"Mock submit {mock_id} missing from manifest"
        entry = by_id[mock_id]
        assert entry.source_mode == "mock", f"{mock_id} expected source_mode=mock"
        assert entry.policy_authority_url, (
            f"{mock_id} must declare policy_authority_url (Audit-4 P0-9)"
        )
        assert entry.policy_authority_url.startswith("https://"), (
            f"{mock_id} policy_authority_url must be HTTPS, got {entry.policy_authority_url!r}"
        )

    assert by_id["mock_submit_module_gov24_minwon"].name == "정부24 민원신청"
    assert by_id["mock_submit_module_hometax_taxreturn"].name == "홈택스 종합소득세 신고"

    # Zero "policy_authority_url is required" warnings during the walk.
    blocking_warnings = [rec for rec in caplog.records if "no policy URL" in rec.message]
    assert blocking_warnings == [], (
        f"Audit-4 P0-9 regression: {len(blocking_warnings)} adapter(s) still missing "
        f"policy URL: {[r.message for r in blocking_warnings]}"
    )
