# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping

from pydantic import BaseModel

from ummaya.tools.routing.types import SchemaFieldSummary


def model_json_schema(model: type[BaseModel]) -> dict[str, object]:
    return {str(key): value for key, value in model.model_json_schema().items()}


def schema_summary(schema: Mapping[str, object]) -> tuple[SchemaFieldSummary, ...]:
    raw_properties = schema.get("properties")
    if not isinstance(raw_properties, Mapping):
        return ()
    required = required_names(schema)
    summaries: list[SchemaFieldSummary] = []
    for raw_name, raw_spec in raw_properties.items():
        name = str(raw_name)
        spec = raw_spec if isinstance(raw_spec, Mapping) else {}
        summaries.append(
            SchemaFieldSummary(
                name=name,
                type=schema_type(spec),
                required=name in required,
                description=schema_description(spec),
            )
        )
    return tuple(summaries)


def required_names(schema: Mapping[str, object]) -> frozenset[str]:
    raw_required = schema.get("required")
    if not isinstance(raw_required, list):
        return frozenset()
    return frozenset(str(item) for item in raw_required if isinstance(item, str))


def schema_type(spec: Mapping[str, object]) -> str:
    raw_type = spec.get("type")
    if isinstance(raw_type, str):
        return raw_type
    if isinstance(raw_type, list):
        return "|".join(str(item) for item in raw_type)
    if "$ref" in spec:
        return "ref"
    if "anyOf" in spec:
        return "anyOf"
    if "oneOf" in spec:
        return "oneOf"
    return "unknown"


def schema_description(spec: Mapping[str, object]) -> str | None:
    value = spec.get("description")
    return value if isinstance(value, str) and value.strip() else None


def sha256(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value).strip()
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result
