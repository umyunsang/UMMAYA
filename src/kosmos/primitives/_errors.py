# SPDX-License-Identifier: Apache-2.0
"""Structured error envelopes for the active primitive harness (T011).

All primitives return structured errors (never raw exceptions) per FR-005 and
the general harness principle. Shapes mirror Spec 022's ``LookupError`` idiom
so cross-primitive serialization stays uniform.

Reference: specs/031-five-primitive-harness/data-model.md § 7.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AdapterNotFoundError(BaseModel):
    """Registry lookup miss — requested ``tool_id`` has no registered adapter.

    Surfaced by :mod:`kosmos.primitives.submit` and ``verify``
    when their dispatch path cannot resolve ``tool_id`` against the registry.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: Literal["adapter_not_found"] = "adapter_not_found"
    tool_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1)


class AdapterInvocationError(BaseModel):
    """Adapter body raised or returned a structured failure.

    ``structured`` carries the adapter-specific error payload verbatim so the
    LLM can reason about the domain failure (e.g., upstream 5xx, validation
    rejection). ``message`` is a human-readable one-line summary.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: Literal["adapter_invocation_failed"] = "adapter_invocation_failed"
    tool_id: str = Field(min_length=1, max_length=128)
    structured: dict[str, object]
    message: str = Field(min_length=1)


__all__ = [
    "AdapterInvocationError",
    "AdapterNotFoundError",
]
