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
   Adapters that do not have a :class:`~ummaya.tools.registry.AdapterRegistration`
   stored in a primitive sub-registry (e.g. verify mocks that register via the
   simple ``register_verify_adapter(family, fn)`` API) may call
   :func:`register_manifest_entry` at module-import time to expose metadata to
   this emitter.  Takes precedence over all other sources for the same
   ``tool_id``.

2. **Send primitive sub-registry**:
   ``ummaya.primitives.submit._ADAPTER_REGISTRY`` →
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
import importlib
import json
import logging
import os
from datetime import UTC, datetime
from typing import IO, Any, Literal

from pydantic import BaseModel

from ummaya.ipc.frame_schema import AdapterManifestEntry, AdapterManifestSyncFrame
from ummaya.tools.manifest_metadata import enrich_input_schema_json

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

        from ummaya.ipc.adapter_manifest_emitter import register_manifest_entry
        from ummaya.ipc.frame_schema import AdapterManifestEntry

        register_manifest_entry(AdapterManifestEntry(
            tool_id="mock_verify_module_simple_auth",
            name="간편인증 / Simple Auth (Mock)",
            primitive="check",
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
        registry: A :class:`ummaya.tools.registry.ToolRegistry` instance.
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
        from ummaya.primitives.submit import (
            _ADAPTER_REGISTRY as _submit_registry,  # noqa: PLC0415, N811
        )
    except ImportError:
        _submit_registry = {}

    registry_tools = getattr(registry, "_tools", {})

    for tool_id, (reg, _fn) in _submit_registry.items():
        if tool_id in seen:
            continue
        source_mode_raw = (
            reg.source_mode.value if hasattr(reg.source_mode, "value") else str(reg.source_mode)
        )
        source_mode_val = _map_source_mode(source_mode_raw)
        policy_url: str | None = None
        if reg.policy is not None:
            policy_url = reg.policy.real_classification_url
        registry_tool = registry_tools.get(tool_id) if isinstance(registry_tools, dict) else None
        if registry_tool is not None:
            try:
                rich_entry = _entry_from_tool(
                    registry_tool,
                    warn_on_missing=warn_on_missing,
                    source_mode_override=source_mode_val,
                )
                seen[tool_id] = AdapterManifestEntry(
                    tool_id=rich_entry.tool_id,
                    name=_adapter_display_name(reg),
                    primitive=rich_entry.primitive,
                    policy_authority_url=policy_url or rich_entry.policy_authority_url,
                    source_mode=source_mode_val,
                    search_hint=rich_entry.search_hint or _adapter_search_hint(reg),
                    llm_description=rich_entry.llm_description or _submit_llm_description(tool_id),
                    input_schema_json=rich_entry.input_schema_json,
                    output_schema_json=rich_entry.output_schema_json,
                )
                continue
            except Exception as exc:
                logger.warning(
                    "manifest_emitter: falling back to submit registration for %s — %s",
                    tool_id,
                    exc,
                )

        if source_mode_val in ("live", "mock") and not policy_url and warn_on_missing:
            logger.warning(
                "manifest_emitter: submit adapter %s has no policy URL (source_mode=%s)",
                tool_id,
                source_mode_val,
            )
        try:
            input_model = _resolve_model_ref(getattr(reg, "input_model_ref", ""))
            entry = AdapterManifestEntry(
                tool_id=tool_id,
                name=_adapter_display_name(reg),
                primitive=_map_primitive(reg.primitive),
                policy_authority_url=policy_url,
                source_mode=source_mode_val,
                search_hint=_adapter_search_hint(reg),
                llm_description=_submit_llm_description(tool_id),
                input_schema_json=_model_json_schema(input_model, tool_id=tool_id),
                output_schema_json=_submit_output_schema(),
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
        from ummaya.primitives.verify import (
            _VERIFY_ADAPTERS as _verify_adapters,  # noqa: PLC0415, N811
        )
    except ImportError:
        _verify_adapters = {}

    verify_family_metadata = _verify_family_metadata_by_family()
    for family in _verify_adapters:
        # Surface verify families under their family name (matches the
        # family_hint argument the LLM passes to verify(family_hint=...)).
        if family in seen:
            continue
        if family in verify_family_metadata:
            seen[family] = _entry_from_verify_family(family, verify_family_metadata[family])
            continue
        seen[family] = AdapterManifestEntry(
            tool_id=family,
            name=f"check:{family}",
            primitive="check",
            policy_authority_url=None,
            source_mode="internal",
            search_hint=(
                f"{family} verify check authentication delegation consent scope_list "
                "purpose_ko purpose_en"
            ),
            llm_description=_verify_family_llm_description(family, None),
            input_schema_json=_model_json_schema(
                _resolve_verify_params_shell(),
                tool_id=family,
            ),
            output_schema_json=_model_json_schema(_resolve_verify_output_shell()),
        )

    # --- Source 3: main ToolRegistry -----------------------------------------
    try:
        tools_list = list(registry_tools.values()) if isinstance(registry_tools, dict) else []
    except Exception:
        tools_list = []

    root_primitive_tool_ids = frozenset({"locate", "find", "check", "send"})

    for tool in tools_list:
        tool_id_opt: str | None = tool.id if hasattr(tool, "id") else getattr(tool, "tool_id", None)
        if tool_id_opt is None or tool_id_opt in root_primitive_tool_ids or tool_id_opt in seen:
            continue
        tool_id = tool_id_opt
        try:
            seen[tool_id] = _entry_from_tool(tool, warn_on_missing=warn_on_missing)
        except Exception as exc:
            logger.warning("manifest_emitter: skipping ToolRegistry entry %s — %s", tool_id, exc)

    return sorted(seen.values(), key=lambda e: e.tool_id)


def _entry_from_tool(  # noqa: ANN401
    tool: Any,
    *,
    warn_on_missing: bool = False,
    source_mode_override: Literal["live", "mock", "internal"] | None = None,
) -> AdapterManifestEntry:
    """Build a manifest entry from a full GovAPITool-like registry record."""
    tool_id = str(getattr(tool, "id", getattr(tool, "tool_id", "")))
    policy = getattr(tool, "policy", None)
    policy_url = policy.real_classification_url if policy is not None else None

    raw_primitive: Any = getattr(tool, "primitive", None)
    if raw_primitive is None:
        raw_primitive = "find"

    adapter_mode = str(getattr(tool, "adapter_mode", "live"))
    source_mode_val: Literal["live", "mock", "internal"] = (
        "mock" if adapter_mode == "mock" else "live"
    )
    if source_mode_override is not None:
        source_mode_val = source_mode_override

    if source_mode_val in ("live", "mock") and not policy_url and warn_on_missing:
        logger.warning(
            "manifest_emitter: registry adapter %s has no policy URL (source_mode=%s)",
            tool_id,
            source_mode_val,
        )

    return AdapterManifestEntry(
        tool_id=tool_id,
        name=getattr(tool, "name_ko", tool_id),
        primitive=_map_primitive(raw_primitive),
        policy_authority_url=policy_url,
        source_mode=source_mode_val,
        search_hint=getattr(tool, "search_hint", None),
        llm_description=getattr(tool, "llm_description", None),
        input_schema_json=_schema_attr_json(tool, "input_schema", tool_id=tool_id),
        output_schema_json=_schema_attr_json(tool, "output_schema"),
    )


def _entry_from_verify_family(
    family: str,
    metadata: dict[str, object],
) -> AdapterManifestEntry:
    """Build the internal manifest entry for one verify family."""

    name = str(metadata.get("name_ko") or family).strip()
    return AdapterManifestEntry(
        tool_id=family,
        name=f"check:{name}",
        primitive="check",
        policy_authority_url=None,
        source_mode="internal",
        search_hint=_verify_search_hint(metadata),
        llm_description=_verify_family_llm_description(family, metadata),
        input_schema_json=_model_json_schema(
            _resolve_verify_params_shell(),
            tool_id=family,
        ),
        output_schema_json=_model_json_schema(_resolve_verify_output_shell()),
    )


def _verify_family_metadata_by_family() -> dict[str, dict[str, object]]:
    """Return discovery-bridge verify metadata keyed by family id."""

    try:
        from ummaya.tools.discovery_bridge import _VERIFY_FAMILIES  # noqa: PLC0415
    except ImportError:
        return {}

    result: dict[str, dict[str, object]] = {}
    for entry in _VERIFY_FAMILIES:
        family = str(entry.get("family") or "").strip()
        if family:
            result[family] = dict(entry)
    return result


def _verify_search_hint(metadata: dict[str, object]) -> str:
    """Compose the bilingual discovery phrase for one verify family."""

    ko = " ".join(_string_list(metadata.get("search_hint_ko")))
    en = " ".join(_string_list(metadata.get("search_hint_en")))
    family = str(metadata.get("family") or "").strip()
    tool_id = str(metadata.get("tool_id") or "").strip()
    return (
        f"{ko} {en} {family} {tool_id} verify check authentication "
        "인증 인증서 위임 delegation scope_list purpose_ko purpose_en"
    ).strip()


def _verify_family_llm_description(
    family: str,
    metadata: dict[str, object] | None,
) -> str:
    """Build model-facing prose for a verify-family manifest entry."""

    metadata = metadata or {}
    tool_id = str(metadata.get("tool_id") or family).strip()
    name = str(metadata.get("name_ko") or family).strip()
    scope_rules = str(metadata.get("scope_rules") or "").strip()
    scope_clause = f" {scope_rules}" if scope_rules else ""
    return (
        f"Internal check-family surface for {name} (family_hint='{family}', "
        f"bridged adapter id '{tool_id}'). Use this only through the core check "
        "primitive before a downstream protected find/send action needs delegated "
        "authorization. Params must follow input_schema_json exactly: scope_list "
        "contains '<verb>:<adapter_family>.<action>' scope strings, purpose_ko is "
        "the Korean citizen-facing consent purpose, and purpose_en is the audit-log "
        "English purpose. The manifest entry stays source_mode='internal' because "
        "the agency citation is emitted by the verify response transparency stamp, "
        "while the pre-call tool schema remains stable for the TUI and LLM loop."
        f"{scope_clause}"
    )


def _string_list(value: object) -> list[str]:
    """Return non-empty strings from a loosely typed metadata list."""

    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _resolve_verify_params_shell() -> type[BaseModel] | None:
    """Resolve the discovery bridge check params schema without import-time coupling."""

    try:
        from ummaya.tools.discovery_bridge import _VerifyParamsShell  # noqa: PLC0415
    except ImportError:
        return None
    return _VerifyParamsShell


def _resolve_verify_output_shell() -> type[BaseModel] | None:
    """Resolve the discovery bridge opaque output schema without import-time coupling."""

    try:
        from ummaya.tools.discovery_bridge import _OpaqueOutput  # noqa: PLC0415
    except ImportError:
        return None
    return _OpaqueOutput


def _schema_attr_json(  # noqa: ANN401
    owner: Any,
    attr: str,
    *,
    tool_id: str | None = None,
) -> dict[str, object]:
    """Export ``owner.<attr>.model_json_schema()`` when present."""
    model = getattr(owner, attr, None)
    return _model_json_schema(model, tool_id=tool_id)


def _model_json_schema(
    model: object | None,
    *,
    tool_id: str | None = None,
) -> dict[str, object]:
    """Return a Pydantic JSON Schema dict for ``model`` or ``{}`` on absence."""
    if model is None:
        return {}
    if not isinstance(model, type) or not issubclass(model, BaseModel):
        return {}
    try:
        schema = model.model_json_schema()
    except Exception as exc:  # pragma: no cover - defensive registry path
        logger.warning("manifest_emitter: failed to export schema for %s — %s", model, exc)
        return {}
    exported = {str(key): value for key, value in schema.items()}
    if tool_id is not None:
        return enrich_input_schema_json(tool_id, exported)
    return exported


def _resolve_model_ref(model_ref: str) -> type[BaseModel] | None:
    """Resolve ``module.Model`` references used by submit AdapterRegistration."""
    if not model_ref or "." not in model_ref:
        return None
    try:
        module_name, model_name = model_ref.rsplit(".", 1)
        model = getattr(importlib.import_module(module_name), model_name)
    except Exception as exc:  # pragma: no cover - defensive registry path
        logger.warning("manifest_emitter: failed to resolve input model %s — %s", model_ref, exc)
        return None
    if isinstance(model, type) and issubclass(model, BaseModel):
        return model
    return None


def _submit_output_schema() -> dict[str, object]:
    """Export the submit primitive output envelope schema."""
    try:
        from ummaya.primitives.submit import SubmitOutput  # noqa: PLC0415
    except ImportError:
        return {}
    return _model_json_schema(SubmitOutput)


def _adapter_search_hint(reg: Any) -> str | None:  # noqa: ANN401
    """Flatten AdapterRegistration bilingual search hints."""
    search_hint = getattr(reg, "search_hint", None)
    if not isinstance(search_hint, dict):
        return None
    parts: list[str] = []
    for locale in ("ko", "en"):
        values = search_hint.get(locale)
        if isinstance(values, list):
            parts.extend(str(value).strip() for value in values if str(value).strip())
    return " ".join(parts) or None


def _submit_llm_description(tool_id: str) -> str:
    """Build the model-facing usage prose for submit adapters without a GovAPITool wrapper."""
    return (
        f"send primitive adapter {tool_id}. Requires a prior check call that returns a "
        "matching DelegationContext. Pass the adapter-specific payload described by "
        "input_schema_json; credential and authorization material is supplied by UMMAYA runtime."
    )


def _map_source_mode(raw: str) -> Literal["live", "mock", "internal"]:
    """Normalise AdapterSourceMode enum value to 'live' | 'mock' | 'internal'."""
    if raw in ("live", "LIVE", "OPENAPI"):
        return "live"
    if raw in ("mock", "MOCK", "OOS", "HARNESS_ONLY"):
        return "mock"
    return "mock"  # fail-safe: unknown modes → mock (conservative)


def _map_primitive(
    raw: Any,
) -> Literal["find", "send", "check", "locate"]:  # noqa: ANN401
    """Normalise AdapterPrimitive enum value or string to the literal form."""
    s = raw.value if hasattr(raw, "value") else str(raw)
    if s == "find":
        return "find"
    if s == "send":
        return "send"
    if s == "check":
        return "check"
    if s == "locate":
        return "locate"
    return "find"  # fail-safe


def _adapter_display_name(reg: Any) -> str:  # noqa: ANN401
    """Extract a human-readable display name from an AdapterRegistration."""
    tool_id: str = reg.tool_id

    policy = getattr(reg, "policy", None)
    policy_text = getattr(policy, "real_classification_text", None)
    if isinstance(policy_text, str):
        text = policy_text.strip()
        if text:
            # Adapter policy text is the authoritative citizen-facing source.
            # Most submit mocks phrase it as "<service name> -- <authority note>".
            service_name = text.split("—", 1)[0].split(" - ", 1)[0].strip()
            if service_name:
                return service_name

    search_hint = getattr(reg, "search_hint", None)
    if isinstance(search_hint, dict):
        ko_hints = search_hint.get("ko")
        if isinstance(ko_hints, list):
            hints = [str(h).strip() for h in ko_hints if str(h).strip()]
            if hints:
                return " ".join(hints[:2])

    return tool_id.replace("_", " ")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def emit_manifest(
    stdout_writer: IO[str],
    registry: Any,  # ummaya.tools.registry.ToolRegistry
    *,
    pid: int | None = None,
) -> None:
    """Emit a single ``AdapterManifestSyncFrame`` to ``stdout_writer``.

    Called once from ``mcp_server.main()`` after ``register_all_tools()``
    completes successfully.  Frame construction failures exit the backend with
    ``SystemExit(78)`` per Constitution § II + Spec 1634 boot-validation.

    Args:
        stdout_writer: Writable text stream (typically ``sys.stdout``).
        registry:      Fully booted :class:`~ummaya.tools.registry.ToolRegistry`.
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
