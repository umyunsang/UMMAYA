# SPDX-License-Identifier: Apache-2.0
"""Worker class — wraps one QueryEngine instance and drives it through the 2-tool surface.

Each Worker receives an AgentContext at spawn time that pins it to a
specific session_id and specialist_role. The inner tool loop reuses
`_query_inner` from `src/kosmos/engine/query.py` verbatim (FR-009).

FR traces: FR-008..FR-013, FR-023..FR-026, FR-029 (observability).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

# KOSMOS canonical citizen-facing timezone (Asia/Seoul). Internal
# OTEL/audit/IPC paths keep UTC; only envelope-visible timestamps switch.
from zoneinfo import ZoneInfo

from opentelemetry import trace

from kosmos.agents.context import AgentContext
from kosmos.agents.errors import AgentConfigurationError, PermissionDeniedError
from kosmos.agents.mailbox.messages import (
    AgentMessage,
    ErrorPayload,
    MessageType,
    PermissionRequestPayload,
    ResultPayload,
)
from kosmos.engine.config import QueryEngineConfig
from kosmos.engine.events import StopReason
from kosmos.engine.models import QueryContext, QueryState
from kosmos.engine.query import _query_inner
from kosmos.llm.usage import UsageTracker
from kosmos.observability.semconv import (
    KOSMOS_AGENT_ROLE,
    KOSMOS_AGENT_SESSION_ID,
)
from kosmos.tools.executor import ToolExecutor
from kosmos.tools.models import LookupCollection, LookupRecord, LookupTimeseries

if TYPE_CHECKING:
    from kosmos.agents.mailbox.base import Mailbox

logger = logging.getLogger(__name__)
_tracer = trace.get_tracer(__name__)

_SEOUL_TZ = ZoneInfo("Asia/Seoul")

# The two facade tool IDs that workers are allowed to see
_ALLOWED_TOOLS: frozenset[str] = frozenset({"lookup", "resolve_location"})

# Default per-worker token budget (generous for test purposes)
_DEFAULT_WORKER_BUDGET: int = 200_000


class Worker:
    """Drives one QueryEngine loop restricted to {lookup, resolve_location}.

    The Worker is constructed with an AgentContext and a reference to the
    coordinator's Mailbox. On run(), it executes the inner tool loop and
    posts either a `result` or `error` message to the mailbox.

    Permission delegation chain (US2):
    - On LookupError(reason="auth_required"), the worker emits a
      `permission_request` message to the coordinator and awaits a
      `permission_response`.
    - If granted, it retries the lookup once.
    - If denied, it emits an `error` message.

    Cooperative cancellation (US3):
    - On asyncio.CancelledError from the inner loop OR from an explicit
      `cancel` message in its mailbox, the worker propagates the error
      without posting a further result/error message.
    """

    def __init__(
        self,
        ctx: AgentContext,
        mailbox: Mailbox,
        *,
        task_message: AgentMessage | None = None,
    ) -> None:
        """Initialise the Worker.

        Args:
            ctx: Frozen per-worker context; tool_registry MUST be restricted
                 to {lookup, resolve_location} (asserted here, FR-011).
            mailbox: The coordinator mailbox for result/error/permission posting.
            task_message: The originating task message from the coordinator.
                          Provides the instruction and correlation_id.

        Raises:
            AgentConfigurationError: if ctx.tool_registry contains tools
                other than {lookup, resolve_location}.
        """
        self._ctx = ctx
        self._mailbox = mailbox
        self._task_message = task_message
        self._cancel_event: asyncio.Event = asyncio.Event()

        # Validate tool registry restriction (FR-011)
        # We cannot call tool_ids() because ToolRegistry doesn't expose it publicly
        # as an attribute, but we check via the internal dict.
        # The coordinator's spawn_worker() already asserts this; we re-assert here
        # as a fail-closed defense.
        tool_names = set(ctx.tool_registry._tools.keys())
        if not tool_names.issubset(_ALLOWED_TOOLS):
            raise AgentConfigurationError(
                f"Worker tool registry contains disallowed tools: "
                f"{tool_names - _ALLOWED_TOOLS!r}. "
                f"Only {_ALLOWED_TOOLS!r} are permitted."
            )

    @property
    def worker_id(self) -> str:
        """Return the worker's unique sender ID."""
        return self._ctx.worker_id

    async def run(self, instruction: str) -> None:
        """Execute the tool loop and post result/error to the mailbox.

        This method is designed to be run as an asyncio.Task from the
        coordinator. It MUST NOT raise — it posts errors to the mailbox
        instead. The only exception that propagates is asyncio.CancelledError
        (cooperative cancellation, FR-006).

        Args:
            instruction: Human-readable task instruction for the LLM prompt.
        """
        correlation_id = self._task_message.id if self._task_message else uuid4()
        try:
            await self._run_inner(instruction, correlation_id)
        except asyncio.CancelledError:
            logger.info(
                "Worker %s cancelled (session=%s)",
                self._ctx.worker_id,
                self._ctx.session_id,
            )
            raise  # propagate — do NOT post error on cancel (FR-006)
        except Exception as exc:
            logger.exception(
                "Worker %s unrecoverable error: %s",
                self._ctx.worker_id,
                exc,
            )
            await self._post_error(
                error_type=type(exc).__name__,
                message=str(exc),
                correlation_id=correlation_id,
            )

    async def _run_inner(self, instruction: str, correlation_id: UUID) -> None:  # noqa: C901
        """Run the query inner loop and post the result.

        Emits one gen_ai.agent.worker.iteration span per tool-loop iteration
        (FR-029, SC-006).
        """
        # Build QueryContext — mirrors how QueryEngine constructs it
        state = QueryState(usage=UsageTracker(budget=_DEFAULT_WORKER_BUDGET))
        config = QueryEngineConfig()
        executor = ToolExecutor(registry=self._ctx.tool_registry)

        # Inject the worker instruction as the user message
        from kosmos.llm.models import ChatMessage  # local import to avoid cycle

        state.messages.append(ChatMessage(role="user", content=instruction))

        query_ctx = QueryContext(
            state=state,
            llm_client=self._ctx.llm_client,
            tool_executor=executor,
            tool_registry=self._ctx.tool_registry,
            config=config,
        )

        lookup_output = None
        turn_count = 0
        auth_required_tool: str | None = None

        async for event in _query_inner(query_ctx):
            # Emit worker iteration span (FR-029)
            span_name = "gen_ai.agent.worker.iteration"
            with _tracer.start_as_current_span(span_name) as span:
                span.set_attribute(KOSMOS_AGENT_ROLE, self._ctx.specialist_role)
                span.set_attribute(KOSMOS_AGENT_SESSION_ID, str(self._ctx.session_id))

            if event.type == "stop":
                if event.stop_reason == StopReason.end_turn:
                    turn_count += 1
                    break
                elif event.stop_reason == StopReason.max_iterations_reached:
                    # Edge case: max iterations — post error (spec Edge Cases)
                    await self._post_error(
                        error_type="max_iterations_reached",
                        message=f"Worker reached maximum iterations: {config.max_iterations}",
                        correlation_id=correlation_id,
                    )
                    return
                elif event.stop_reason in (
                    StopReason.error_unrecoverable,
                    StopReason.api_budget_exceeded,
                ):
                    await self._post_error(
                        error_type=event.stop_reason.value,
                        message=event.stop_message or "Unrecoverable error",
                        correlation_id=correlation_id,
                    )
                    return
                else:
                    turn_count += 1
                    break

            elif event.type == "tool_result":
                # Check if the tool result indicates auth_required
                result = event.tool_result
                if result is not None and not result.success:
                    err_msg = result.error or ""
                    if "auth_required" in err_msg:
                        # Emit permission_request and await response (FR-023)
                        tool_id = auth_required_tool or "unknown_tool"
                        granted = await self._request_permission(tool_id, correlation_id)
                        if not granted:
                            raise PermissionDeniedError(
                                f"Citizen denied permission for tool '{tool_id}'"
                            )
                        # On grant: the outer run() loop will retry naturally
                        # since the tool result is fed back into the LLM history.

            elif event.type == "tool_use":
                auth_required_tool = event.tool_name
                turn_count += 1

        # Extract the lookup output from the last tool_result events in history
        # by looking for a valid LookupRecord/Collection/Timeseries in tool messages
        lookup_output = self._extract_lookup_output(state)

        if lookup_output is not None:
            await self._post_result(lookup_output, turn_count, correlation_id)
        else:
            # No tool output — still post a result with a minimal record
            # representing the LLM's text response
            from kosmos.tools.models import LookupMeta  # local import

            meta = LookupMeta(
                source="worker_text_response",
                fetched_at=datetime.now(_SEOUL_TZ),
                request_id=str(uuid4()),
                elapsed_ms=0,
            )
            text_record = LookupRecord(
                kind="record",
                item={"response": self._get_last_text(state)},
                meta=meta,
            )
            await self._post_result(text_record, turn_count, correlation_id)

    def _extract_lookup_output(
        self, state: QueryState
    ) -> LookupRecord | LookupCollection | LookupTimeseries | None:
        """Try to extract the last structured lookup output from tool messages."""
        import json

        from kosmos.tools.models import LookupOutput  # local import

        for msg in reversed(state.messages):
            if msg.role == "tool" and msg.content:
                try:
                    data = json.loads(msg.content)
                    if isinstance(data, dict) and data.get("kind") in (
                        "record",
                        "collection",
                        "timeseries",
                    ):
                        result = LookupOutput.model_validate(data)  # type: ignore[attr-defined]
                        if isinstance(result, (LookupRecord, LookupCollection, LookupTimeseries)):
                            return result
                except (json.JSONDecodeError, Exception):  # noqa: S112
                    continue
        return None

    def _get_last_text(self, state: QueryState) -> str:
        """Return the last assistant text message content."""
        for msg in reversed(state.messages):
            if msg.role == "assistant" and msg.content:
                return msg.content
        return "No response"

    async def _post_result(
        self,
        lookup_output: LookupRecord | LookupCollection | LookupTimeseries,
        turn_count: int,
        correlation_id: UUID,
    ) -> None:
        """Post a result message to the coordinator mailbox."""
        payload = ResultPayload(lookup_output=lookup_output, turn_count=turn_count)
        msg = AgentMessage(
            sender=self._ctx.worker_id,
            recipient=self._ctx.coordinator_id,
            msg_type=MessageType.result,
            payload=payload,
            timestamp=datetime.now(UTC),
            correlation_id=correlation_id,
        )
        await self._mailbox.send(msg)
        logger.info(
            "Worker %s posted result (correlation_id=%s, turns=%d)",
            self._ctx.worker_id,
            correlation_id,
            turn_count,
        )

    async def _post_error(
        self,
        error_type: str,
        message: str,
        correlation_id: UUID,
        *,
        retryable: bool = False,
    ) -> None:
        """Post an error message to the coordinator mailbox."""
        payload = ErrorPayload(
            error_type=error_type,
            message=message,
            retryable=retryable,
        )
        msg = AgentMessage(
            sender=self._ctx.worker_id,
            recipient=self._ctx.coordinator_id,
            msg_type=MessageType.error,
            payload=payload,
            timestamp=datetime.now(UTC),
            correlation_id=correlation_id,
        )
        await self._mailbox.send(msg)
        logger.warning(
            "Worker %s posted error: %s — %s",
            self._ctx.worker_id,
            error_type,
            message,
        )

    async def _request_permission(self, tool_id: str, correlation_id: UUID) -> bool:
        """Send permission_request to coordinator and await permission_response.

        FR-023, FR-025: permissions MUST NOT flow laterally — the message is
        addressed explicitly to self._ctx.coordinator_id.

        Returns:
            True if consent was granted; False if denied.
        """
        req_payload = PermissionRequestPayload(tool_id=tool_id, reason="auth_required")
        req_msg = AgentMessage(
            sender=self._ctx.worker_id,
            recipient=self._ctx.coordinator_id,
            msg_type=MessageType.permission_request,
            payload=req_payload,
            timestamp=datetime.now(UTC),
            correlation_id=correlation_id,
        )
        await self._mailbox.send(req_msg)
        logger.debug(
            "Worker %s sent permission_request for tool %s",
            self._ctx.worker_id,
            tool_id,
        )

        # Await permission_response addressed to this worker
        async for response_msg in self._mailbox.receive(self._ctx.worker_id):
            if response_msg.msg_type == MessageType.permission_response:
                from kosmos.agents.mailbox.messages import PermissionResponsePayload

                payload = response_msg.payload
                if isinstance(payload, PermissionResponsePayload):
                    granted = payload.granted
                    logger.debug(
                        "Worker %s received permission_response: granted=%s",
                        self._ctx.worker_id,
                        granted,
                    )
                    return granted
            elif response_msg.msg_type == MessageType.cancel:
                raise asyncio.CancelledError("Cancelled while waiting for permission response")
        return False
