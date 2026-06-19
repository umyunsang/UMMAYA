# SPDX-License-Identifier: Apache-2.0
"""Tool-layer Evidence Fabric event models."""

from __future__ import annotations

from typing import Literal, Self, assert_never

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

ToolLayerExposureState = Literal[
    "always-loaded",
    "deferred-searchable",
    "permission-gated-callable",
    "hidden",
    "unsupported",
]
ToolLayerTrustTier = Literal[0, 1, 2, 3, 4, 5]
ToolLayerPermissionDecision = Literal[
    "not_required",
    "approved",
    "denied",
    "blocked_pending_approval",
    "policy_preapproved",
]
ToolLayerResultStatus = Literal["succeeded", "failed", "blocked"]
ToolLayerBlockedState = Literal[
    "not_blocked",
    "blocked_by_permission",
    "blocked_by_policy",
    "blocked_by_missing_source",
    "blocked_by_unsupported",
]
ToolLayerRenderFrame = Literal[
    "permission_prompt",
    "tool_call",
    "tool_result",
    "blocked_state",
]
ToolLayerPromptInjectionState = Literal["detected", "not_detected"]
ToolLayerSourceTrust = Literal["trusted", "untrusted"]
ToolLayerSourceInstructionVisibility = Literal["evidence_only"]


def _validation_error(code: str, message: str) -> PydanticCustomError:
    return PydanticCustomError(code, message)


class ToolLayerEvidenceEvent(BaseModel):
    """One recovered Claude Code support-tool exposure and provenance event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    frame_hash: str = Field(min_length=64, max_length=64)
    render_frame: ToolLayerRenderFrame
    selected_tool: str = Field(min_length=1)
    exposure_state: ToolLayerExposureState
    trust_tier: ToolLayerTrustTier
    permission_decision: ToolLayerPermissionDecision
    source_url: str | None
    source_local_handle: str | None
    source_citation_id: str = Field(min_length=1)
    provenance_id: str = Field(min_length=1)
    source_trust: ToolLayerSourceTrust
    source_prompt_injection: ToolLayerPromptInjectionState
    source_instruction_visibility: ToolLayerSourceInstructionVisibility = "evidence_only"
    result_status: ToolLayerResultStatus
    result_summary: str | None
    error_summary: str | None
    blocked_state: ToolLayerBlockedState

    @field_validator("frame_hash")
    @classmethod
    def _validate_frame_hash(cls, value: str) -> str:
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise _validation_error(
                "tool_layer_frame_hash", "frame_hash must be lowercase SHA-256 hex"
            )
        return value

    @field_validator("source_url", "source_local_handle", "source_citation_id", "provenance_id")
    @classmethod
    def _reject_model_visible_leakage_keys(cls, value: str | None) -> str | None:
        if value is not None and ("adapter_id" in value or "expected_tool" in value):
            raise _validation_error(
                "tool_layer_model_visible_leakage",
                "tool-layer evidence cannot carry model-visible leakage keys",
            )
        return value

    @field_validator("result_summary", "error_summary")
    @classmethod
    def _reject_empty_summary(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise _validation_error(
                "tool_layer_blank_summary", "tool-layer summaries cannot be blank"
            )
        return value

    @model_validator(mode="after")
    def _requires_source_reference(self) -> Self:
        if self.source_url is None and self.source_local_handle is None:
            raise _validation_error(
                "tool_layer_missing_source",
                "tool-layer evidence requires source_url or source_local_handle",
            )
        return self

    @model_validator(mode="after")
    def _requires_status_payload(self) -> Self:
        match self.result_status:
            case "succeeded":
                if self.result_summary is None:
                    raise _validation_error(
                        "tool_layer_missing_result_summary",
                        "succeeded tool-layer event requires result_summary",
                    )
                if self.error_summary is not None:
                    raise _validation_error(
                        "tool_layer_unexpected_error_summary",
                        "succeeded tool-layer event cannot carry error_summary",
                    )
                if self.blocked_state != "not_blocked":
                    raise _validation_error(
                        "tool_layer_unexpected_blocked_state",
                        "succeeded tool-layer event must not be blocked",
                    )
            case "failed":
                if self.error_summary is None:
                    raise _validation_error(
                        "tool_layer_failed_without_error",
                        "failed tool-layer event requires error_summary",
                    )
            case "blocked":
                if self.error_summary is None:
                    raise _validation_error(
                        "tool_layer_blocked_without_error",
                        "blocked tool-layer event requires error_summary",
                    )
                if self.blocked_state == "not_blocked":
                    raise _validation_error(
                        "tool_layer_blocked_without_state",
                        "blocked tool-layer event requires a blocked_state",
                    )
            case unreachable:
                assert_never(unreachable)
        return self
