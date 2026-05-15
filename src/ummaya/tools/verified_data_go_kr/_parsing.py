# SPDX-License-Identifier: Apache-2.0
"""Response parsers for verified data.go.kr-style adapters."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping, Sequence
from typing import cast

from ummaya.tools.verified_data_go_kr._models import (
    ResponseFormat,
    VerifiedPublicDataItem,
    VerifiedPublicDataOutput,
)

SUCCESS_CODES = frozenset({"0", "00", "INFO-000"})
MAX_PAYLOAD_BYTES = 2_000_000


class VerifiedUpstreamError(ValueError):
    """Raised when an upstream payload is structurally valid but reports failure."""

    def __init__(self, upstream_code: str, upstream_message: str) -> None:
        super().__init__(f"Verified upstream returned {upstream_code}: {upstream_message}")
        self.upstream_code = upstream_code
        self.upstream_message = upstream_message


def parse_verified_payload(
    payload: bytes,
    *,
    response_format: ResponseFormat,
    record_tag: str | None = None,
) -> VerifiedPublicDataOutput:
    """Parse a verified live-probe payload into a collection envelope."""

    if len(payload) > MAX_PAYLOAD_BYTES:
        raise VerifiedUpstreamError("PAYLOAD_TOO_LARGE", f"{len(payload)} bytes")

    if response_format == "json":
        raw: object = json.loads(payload.decode("utf-8-sig"))
        return _parse_json_payload(raw)
    root = ET.fromstring(payload.decode("utf-8-sig"))  # noqa: S314
    return _parse_xml_payload(root, record_tag=record_tag)


def _parse_json_payload(raw: object) -> VerifiedPublicDataOutput:
    code, message = _find_json_status(raw)
    if code is not None and code not in SUCCESS_CODES:
        raise VerifiedUpstreamError(code, message or "")

    records = _extract_json_records(raw)
    total_count = _find_first_int(raw, ("totalCount", "totData", "list_total_count"))
    return VerifiedPublicDataOutput(
        items=[VerifiedPublicDataItem(record=record) for record in records],
        total_count=total_count if total_count is not None else len(records),
    )


def _parse_xml_payload(
    root: ET.Element,
    *,
    record_tag: str | None,
) -> VerifiedPublicDataOutput:
    code = _find_xml_text(root, "resultCode")
    message = _find_xml_text(root, "resultMsg") or ""
    if code is not None and code not in SUCCESS_CODES:
        raise VerifiedUpstreamError(code, message)

    if record_tag is not None:
        elements = [_el for _el in root.iter() if _strip_namespace(_el.tag) == record_tag]
    else:
        elements = [_el for _el in root.iter() if _strip_namespace(_el.tag) == "item"]

    records = [_xml_record(element) for element in elements]
    total_count = _to_int(_find_xml_text(root, "totalCount"))
    return VerifiedPublicDataOutput(
        items=[VerifiedPublicDataItem(record=record) for record in records],
        total_count=total_count if total_count is not None else len(records),
    )


def _find_json_status(raw: object) -> tuple[str | None, str | None]:
    for mapping in _walk_mappings(raw):
        result_code = _string_value(mapping.get("resultCode"))
        if result_code is not None:
            return result_code, _string_value(mapping.get("resultMsg"))
        result = mapping.get("RESULT")
        if isinstance(result, Mapping):
            result_map = cast(Mapping[object, object], result)
            code = _string_value(result_map.get("CODE"))
            if code is not None:
                return code, _string_value(result_map.get("MESSAGE"))
    return None, None


def _extract_json_records(raw: object) -> list[dict[str, object]]:
    root = _as_mapping(raw)
    if root is None:
        return _coerce_records(raw)

    response = _as_mapping(root.get("response"))
    if response is not None:
        body = _as_mapping(response.get("body"))
        if body is not None:
            items = body.get("items")
            item_records = _extract_items_value(items)
            if item_records:
                return item_records

    reb_rows = _extract_reb_rows(root)
    if reb_rows:
        return reb_rows

    data_records = _coerce_records(root.get("data"))
    if data_records:
        return data_records

    row_records = _coerce_records(root.get("row"))
    if row_records:
        return row_records

    return _coerce_records(raw)


def _extract_items_value(value: object) -> list[dict[str, object]]:
    items = _as_mapping(value)
    if items is not None:
        nested = _coerce_records(items.get("item"))
        if nested:
            return nested
        return _coerce_records(items)
    return _coerce_records(value)


def _extract_reb_rows(root: Mapping[object, object]) -> list[dict[str, object]]:
    for value in root.values():
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            continue
        for entry in value:
            entry_map = _as_mapping(entry)
            if entry_map is None:
                continue
            rows = _coerce_records(entry_map.get("row"))
            if rows:
                return rows
    return []


def _coerce_records(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        records: list[dict[str, object]] = []
        for item in value:
            item_map = _as_mapping(item)
            if item_map is not None:
                records.append(_normalize_mapping(item_map))
        return records
    value_map = _as_mapping(value)
    if value_map is not None:
        return [_normalize_mapping(value_map)]
    return []


def _walk_mappings(value: object) -> Iterable[Mapping[object, object]]:
    value_map = _as_mapping(value)
    if value_map is not None:
        yield value_map
        for child in value_map.values():
            yield from _walk_mappings(child)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            yield from _walk_mappings(item)


def _find_first_int(value: object, keys: tuple[str, ...]) -> int | None:
    for mapping in _walk_mappings(value):
        for key in keys:
            parsed = _to_int(_string_value(mapping.get(key)))
            if parsed is not None:
                return parsed
    return None


def _normalize_mapping(mapping: Mapping[object, object]) -> dict[str, object]:
    return {str(key): _normalize_value(value) for key, value in mapping.items()}


def _normalize_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _normalize_mapping(cast(Mapping[object, object], value))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize_value(item) for item in value]
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _as_mapping(value: object) -> Mapping[object, object] | None:
    if isinstance(value, Mapping):
        return cast(Mapping[object, object], value)
    return None


def _string_value(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def _to_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _find_xml_text(root: ET.Element, tag_name: str) -> str | None:
    for element in root.iter():
        if _strip_namespace(element.tag) == tag_name:
            text = element.text.strip() if element.text is not None else ""
            return text or None
    return None


def _xml_record(element: ET.Element) -> dict[str, object]:
    record: dict[str, object] = {}
    for child in list(element):
        tag = _strip_namespace(child.tag)
        if list(child):
            record[tag] = _xml_record(child)
        else:
            record[tag] = child.text.strip() if child.text is not None else ""
    if not record:
        text = element.text.strip() if element.text is not None else ""
        record[_strip_namespace(element.tag)] = text
    return record


def _strip_namespace(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]
