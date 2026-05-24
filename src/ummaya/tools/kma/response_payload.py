# SPDX-License-Identifier: Apache-2.0
"""KMA response payload decoding helpers.

The KMA VilageFcstInfoService_2.0 technical guide documents XML as the default
wire format. Some data.go.kr services also return XML for successful responses
even when callers prefer JSON. These helpers convert the official XML envelope
into the same nested dict shape produced by the JSON response so adapter parsers
can stay format-agnostic.
"""

from __future__ import annotations

from typing import cast
from xml.etree import ElementTree

import httpx


class KmaPayloadDecodeError(ValueError):
    """Raised when an upstream KMA response body cannot be decoded."""


def summarize_http_status_error(exc: httpx.HTTPStatusError) -> str:
    """Return a short, secret-safe summary for a KMA non-2xx response."""
    status_code = exc.response.status_code
    detail = " ".join(exc.response.text.strip().split())
    if not detail:
        return str(status_code)
    if len(detail) > 160:
        detail = f"{detail[:157]}..."
    return f"{status_code} upstream_body={detail!r}"


def _element_to_value(element: ElementTree.Element) -> object:
    children = list(element)
    if not children:
        return (element.text or "").strip()

    result: dict[str, object] = {}
    for child in children:
        child_value = _element_to_value(child)
        existing = result.get(child.tag)
        if existing is None:
            result[child.tag] = child_value
        elif isinstance(existing, list):
            existing.append(child_value)
        else:
            result[child.tag] = [existing, child_value]
    return result


def parse_xml_payload(text: str) -> dict[str, object]:
    """Parse a KMA XML envelope into a dict keyed by the root tag."""
    try:
        root = ElementTree.fromstring(text)  # noqa: S314 — KMA data.go.kr XML envelope
    except ElementTree.ParseError as exc:
        raise KmaPayloadDecodeError(f"Invalid KMA XML response: {exc}") from exc

    return {root.tag: _element_to_value(root)}


def decode_response_payload(response: httpx.Response) -> dict[str, object]:
    """Decode a KMA HTTP response as JSON or official XML."""
    content_type = response.headers.get("content-type", "").lower()

    if "json" in content_type:
        try:
            payload = response.json()
        except ValueError as exc:
            raise KmaPayloadDecodeError(f"Invalid KMA JSON response: {exc}") from exc
        if not isinstance(payload, dict):
            raise KmaPayloadDecodeError("KMA JSON response root is not an object.")
        return cast(dict[str, object], payload)

    text = response.text
    if "xml" in content_type or text.lstrip().startswith("<"):
        return parse_xml_payload(text)

    try:
        payload = response.json()
    except ValueError as exc:
        raise KmaPayloadDecodeError(
            f"Unsupported KMA response content-type {content_type!r}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise KmaPayloadDecodeError("KMA response root is not an object.")
    return cast(dict[str, object], payload)


def apply_format_params(
    query_params: dict[str, str | int],
    data_type: str,
) -> dict[str, str | int]:
    """Apply KMA format selectors.

    XML is the official default and matches the public guide examples, so the
    adapter omits format selectors for XML. JSON remains available when
    explicitly requested.
    """
    if data_type == "JSON":
        query_params["dataType"] = "JSON"
        query_params["_type"] = "json"
    return query_params
