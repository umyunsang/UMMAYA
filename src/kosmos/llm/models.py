# SPDX-License-Identifier: Apache-2.0
"""Pydantic v2 message and response models for the KOSMOS LLM client."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class FunctionCall(BaseModel):
    """Function name and serialized arguments requested by the model."""

    model_config = ConfigDict(frozen=True)

    name: str
    arguments: str  # JSON-serialized string


class ToolCall(BaseModel):
    """Tool invocation requested by the model."""

    model_config = ConfigDict(frozen=True)

    id: str
    type: Literal["function"] = "function"
    function: FunctionCall


class ChatMessage(BaseModel):
    """A single message in a conversation, following the OpenAI chat format."""

    model_config = ConfigDict(frozen=True)

    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    name: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None

    @model_validator(mode="after")
    def _validate_role_constraints(self) -> ChatMessage:
        """Enforce role-specific field requirements."""
        if self.role == "tool" and self.tool_call_id is None:
            raise ValueError("ChatMessage with role='tool' must provide tool_call_id")
        if self.role in ("system", "user") and self.content is None:
            raise ValueError(f"ChatMessage with role='{self.role}' must provide content")
        if self.tool_calls is not None and self.role != "assistant":
            raise ValueError("tool_calls is only valid on role='assistant' messages")
        if self.tool_call_id is not None and self.role != "tool":
            raise ValueError("tool_call_id is only valid on role='tool' messages")
        return self


class TokenUsage(BaseModel):
    """Token counts reported by a single LLM call."""

    model_config = ConfigDict(frozen=True)

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_tokens(self) -> int:
        """Sum of input and output tokens."""
        return self.input_tokens + self.output_tokens


class ChatCompletionResponse(BaseModel):
    """Complete response from a non-streaming LLM call."""

    model_config = ConfigDict(frozen=True)

    id: str
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: TokenUsage
    model: str
    finish_reason: Literal["stop", "tool_calls", "length"]


class StreamEvent(BaseModel):
    """A single event emitted during a streaming LLM response.

    Mirrors the Anthropic Messages API streaming event shape used by the
    Claude Code reference (``_cc_reference/claude.ts:1979-2304``). KOSMOS
    flattens the nested ``content_block_start/delta/stop`` envelope into a
    single discriminated event because the OpenAI-compatible FriendliAI SSE
    feed never opens or closes a content block — every chunk is a delta on
    an implicit single-block message. The event types map 1:1 to the deltas
    CC's reducer cares about:

    * ``content_delta`` ↔ Anthropic ``text_delta``
    * ``thinking_delta`` ↔ Anthropic ``thinking_delta``  — K-EXAONE emits
      this on the ``delta.reasoning_content`` channel; CC mirrors it on its
      ``thinking`` content block. Forwarding (rather than dropping) lets the
      TUI render the reasoning in ``AssistantThinkingMessage`` so users see
      *why* the model answered the way it did.
    * ``tool_call_delta`` ↔ Anthropic ``input_json_delta`` (function call
      streaming)
    * ``usage``           ↔ Anthropic ``message_delta.usage``
    * ``done``            ↔ Anthropic ``message_stop``
    """

    model_config = ConfigDict(frozen=True)

    type: Literal[
        "content_delta",
        "thinking_delta",
        "tool_call_delta",
        "usage",
        "done",
        "error",
    ]
    content: str | None = None
    # Mirror of Anthropic's ``BetaThinkingDelta.thinking`` (claude.ts:2148)
    # populated when the provider emits ``delta.reasoning_content``.
    thinking: str | None = None
    tool_call_index: int | None = None
    tool_call_id: str | None = None
    function_name: str | None = None
    function_args_delta: str | None = None
    usage: TokenUsage | None = None


class FunctionSchema(BaseModel):
    """Schema definition for a function/tool."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    # dict[str, Any] is acceptable here: this field holds an external JSON Schema
    # object whose structure is defined by the OpenAI/FriendliAI spec, not by KOSMOS
    # internal I/O contracts. Using Any is the only correct representation.
    parameters: dict[str, Any]
    strict: bool | None = None

    # Epic #2152 R6 — KOSMOS-internal metadata carrying the per-tool trigger
    # phrase that ``build_system_prompt_with_tools`` emits inside the
    # ``## Available tools`` block. ``exclude=True`` keeps the field out of
    # the OpenAI/FriendliAI tool-definition payload (the upstream API rejects
    # unknown fields), while leaving it visible to in-process consumers.
    trigger_phrase: str | None = Field(default=None, exclude=True)


class ToolDefinition(BaseModel):
    """Tool schema sent to the model for function calling."""

    model_config = ConfigDict(frozen=True)

    type: Literal["function"] = "function"
    function: FunctionSchema
