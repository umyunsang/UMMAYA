"""Boot-time validation + primitive→adapter routing map.

Called from kosmos.tools.register_all at process start. Fails closed on:
- Any registered adapter with primitive=None
- Any registered adapter missing adapter_mode declaration in mock subtree (CI-only; not runtime)
- Duplicate tool_id across the registry

Returns a RoutingIndex that lookup(mode="search") consumes for primitive-
filtered ranking.
"""

from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, ConfigDict

from kosmos.tools.models import GovAPITool

# Primitive literal type — the closed set enforced by invariant 1.
_PrimitiveT = Literal["lookup", "resolve_location", "submit", "verify"]


class RoutingIndex(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    by_primitive: dict[
        Literal["lookup", "resolve_location", "submit", "verify"],
        tuple[GovAPITool, ...],
    ]
    by_tool_id: dict[str, GovAPITool]
    warnings: tuple[str, ...]


class RoutingValidationError(Exception):
    """Fail-closed boot error naming the offending adapter and invariant."""


def build_routing_index(adapters: list[GovAPITool]) -> RoutingIndex:
    """Validate every adapter; return immutable routing index.

    Raises RoutingValidationError on the first failure with a message of the
    form: "<tool_id>: <invariant> — <details>".
    """
    by_primitive: dict[_PrimitiveT, list[GovAPITool]] = defaultdict(list)
    by_tool_id: dict[str, GovAPITool] = {}
    warnings: list[str] = []

    for adapter in adapters:
        # Invariant 1: primitive declared
        if adapter.primitive is None:
            raise RoutingValidationError(
                f"{adapter.id}: invariant 1 (primitive declared) — "
                f"primitive=None on registered adapter"
            )

        # Invariant 4: tool_id unique
        if adapter.id in by_tool_id:
            raise RoutingValidationError(
                f"{adapter.id}: invariant 4 (unique tool_id) — duplicate registration"
            )

        # Warning: ministry="OTHER"
        if hasattr(adapter, "ministry") and adapter.ministry == "OTHER":
            warnings.append(f"{adapter.id}: ministry='OTHER' (transitional escape hatch)")

        # Invariant 1 guarantees adapter.primitive is non-None at this point;
        # mypy narrows the Optional[Literal[...]] to Literal[...] via the early
        # raise above, so the literal matches dict[_PrimitiveT, ...] directly.
        by_primitive[adapter.primitive].append(adapter)
        by_tool_id[adapter.id] = adapter

    return RoutingIndex(
        by_primitive={k: tuple(v) for k, v in by_primitive.items()},
        by_tool_id=by_tool_id,
        warnings=tuple(warnings),
    )
