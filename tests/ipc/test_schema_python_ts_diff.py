# SPDX-License-Identifier: Apache-2.0
"""Schema parity CI guard — Spec 032 T020.

Ensures that the committed JSON Schema file at
``tui/src/ipc/schema/frame.schema.json`` is byte-equivalent (after JSON
normalisation) to what Pydantic generates live from ``IPCFrame``.

If this test fails in CI it means:
- Someone edited ``frame_schema.py`` but forgot to regenerate the schema, OR
- Someone edited the .json file directly instead of running ``bun run gen:ipc``

Fix:
    cd tui && bun run gen:ipc

References: FR-040 (schema drift gate), SC-006 (TS/Python parity).
"""

from __future__ import annotations

import json
import pathlib

import pytest

from ummaya.ipc.frame_schema import ipc_frame_json_schema

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_WORKTREE_ROOT = pathlib.Path(__file__).parent.parent.parent
_COMMITTED_SCHEMA_PATH = _WORKTREE_ROOT / "tui" / "src" / "ipc" / "schema" / "frame.schema.json"

# Expected number of frame arms (Spec 287 baseline 10 + Spec 032 additions 9
# + Epic #1636 P5 plugin_op + Spec 1978 chat_request + Epic ε #2296 adapter_manifest_sync
# + Epic 2 consent_revoke_request/response + K-EXAONE progress_event = 25).
_EXPECTED_KIND_COUNT = 25


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise(schema: dict) -> str:  # type: ignore[type-arg]
    """Return a canonical JSON string (sorted keys, no trailing whitespace).

    Using ``sort_keys=True`` makes comparison independent of dict insertion
    order, which can differ between Python versions.
    """
    return json.dumps(schema, sort_keys=True, ensure_ascii=False)


def _extract_kinds_from_schema(schema: dict) -> set[str]:  # type: ignore[type-arg]
    """Extract the set of discriminator kind values from a Pydantic v2 JSON Schema.

    Pydantic v2 emits::

        {
          "discriminator": {
            "mapping": { "user_input": "#/$defs/UserInputFrame", ... },
            "propertyName": "kind"
          },
          "oneOf": [...]
        }

    at the top level for a discriminated union.  We prefer the mapping keys
    over iterating $defs because $defs may include non-arm helpers (e.g.
    FrameTrailer, ToolResultEnvelope).
    """
    discriminator = schema.get("discriminator", {})
    mapping = discriminator.get("mapping", {})
    return set(mapping.keys())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSchemaParity:
    """Suite: Python-generated schema matches committed tui/ JSON file."""

    def test_committed_schema_file_exists(self) -> None:
        """Guard: the committed schema file must be present."""
        assert _COMMITTED_SCHEMA_PATH.exists(), (
            f"Committed schema not found at {_COMMITTED_SCHEMA_PATH}. "
            "Run `cd tui && bun run gen:ipc` to regenerate."
        )

    def test_committed_schema_is_valid_json(self) -> None:
        """Guard: the committed file must be parseable as JSON."""
        text = _COMMITTED_SCHEMA_PATH.read_text(encoding="utf-8")
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            pytest.fail(f"Committed schema is not valid JSON: {exc}")

    def test_python_generated_schema_has_expected_kinds(self) -> None:
        """Python-side schema exposes the expected discriminator kind count."""
        live_schema = ipc_frame_json_schema()
        kinds = _extract_kinds_from_schema(live_schema)
        assert len(kinds) == _EXPECTED_KIND_COUNT, (
            f"Expected {_EXPECTED_KIND_COUNT} discriminator kinds, "
            f"got {len(kinds)}: {sorted(kinds)}"
        )

    def test_committed_schema_has_expected_kinds(self) -> None:
        """Committed JSON schema file exposes the expected discriminator kind count."""
        committed_schema = json.loads(_COMMITTED_SCHEMA_PATH.read_text(encoding="utf-8"))
        kinds = _extract_kinds_from_schema(committed_schema)
        assert len(kinds) == _EXPECTED_KIND_COUNT, (
            f"Committed schema: expected {_EXPECTED_KIND_COUNT} kinds, "
            f"got {len(kinds)}: {sorted(kinds)}"
        )

    def test_all_expected_kinds_present_in_python_schema(self) -> None:
        """All expected kind names appear in the Python-generated schema."""
        expected_kinds = {
            # Spec 287 baseline
            "user_input",
            "assistant_chunk",
            "tool_call",
            "tool_result",
            "coordinator_phase",
            "worker_status",
            "permission_request",
            "permission_response",
            "session_event",
            "error",
            # Spec 032 additions
            "payload_start",
            "payload_delta",
            "payload_end",
            "backpressure",
            "resume_request",
            "resume_response",
            "resume_rejected",
            "heartbeat",
            "notification_push",
            # Epic #1636 P5 — plugin install/uninstall/list control plane
            "plugin_op",
            # Spec 1978 ADR-0001 — TUI tools-aware chat request
            "chat_request",
            # Epic ε #2296 — adapter manifest sync (backend boot)
            "adapter_manifest_sync",
            # Epic 2 — consent revoke IPC round-trip (arms 22-23)
            "consent_revoke_request",
            "consent_revoke_response",
            # K-EXAONE reasoning/progress painting
            "progress_event",
        }
        live_schema = ipc_frame_json_schema()
        live_kinds = _extract_kinds_from_schema(live_schema)
        missing = expected_kinds - live_kinds
        extra = live_kinds - expected_kinds
        assert not missing, f"Kinds missing from Python schema: {sorted(missing)}"
        assert not extra, f"Unexpected kinds in Python schema: {sorted(extra)}"

    def test_all_expected_kinds_present_in_committed_schema(self) -> None:
        """All expected kind names appear in the committed schema file."""
        expected_kinds = {
            "user_input",
            "assistant_chunk",
            "tool_call",
            "tool_result",
            "coordinator_phase",
            "worker_status",
            "permission_request",
            "permission_response",
            "session_event",
            "error",
            "payload_start",
            "payload_delta",
            "payload_end",
            "backpressure",
            "resume_request",
            "resume_response",
            "resume_rejected",
            "heartbeat",
            "notification_push",
            # Epic #1636 P5 — plugin install/uninstall/list control plane
            "plugin_op",
            # Spec 1978 ADR-0001 — TUI tools-aware chat request
            "chat_request",
            # Epic ε #2296 — adapter manifest sync (backend boot)
            "adapter_manifest_sync",
            # Epic 2 — consent revoke IPC round-trip
            "consent_revoke_request",
            "consent_revoke_response",
            # K-EXAONE reasoning/progress painting
            "progress_event",
        }
        committed_schema = json.loads(_COMMITTED_SCHEMA_PATH.read_text(encoding="utf-8"))
        committed_kinds = _extract_kinds_from_schema(committed_schema)
        missing = expected_kinds - committed_kinds
        extra = committed_kinds - expected_kinds
        assert not missing, (
            f"Kinds missing from committed schema: {sorted(missing)}. "
            "Run `cd tui && bun run gen:ipc` to regenerate."
        )
        assert not extra, f"Unexpected kinds in committed schema: {sorted(extra)}."

    def test_python_and_committed_schemas_are_structurally_equivalent(self) -> None:
        """Python-generated and committed schemas have identical discriminator structure.

        We compare the discriminator mapping keys and $defs keys rather than
        byte-exact equality because Pydantic may emit float/int formatting
        differences that are semantically equivalent.  The discriminator
        mapping and $defs key sets must match exactly.

        For CI enforcement of byte-exact parity, use the companion
        test_schema_normalised_equality test below.
        """
        live_schema = ipc_frame_json_schema()
        committed_schema = json.loads(_COMMITTED_SCHEMA_PATH.read_text(encoding="utf-8"))

        live_kinds = _extract_kinds_from_schema(live_schema)
        committed_kinds = _extract_kinds_from_schema(committed_schema)
        assert live_kinds == committed_kinds, (
            f"Discriminator mapping mismatch.\n"
            f"  Live only: {sorted(live_kinds - committed_kinds)}\n"
            f"  Committed only: {sorted(committed_kinds - live_kinds)}\n"
            "Run `cd tui && bun run gen:ipc` to regenerate."
        )

        live_defs = set(live_schema.get("$defs", {}).keys())
        committed_defs = set(committed_schema.get("$defs", {}).keys())
        assert live_defs == committed_defs, (
            f"$defs key mismatch.\n"
            f"  Live only: {sorted(live_defs - committed_defs)}\n"
            f"  Committed only: {sorted(committed_defs - live_defs)}\n"
            "Run `cd tui && bun run gen:ipc` to regenerate."
        )

    def test_schema_normalised_equality(self) -> None:
        """Python-generated and committed schemas are normalised-JSON equal.

        This is the strict CI gate (FR-040 / SC-006).  If this test fails,
        it means the committed ``frame.schema.json`` is out of sync with
        ``frame_schema.py``.  Fix by running::

            cd tui && bun run gen:ipc

        and committing the result.
        """
        live_schema = ipc_frame_json_schema()
        committed_schema = json.loads(_COMMITTED_SCHEMA_PATH.read_text(encoding="utf-8"))

        live_normalised = _normalise(live_schema)
        committed_normalised = _normalise(committed_schema)

        if live_normalised != committed_normalised:
            # Produce a useful diff summary — show first diverging key path
            live_parsed: dict[str, object] = json.loads(live_normalised)
            committed_parsed: dict[str, object] = json.loads(committed_normalised)

            live_top_keys = set(live_parsed.keys())
            committed_top_keys = set(committed_parsed.keys())
            top_diff = live_top_keys.symmetric_difference(committed_top_keys)

            diff_hint = (
                f"Top-level key diff: {sorted(top_diff)}"
                if top_diff
                else "Top-level keys match; divergence is in nested values"
            )

            pytest.fail(
                f"Schema drift detected (FR-040 / SC-006).\n"
                f"{diff_hint}\n"
                f"Run `cd tui && bun run gen:ipc` from the worktree and "
                f"commit the updated frame.schema.json."
            )
