# SPDX-License-Identifier: Apache-2.0
"""ContextBuilder — the single public assembly facade for Layer 5.

``ContextBuilder`` wires together all context assembly sub-systems:

- ``SystemPromptAssembler``  → deterministic system message (US1)
- ``AttachmentCollector``    → per-turn dynamic attachment (US2)
- Tool schema injection      → core prefix + situational suffix (US3)
- ``BudgetEstimator``        → token budget guard (US4)

It is intentionally stateless between turns: all session state is passed in at
call time via ``QueryState``.  The only internal mutable state is the cached
system message (computed once on the first ``build_system_message()`` call and
reused on subsequent calls — NFR-003).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from ummaya.context.attachments import AttachmentCollector
from ummaya.context.budget import BudgetEstimator
from ummaya.context.compact_models import CompactionConfig, CompactionResult
from ummaya.context.models import (
    AssembledContext,
    ContextLayer,
    SystemPromptConfig,
)
from ummaya.context.system_prompt import SystemPromptAssembler
from ummaya.llm.models import ChatMessage
from ummaya.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from ummaya.engine.models import QueryState

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Assembles the full context sent to the LLM on every turn.

    Args:
        config: Prompt configuration.  A default ``SystemPromptConfig`` is
                used when ``None``.
        registry: Tool registry providing core / situational tool schemas.
                  May be ``None`` when tool injection is not required (e.g.
                  unit tests that only exercise the system-message path).
    """

    def __init__(
        self,
        config: SystemPromptConfig | None = None,
        registry: ToolRegistry | None = None,
        compaction_config: CompactionConfig | None = None,
    ) -> None:
        self._config = config or SystemPromptConfig()
        self._registry = registry
        self._compaction_config = compaction_config
        self._assembler = SystemPromptAssembler()
        self._attachment_collector = AttachmentCollector(config=self._config)
        self._budget_estimator = BudgetEstimator()
        self._core_tool_defs_cache_key: tuple[str, ...] | None = None
        self._core_tool_defs_cache: list[dict[str, object]] = []

        # Cached assembled ChatMessage (set on first build_system_message() call).
        self._system_message: ChatMessage | None = None

    # ------------------------------------------------------------------
    # US1 — Stable System Prompt Assembly
    # ------------------------------------------------------------------

    def build_system_message(self) -> ChatMessage:
        """Return the deterministic system ``ChatMessage``.

        The result is memoised: the first call assembles the prompt and caches
        it; subsequent calls return the cached instance unchanged.  This
        ensures the FriendliAI prompt-cache prefix is never invalidated between
        turns (NFR-003, SC-001).

        Returns:
            Frozen ``ChatMessage(role='system', content=<assembled prompt>)``.
        """
        if self._system_message is None:
            prompt = self._assembler.assemble(self._config)
            self._system_message = ChatMessage(role="system", content=prompt)
            logger.debug("System message assembled and cached (%d chars)", len(prompt))
        return self._system_message

    # ------------------------------------------------------------------
    # US2 — Per-Turn Attachment Injection
    # ------------------------------------------------------------------

    def build_turn_attachment(
        self,
        state: QueryState,
        api_health: dict[str, str] | None = None,
    ) -> ContextLayer | None:
        """Assemble the per-turn dynamic context attachment.

        Delegates to ``AttachmentCollector.collect()``.  Returns ``None`` for
        empty sessions (turn 0, no resolved tasks, no in-flight calls) so that
        the caller does not insert an empty ``ChatMessage`` into the history
        (FR-002, edge case: empty session).

        Args:
            state: Current mutable session state.
            api_health: Optional mapping of tool_id → degradation status string.

        Returns:
            ``ContextLayer(role='user', layer_name='turn_attachment', content=…)``
            or ``None`` when no attachment content exists.
        """
        collected = self._attachment_collector.collect(state=state, api_health=api_health)
        if collected is None:
            return None
        return ContextLayer(role="user", layer_name="turn_attachment", content=collected)

    # ------------------------------------------------------------------
    # US3 — Tool Schema Injection with Cache Partitioning
    # ------------------------------------------------------------------

    def build_assembled_context(
        self,
        state: QueryState,
        api_health: dict[str, str] | None = None,
        hard_limit: int = 128_000,
    ) -> AssembledContext:
        """Assemble the complete context for one LLM turn.

        Steps:
          1. Build (or return cached) system message as ContextLayer.
          2. Build per-turn attachment (may be None).
          3. Build tool_definitions: core tools (sorted by id) first, then
             active situational tools (sorted by id) — FR-004, FR-005.
          4. Compute ContextBudget via BudgetEstimator — FR-006, FR-007.
          5. Log WARNING if is_near_limit — FR-006.

        Args:
            state: Current session state supplying active_situational_tools,
                   resolved_tasks, turn_count, etc.
            api_health: Optional dict of tool_id → health status string.
            hard_limit: Context window size in tokens. Defaults to 128_000 for
                        backward compatibility; callers should pass the engine's
                        configured ``context_window`` value.

        Returns:
            Frozen ``AssembledContext`` with all fields populated.
        """
        # --- System layer ---
        sys_msg = self.build_system_message()
        system_layer = ContextLayer(
            role="system",
            layer_name="system_prompt",
            content=sys_msg.content or "",
        )

        # --- Turn attachment ---
        turn_attachment = self.build_turn_attachment(state, api_health)

        # --- Tool definitions (FR-004, FR-005) ---
        tool_definitions = self._build_tool_definitions(state)

        # --- Budget (US4) ---
        assembled_no_budget = AssembledContext(
            system_layer=system_layer,
            turn_attachment=turn_attachment,
            tool_definitions=tool_definitions,
        )
        budget = self._budget_estimator.estimate(
            context=assembled_no_budget,
            hard_limit=hard_limit,
            soft_limit=int(hard_limit * 0.80),
        )

        if budget.is_near_limit:
            logger.warning(
                "Context near token limit: estimated=%d, soft=%d, hard=%d",
                budget.estimated_tokens,
                budget.soft_limit_tokens,
                budget.hard_limit_tokens,
            )

        return AssembledContext(
            system_layer=system_layer,
            turn_attachment=turn_attachment,
            tool_definitions=tool_definitions,
            budget=budget,
        )

    # ------------------------------------------------------------------
    # US5 — Context Compaction
    # ------------------------------------------------------------------

    async def maybe_compact_history(
        self,
        messages: list[ChatMessage],
    ) -> tuple[list[ChatMessage], CompactionResult | None]:
        """Apply auto-compaction to conversation history when needed.

        Delegates to ``AutoCompactor.maybe_compact()``.  Returns the
        (possibly compacted) message list and an optional ``CompactionResult``
        describing what was done (``None`` when no compaction was needed).

        Args:
            messages: Full conversation history (most recent turn appended).

        Returns:
            Tuple of (message list, CompactionResult | None).
        """
        from ummaya.context.auto_compact import AutoCompactor  # noqa: PLC0415

        compactor = AutoCompactor(config=self._compaction_config)
        return await compactor.maybe_compact(messages, self._compaction_config)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_tool_definitions(self, state: QueryState) -> list[dict[str, object]]:
        """Build the ordered tool definitions list (core prefix + situational suffix).

        Core tools are sorted by id (stable).  Situational tools are those in
        ``state.active_situational_tools`` that are registered in the registry,
        also sorted by id.

        Emits WARNING when no core tools are registered (breaks cache-prefix
        assumptions from arXiv 2601.06007).
        """
        if self._registry is None:
            return []

        # Core prefix (deterministic, sorted by id — FR-004).  Core tool
        # schemas are stable across turns, so cache the expensive Pydantic JSON
        # schema export and invalidate only when the active core id set changes.
        core_tools = self._registry.core_tools()
        core_cache_key = tuple(tool.id for tool in core_tools)
        if core_cache_key != self._core_tool_defs_cache_key:
            self._core_tool_defs_cache = [tool.to_openai_tool() for tool in core_tools]
            self._core_tool_defs_cache_key = core_cache_key
        core_defs = self._core_tool_defs_cache

        # Situational suffix (dynamic, sorted by id — FR-004)
        situational_defs: list[dict[str, object]] = []
        active_ids = sorted(state.active_situational_tools)
        for tool_id in active_ids:
            try:
                tool = self._registry.find(tool_id)
                if not tool.is_core:
                    situational_defs.append(tool.to_openai_tool())
            except Exception:  # noqa: BLE001
                logger.warning("Active situational tool not found in registry: %s", tool_id)

        if (
            not core_defs
            and (situational_defs or not active_ids)
            and self._registry
            and len(self._registry) > 0
        ):
            logger.warning(
                "No core tools registered; all tools are situational. "
                "This breaks prompt-cache prefix assumptions (arXiv 2601.06007)."
            )

        return list(core_defs) + situational_defs

    def _estimate_tool_defs_tokens(self, defs: list[dict[str, object]]) -> int:
        """Rough token estimate for a list of tool definition dicts."""
        from ummaya.engine.tokens import estimate_tokens  # noqa: PLC0415

        return estimate_tokens(json.dumps(defs))
