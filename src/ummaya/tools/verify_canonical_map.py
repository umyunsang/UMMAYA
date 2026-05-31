# SPDX-License-Identifier: Apache-2.0
"""Canonical map: ``tool_id`` → ``family_hint`` for the check primitive.

The mapping is derived from adapter metadata, not from the system prompt. The
system prompt describes available tools; it is not a runtime source of truth for
dispatch.

Public API
----------
``resolve_family(tool_id)``  → ``str | None``
    Return the ``family_hint`` string for the given check tool_id, or ``None``
    if the tool_id is not recognised.

``resolve_tool_id(identifier)``  → ``str | None``
    Return the canonical ``mock_verify_*`` tool_id when *identifier* is either a
    canonical check tool_id or an internal family_hint alias such as
    ``mobile_id`` / ``simple_auth_module``.

``get_canonical_map()``  → ``Mapping[str, str]``
    Return the full frozen ``{tool_id: family_hint}`` mapping.

Design
------
- Runtime dispatch must not parse ``prompts/system_v1.md``.
- The bridge metadata in :mod:`ummaya.tools.discovery_bridge` is the adapter
  inventory mirrored into the central ToolRegistry for discovery.
- FR-008b: raises ``RuntimeError`` if fewer than 10 entries are available.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from types import MappingProxyType

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Explicit overrides for tool_ids whose family_hint differs from the simple
# prefix-stripped value.  These two entries have the canonical ``_module``
# suffix in the family_hint even though it is absent from the tool_id suffix.
# Source: data-model.md § 2 + src/ummaya/primitives/verify.py
# (Literal["simple_auth_module"] / Literal["geumyung_module"]).
_FAMILY_OVERRIDES: dict[str, str] = {
    "mock_verify_module_simple_auth": "simple_auth_module",
    "mock_verify_module_geumyung": "geumyung_module",
}

_MODULE_PREFIX = "mock_verify_module_"
_PLAIN_PREFIX = "mock_verify_"


def _tool_id_to_family(tool_id: str) -> str:
    """Derive the family_hint from a tool_id string.

    Checks the override table first, then falls back to prefix stripping:
    - ``mock_verify_module_<suffix>`` → ``<suffix>``
    - ``mock_verify_<suffix>``        → ``<suffix>``
    """
    if tool_id in _FAMILY_OVERRIDES:
        return _FAMILY_OVERRIDES[tool_id]
    if tool_id.startswith(_MODULE_PREFIX):
        return tool_id[len(_MODULE_PREFIX) :]
    if tool_id.startswith(_PLAIN_PREFIX):
        return tool_id[len(_PLAIN_PREFIX) :]
    return tool_id


@lru_cache(maxsize=1)
def _load_map() -> Mapping[str, str]:
    """Read check adapter metadata and return a frozen mapping.

    Raises
    ------
    RuntimeError
        If fewer than 10 entries are available (FR-008b).
    """
    from ummaya.tools.discovery_bridge import _VERIFY_FAMILIES  # noqa: PLC0415

    mapping: dict[str, str] = {
        str(entry["tool_id"]): _tool_id_to_family(str(entry["tool_id"]))
        for entry in _VERIFY_FAMILIES
        if isinstance(entry, dict) and isinstance(entry.get("tool_id"), str)
    }

    if len(mapping) < 10:
        raise RuntimeError(f"verify_canonical_map: expected ≥10 entries, got {len(mapping)}")

    return MappingProxyType(mapping)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_family(tool_id: str) -> str | None:
    """Return the ``family_hint`` for *tool_id*, or ``None`` if unknown.

    The mapping is loaded once from adapter metadata at first call
    (``lru_cache``). Subsequent calls return the cached mapping.
    """
    return _load_map().get(tool_id)


def resolve_tool_id(identifier: str) -> str | None:
    """Return the canonical check tool_id for *identifier*.

    This is the runtime guard for model-facing alias drift.  The manifest can
    include internal verify-family entries for backward compatibility, but
    adapter dispatch is owned by canonical ``mock_verify_*`` tool ids.
    """
    mapping = _load_map()
    if identifier in mapping:
        return identifier
    for tool_id, family in mapping.items():
        if family == identifier:
            return tool_id
    return None


def get_canonical_map() -> Mapping[str, str]:
    """Return the full ``{tool_id: family_hint}`` frozen mapping (read-only)."""
    return _load_map()
