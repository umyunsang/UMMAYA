# SPDX-License-Identifier: Apache-2.0
"""Typed models for verified public-data adapter wrappers."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ummaya.tools.models import Ministry

ResponseFormat = Literal["json", "xml"]


class VerifiedPublicDataItem(BaseModel):
    """One normalized upstream row."""

    model_config = ConfigDict(extra="forbid")

    record: dict[str, object] = Field(
        ...,
        description="Provider row as a typed JSON-compatible object map.",
    )


class VerifiedPublicDataOutput(BaseModel):
    """Envelope-ready collection output returned by verified adapters."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["collection"] = "collection"
    items: list[VerifiedPublicDataItem]
    total_count: int = Field(ge=0)


class VerifiedAdapterSpec(BaseModel):
    """Static manifest entry for one direct-curl verified API."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: str
    tool_id: str
    module_name: str
    name_ko: str
    ministry: Ministry
    category: list[str]
    endpoint: str = Field(pattern=r"^https://")
    env_var: str
    auth_query_param: str
    response_format: ResponseFormat
    query_param_map: dict[str, str]
    static_query_params: dict[str, str] = Field(default_factory=dict)
    record_tag: str | None = None
    evidence_path: str
    policy_url: str
    policy_text: str
    last_verified: datetime
    search_hint: str
    llm_description: str
    trigger_examples: list[str] = Field(default_factory=list)
    primitive: Literal["find"] = "find"
    adapter_mode: Literal["live"] = "live"
    citizen_facing_gate: Literal["read-only"] = "read-only"
