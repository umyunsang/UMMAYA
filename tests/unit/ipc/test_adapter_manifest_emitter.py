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
from unittest.mock import MagicMock, patch

import pytest

from kosmos.ipc.adapter_manifest_emitter import (
    _EXTRA_REGISTRY,
    _build_entries,
    _canonical_json,
    emit_manifest,
    register_manifest_entry,
)
from kosmos.ipc.frame_schema import AdapterManifestEntry, AdapterManifestSyncFrame

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(
    tool_id: str,
    primitive: str = "lookup",
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


# ---------------------------------------------------------------------------
# Test 1: Happy emission
# ---------------------------------------------------------------------------


def test_emit_manifest_happy_path() -> None:
    """emit_manifest writes a valid JSON-encoded AdapterManifestSyncFrame."""
    # Seed the extra registry with two known adapters.
    _EXTRA_REGISTRY.clear()
    _EXTRA_REGISTRY["alpha_tool"] = _make_entry("alpha_tool", "submit")
    _EXTRA_REGISTRY["beta_tool"] = _make_entry("beta_tool", "verify")

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
    _EXTRA_REGISTRY["zebra_tool"] = _make_entry("zebra_tool", "submit")
    _EXTRA_REGISTRY["apple_tool"] = _make_entry("apple_tool", "lookup")
    _EXTRA_REGISTRY["mango_tool"] = _make_entry("mango_tool", "verify")

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
    _EXTRA_REGISTRY["gamma_tool"] = _make_entry("gamma_tool", "lookup")

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

    # Register an entry for "conflict_tool" in the extra registry.
    extra_entry = AdapterManifestEntry(
        tool_id="conflict_tool",
        name="Extra Version",
        primitive="verify",
        policy_authority_url="https://extra.gov.kr/policy.do",
        source_mode="mock",
    )
    register_manifest_entry(extra_entry)

    # Simulate a main ToolRegistry tool with the same tool_id.
    mock_tool = MagicMock()
    mock_tool.id = "conflict_tool"
    mock_tool.name_ko = "Registry Version"
    mock_tool.primitive = "lookup"
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
    with patch("kosmos.ipc.adapter_manifest_emitter._build_entries", return_value=[]):
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
    """Pre-Audit-4: 5 Mock submit adapters lacked an AdapterRealDomainPolicy
    citation, dropping them from the manifest with 10 warnings on every boot.
    Post-Audit-4: each REGISTRATION carries a populated ``policy=`` block, so
    the emitter walks them cleanly and emits zero ``policy_authority_url is
    required`` warnings."""
    import logging

    from kosmos.ipc.adapter_manifest_emitter import _build_entries
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.register_all import register_all_tools
    from kosmos.tools.registry import ToolRegistry

    # Eager-import the Mock tree so submit adapters self-register.
    import kosmos.tools.mock  # noqa: F401

    reg = ToolRegistry()
    register_all_tools(reg, ToolExecutor(registry=reg))

    with caplog.at_level(logging.WARNING, logger="kosmos.ipc.adapter_manifest_emitter"):
        entries = _build_entries(reg, warn_on_missing=True)

    # Five Mock submit adapters MUST surface with policy_authority_url populated.
    expected_mock_submits = {
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

    # Zero "policy_authority_url is required" warnings during the walk.
    blocking_warnings = [
        rec for rec in caplog.records if "no policy URL" in rec.message
    ]
    assert blocking_warnings == [], (
        f"Audit-4 P0-9 regression: {len(blocking_warnings)} adapter(s) still missing "
        f"policy URL: {[r.message for r in blocking_warnings]}"
    )
