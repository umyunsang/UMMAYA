# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import Collection, Iterable

from ummaya.tools.routing.intent_patterns import (
    _ADMIN_LOCATION_RE,
    _ARTIFACT_ID_RE,
    _COORDINATE_PAIR_RE,
    _CREDENTIAL_RE,
    _DOCUMENT_FORMAT_RE,
    _DOCUMENT_INTENT_RE,
    _DOCUMENT_LOCAL_HINT_RE,
    _DOCUMENT_PATH_RE,
    _DOCUMENT_WRITE_INTENT_RE,
    _EXPLICIT_TOOL_ID_RE,
    _PAYMENT_SIDE_EFFECT_RE,
    _POI_LOCATION_RE,
    _SIDE_EFFECT_RE,
    _SUBMIT_SIDE_EFFECT_RE,
    _WHITESPACE_RE,
)
from ummaya.tools.routing.intent_public_data import extract_public_data_refs
from ummaya.tools.routing.intent_types import (
    ACTIVE_PRIMITIVES,
    ActivePrimitive,
    ToolSelectionIntent,
)


def extract_tool_selection_intent(
    query: str, *, known_tool_ids: Collection[str] = ()
) -> ToolSelectionIntent:
    normalized_query = _normalize_query(query)
    document_refs = _extract_document_refs(query)
    location_refs = _extract_location_refs(query)
    public_data_refs = extract_public_data_refs(query)
    credential_refs = _extract_credential_refs(query)
    side_effect_markers = _extract_side_effect_markers(query, document_refs=document_refs)
    explicit_tool_ids = _extract_explicit_tool_ids(query, known_tool_ids=known_tool_ids)
    explicit_artifact_ids = _ordered_unique(_ARTIFACT_ID_RE.findall(query))
    candidate_primitives = _candidate_primitives(
        normalized_query=normalized_query,
        document_refs=document_refs,
        location_refs=location_refs,
        public_data_refs=public_data_refs,
        credential_refs=credential_refs,
        side_effect_markers=side_effect_markers,
        explicit_tool_ids=explicit_tool_ids,
    )
    return ToolSelectionIntent(
        raw_query=query,
        normalized_query=normalized_query,
        intent_verbs=candidate_primitives,
        entities=(),
        document_refs=document_refs,
        location_refs=location_refs,
        time_refs=(),
        public_data_refs=public_data_refs,
        credential_refs=credential_refs,
        side_effect_markers=side_effect_markers,
        explicit_tool_ids=explicit_tool_ids,
        explicit_artifact_ids=explicit_artifact_ids,
        candidate_primitives=candidate_primitives,
        missing_slots=_missing_slots(location_refs, public_data_refs),
        unsafe_assumptions=_unsafe_assumptions(location_refs, public_data_refs),
        requires_clarification=not normalized_query,
        requires_permission=bool(credential_refs or side_effect_markers),
    )


def _normalize_query(query: str) -> str:
    return _WHITESPACE_RE.sub(" ", query.strip()).lower()


def _extract_explicit_tool_ids(query: str, *, known_tool_ids: Collection[str]) -> tuple[str, ...]:
    matches: list[tuple[int, str]] = []
    for match in _EXPLICIT_TOOL_ID_RE.finditer(query):
        matches.append((match.start(1), match.group(1)))
    query_lower = query.lower()
    for tool_id in known_tool_ids:
        index = query_lower.find(tool_id.lower())
        if index >= 0:
            matches.append((index, tool_id))
    return _ordered_unique(value for _index, value in sorted(matches))


def _extract_document_refs(query: str) -> tuple[str, ...]:
    refs: list[str] = []
    refs.extend(match.group(1).strip() for match in _DOCUMENT_PATH_RE.finditer(query))
    refs.extend(f"format:{match.group(1).lower()}" for match in _DOCUMENT_FORMAT_RE.finditer(query))
    if _is_document_harness_query(query):
        refs.append("document_harness")
    return _ordered_unique(refs)


def _extract_location_refs(query: str) -> tuple[str, ...]:
    refs: list[str] = []
    for match in _COORDINATE_PAIR_RE.finditer(query):
        lat = float(match.group("lat"))
        lon = float(match.group("lon"))
        if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
            refs.append(f"coordinate:{_format_decimal(lat)},{_format_decimal(lon)}")
    if _POI_LOCATION_RE.search(query):
        refs.append("poi")
    if _ADMIN_LOCATION_RE.search(query):
        refs.append("admin")
    return _ordered_unique(refs)


def _extract_credential_refs(query: str) -> tuple[str, ...]:
    if not _CREDENTIAL_RE.search(query):
        return ()
    refs: list[str] = []
    lowered = query.lower()
    if "간편인증" in query:
        refs.append("simple_auth")
    if "모바일" in query and "신분증" in query:
        refs.append("mobile_id")
    if "인증서" in query:
        refs.append("certificate")
    if "동의" in query or "consent" in lowered or "delegation" in lowered:
        refs.append("delegation")
    if not refs:
        refs.append("credential")
    return _ordered_unique(refs)


def _extract_side_effect_markers(query: str, *, document_refs: tuple[str, ...]) -> tuple[str, ...]:
    refs: list[str] = []
    if _SIDE_EFFECT_RE.search(query):
        refs.append("action")
    if _SUBMIT_SIDE_EFFECT_RE.search(query):
        refs.append("submit")
    if _PAYMENT_SIDE_EFFECT_RE.search(query):
        refs.append("payment")
    if document_refs and _DOCUMENT_WRITE_INTENT_RE.search(query):
        refs.append("document_write")
    return _ordered_unique(refs)


def _candidate_primitives(
    *,
    normalized_query: str,
    document_refs: tuple[str, ...],
    location_refs: tuple[str, ...],
    public_data_refs: tuple[str, ...],
    credential_refs: tuple[str, ...],
    side_effect_markers: tuple[str, ...],
    explicit_tool_ids: tuple[str, ...],
) -> tuple[ActivePrimitive, ...]:
    primitives: set[ActivePrimitive] = set()
    if normalized_query or public_data_refs or document_refs or explicit_tool_ids:
        primitives.add("find")
    if location_refs:
        primitives.add("locate")
    if side_effect_markers:
        primitives.add("send")
    if credential_refs:
        primitives.add("check")
    return tuple(primitive for primitive in ACTIVE_PRIMITIVES if primitive in primitives)


def _missing_slots(
    location_refs: tuple[str, ...], public_data_refs: tuple[str, ...]
) -> tuple[str, ...]:
    has_coordinate = any(ref.startswith("coordinate:") for ref in location_refs)
    coordinate_bound_refs = {"emergency_medical", "aed"}
    if not has_coordinate and any(ref in coordinate_bound_refs for ref in public_data_refs):
        return ("lat", "lon")
    return ()


def _unsafe_assumptions(
    location_refs: tuple[str, ...], public_data_refs: tuple[str, ...]
) -> tuple[str, ...]:
    if "poi" in location_refs and not any(ref.startswith("coordinate:") for ref in location_refs):
        return ("poi_requires_location_resolution",)
    return ()


def _is_document_harness_query(query: str) -> bool:
    return bool(
        _DOCUMENT_PATH_RE.search(query)
        or (_DOCUMENT_FORMAT_RE.search(query) and _DOCUMENT_INTENT_RE.search(query))
        or (
            _DOCUMENT_INTENT_RE.search(query)
            and _DOCUMENT_WRITE_INTENT_RE.search(query)
            and _DOCUMENT_LOCAL_HINT_RE.search(query)
        )
    )


def _format_decimal(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)
