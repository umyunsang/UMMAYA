# SPDX-License-Identifier: Apache-2.0
"""Core state models for the UMMAYA Query Engine (Layer 1).

Three model types form the session and per-turn state contract:

- QueryState   — mutable per-session state that accumulates across turns.
                 Implemented as a plain dataclass because Pydantic frozen models
                 cannot be mutated in-place.
- QueryContext — frozen per-turn context assembled at the start of each
                 iteration and discarded when the turn ends.  Holds references
                 to the session infrastructure (LLM client, executor, registry).
- SessionBudget — frozen read-only snapshot of remaining budget, derived from
                  QueryState + QueryEngineConfig via SessionBudget.from_state().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from ummaya.permissions.models import SessionContext

from ummaya.engine.config import QueryEngineConfig
from ummaya.llm.client import LLMClientRuntimeType as LLMClient
from ummaya.llm.models import ChatMessage
from ummaya.llm.usage import UsageTracker
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# QueryState
# ---------------------------------------------------------------------------


@dataclass
class QueryState:
    """Mutable per-session state that grows across turns.

    Holds the running message history, turn counter, token usage tracker,
    and a log of tasks resolved during the session.

    The ``usage`` field must be supplied at construction time — there is no
    default because the budget configuration is caller-owned.
    """

    usage: UsageTracker
    """Session-level token usage tracker (caller-supplied, no default)."""

    messages: list[ChatMessage] = field(default_factory=list)
    """Ordered conversation history accumulated across all turns."""

    turn_count: int = 0
    """Number of completed turns in this session."""

    resolved_tasks: list[str] = field(default_factory=list)
    """Human-readable descriptions of tasks resolved during the session."""

    active_situational_tools: set[str] = field(default_factory=set)
    """Tool IDs that have been activated for the current session mid-flight.

    Populated by the tool discovery flow (e.g. ``search_tools``).  The
    context assembler reads this set to build the situational suffix partition
    of ``AssembledContext.tool_definitions``.
    """


# ---------------------------------------------------------------------------
# QueryContext
# ---------------------------------------------------------------------------


class QueryContext(BaseModel):
    """Frozen per-turn context assembled at the start of each iteration.

    Created once per turn, passed through the tool loop, and discarded when
    the turn ends.  Holds references to the session infrastructure objects
    that are shared across iterations within a single turn.

    ``arbitrary_types_allowed`` is required because the infrastructure objects
    (LLMClient, ToolExecutor, ToolRegistry, UsageTracker, QueryState) are not
    Pydantic models.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    state: QueryState
    """Mutable session state shared across all turns."""

    llm_client: LLMClient
    """Async LLM client used to issue completion requests."""

    tool_executor: ToolExecutor
    """Dispatcher that validates and executes tool calls."""

    tool_registry: ToolRegistry
    """Registry of available government API tools."""

    config: QueryEngineConfig
    """Immutable engine configuration for this session."""

    iteration: int = 0
    """Zero-based iteration counter within the current turn."""

    session_context: SessionContext | None = None
    """Optional session context supplied to the permission pipeline per tool call.

    Only forwarded to the pipeline when both this field and ``permission_pipeline``
    are non-None.
    """

    correlation_id: str | None = None
    """UUIDv7 correlation chain identifier for the current turn (Spec 032 T049).

    Threaded from the inbound ``user_input`` frame's envelope through the tool
    loop so that every IPC frame emitted during this turn carries the same
    ``ummaya.ipc.correlation_id`` OTEL attribute (FR-027 / FR-053).  ``None``
    when the engine is driven outside the stdio bridge (unit tests / REPL).
    """

    allowed_core_tool_ids: frozenset[str] | None = None
    """Legacy per-turn allow-list for primitive wrappers.

    Preserved for callers that still expose the old root primitives. New turns
    should prefer ``turn_tool_ids`` so the model sees concrete adapter schemas.
    """

    turn_tool_ids: tuple[str, ...] = ()
    """Concrete adapter tool IDs selected for this citizen turn.

    When populated, the query loop exports these concrete adapter schemas as the
    provider tool surface instead of dumping the root primitive wrappers.
    """

    turn_start_message_index: int = 0
    """Index of the first message appended for this user turn.

    Query-loop guards use this to distinguish tool results produced during the
    current turn from successful tool results left in prior session history.
    """


# ---------------------------------------------------------------------------
# SessionBudget
# ---------------------------------------------------------------------------


class SessionBudget(BaseModel):
    """Frozen read-only snapshot of the current session budget status.

    Derived from QueryState and QueryEngineConfig via the class method
    ``from_state()``.  All fields are non-negative integers or a boolean flag;
    ``is_exhausted`` is True when either the token budget or the turn budget
    is fully consumed.
    """

    model_config = ConfigDict(frozen=True)

    tokens_used: int
    """Total tokens consumed so far in this session."""

    tokens_remaining: int
    """Tokens still available before the session budget is exhausted."""

    tokens_budget: int
    """Configured token budget for the session."""

    turns_used: int
    """Number of turns completed so far."""

    turns_remaining: int
    """Turns still available before the session turn limit is reached."""

    turns_budget: int
    """Configured maximum turns for the session."""

    is_exhausted: bool
    """True when either the token budget or the turn budget is fully consumed."""

    @classmethod
    def from_state(cls, state: QueryState, config: QueryEngineConfig) -> SessionBudget:
        """Construct a SessionBudget snapshot from current session state.

        Args:
            state: The mutable QueryState holding live usage counters.
            config: The engine configuration supplying budget limits.

        Returns:
            A frozen SessionBudget reflecting the current state of the session.
        """
        return cls(
            tokens_used=state.usage.total_used,
            tokens_remaining=state.usage.remaining,
            tokens_budget=state.usage.budget,
            turns_used=state.turn_count,
            turns_remaining=max(0, config.max_turns - state.turn_count),
            turns_budget=config.max_turns,
            is_exhausted=state.usage.is_exhausted or state.turn_count >= config.max_turns,
        )


# ---------------------------------------------------------------------------
# Resolve forward references for QueryContext
#
# ``from __future__ import annotations`` defers all annotations as strings.
# Pydantic v2 evaluates them lazily; calling model_rebuild() here with the
# real permission types in the namespace ensures forward references are
# resolved once at import time.  Test-level model_rebuild() calls become
# no-ops (Pydantic skips a rebuild if the model is already complete).
# ---------------------------------------------------------------------------
from ummaya.permissions.models import SessionContext  # noqa: E402

QueryContext.model_rebuild(
    _types_namespace={
        "SessionContext": SessionContext,
    }
)
