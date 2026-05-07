# SPDX-License-Identifier: Apache-2.0
"""Shadow-eval fixture schema for Epic η #2298 citizen chain teaching.

Each fixture file is a single JSON object loaded by
tests/integration/test_shadow_eval_citizen_chain_fixtures.py and consumed by
.github/workflows/shadow-eval.yml twin-run runner.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExpectedToolCall(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Literal["verify", "lookup", "submit", "resolve_location"]
    arguments: dict[str, str | list[str]] = Field(default_factory=dict)


class CitizenChainFixture(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    fixture_id: str = Field(pattern=r"^[a-z0-9_]+$", min_length=3, max_length=64)
    citizen_prompt: str = Field(min_length=1, max_length=200)
    expected_first_tool_call: ExpectedToolCall
    expected_family_hint: str | None = None
    notes: str | None = None
