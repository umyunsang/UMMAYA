# SPDX-License-Identifier: Apache-2.0
"""Per-session orchestrator for the UMMAYA Query Engine.

``QueryEngine`` is the only public entry point for consumers of the query
engine module. It owns the session state and delegates per-turn execution to
the standalone ``query()`` async generator.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from ummaya.context.builder import ContextBuilder
from ummaya.engine.config import QueryEngineConfig
from ummaya.engine.events import QueryEvent, StopReason
from ummaya.engine.models import QueryContext, QueryState, SessionBudget
from ummaya.engine.query import query
from ummaya.llm.client import LLMClient
from ummaya.llm.models import ChatMessage
from ummaya.tools.errors import ToolNotFoundError
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from ummaya.permissions.models import SessionContext

logger = logging.getLogger(__name__)

_LOCATION_DEPENDENT_SCHEMA_KEYS = frozenset(
    {
        "adm_cd",
        "admcd",
        "admin_code",
        "administrative_code",
        "latitude",
        "lat",
        "longitude",
        "lon",
        "lng",
        "nx",
        "ny",
        "region_cd",
        "region_code",
    }
)


def _schema_requires_location_resolution(
    input_schema_json: object,
    required_params: object,
) -> bool:
    """Return True when an adapter schema needs prior locate output."""

    return _contains_location_dependent_key(input_schema_json) or _contains_location_dependent_key(
        required_params
    )


def _contains_location_dependent_key(value: object) -> bool:
    """Recursively detect coordinate/admin-code schema fields."""

    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in _LOCATION_DEPENDENT_SCHEMA_KEYS:
                return True
            if _contains_location_dependent_key(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_location_dependent_key(item) for item in value)
    elif isinstance(value, str):
        return value.lower() in _LOCATION_DEPENDENT_SCHEMA_KEYS
    return False


class QueryEngine:
    """Per-session orchestrator for the UMMAYA query engine.

    The only public entry point for consumers. Each instance manages one
    conversational session: it owns the message history, token budget, and
    turn counter, and delegates per-turn execution to ``query()``.

    Args:
        llm_client: Configured LLM client for streaming completions.
        tool_registry: Registry with registered tools and rate limiters.
        tool_executor: Dispatcher with registered adapters.
        config: Engine configuration. Uses defaults if None.
        context_builder: Context assembly helper used to build the system
                         message and per-turn attachments. A default
                         ContextBuilder is created if None.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        tool_executor: ToolExecutor,
        config: QueryEngineConfig | None = None,
        context_builder: ContextBuilder | None = None,
        permission_session: SessionContext | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._tool_registry = tool_registry
        self._tool_executor = tool_executor
        self._config = config or QueryEngineConfig()
        self._context_builder = context_builder or ContextBuilder(registry=tool_registry)
        self._permission_session = permission_session

        system_msg = self._context_builder.build_system_message()
        self._state = QueryState(
            usage=llm_client.usage,
            messages=[system_msg],
        )

        logger.info(
            "QueryEngine initialized: max_iterations=%d, max_turns=%d, context_window=%d, tools=%d",
            self._config.max_iterations,
            self._config.max_turns,
            self._config.context_window,
            len(self._tool_registry),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, user_message: str) -> AsyncIterator[QueryEvent]:
        """Execute a single turn of the query engine.

        This is the primary public API. Each call represents one citizen turn:
        the user message is appended to history, and the engine loops through
        LLM call → tool dispatch → decide until a stop condition.

        Args:
            user_message: The citizen's natural-language input.

        Yields:
            QueryEvent: Progress events in order — text_delta, tool_use,
                        tool_result, usage_update, and finally stop.

        Raises:
            No exceptions propagate. All errors are captured as
            QueryEvent(type="stop", stop_reason=StopReason.error_unrecoverable).
        """
        logger.info(
            "Turn %d started: %s",
            self._state.turn_count + 1,
            user_message[:80],
        )

        # --- Budget enforcement: check turn limit before processing ---
        if self._state.turn_count >= self._config.max_turns:
            budget_snap = self.budget
            yield QueryEvent(
                type="stop",
                stop_reason=StopReason.api_budget_exceeded,
                stop_message=(
                    f"Turn budget exhausted: {budget_snap.turns_used}"
                    f"/{budget_snap.turns_budget} turns used"
                ),
            )
            return

        # --- Budget enforcement: check token budget ---
        if self._state.usage.is_exhausted:
            budget_snap = self.budget
            yield QueryEvent(
                type="stop",
                stop_reason=StopReason.api_budget_exceeded,
                stop_message=(
                    f"Token budget exhausted: {budget_snap.tokens_used}"
                    f"/{budget_snap.tokens_budget} tokens used"
                ),
            )
            return

        # --- Budget check via context assembly (before mutating message history) ---
        # Build the assembled context first so that a budget-exceeded early exit
        # does not leave a stray attachment in self._state.messages.
        assembled = self._context_builder.build_assembled_context(
            self._state,
            api_health=None,
            hard_limit=self._config.context_window,
        )
        # assembled.tool_definitions is intentionally not used here: tool defs are
        # exported inside the per-turn query loop via ToolRegistry.export_core_tools_openai()
        # (see query.py) to ensure the snapshot is taken after the user message is appended.
        if assembled.budget and assembled.budget.is_over_limit:
            yield QueryEvent(
                type="stop",
                stop_reason=StopReason.api_budget_exceeded,
                stop_message="Context token budget exceeded",
            )
            return

        turn_start_message_index = len(self._state.messages)

        # --- Context assembly: insert turn attachment after passing budget check ---
        # Re-use the turn_attachment already computed in assembled; avoids a second
        # call to build_turn_attachment() which would duplicate context assembly work.
        if assembled.turn_attachment is not None:
            self._state.messages.append(
                ChatMessage(role="user", content=assembled.turn_attachment.content),
            )

        dynamic_adapter_message, turn_tool_ids = self._build_available_adapters_context(
            user_message
        )
        if dynamic_adapter_message is not None:
            self._state.messages.append(dynamic_adapter_message)

        # Append user message to history
        self._state.messages.append(
            ChatMessage(role="user", content=user_message),
        )

        # Create per-turn context
        ctx = QueryContext(
            state=self._state,
            llm_client=self._llm_client,
            tool_executor=self._tool_executor,
            tool_registry=self._tool_registry,
            config=self._config,
            session_context=self._permission_session,
            turn_tool_ids=turn_tool_ids,
            turn_start_message_index=turn_start_message_index,
        )

        # Delegate to per-turn query loop
        try:
            async for event in query(ctx):
                yield event
        except Exception as exc:
            logger.exception("Unexpected error in query loop: %s", exc)
            yield QueryEvent(
                type="stop",
                stop_reason=StopReason.error_unrecoverable,
                stop_message=f"Unexpected error: {exc}",
            )
        finally:
            if dynamic_adapter_message is not None:
                try:
                    self._state.messages.remove(dynamic_adapter_message)
                except ValueError:
                    logger.debug("Dynamic adapter context already absent from state")
            self._state.turn_count += 1
            logger.info(
                "Turn %d completed: tokens_used=%d, messages=%d",
                self._state.turn_count,
                self._state.usage.total_used,
                len(self._state.messages),
            )

    def reset(self) -> None:
        """Reset the conversation state for a new session.

        Clears the message history (re-initialises with the system message),
        resets the turn counter, and preserves the existing token usage tracker
        so that the budget continues from where it left off.
        """
        system_msg = self._context_builder.build_system_message()
        self._state = QueryState(
            usage=self._llm_client.usage,
            messages=[system_msg],
        )
        logger.info("QueryEngine reset: conversation cleared")

    def _build_available_adapters_message(self, user_message: str) -> ChatMessage | None:
        """Inject BM25 adapter candidates for the current citizen utterance."""

        message, _turn_tool_ids = self._build_available_adapters_context(user_message)
        return message

    def _build_available_adapters_context(
        self, user_message: str
    ) -> tuple[ChatMessage | None, tuple[str, ...]]:
        """Build dynamic adapter context and per-turn concrete tool exposure."""

        try:
            from ummaya.tools.search import search  # noqa: PLC0415

            candidates = search(
                user_message,
                self._tool_registry.bm25_index,
                self._tool_registry,
                top_k=15,
            )
        except Exception:  # noqa: BLE001
            logger.exception("available_adapters auto-inject failed")
            return None, ()

        adapter_lines: list[str] = []
        selected_tool_ids: list[str] = []
        primary_find_without_location = False
        visible_count = 0
        for candidate in candidates:
            try:
                tool = self._tool_registry.find(candidate.tool_id)
            except ToolNotFoundError:
                continue
            if candidate.score <= 0:
                continue
            if tool.is_core or tool.ministry == "UMMAYA":
                continue
            primitive = candidate.primitive if isinstance(candidate.primitive, str) else None
            requires_location = _schema_requires_location_resolution(
                candidate.input_schema_json,
                candidate.required_params,
            )
            primary_find_without_location = primary_find_without_location or (
                visible_count == 0 and primitive == "find" and not requires_location
            )
            if visible_count > 0 and primary_find_without_location and requires_location:
                continue
            schema_json = json.dumps(
                candidate.input_schema_json,
                ensure_ascii=False,
                sort_keys=True,
            )
            selected_tool_ids.append(candidate.tool_id)
            adapter_lines.extend(
                [
                    f"- tool_id: {candidate.tool_id}",
                    f"  primitive: {candidate.primitive}",
                    f"  description: {candidate.llm_description or tool.name_ko}",
                    f"  required_params: {candidate.required_params}",
                    f"  input_schema_json: {schema_json}",
                    f"  call_hint: {candidate.tool_id}({{...}})",
                    f"  policy_url: {candidate.real_classification_url or ''}",
                ]
            )
            visible_count += 1
            if visible_count >= 5:
                break

        if not adapter_lines:
            return None, ()

        content = "\n".join(
            [
                "<available_adapters>",
                "Use these adapter candidates for this citizen request. "
                "Call the function named exactly as tool_id with that adapter's "
                "schema arguments. Do not wrap adapter calls in root primitives "
                "such as find({tool_id, params}), locate({tool_id, params}), "
                "check({tool_id, params}), or send({tool_id, params}). "
                "Do not call locate just because the citizen text contains a "
                "city/province name; treat that as the dataset/filter term. "
                "Call locate only when the selected adapter schema requires "
                "coordinates, administrative codes, or a place-to-region conversion.",
                *adapter_lines,
                "</available_adapters>",
            ]
        )
        return ChatMessage(role="system", content=content), tuple(selected_tool_ids)

    def set_permission_session(self, session: SessionContext | None) -> None:
        """Update the permission-pipeline session used for subsequent turns.

        The REPL calls this when it creates or resumes a session so that
        the ``session_id`` recorded in permission audits matches the real
        REPL session identifier instead of a placeholder.

        Args:
            session: Fresh :class:`SessionContext`, or ``None`` to disable
                permission checks (not recommended in production).
        """
        self._permission_session = session
        if session is not None:
            logger.info(
                "QueryEngine permission session updated: session_id=%s",
                session.session_id,
            )
        else:
            logger.warning("QueryEngine permission session cleared")

    @property
    def permission_session(self) -> SessionContext | None:
        """Return the currently installed permission :class:`SessionContext`."""
        return self._permission_session

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def budget(self) -> SessionBudget:
        """Return a read-only snapshot of current budget status."""
        return SessionBudget.from_state(self._state, self._config)

    @property
    def message_count(self) -> int:
        """Return the number of messages in the conversation history."""
        return len(self._state.messages)
