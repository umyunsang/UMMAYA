# SPDX-License-Identifier: Apache-2.0
"""Adapter manifest emitter — Epic ε #2296 · T008.

Emits an ``AdapterManifestSyncFrame`` to stdout (NDJSON) exactly once after
``register_all_tools()`` completes at backend boot.  The frame announces the
complete, sorted registry snapshot so the TS-side can resolve any
``tool_id`` to its citation and source_mode without a round-trip.

Contract: specs/2296-ax-mock-adapters/contracts/ipc-adapter-manifest-frame.md § 5.1

Design
------
Three sources of adapter metadata are walked in priority order:

1. **Extra manifest registry** (``_EXTRA_REGISTRY``):
   Adapters that do not have a :class:`~kosmos.tools.registry.AdapterRegistration`
   stored in a primitive sub-registry (e.g. verify mocks that register via the
   simple ``register_verify_adapter(family, fn)`` API) may call
   :func:`register_manifest_entry` at module-import time to expose metadata to
   this emitter.  Takes precedence over all other sources for the same
   ``tool_id``.

2. **Submit primitive sub-registry**:
   ``kosmos.primitives.submit._ADAPTER_REGISTRY`` →
       keyed by ``tool_id``; values are ``(AdapterRegistration, callable)``.
   Adapters here emit an entry with ``source_mode=registration.source_mode``
   and ``policy_authority_url=registration.policy.real_classification_url``
   when the policy is populated.

3. **Main ToolRegistry** (``GovAPITool`` entries):
   Walked last; entries already covered by sources 1 or 2 are skipped to
   avoid duplicates.

Hard rules (per AGENTS.md)
--------------------------
- Zero new runtime dependencies.
- All source text English.
- Pydantic v2 frozen models, no ``Any``.
- Backend exits with ``SystemExit(78)`` if frame construction raises
  ``ValueError`` (boot-validation pattern per Constitution § II).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import UTC, datetime
from typing import IO, Any, Literal

from kosmos.ipc.frame_schema import AdapterManifestEntry, AdapterManifestSyncFrame

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Extra manifest registry — populated by adapters that lack a structured
# AdapterRegistration in a primitive sub-registry.
# ---------------------------------------------------------------------------

_EXTRA_REGISTRY: dict[str, AdapterManifestEntry] = {}


def register_manifest_entry(entry: AdapterManifestEntry) -> None:
    """Register a manifest entry for an adapter that cannot self-describe via
    the sub-registry.

    Adapters call this at module-import time (after ``register_verify_adapter``
    or similar).  For example::

        from kosmos.ipc.adapter_manifest_emitter import register_manifest_entry
        from kosmos.ipc.frame_schema import AdapterManifestEntry

        register_manifest_entry(AdapterManifestEntry(
            tool_id="mock_verify_module_simple_auth",
            name="간편인증 / Simple Auth (Mock)",
            primitive="verify",
            policy_authority_url="https://www.mois.go.kr/.../mobile-id-policy.do",
            source_mode="mock",
        ))

    Args:
        entry: A fully-validated :class:`AdapterManifestEntry` instance.
    """
    _EXTRA_REGISTRY[entry.tool_id] = entry
    logger.debug("manifest_emitter: registered extra entry %s", entry.tool_id)


def _canonical_json(entries: list[AdapterManifestEntry]) -> str:
    """Produce canonical JSON of the sorted entry list for hash computation.

    Entries MUST already be sorted by ``tool_id`` before calling this function.
    Sort is the caller's responsibility.
    """
    dicts = [e.model_dump(mode="json", by_alias=False) for e in entries]
    return json.dumps(dicts, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _compute_manifest_hash(entries: list[AdapterManifestEntry]) -> str:
    """SHA-256 hash over canonical JSON of sorted entries (invariant I3)."""
    return hashlib.sha256(_canonical_json(entries).encode("utf-8")).hexdigest()


def _build_entries(  # noqa: C901, ANN401 — three-source walker, refactor deferred
    registry: Any,
    *,
    warn_on_missing: bool = False,
) -> list[AdapterManifestEntry]:
    """Build the complete sorted list of :class:`AdapterManifestEntry` objects.

    Walks three sources in priority order (extra registry → primitive
    sub-registries → main ToolRegistry) and de-duplicates by ``tool_id``.

    Args:
        registry: A :class:`kosmos.tools.registry.ToolRegistry` instance.
        warn_on_missing: If ``True``, log a warning for entries that cannot
            produce a ``policy_authority_url`` (only for non-internal entries).

    Returns:
        Sorted list of :class:`AdapterManifestEntry` (sorted by ``tool_id``).
    """
    seen: dict[str, AdapterManifestEntry] = {}

    # --- Source 1: extra manifest registry -----------------------------------
    for tool_id, entry in _EXTRA_REGISTRY.items():
        seen[tool_id] = entry

    # --- Source 2a: submit sub-registry --------------------------------------
    try:
        from kosmos.primitives.submit import (
            _ADAPTER_REGISTRY as _submit_registry,  # noqa: PLC0415, N811
        )
    except ImportError:
        _submit_registry = {}

    for tool_id, (reg, _fn) in _submit_registry.items():
        if tool_id in seen:
            continue
        policy_url: str | None = None
        if reg.policy is not None:
            policy_url = reg.policy.real_classification_url
        source_mode_raw = (
            reg.source_mode.value if hasattr(reg.source_mode, "value") else str(reg.source_mode)
        )
        source_mode_val = _map_source_mode(source_mode_raw)
        if source_mode_val in ("live", "mock") and not policy_url and warn_on_missing:
            logger.warning(
                "manifest_emitter: submit adapter %s has no policy URL (source_mode=%s)",
                tool_id,
                source_mode_val,
            )
        try:
            entry = AdapterManifestEntry(
                tool_id=tool_id,
                name=_adapter_display_name(reg),
                primitive=_map_primitive(reg.primitive),
                policy_authority_url=policy_url,
                source_mode=source_mode_val,
            )
            seen[tool_id] = entry
        except Exception as exc:
            logger.warning("manifest_emitter: skipping submit adapter %s — %s", tool_id, exc)

    # --- Source 2c: verify sub-registry --------------------------------------
    # Codex P1 #2445 fix: verify families register via register_verify_adapter()
    # which stores only (family, callable) — no AdapterRegistration is captured.
    # Emit a minimal manifest entry per family so Tier-1 manifest resolution in
    # tui/src/tools/VerifyPrimitive/VerifyPrimitive.ts does not fail closed with
    # AdapterNotFound on legitimate verify family IDs. Verify mocks may also
    # call register_manifest_entry() at module-load to override this default.
    #
    # source_mode is "internal" (not "mock") because verify families do not
    # carry an agency-published HTTPS policy URL at the registry level — their
    # `_policy_authority` lives in the per-call response transparency fields
    # (FR-005), which the audit ledger captures post-call. The pre-call permission
    # UI cite-slot is populated from the response transparency stamp at render
    # time, not from this manifest entry. (Constitution § II preserved: the
    # citizen still sees the agency-published citation, just sourced from the
    # response payload rather than the registry snapshot.)
    try:
        from kosmos.primitives.verify import (
            _VERIFY_ADAPTERS as _verify_adapters,  # noqa: PLC0415, N811
        )
    except ImportError:
        _verify_adapters = {}

    for family in _verify_adapters:
        # Surface verify families under their family name (matches the
        # family_hint argument the LLM passes to verify(family_hint=...)).
        if family in seen:
            continue
        seen[family] = AdapterManifestEntry(
            tool_id=family,
            name=f"verify:{family}",
            primitive="verify",
            policy_authority_url=None,
            source_mode="internal",
        )

    # --- Source 3: main ToolRegistry -----------------------------------------
    try:
        tools_list = list(getattr(registry, "_tools", {}).values())
    except Exception:
        tools_list = []

    for tool in tools_list:
        tool_id_opt: str | None = tool.id if hasattr(tool, "id") else getattr(tool, "tool_id", None)
        if tool_id_opt is None or tool_id_opt in seen:
            continue
        tool_id = tool_id_opt
        policy_url = None
        if tool.policy is not None:
            policy_url = tool.policy.real_classification_url

        raw_primitive: Any = tool.primitive
        if raw_primitive is None:
            # Primitive may be None during pre-v1.2 compatibility window;
            # infer from adapter_mode or skip.
            raw_primitive = "lookup"

        adapter_mode: str = getattr(tool, "adapter_mode", "live")
        source_mode_val = "mock" if adapter_mode == "mock" else "live"

        try:
            entry = AdapterManifestEntry(
                tool_id=tool_id,
                name=getattr(tool, "name_ko", tool_id),
                primitive=_map_primitive(raw_primitive),
                policy_authority_url=policy_url,
                source_mode=source_mode_val,
            )
            seen[tool_id] = entry
        except Exception as exc:
            logger.warning("manifest_emitter: skipping ToolRegistry entry %s — %s", tool_id, exc)

    # --- Add internal MVP surface entries (resolve_location, lookup) ----------
    _add_internal_if_absent(seen, "resolve_location", "Resolve Location", "resolve_location")
    _add_internal_if_absent(seen, "lookup", "Lookup", "lookup")

    return sorted(seen.values(), key=lambda e: e.tool_id)


def _add_internal_if_absent(
    seen: dict[str, AdapterManifestEntry],
    tool_id: str,
    name: str,
    primitive: str,
) -> None:
    """Add an internal (no policy URL) entry if the tool_id is not yet recorded."""
    if tool_id in seen:
        return
    try:
        seen[tool_id] = AdapterManifestEntry(
            tool_id=tool_id,
            name=name,
            primitive=primitive,  # type: ignore[arg-type]
            policy_authority_url=None,
            source_mode="internal",
        )
    except Exception as exc:
        logger.warning("manifest_emitter: could not add internal entry %s — %s", tool_id, exc)


def _map_source_mode(raw: str) -> Literal["live", "mock", "internal"]:
    """Normalise AdapterSourceMode enum value to 'live' | 'mock' | 'internal'."""
    if raw in ("live", "LIVE", "OPENAPI"):
        return "live"
    if raw in ("mock", "MOCK", "OOS", "HARNESS_ONLY"):
        return "mock"
    return "mock"  # fail-safe: unknown modes → mock (conservative)


def _map_primitive(
    raw: Any,
) -> Literal["lookup", "submit", "verify", "resolve_location"]:  # noqa: ANN401
    """Normalise AdapterPrimitive enum value or string to the literal form."""
    s = raw.value if hasattr(raw, "value") else str(raw)
    if s == "lookup":
        return "lookup"
    if s == "submit":
        return "submit"
    if s == "verify":
        return "verify"
    if s == "resolve_location":
        return "resolve_location"
    return "lookup"  # fail-safe


def _adapter_display_name(reg: Any) -> str:  # noqa: ANN401
    """Extract a human-readable display name from an AdapterRegistration."""
    # Prefer module_path tail as a display name fallback.
    tool_id: str = reg.tool_id
    return tool_id.replace("_", " ").title()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def emit_manifest(
    stdout_writer: IO[str],
    registry: Any,  # kosmos.tools.registry.ToolRegistry
    *,
    pid: int | None = None,
) -> None:
    """Emit a single ``AdapterManifestSyncFrame`` to ``stdout_writer``.

    Called once from ``mcp_server.main()`` after ``register_all_tools()``
    completes successfully.  Frame construction failures exit the backend with
    ``SystemExit(78)`` per Constitution § II + Spec 1634 boot-validation.

    Args:
        stdout_writer: Writable text stream (typically ``sys.stdout``).
        registry:      Fully booted :class:`~kosmos.tools.registry.ToolRegistry`.
        pid:           Emitter PID override (defaults to ``os.getpid()``).
    """
    emitter_pid = pid if pid is not None else os.getpid()

    try:
        entries = _build_entries(registry)
        if not entries:
            raise ValueError("No adapter entries available — registry may be empty.")

        manifest_hash = _compute_manifest_hash(entries)

        frame = AdapterManifestSyncFrame(
            kind="adapter_manifest_sync",
            role="backend",
            session_id="",
            correlation_id=_new_ulid(),
            ts=datetime.now(UTC).isoformat(),
            entries=entries,
            manifest_hash=manifest_hash,
            emitter_pid=emitter_pid,
        )
    except Exception as exc:  # noqa: BLE001
        logger.critical("manifest_emitter: failed to build AdapterManifestSyncFrame — %s", exc)
        raise SystemExit(78) from exc  # noqa: TRY200

    json_line = frame.model_dump_json() + "\n"
    stdout_writer.write(json_line)
    stdout_writer.flush()
    logger.info(
        "manifest_emitter: emitted %d entries (hash=%s...)",
        len(entries),
        manifest_hash[:16],
    )


# ---------------------------------------------------------------------------
# Minimal ULID-ish correlation_id (stdlib only, no new deps)
# ---------------------------------------------------------------------------


def _new_ulid() -> str:
    """Return a UUID4-format hex string suitable as a correlation_id.

    Uses ``os.urandom`` (stdlib); no new dependency needed.
    """
    import uuid  # noqa: PLC0415

    return str(uuid.uuid4())
