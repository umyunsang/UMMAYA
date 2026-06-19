# SPDX-License-Identifier: Apache-2.0
"""JSON-compatible type aliases for Evidence Fabric payload assembly."""

from __future__ import annotations

from typing import Final

from pydantic import TypeAdapter

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonArray = list[JsonValue]
type JsonObject = dict[str, JsonValue]

_JSON_OBJECT_ADAPTER: Final[TypeAdapter[JsonObject]] = TypeAdapter(JsonObject)


def parse_json_object(value: JsonValue) -> JsonObject:
    """Parse a JSON-compatible value into a JSON mapping."""
    return _JSON_OBJECT_ADAPTER.validate_python(value)
