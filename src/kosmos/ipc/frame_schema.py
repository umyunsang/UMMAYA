# SPDX-License-Identifier: Apache-2.0
"""IPC frame schema — Pydantic v2 discriminated union.

Source of truth for the KOSMOS TUI <-> Python backend NDJSON protocol.
Every change here MUST be reflected in the TypeScript generated types by
running ``bun run gen:ipc`` from ``tui/``.

Protocol version: 1.0  (matches ``version`` field on every frame)

Spec 032 extensions
-------------------
- ``_BaseFrame`` extended with 5 new envelope fields:
  ``version``, ``role``, ``frame_seq``, ``transaction_id``, ``trailer``.
- ``FrameTrailer`` sub-model (final, transaction_id, checksum_sha256).
- 9 new frame arms added (Spec 032 §2):
  ``PayloadStartFrame``, ``PayloadDeltaFrame``, ``PayloadEndFrame``,
  ``BackpressureSignalFrame``, ``ResumeRequestFrame``, ``ResumeResponseFrame``,
  ``ResumeRejectedFrame``, ``HeartbeatFrame``, ``NotificationPushFrame``.
- Cross-field invariants E1-E6 enforced via ``@model_validator(mode="after")``.
- ``IPCFrame`` discriminated union updated to 19 kinds.

Epic ε #2296 extension
----------------------
- ``AdapterManifestEntry`` sub-model (per-adapter registry entry).
- ``AdapterManifestSyncFrame``: 21st arm of the ``IPCFrame`` discriminated union.
  Backend emits exactly once after ``register_all_tools()`` completes.
  Invariants I1-I7 enforced at construction.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, field_validator, model_validator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Envelope version constant
# ---------------------------------------------------------------------------

ENVELOPE_VERSION: Literal["1.0"] = "1.0"

# ---------------------------------------------------------------------------
# role <-> kind allow-list (invariant E3)
# ---------------------------------------------------------------------------

# Maps each frame kind to the set of roles allowed to emit it.
_ROLE_KIND_ALLOW_LIST: dict[str, frozenset[str]] = {
    # Spec 287 baseline arms
    "user_input": frozenset({"tui"}),
    # Spec 1978 ADR-0001 — tools-aware chat request from TUI
    "chat_request": frozenset({"tui"}),
    "assistant_chunk": frozenset({"backend", "llm"}),
    "tool_call": frozenset({"backend", "tool"}),
    "tool_result": frozenset({"backend", "tool"}),
    "coordinator_phase": frozenset({"backend"}),
    "worker_status": frozenset({"backend"}),
    "permission_request": frozenset({"backend"}),
    # Gap A fix: backend echoes permission_response back to TUI with
    # receipt_id attached (role="backend"). The TUI origin (role="tui")
    # is preserved for the citizen-decision direction. Both directions are
    # valid; consumers discriminate on ``role`` to distinguish the echo.
    "permission_response": frozenset({"tui", "backend"}),
    "session_event": frozenset({"tui", "backend"}),
    "error": frozenset({"backend", "tui"}),
    # Spec 032 new arms
    "payload_start": frozenset({"backend", "tool", "llm"}),
    "payload_delta": frozenset({"backend", "tool", "llm"}),
    "payload_end": frozenset({"backend", "tool", "llm"}),
    "backpressure": frozenset({"tui", "backend"}),
    "resume_request": frozenset({"tui"}),
    "resume_response": frozenset({"backend"}),
    "resume_rejected": frozenset({"backend"}),
    "heartbeat": frozenset({"tui", "backend"}),
    "notification_push": frozenset({"notification"}),
    # Epic #1636 P5 — plugin install/uninstall/list control plane
    "plugin_op": frozenset({"tui", "backend"}),
    # Epic ε #2296 — adapter manifest sync from backend on boot
    "adapter_manifest_sync": frozenset({"backend"}),
    # Epic 2 — consent revoke IPC round-trip (arms 22-23)
    # arm 22: TUI initiates revoke
    "consent_revoke_request": frozenset({"tui"}),
    # arm 23: backend responds with revoke outcome
    "consent_revoke_response": frozenset({"backend"}),
}

# Kinds on which trailer.final=true is permitted (invariant E6).
_TERMINAL_KINDS: frozenset[str] = frozenset(
    {
        "payload_end",
        "tool_result",
        "resume_response",
        "resume_rejected",
        "error",
        # plugin_op carries op="complete" which terminates a plugin install
        # control flow; trailer.final=True is permitted on those frames.
        "plugin_op",
    }
)

# ---------------------------------------------------------------------------
# FrameTrailer sub-model
# ---------------------------------------------------------------------------


class FrameTrailer(BaseModel):
    """Completion/validation metadata on terminal frames (FR-006)."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    final: bool = Field(description="True when this frame terminates a logical payload/stream.")
    transaction_id: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Mirror of envelope transaction_id for trailer-only consumers. "
            "Non-empty when present (parity with codec.ts trailer schema — Spec 2642 § US3)."
        ),
    )
    checksum_sha256: str | None = Field(
        default=None,
        description="Hex SHA-256 of the concatenated payload bytes for streamed payloads.",
    )


# ---------------------------------------------------------------------------
# Base frame — shared envelope fields
# ---------------------------------------------------------------------------


class _BaseFrame(BaseModel):
    """Shared envelope fields present on every IPC frame.

    Invariants enforced at construction (model_validator mode='after'):
    - E1: version == "1.0"
    - E3: role allowed for this kind
    - E4: transaction_id required for irreversible terminal kinds
    - E5: correlation_id non-empty
    - E6: trailer.final=True only on terminal kinds
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    # --- Spec 287 original fields (unchanged) ---
    # Note: session_id may be "" before the TUI has received a backend-assigned
    # session — slash-command builders (/new, /save, /sessions, /resume) and
    # the initial user_input emit empty session_id and rely on the bridge to
    # stamp the real id once handshake completes. E1-E6 do not constrain it.
    session_id: str = Field(description="Opaque session identifier.")
    correlation_id: str = Field(
        min_length=1,
        description=(
            "UUIDv7 string for new emissions; ULID accepted for back-compat. "
            "Non-empty; emitter SHOULD use UUIDv7. (E5)"
        ),
    )
    ts: str = Field(description="ISO-8601 UTC timestamp with sub-ms precision.")

    # --- Spec 032 new envelope fields ---
    version: Literal["1.0"] = Field(
        default="1.0",
        description="Envelope version. Hard-fail on mismatch (E1, FR-001).",
    )
    role: Literal["tui", "backend", "tool", "llm", "notification"] = Field(
        description="Origin role. Validated against kind<->role allow-list (E3, FR-004).",
    )
    frame_seq: NonNegativeInt = Field(
        default=0,
        description="Per-session monotonic sequence number (ge=0). Gap detection uses this.",
    )
    transaction_id: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "UUIDv7. Populated for idempotent state-change frames (irreversible tools). "
            "None for streaming chunks. (FR-026) Non-empty when present (parity with "
            "codec.ts ``z.string().min(1).nullable().optional()`` — Spec 2642 § US3)."
        ),
    )
    trailer: FrameTrailer | None = Field(
        default=None,
        description="Completion/validation metadata. Populated on terminal frames. (FR-006)",
    )

    @model_validator(mode="after")
    def _enforce_invariants(self) -> _BaseFrame:
        """Enforce cross-field invariants E1, E3, E5, E6.

        Note: E1 (version) is already handled by Literal["1.0"] type.
        Note: E5 (correlation_id min_length=1) is handled by Field(min_length=1).
        """
        kind: str = getattr(self, "kind", "")

        # E3: role <-> kind allow-list
        if kind and kind in _ROLE_KIND_ALLOW_LIST:
            allowed_roles = _ROLE_KIND_ALLOW_LIST[kind]
            if self.role not in allowed_roles:
                raise ValueError(
                    f"role={self.role!r} is not allowed for kind={kind!r}. "
                    f"Allowed roles: {sorted(allowed_roles)}"
                )

        # E6: trailer.final=True only on terminal-capable kinds
        if self.trailer is not None and self.trailer.final and kind not in _TERMINAL_KINDS:
            raise ValueError(
                f"trailer.final=True is not allowed for kind={kind!r}. "
                f"Terminal-capable kinds: {sorted(_TERMINAL_KINDS)}"
            )

        return self


# ---------------------------------------------------------------------------
# Arm: user_input  (Spec 287 baseline — unchanged)
# ---------------------------------------------------------------------------


class UserInputFrame(_BaseFrame):
    """TUI -> backend: a citizen's typed input."""

    kind: Literal["user_input"] = Field(default="user_input", description="Frame discriminator.")
    text: str = Field(description="Raw user text in UTF-8 (may contain Korean, English, emoji).")


# ---------------------------------------------------------------------------
# Arm: chat_request  (Spec 1978 ADR-0001 — TUI tools-aware chat request)
# ---------------------------------------------------------------------------


class ChatMessageFunctionCall(BaseModel):
    """OpenAI-spec ``function`` block carried inside ``ChatMessageToolCall``.

    Mirrors ``kosmos.llm.models.FunctionCall`` (the LLM-client-internal model)
    but lives on the *wire* so the TUI can transmit assistant ``tool_use``
    blocks across multi-turn boundaries (Lead-Diag-4, role='tool' wire fix).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    name: str = Field(description="Function/tool name the model requested.")
    arguments: str = Field(
        description="JSON-serialised string of the function arguments (OpenAI spec)."
    )


class ChatMessageToolCall(BaseModel):
    """OpenAI-spec ``tool_calls[i]`` entry carried by an assistant ``ChatMessage``.

    OpenAI Chat Completions API spec: every ``role='tool'`` message MUST be
    paired (by ``tool_call_id``) with a ``tool_calls[i].id`` from a preceding
    assistant turn. The TUI carries this pairing across the wire so multi-turn
    conversations replay correctly to FriendliAI / OpenAI-compatible providers
    (Lead-Diag-4 fix, 2026-05-04).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    id: str = Field(
        description="Matching ``ToolCallFrame.call_id`` / ``role='tool'.tool_call_id``."
    )
    type: Literal["function"] = Field(
        default="function",
        description="OpenAI tool envelope; only 'function' is currently supported.",
    )
    function: ChatMessageFunctionCall = Field(
        description="Inner function name + JSON-serialised arguments."
    )


class ChatMessage(BaseModel):
    """One conversation-history entry carried by ``ChatRequestFrame.messages``.

    ``role="tool"`` messages MUST also set ``name`` (the tool name that was
    invoked) and ``tool_call_id`` (the originating ``tool_call`` envelope's
    correlation id). This is the data-model invariant D4 (tool message
    integrity) enforced by the ``ChatRequestFrame`` validator below.

    Lead-Diag-4 (2026-05-04): added optional ``tool_calls`` for ``role='assistant'``
    turns so assistant ``tool_use`` blocks survive the wire round-trip and the
    OpenAI Chat Completions multi-turn pairing invariant (every ``role='tool'``
    message MUST follow an assistant message whose ``tool_calls[i].id`` matches
    the result's ``tool_call_id``) is satisfied. Backward compatible: legacy
    senders that omit ``tool_calls`` are unaffected.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    role: Literal["system", "user", "assistant", "tool"] = Field(
        description="Conversation turn author."
    )
    content: str = Field(description="UTF-8 message body.")
    name: str | None = Field(
        default=None,
        description="Tool name when role='tool'; None otherwise.",
    )
    tool_call_id: str | None = Field(
        default=None,
        description="Matching ``ToolCallFrame.call_id`` when role='tool'; None otherwise.",
    )
    tool_calls: list[ChatMessageToolCall] | None = Field(
        default=None,
        description=(
            "OpenAI Chat Completions assistant-turn tool invocations. Set ONLY on "
            "role='assistant' messages that requested one or more tool calls. None "
            "for every other role. Each entry's ``id`` is the pairing key that the "
            "corresponding role='tool' result message MUST set as its ``tool_call_id``."
        ),
    )


class ToolDefinitionFunction(BaseModel):
    """Inner ``function`` block of an OpenAI-style tool definition."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    name: str = Field(description="Tool name (matches the primitive registry id).")
    description: str | None = Field(
        default=None,
        description="Human-readable description shown to the model for tool selection.",
    )
    parameters: dict[str, object] = Field(
        default_factory=dict,
        description=(
            "JSON Schema (Draft 2020-12) for the tool input. Pydantic accepts any "
            "dict shape; deeper schema validation is delegated to LLMClient."
        ),
    )


class ToolDefinition(BaseModel):
    """OpenAI-style tool definition (function-calling)."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    type: Literal["function"] = Field(
        default="function",
        description="OpenAI tool envelope; only 'function' is currently supported.",
    )
    function: ToolDefinitionFunction = Field(description="Inner function metadata.")


class ChatRequestFrame(_BaseFrame):
    """TUI -> backend: tools-aware chat request (Spec 1978 ADR-0001).

    Coexists with ``UserInputFrame`` (which remains the echo / smoke-test path).
    The backend treats a ``UserInputFrame{text=t}`` as
    ``ChatRequestFrame{messages=[{role:'user', content:t}], tools=[]}``.
    """

    kind: Literal["chat_request"] = Field(
        default="chat_request", description="Frame discriminator."
    )
    messages: list[ChatMessage] = Field(
        min_length=1,
        description="Conversation history; tail message has role 'user' or 'tool'.",
    )
    tools: list[ToolDefinition] = Field(
        default_factory=list,
        description="Tools available to the model this turn.",
    )
    system: str | None = Field(
        default=None,
        description="Effective system prompt (may be None if backend supplies its own).",
    )
    max_tokens: int = Field(
        default=8192,
        ge=1,
        le=32000,
        description="Maximum tokens for the assistant turn.",
    )
    temperature: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature.",
    )
    top_p: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling threshold.",
    )

    @model_validator(mode="after")
    def _v_tool_message_integrity(self) -> ChatRequestFrame:
        """Invariant D4: tool messages require both name and tool_call_id.

        Lead-Diag-4 extension: ``tool_calls`` is only valid on role='assistant'
        messages (OpenAI Chat Completions spec). Every ``role='tool'`` message's
        ``tool_call_id`` MUST match an ``id`` from a preceding assistant
        ``tool_calls`` entry — pairing is positional/by-id, not by adjacency,
        because parallel tool calls are allowed.
        """
        for i, msg in enumerate(self.messages):
            if msg.role == "tool":
                if not msg.name:
                    raise ValueError(f"messages[{i}]: role='tool' requires non-empty 'name'")
                if not msg.tool_call_id:
                    raise ValueError(
                        f"messages[{i}]: role='tool' requires non-empty 'tool_call_id'"
                    )
            if msg.tool_calls is not None and msg.role != "assistant":
                raise ValueError(
                    f"messages[{i}]: tool_calls is only valid on role='assistant' "
                    f"(got role='{msg.role}')"
                )
        return self


# ---------------------------------------------------------------------------
# Arm: assistant_chunk  (Spec 287 baseline — unchanged)
# ---------------------------------------------------------------------------


class AssistantChunkFrame(_BaseFrame):
    """backend -> TUI: streaming assistant text delta.

    Mirrors Anthropic's ``content_block_delta`` (CC reference at
    ``kosmos/llm/_cc_reference/claude.ts:2053-2169``). The ``delta`` field
    carries the visible answer text (``text_delta`` in CC nomenclature);
    ``thinking`` carries the model's chain-of-thought (``thinking_delta``
    on the Anthropic side, K-EXAONE's ``delta.reasoning_content`` on the
    OpenAI-compatible FriendliAI feed). Exactly one of ``delta`` /
    ``thinking`` carries content per frame — the empty one is the
    backward-compatible default. ``done`` terminates the message
    regardless of channel.
    """

    kind: Literal["assistant_chunk"] = Field(
        default="assistant_chunk", description="Frame discriminator."
    )
    message_id: str = Field(description="ULID of the assistant message this delta belongs to.")
    delta: str = Field(
        default="",
        description="UTF-8 text appended to the visible answer (text_delta channel).",
    )
    thinking: str = Field(
        default="",
        description=(
            "UTF-8 text appended to the model's chain-of-thought "
            "(thinking_delta channel — K-EXAONE delta.reasoning_content)."
        ),
    )
    done: bool = Field(description="True if this is the terminal chunk for this message_id.")


# ---------------------------------------------------------------------------
# Arm: tool_call  (Spec 287 baseline — arguments changed from Any to dict[str, object])
# ---------------------------------------------------------------------------


class ToolCallFrame(_BaseFrame):
    """backend -> TUI (display only): a tool invocation decision by the model."""

    kind: Literal["tool_call"] = Field(default="tool_call", description="Frame discriminator.")
    call_id: str = Field(description="ULID correlating this call to its subsequent tool_result.")
    name: Literal["lookup", "resolve_location", "submit", "subscribe", "verify"] = Field(
        description="Primitive name per Spec 031."
    )
    arguments: dict[str, object] = Field(
        description="Primitive-specific arguments; shape per Spec 031 input schemas."
    )


# ---------------------------------------------------------------------------
# Arm: tool_result  (Spec 287 baseline)
# ---------------------------------------------------------------------------


class ToolResultEnvelope(BaseModel):
    """5-primitive discriminated union envelope (open schema)."""

    model_config = ConfigDict(frozen=True, extra="allow", populate_by_name=True)

    kind: Literal["lookup", "resolve_location", "submit", "subscribe", "verify"] = Field(
        description="Primitive kind discriminator per Spec 031."
    )


class ToolResultFrame(_BaseFrame):
    """backend -> TUI (render): the output of a tool invocation."""

    kind: Literal["tool_result"] = Field(default="tool_result", description="Frame discriminator.")
    call_id: str = Field(description="ULID correlating this result to its originating tool_call.")
    envelope: ToolResultEnvelope = Field(
        description="5-primitive discriminated union. Unknown kind falls to UnrecognizedPayload."
    )


# ---------------------------------------------------------------------------
# Arm: coordinator_phase  (Spec 287 baseline — unchanged)
# ---------------------------------------------------------------------------


class CoordinatorPhaseFrame(_BaseFrame):
    """backend -> TUI: Spec 027 coordinator phase update."""

    kind: Literal["coordinator_phase"] = Field(
        default="coordinator_phase", description="Frame discriminator."
    )
    phase: Literal["Research", "Synthesis", "Implementation", "Verification"] = Field(
        description="Current coordinator phase."
    )


# ---------------------------------------------------------------------------
# Arm: worker_status  (Spec 287 baseline — unchanged)
# ---------------------------------------------------------------------------


class WorkerStatusFrame(_BaseFrame):
    """backend -> TUI: per-worker status row update from Spec 027 swarm."""

    kind: Literal["worker_status"] = Field(
        default="worker_status", description="Frame discriminator."
    )
    worker_id: str = Field(description="Unique worker identifier.")
    role_id: str = Field(
        description="Specialist label (e.g., transport-specialist, health-specialist)."
    )
    current_primitive: Literal["lookup", "resolve_location", "submit", "subscribe", "verify"] = (
        Field(description="Primitive currently being invoked by this worker.")
    )
    status: Literal["idle", "running", "waiting_permission", "error"] = Field(
        description="Worker execution status."
    )


# ---------------------------------------------------------------------------
# Arm: permission_request  (Spec 287 baseline — unchanged)
# ---------------------------------------------------------------------------


class PermissionRequestFrame(_BaseFrame):
    """backend -> TUI: a worker raises a permission request."""

    kind: Literal["permission_request"] = Field(
        default="permission_request", description="Frame discriminator."
    )
    request_id: str = Field(
        description="ULID; round-trips in the matching permission_response frame."
    )
    worker_id: str = Field(description="Worker requesting permission.")
    primitive_kind: Literal["lookup", "resolve_location", "submit", "subscribe", "verify"] = Field(
        description="The primitive the worker wants to invoke."
    )
    description_ko: str = Field(description="Korean-language description shown to the citizen.")
    description_en: str = Field(
        description="English-language description shown alongside the Korean one."
    )
    risk_level: Literal["low", "medium", "high"] = Field(
        description="Risk classification of the requested operation."
    )
    # Audit-4 P0-10 fix — the fully-qualified adapter id the citizen sees in
    # the modal title and `/consent list` row. Optional for backward-compat:
    # legacy callers that only set `worker_id="main"` continue to work; the
    # TUI falls back to `worker_id || primitive_kind` when this is null. New
    # call sites (stdio.py:_check_permission_gate) MUST populate this with
    # `args_obj.get("tool_id", fname)` so the modal title becomes
    # `"mock_verify_mobile_id" 도구가 신원 확인을 …` rather than `"main" …`.
    tool_id: str | None = Field(
        default=None,
        description=(
            "Fully-qualified adapter id (e.g. `mock_verify_mobile_id`). Falls "
            "back to worker_id || primitive_kind in the TUI when None. None for "
            "legacy callers that have not yet been updated."
        ),
    )


# ---------------------------------------------------------------------------
# Arm: permission_response  (Spec 287 baseline — unchanged)
# ---------------------------------------------------------------------------


class PermissionResponseFrame(_BaseFrame):
    """TUI -> backend: citizen's decision on a permission_request."""

    kind: Literal["permission_response"] = Field(
        default="permission_response", description="Frame discriminator."
    )
    request_id: str = Field(
        description="ULID matching the originating permission_request.request_id."
    )
    # Spec 1978 ADR-0002 + Spec 033 — extends the Spec 287 baseline binary
    # vocabulary (granted | denied) with the 3-decision UI gauntlet
    # (allow_once | allow_session | deny). Backend treats granted == allow_once
    # for backward compatibility; allow_session activates the per-session
    # tool_id grant cache in stdio.py._check_permission_gate.
    decision: Literal[
        "granted",
        "allow_once",
        "allow_session",
        "denied",
        "deny",
    ] = Field(description="Citizen's permission decision.")
    # Gap A fix — backend attaches the consent receipt_id to the echo-back
    # so the TUI addReceipt() callsite can record it without a second round-
    # trip. ``None`` on deny / timeout paths (no receipt written). Backward-
    # compatible: TUI parsers that don't yet read this field ignore it safely.
    receipt_id: str | None = Field(
        default=None,
        description=(
            "Consent receipt UUID written to ~/.kosmos/memdir/user/consent/<id>.json "
            "on granted decisions. None on deny / timeout."
        ),
    )
    # Audit-4 P0-6 / P0-7 / P0-10 fix — the backend echo MUST carry enough
    # context for the TUI to render a meaningful receipt row. Without these
    # fields the TUI's usePermissionReceiptWatcher hardcoded
    # `layer: 1, tool_name: 'unknown'` (UI-C-1 spec violation: Layer 2/3
    # submits / subscribes were colour-coded green like a Layer 1 verify).
    # Both fields are optional so legacy backends remain wire-compatible.
    primitive_kind: (
        Literal["lookup", "resolve_location", "submit", "subscribe", "verify"] | None
    ) = Field(
        default=None,
        description=(
            "The primitive that was authorised. The TUI feeds this into "
            "`aalToLayer(primitive, isIrreversible)` to recompute the gauntlet "
            "layer (1=green / 2=orange / 3=red) for the receipt row. None on "
            "deny / timeout / legacy backends."
        ),
    )
    tool_id: str | None = Field(
        default=None,
        description=(
            "The fully-qualified adapter id (e.g. `mock_verify_mobile_id`, "
            "`mock_submit_welfare_grant`) the citizen authorised. The TUI uses "
            "this to render the human-readable Korean adapter name in "
            "/consent list and the modal title. None for non-adapter primitives "
            "(rare) or legacy backends."
        ),
    )


# ---------------------------------------------------------------------------
# Arm: session_event  (Spec 287 baseline — payload changed from Any to dict[str, object])
# ---------------------------------------------------------------------------


class SessionEventFrame(_BaseFrame):
    """Bidirectional: session lifecycle events."""

    kind: Literal["session_event"] = Field(
        default="session_event", description="Frame discriminator."
    )
    event: Literal["save", "load", "list", "resume", "new", "exit"] = Field(
        description="Session lifecycle event type."
    )
    payload: dict[str, object] = Field(
        description=(
            "Event-specific payload. "
            "For list: {sessions: [{id, created_at, turn_count}]}. "
            "For resume: {id: str}. For others: {}."
        )
    )


# ---------------------------------------------------------------------------
# Arm: error  (Spec 287 baseline — details changed from Any to dict[str, object])
# ---------------------------------------------------------------------------


class ErrorFrame(_BaseFrame):
    """backend -> TUI: a backend error surfaced to the TUI for rendering."""

    kind: Literal["error"] = Field(default="error", description="Frame discriminator.")
    code: str = Field(
        description="Machine-readable error code (e.g., 'backend_crash', 'protocol_mismatch')."
    )
    message: str = Field(
        description=(
            "Human-readable short message. "
            "MUST NOT contain KOSMOS_*-prefixed env var values (FR-004 redaction rule)."
        )
    )
    details: dict[str, object] = Field(
        description="Structured error details. KOSMOS_* env var values MUST be redacted."
    )


# ===========================================================================
# Spec 032 NEW ARMS (T005-T009)
# ===========================================================================

# ---------------------------------------------------------------------------
# Arm: payload_start  (Spec 032 §2.1)
# ---------------------------------------------------------------------------


class PayloadStartFrame(_BaseFrame):
    """Begins a streamed payload (assistant output, tool result chunking).

    Sender MUST follow with >= 1 payload_delta and exactly one payload_end.
    role allow-list: backend, tool, llm.
    """

    kind: Literal["payload_start"] = Field(
        default="payload_start", description="Frame discriminator."
    )
    content_type: Literal["text/markdown", "application/json", "text/plain"] = Field(
        description="Payload MIME type."
    )
    estimated_bytes: NonNegativeInt | None = Field(
        default=None,
        description="Optional size hint for HUD progress bars.",
    )


# ---------------------------------------------------------------------------
# Arm: payload_delta  (Spec 032 §2.2)
# ---------------------------------------------------------------------------


class PayloadDeltaFrame(_BaseFrame):
    """One chunk of a streamed payload.

    role allow-list: backend, tool, llm.
    """

    kind: Literal["payload_delta"] = Field(
        default="payload_delta", description="Frame discriminator."
    )
    delta_seq: NonNegativeInt = Field(description="Monotonic within the payload (first delta = 0).")
    payload: str = Field(
        description=(
            "UTF-8 text. If content-type is application/json, "
            "this is a JSON-encoded fragment string."
        )
    )


# ---------------------------------------------------------------------------
# Arm: payload_end  (Spec 032 §2.3)
# ---------------------------------------------------------------------------


class PayloadEndFrame(_BaseFrame):
    """Terminates a streamed payload.

    MUST carry a trailer with final=True.
    role allow-list: backend, tool, llm.
    """

    kind: Literal["payload_end"] = Field(default="payload_end", description="Frame discriminator.")
    delta_count: NonNegativeInt = Field(description="Total number of payload_delta frames emitted.")
    status: Literal["ok", "aborted"] = Field(description="Terminal disposition.")


# ---------------------------------------------------------------------------
# Arm: backpressure  (Spec 032 §2.4)
# ---------------------------------------------------------------------------


class BackpressureSignalFrame(_BaseFrame):
    """Emitted when outgoing queue crosses HWM or a 429 condition is detected.

    role allow-list: tui (tui_reader), backend (backend_writer, upstream_429).
    FR-012, FR-015: hud_copy_ko/en MUST be non-empty (min_length=1).
    """

    kind: Literal["backpressure"] = Field(
        default="backpressure", description="Frame discriminator."
    )
    signal: Literal["pause", "resume", "throttle"] = Field(
        description="Reader action. pause=stop emitting; resume=clear; throttle=slow down."
    )
    source: Literal["tui_reader", "backend_writer", "upstream_429"] = Field(
        description="Origin of the signal."
    )
    queue_depth: NonNegativeInt = Field(description="Current outbound queue size.")
    hwm: int = Field(ge=1, description="High-water mark threshold in effect (default 64).")
    retry_after_ms: NonNegativeInt | None = Field(
        default=None,
        description="For throttle sourced from upstream_429; reflects Retry-After. ge=0.",
    )
    hud_copy_ko: str = Field(
        min_length=1,
        description="Korean HUD copy (civic-facing). Must be non-empty (FR-015).",
    )
    hud_copy_en: str = Field(
        min_length=1,
        description="English HUD copy (dev-facing). Must be non-empty (FR-015).",
    )


# ---------------------------------------------------------------------------
# Arm: resume_request  (Spec 032 §2.5)
# ---------------------------------------------------------------------------


class ResumeRequestFrame(_BaseFrame):
    """Sent by the reconnecting TUI after a stdio drop.

    role allow-list: tui.
    """

    kind: Literal["resume_request"] = Field(
        default="resume_request", description="Frame discriminator."
    )
    last_seen_correlation_id: str | None = Field(
        default=None,
        description="Last correlation_id the TUI successfully applied. None if no prior frame.",
    )
    last_seen_frame_seq: NonNegativeInt | None = Field(
        default=None,
        description="Last frame_seq applied. None if none.",
    )
    tui_session_token: str = Field(
        min_length=1,
        description="TUI-local session token for authenticity binding.",
    )


# ---------------------------------------------------------------------------
# Arm: resume_response  (Spec 032 §2.6)
# ---------------------------------------------------------------------------


class ResumeResponseFrame(_BaseFrame):
    """Backend accepts the resume.

    Must be followed by replay of frames with frame_seq > last_seen_frame_seq.
    Trailer with final=True MUST be set (E6).
    role allow-list: backend.
    """

    kind: Literal["resume_response"] = Field(
        default="resume_response", description="Frame discriminator."
    )
    resumed_from_frame_seq: NonNegativeInt = Field(
        description="Inclusive lower bound of frames that will be replayed."
    )
    replay_count: NonNegativeInt = Field(
        description="Total frames the backend will replay. Bounded by ring buffer size."
    )
    server_session_id: str = Field(
        description="Backend-assigned session id the TUI should use going forward."
    )
    heartbeat_interval_ms: int = Field(
        ge=1000,
        description="Negotiated heartbeat cadence (default 30000).",
    )


# ---------------------------------------------------------------------------
# Arm: resume_rejected  (Spec 032 §2.7)
# ---------------------------------------------------------------------------


class ResumeRejectedFrame(_BaseFrame):
    """Backend cannot honor the resume request.

    Trailer with final=True MUST be set (E6).
    role allow-list: backend.
    """

    kind: Literal["resume_rejected"] = Field(
        default="resume_rejected", description="Frame discriminator."
    )
    reason: Literal[
        "ring_evicted",
        "session_unknown",
        "token_mismatch",
        "protocol_incompatible",
        "session_expired",
    ] = Field(description="Machine-readable reason code.")
    detail: str = Field(
        description="Human-readable Korean/English detail for HUD.",
    )


# ---------------------------------------------------------------------------
# Arm: heartbeat  (Spec 032 §2.8)
# ---------------------------------------------------------------------------


class HeartbeatFrame(_BaseFrame):
    """Emitted every 30 s (default) by both sides to prove liveness.

    Note: Heartbeat frames do NOT increment frame_seq — they use a dedicated
    counter. This keeps ring-buffer economy tight.
    role allow-list: tui, backend.
    """

    kind: Literal["heartbeat"] = Field(default="heartbeat", description="Frame discriminator.")
    direction: Literal["ping", "pong"] = Field(description="ping from sender, pong from receiver.")
    peer_frame_seq: NonNegativeInt = Field(
        description="Sender's current outbound frame_seq high-water."
    )


# ---------------------------------------------------------------------------
# Arm: notification_push  (Spec 032 §2.9)
# ---------------------------------------------------------------------------


class NotificationPushFrame(_BaseFrame):
    """Push from subscription surfaces (Spec 031 SubscriptionHandle).

    Carried over the same stdio channel to keep a single correlation plane.
    role allow-list: notification.

    CC parity: NO equivalent — Claude Code's notification surface is
    terminal OSC sequences (iTerm2, Kitty, Ghostty, bell) emitted
    in-process from ``ink/useTerminalNotification.ts``. There is no
    push-based IPC notification arm in CC. KOSMOS adds this arm as a
    swap-2 addition for Korean civic push channels (KMA disaster CBS,
    RSS newsroom subscribe, hospital-alert subscribe) carried over the
    same stdio plane to keep a single correlation plane. Spec 2642
    Epic F · S7 audit recorded this finding (specs/cc-migration-audit/
    scope-S7-ipc-bridge.md § 5 Finding 3 — resolved as orthogonal
    KOSMOS swap-2 add-on, not a CC-divergence regression).
    """

    kind: Literal["notification_push"] = Field(
        default="notification_push", description="Frame discriminator."
    )
    subscription_id: str = Field(description="Handle from Spec 031 subscribe registration.")
    adapter_id: str = Field(description="e.g., disaster_alert_cbs_push, rss_newsroom_subscribe.")
    event_guid: str = Field(description="RSS guid or CBS event hash for duplicate suppression.")
    payload_content_type: Literal["text/plain", "application/json"] = Field(
        description="Inline payload MIME."
    )
    payload: str = Field(description="Inline notification content (Korean for civic users).")


# ---------------------------------------------------------------------------
# Arm: plugin_op  (Epic #1636 P5 § contracts/plugin-install.cli.md)
# ---------------------------------------------------------------------------


class PluginOpFrame(_BaseFrame):
    """Plugin install / uninstall / list control-plane frame.

    Single arm carrying the three operation states discriminated by the
    inner ``op`` field. Modelled as one ``kind`` so the IPC discriminator
    keeps ``plugin_op`` as a single 20th arm — matching the migration
    tree's "20th arm" decision while preserving the per-phase shape
    documented in ``contracts/plugin-install.cli.md``.

    Op-specific shape rules (enforced by ``_v_plugin_op_shape``):

    * ``op="request"``: ``name`` required when ``request_op`` is
      ``"install"`` or ``"uninstall"``; ``progress_phase`` /
      ``progress_message_ko`` / ``progress_message_en`` / ``result`` /
      ``exit_code`` MUST be ``None``.
    * ``op="progress"``: ``progress_phase`` (1-7), ``progress_message_ko``,
      ``progress_message_en`` required; install-request fields must be
      ``None``.
    * ``op="complete"``: ``result`` + ``exit_code`` required; everything
      else None except optional ``receipt_id``.

    role allow-list: tui (request), backend (progress / complete).
    """

    kind: Literal["plugin_op"] = Field(default="plugin_op", description="Frame discriminator.")
    op: Literal["request", "progress", "complete"] = Field(
        description=(
            "Operation phase. ``request`` = TUI initiates install/uninstall/list; "
            "``progress`` = backend reports phase tick; ``complete`` = backend "
            "reports terminal outcome."
        ),
    )

    # Request-only fields (op="request").
    request_op: Literal["install", "uninstall", "list"] | None = Field(
        default=None,
        description=("Sub-action when op='request'. Required for op='request'; None otherwise."),
    )
    name: str | None = Field(
        default=None,
        description=(
            "Plugin catalog name (matches CatalogEntry.name). Required when "
            "request_op in {install, uninstall}; None otherwise."
        ),
    )
    requested_version: str | None = Field(
        default=None,
        description=(
            "Optional SemVer pin for op='request'/install. Renamed from "
            "`version` to avoid shadowing the envelope's protocol version."
        ),
    )
    dry_run: bool | None = Field(
        default=None,
        description="When True, install verifies but writes nothing (op='request').",
    )

    # Progress-only fields (op="progress").
    progress_phase: int | None = Field(
        default=None,
        description=(
            "Install phase index 1-7 per contracts/plugin-install.cli.md. "
            "Required when op='progress'."
        ),
    )
    progress_message_ko: str | None = Field(
        default=None,
        description="Korean-primary progress message shown in the Ink overlay.",
    )
    progress_message_en: str | None = Field(
        default=None,
        description="English fallback progress message.",
    )

    # Complete-only fields (op="complete").
    result: Literal["success", "failure"] | None = Field(
        default=None,
        description="Terminal outcome. Required when op='complete'.",
    )
    exit_code: int | None = Field(
        default=None,
        description=(
            "Process exit code per contracts/plugin-install.cli.md exit-code table. "
            "Required when op='complete'."
        ),
    )
    receipt_id: str | None = Field(
        default=None,
        description="Spec 035 consent receipt id when op='complete' AND result='success'.",
    )
    error_kind: str | None = Field(
        default=None,
        description=(
            "Machine-readable failure kind (e.g. 'bundle_sha_mismatch', "
            "'slsa_skip_in_production') when op='complete' AND result='failure'. "
            "Used by the TUI to map exit codes to citizen-friendly Korean messages."
        ),
    )
    error_message: str | None = Field(
        default=None,
        description="Developer-facing English error detail when op='complete' AND result='failure'.",
    )
    was_idempotent_noop: bool | None = Field(
        default=None,
        description=(
            "True when op='complete' + result='success' but the operation was a no-op "
            "because the plugin was already in the target state (e.g. uninstall of "
            "a plugin that was never installed). TUI uses this to show '이미 제거됨' "
            "instead of '제거 완료'."
        ),
    )

    @model_validator(mode="after")
    def _v_plugin_op_shape(self) -> PluginOpFrame:  # noqa: C901 — discriminated union shape
        """Enforce per-op-state required/forbidden field shape."""
        if self.op == "request":
            if self.request_op is None:
                raise ValueError("plugin_op.request requires request_op")
            if self.request_op in ("install", "uninstall") and not self.name:
                raise ValueError(
                    f"plugin_op.request_op={self.request_op!r} requires non-empty name"
                )
            forbidden = {
                "progress_phase": self.progress_phase,
                "progress_message_ko": self.progress_message_ko,
                "progress_message_en": self.progress_message_en,
                "result": self.result,
                "exit_code": self.exit_code,
                "receipt_id": self.receipt_id,
                "error_kind": self.error_kind,
                "error_message": self.error_message,
                "was_idempotent_noop": self.was_idempotent_noop,
            }
            extras = [k for k, v in forbidden.items() if v is not None]
            if extras:
                raise ValueError(
                    f"plugin_op.request must not set progress/complete fields: {extras}"
                )
        elif self.op == "progress":  # noqa: SIM114 — flow-level branches stay flat for clarity.
            if self.progress_phase is None or not (1 <= self.progress_phase <= 7):
                raise ValueError("plugin_op.progress requires progress_phase in [1, 7]")
            if not self.progress_message_ko or not self.progress_message_en:
                raise ValueError(
                    "plugin_op.progress requires progress_message_ko + progress_message_en"
                )
            forbidden = {
                "request_op": self.request_op,
                "name": self.name,
                "requested_version": self.requested_version,
                "dry_run": self.dry_run,
                "result": self.result,
                "exit_code": self.exit_code,
                "receipt_id": self.receipt_id,
                "error_kind": self.error_kind,
                "error_message": self.error_message,
                "was_idempotent_noop": self.was_idempotent_noop,
            }
            extras = [k for k, v in forbidden.items() if v is not None]
            if extras:
                raise ValueError(
                    f"plugin_op.progress must not set request/complete fields: {extras}"
                )
        elif self.op == "complete":
            if self.result is None:
                raise ValueError("plugin_op.complete requires result")
            if self.exit_code is None:
                raise ValueError("plugin_op.complete requires exit_code")
            if self.result == "failure" and self.receipt_id is not None:
                raise ValueError("plugin_op.complete result='failure' must not set receipt_id")
            if self.result == "success" and self.error_kind is not None:
                raise ValueError(
                    "plugin_op.complete result='success' must not set error_kind"
                )
            forbidden = {
                "request_op": self.request_op,
                "name": self.name,
                "requested_version": self.requested_version,
                "dry_run": self.dry_run,
                "progress_phase": self.progress_phase,
                "progress_message_ko": self.progress_message_ko,
                "progress_message_en": self.progress_message_en,
            }
            extras = [k for k, v in forbidden.items() if v is not None]
            if extras:
                raise ValueError(
                    f"plugin_op.complete must not set request/progress fields: {extras}"
                )
        return self


# ---------------------------------------------------------------------------
# Helper: canonical-JSON serialisation for manifest hash computation (I3)
# ---------------------------------------------------------------------------

_TOOL_ID_RE: re.Pattern[str] = re.compile(r"^[a-z][a-z0-9_]*$")


def _canonical_json(obj: Any) -> str:
    """Produce a canonical JSON string (sorted keys, compact separators, ASCII-safe)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


# ---------------------------------------------------------------------------
# Arm: adapter_manifest_sync  (Epic ε #2296 — 21st arm)
# ---------------------------------------------------------------------------


class AdapterManifestEntry(BaseModel):
    """One adapter record inside an ``AdapterManifestSyncFrame.entries`` array.

    Used by the TS-side cache to resolve ``tool_id`` and populate the citation
    slot in permission prompts.

    Validators:
    - ``policy_authority_url`` required (HTTPS) when ``source_mode`` is ``"live"``
      or ``"mock"``; ``None`` only allowed when ``source_mode == "internal"`` (I4/I5).
    - ``tool_id`` matches ``^[a-z][a-z0-9_]*$`` (I7).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_id: str = Field(
        min_length=1,
        description=(
            "Globally unique adapter id within the registry, e.g. 'nmc_emergency_search'. "
            "Lowercase snake-case; validated by I7."
        ),
    )
    name: str = Field(
        min_length=1,
        max_length=80,
        description="Human-readable display name; bilingual permitted.",
    )
    primitive: Literal["lookup", "submit", "subscribe", "verify", "resolve_location"] = Field(
        description="Primitive verb the adapter is registered under (I6).",
    )
    policy_authority_url: str | None = Field(
        default=None,
        max_length=2048,
        description=(
            "Agency-published policy URL (HTTPS). None only when source_mode == 'internal' (I4/I5)."
        ),
    )
    source_mode: Literal["live", "mock", "internal"] = Field(
        description="Tag for the citation-rendering surface.",
    )

    @field_validator("tool_id")
    @classmethod
    def _validate_tool_id_snake_case(cls, v: str) -> str:
        if not _TOOL_ID_RE.match(v):
            raise ValueError(
                f"AdapterManifestEntry.tool_id must match ^[a-z][a-z0-9_]*$, got {v!r}"
            )
        return v

    @model_validator(mode="after")
    def _validate_policy_url_vs_source_mode(self) -> AdapterManifestEntry:
        """I4: live/mock entries must have a non-null HTTPS policy_authority_url.
        I5: internal entries must have policy_authority_url == None.
        """
        if self.source_mode in ("live", "mock"):
            if not self.policy_authority_url:
                raise ValueError(
                    f"AdapterManifestEntry.policy_authority_url is required (non-null, HTTPS) "
                    f"when source_mode={self.source_mode!r} (I4); got None or empty."
                )
            if not self.policy_authority_url.startswith("https://"):
                raise ValueError(
                    f"AdapterManifestEntry.policy_authority_url must be an HTTPS URL "
                    f"when source_mode={self.source_mode!r} (I4); "
                    f"got {self.policy_authority_url!r}."
                )
        elif self.source_mode == "internal":
            if self.policy_authority_url is not None:
                raise ValueError(
                    "AdapterManifestEntry.policy_authority_url must be None "
                    "when source_mode='internal' (I5); "
                    f"got {self.policy_authority_url!r}."
                )
        return self


class AdapterManifestSyncFrame(_BaseFrame):
    """Full registry snapshot emitted by the backend exactly once after boot.

    21st arm of the ``IPCFrame`` discriminated union (Epic ε #2296).

    Invariants enforced at construction:
    - I1: ``entries`` is non-empty.
    - I2: No two entries share the same ``tool_id``.
    - I3: ``manifest_hash == sha256(canonical_json(sorted(entries, key=tool_id)))``.
    - I4/I5/I6/I7: delegated to ``AdapterManifestEntry`` validators.

    On invariant violation the Pydantic validator raises ``ValueError``; the
    backend boot should catch this and exit with ``SystemExit(78)`` per
    Constitution § II + Spec 1634 boot-validation pattern.
    """

    kind: Literal["adapter_manifest_sync"] = Field(
        default="adapter_manifest_sync",
        description="Frame discriminator — 21st arm of IPCFrame.",
    )
    entries: list[AdapterManifestEntry] = Field(
        min_length=1,
        description="Full registry snapshot. Non-empty (I1); no duplicate tool_id (I2).",
    )
    manifest_hash: str = Field(
        min_length=64,
        max_length=64,
        description=(
            "Lowercase hex SHA-256 of canonical-JSON-serialised entries sorted by tool_id (I3). "
            "Cheap change-detection for hot-reload (future epic)."
        ),
    )
    emitter_pid: int = Field(
        gt=0,
        description="Python backend PID at boot. Useful for OTEL span cross-correlation.",
    )

    @model_validator(mode="after")
    def _validate_entries_invariants(self) -> AdapterManifestSyncFrame:
        """Enforce I1 (non-empty), I2 (no duplicate tool_id), I3 (hash matches)."""
        # I1 — already enforced by min_length=1 on the Field; double-check for clarity.
        if not self.entries:
            raise ValueError("AdapterManifestSyncFrame.entries must be non-empty (I1).")

        # I2 — duplicate tool_id check.
        seen: set[str] = set()
        duplicates: list[str] = []
        for entry in self.entries:
            if entry.tool_id in seen:
                duplicates.append(entry.tool_id)
            seen.add(entry.tool_id)
        if duplicates:
            raise ValueError(
                f"AdapterManifestSyncFrame.entries contains duplicate tool_id values (I2): "
                f"{duplicates}"
            )

        # I3 — manifest_hash must match SHA-256 over canonical-JSON-sorted entries.
        sorted_entries = sorted(self.entries, key=lambda e: e.tool_id)
        entries_as_dicts = [e.model_dump(mode="json", by_alias=False) for e in sorted_entries]
        canonical = _canonical_json(entries_as_dicts)
        expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if self.manifest_hash != expected_hash:
            raise ValueError(
                f"AdapterManifestSyncFrame.manifest_hash mismatch (I3): "
                f"expected {expected_hash!r}, got {self.manifest_hash!r}. "
                "Recompute with sha256(canonical_json(sorted(entries, key=tool_id)))."
            )

        return self


# ---------------------------------------------------------------------------
# Arm: consent_revoke_request  (Epic 2 — arm 22, TUI → backend)
# ---------------------------------------------------------------------------


class ConsentRevokeRequestFrame(_BaseFrame):
    """TUI -> backend: citizen requests revocation of a prior consent receipt.

    arm 22 of the ``IPCFrame`` discriminated union (Epic 2).

    Fields:
    - ``request_id``: UUIDv4 string; round-trips in the matching
      ``consent_revoke_response`` frame.
    - ``receipt_id``: The ``rcpt-<id>`` value referencing the receipt file at
      ``~/.kosmos/memdir/user/consent/<receipt_id>.json``.
    - ``scope``: ``"once"`` = revoke this single receipt only;
      ``"session-all"`` = revoke all receipts for the current session.
    - ``reason``: Optional free-text reason logged to the audit ledger.

    role allow-list: tui.
    """

    kind: Literal["consent_revoke_request"] = Field(
        default="consent_revoke_request",
        description="Frame discriminator — arm 22 of IPCFrame.",
    )
    request_id: str = Field(
        min_length=1,
        description="UUIDv4 round-trip correlation ID; matched in consent_revoke_response.",
    )
    receipt_id: str = Field(
        min_length=1,
        description=(
            "Target receipt identifier (rcpt-<id>). Must match an existing receipt file at "
            "~/.kosmos/memdir/user/consent/<receipt_id>.json."
        ),
    )
    scope: Literal["once", "session-all"] = Field(
        description=(
            "Revocation scope. 'once' revokes only this receipt; "
            "'session-all' revokes all receipts in the current session."
        ),
    )
    reason: str | None = Field(
        default=None,
        description="Optional citizen-provided reason logged to the ledger (PIPA §36 citation).",
    )


# ---------------------------------------------------------------------------
# Arm: consent_revoke_response  (Epic 2 — arm 23, backend → TUI)
# ---------------------------------------------------------------------------


class ConsentRevokeResponseFrame(_BaseFrame):
    """backend -> TUI: outcome of a consent_revoke_request.

    arm 23 of the ``IPCFrame`` discriminated union (Epic 2).

    Fields:
    - ``request_id``: Mirrors the originating consent_revoke_request.request_id.
    - ``ok``: True when at least one receipt was revoked; False on error or
      not-found.
    - ``revoked_at``: ISO-8601 UTC timestamp of the revocation (when ok=True).
    - ``record_hash``: Ledger entry SHA-256 for audit chain verification
      (when ok=True; omitted on error).
    - ``error``: Machine-readable error code on failure (``already_revoked``,
      ``not_found``, ``io_error``); omitted on success.

    role allow-list: backend.
    """

    kind: Literal["consent_revoke_response"] = Field(
        default="consent_revoke_response",
        description="Frame discriminator — arm 23 of IPCFrame.",
    )
    request_id: str = Field(
        min_length=1,
        description="Mirrors consent_revoke_request.request_id for round-trip correlation.",
    )
    ok: bool = Field(
        description=(
            "True when at least one receipt was successfully revoked; "
            "False on error or not-found."
        ),
    )
    revoked_at: str | None = Field(
        default=None,
        description="ISO-8601 UTC timestamp of revocation. Populated when ok=True.",
    )
    record_hash: str | None = Field(
        default=None,
        description=(
            "Hex SHA-256 of the ledger withdrawal record. Populated when ok=True "
            "for audit-chain verification."
        ),
    )
    error: Literal["already_revoked", "not_found", "io_error"] | None = Field(
        default=None,
        description="Machine-readable error code when ok=False; None on success.",
    )


# ---------------------------------------------------------------------------
# Discriminated union — 23 kinds (Epic 2 adds consent_revoke_request/response)
# ---------------------------------------------------------------------------

IPCFrame = Annotated[
    UserInputFrame
    | ChatRequestFrame
    | AssistantChunkFrame
    | ToolCallFrame
    | ToolResultFrame
    | CoordinatorPhaseFrame
    | WorkerStatusFrame
    | PermissionRequestFrame
    | PermissionResponseFrame
    | SessionEventFrame
    | ErrorFrame
    | PayloadStartFrame
    | PayloadDeltaFrame
    | PayloadEndFrame
    | BackpressureSignalFrame
    | ResumeRequestFrame
    | ResumeResponseFrame
    | ResumeRejectedFrame
    | HeartbeatFrame
    | NotificationPushFrame
    | PluginOpFrame
    | AdapterManifestSyncFrame  # 21st arm (Epic ε #2296)
    | ConsentRevokeRequestFrame  # 22nd arm (Epic 2)
    | ConsentRevokeResponseFrame,  # 23rd arm (Epic 2)
    Field(discriminator="kind"),
]
"""Discriminated union of all 23 IPC frame arms.

Spec 287 baseline: 10 arms (user_input .. error).
Spec 032 additions: 9 arms (payload_start .. notification_push).
Epic #1636 P5 addition: plugin_op (1 arm with internal op discriminator).
Spec 1978 ADR-0001 addition: chat_request (tools-aware chat from TUI).
Epic ε #2296 addition: adapter_manifest_sync (backend boot manifest).
Epic 2 additions: consent_revoke_request (arm 22), consent_revoke_response (arm 23).

Usage::

    from kosmos.ipc.frame_schema import IPCFrame
    from pydantic import TypeAdapter

    _adapter = TypeAdapter(IPCFrame)
    frame = _adapter.validate_json(raw_line)
"""


def ipc_frame_json_schema() -> dict[str, Any]:
    """Return the JSON Schema for the ``IPCFrame`` discriminated union.

    Delegates to Pydantic v2's ``TypeAdapter.json_schema()``.
    The output is JSON Schema Draft 2020-12 compatible.
    """
    from pydantic import TypeAdapter

    adapter: TypeAdapter[Any] = TypeAdapter(IPCFrame)
    return adapter.json_schema()


__all__ = [
    # Base + trailer
    "FrameTrailer",
    "ENVELOPE_VERSION",
    # Spec 287 baseline arms
    "IPCFrame",
    "UserInputFrame",
    # Spec 1978 ADR-0001 — chat_request + sub-models
    "ChatRequestFrame",
    "ChatMessage",
    "ChatMessageToolCall",
    "ChatMessageFunctionCall",
    "ToolDefinition",
    "ToolDefinitionFunction",
    "AssistantChunkFrame",
    "ToolCallFrame",
    "ToolResultFrame",
    "ToolResultEnvelope",
    "CoordinatorPhaseFrame",
    "WorkerStatusFrame",
    "PermissionRequestFrame",
    "PermissionResponseFrame",
    "SessionEventFrame",
    "ErrorFrame",
    # Spec 032 new arms
    "PayloadStartFrame",
    "PayloadDeltaFrame",
    "PayloadEndFrame",
    "BackpressureSignalFrame",
    "ResumeRequestFrame",
    "ResumeResponseFrame",
    "ResumeRejectedFrame",
    "HeartbeatFrame",
    "NotificationPushFrame",
    # Epic #1636 P5 addition
    "PluginOpFrame",
    # Epic ε #2296 addition
    "AdapterManifestSyncFrame",
    "AdapterManifestEntry",
    # Epic 2 — consent revoke arms 22-23
    "ConsentRevokeRequestFrame",
    "ConsentRevokeResponseFrame",
    # Schema helper
    "ipc_frame_json_schema",
]
