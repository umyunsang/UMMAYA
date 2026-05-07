# SPDX-License-Identifier: Apache-2.0
"""Q8 — Reserved-name & namespace (3 checks).

Backstop for the validators already enforced in
``kosmos.plugins.manifest_schema._v_namespace``. This module re-runs
the same logic on a parsed manifest so the checklist row exists in the
50-item matrix and a tampered manifest (e.g. constructed via
``model_construct``) still gets caught.
"""

from __future__ import annotations

import re

from kosmos.plugins.checks.framework import CheckContext, CheckOutcome, failed, passed

_NAMESPACE_RE = re.compile(r"^plugin\.[a-z][a-z0-9_]*\.(lookup|submit|verify)$")
_ROOT_PRIMITIVES: frozenset[str] = frozenset({"lookup", "submit", "verify"})
_HOST_RESERVED: frozenset[str] = frozenset({"resolve_location"})


def _ensure_manifest(ctx: CheckContext, check_id: str) -> CheckOutcome | None:
    if ctx.manifest is None:
        return failed(
            ko=f"manifest 검증 실패로 {check_id} 확인 불가",
            en=f"cannot run {check_id} — manifest failed validation",
        )
    return None


def check_namespace(ctx: CheckContext) -> CheckOutcome:
    """Q8-NAMESPACE — tool_id matches plugin.<id>.<verb> regex."""
    blocked = _ensure_manifest(ctx, "Q8-NAMESPACE")
    if blocked:
        return blocked
    assert ctx.manifest is not None
    tool_id = ctx.manifest.adapter.tool_id
    if not _NAMESPACE_RE.fullmatch(tool_id):
        return failed(
            ko=(
                f"tool_id {tool_id!r} 가 plugin.<id>.<verb> 형식이 아님 "
                "(verb ∈ lookup/submit/verify)"
            ),
            en=(
                f"tool_id {tool_id!r} does not match plugin.<id>.<verb> "
                "(verb ∈ lookup/submit/verify)"
            ),
        )
    return passed()


def check_no_root_override(ctx: CheckContext) -> CheckOutcome:
    """Q8-NO-ROOT-OVERRIDE — tool_id 's verb is NOT a host-reserved primitive.

    `resolve_location` is host-only (Migration tree § L1-C C6); plugins
    cannot override it even though the AdapterRegistration regex allows
    it for symmetry with the in-tree adapter.
    """
    blocked = _ensure_manifest(ctx, "Q8-NO-ROOT-OVERRIDE")
    if blocked:
        return blocked
    assert ctx.manifest is not None
    tool_id = ctx.manifest.adapter.tool_id
    parts = tool_id.split(".")
    if len(parts) != 3:
        return failed(
            ko=f"tool_id {tool_id!r} 형식 오류",
            en=f"tool_id {tool_id!r} has wrong shape",
        )
    verb = parts[2]
    if verb in _HOST_RESERVED:
        return failed(
            ko=(f"verb {verb!r} 는 host 가 소유한 built-in primitive — 플러그인이 override 불가"),
            en=(f"verb {verb!r} is a host-owned built-in primitive — plugins cannot override"),
        )
    return passed()


def check_verb_in_primitives(ctx: CheckContext) -> CheckOutcome:
    """Q8-VERB-IN-PRIMITIVES — tool_id verb ∈ active plugin primitive verbs."""
    blocked = _ensure_manifest(ctx, "Q8-VERB-IN-PRIMITIVES")
    if blocked:
        return blocked
    assert ctx.manifest is not None
    tool_id = ctx.manifest.adapter.tool_id
    parts = tool_id.split(".")
    if len(parts) != 3:
        return failed(
            ko=f"tool_id {tool_id!r} 형식 오류",
            en=f"tool_id {tool_id!r} has wrong shape",
        )
    verb = parts[2]
    if verb not in _ROOT_PRIMITIVES:
        sorted_primitives = sorted(_ROOT_PRIMITIVES)
        return failed(
            ko=(f"verb {verb!r} 는 active plugin primitive 중 하나가 아님 ({sorted_primitives})"),
            en=(f"verb {verb!r} is not one of the active plugin primitives ({sorted_primitives})"),
        )
    return passed()


__all__ = [
    "check_namespace",
    "check_no_root_override",
    "check_verb_in_primitives",
]
