# SPDX-License-Identifier: Apache-2.0
"""Standalone per-turn query loop for the UMMAYA Query Engine.

The ``query()`` async generator is the core execution loop that drives a single
turn of the engine: preprocess → immutable snapshot → LLM stream → tool dispatch
→ decide.  It is separated from ``QueryEngine`` to enable independent unit
testing (FR-012).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from opentelemetry import context as _otel_context
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from pydantic import ValidationError

from ummaya.engine.events import QueryEvent, StopReason
from ummaya.engine.models import QueryContext
from ummaya.engine.preprocessing import PreprocessingPipeline
from ummaya.engine.tokens import estimate_tokens
from ummaya.llm.errors import BudgetExceededError, StreamInterruptedError
from ummaya.llm.models import ChatMessage, FunctionCall, ToolCall, ToolDefinition
from ummaya.observability import (
    ERROR_TYPE,
    GEN_AI_AGENT_NAME,
    GEN_AI_CONVERSATION_ID,
    GEN_AI_OPERATION_NAME,
)
from ummaya.tools.errors import ToolNotFoundError
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.models import ToolResult
from ummaya.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from ummaya.permissions.models import SessionContext

logger = logging.getLogger(__name__)

_tracer = trace.get_tracer(__name__)


# ---------------------------------------------------------------------------
# Internal helpers for streaming tool-call accumulation
# ---------------------------------------------------------------------------


@dataclass
class _PendingToolCall:
    """Accumulator for streaming tool_call_delta events from a single tool."""

    index: int
    tool_call_id: str = ""
    function_name: str = ""
    function_args: str = ""


def _assemble_tool_calls(
    pending: dict[int, _PendingToolCall],
) -> list[ToolCall]:
    """Convert accumulated streaming deltas into finalized ToolCall objects.

    Returns tool calls sorted by their original stream index to preserve
    the order in which the model requested them.
    """
    return [
        ToolCall(
            id=p.tool_call_id,
            function=FunctionCall(
                name=p.function_name,
                arguments=p.function_args,
            ),
        )
        for p in sorted(pending.values(), key=lambda p: p.index)
    ]


def _tool_definition_name(tool_def: ToolDefinition | dict[str, object]) -> str | None:
    """Extract a function name from an OpenAI tool definition."""

    if isinstance(tool_def, ToolDefinition):
        return tool_def.function.name
    function = tool_def.get("function")
    if not isinstance(function, dict):
        return None
    name = function.get("name")
    return name if isinstance(name, str) else None


def _export_turn_tool_definitions(
    tool_registry: ToolRegistry,
    tool_ids: tuple[str, ...],
) -> list[dict[str, object]]:
    """Export selected concrete adapter schemas in ranking order."""

    tool_defs: list[dict[str, object]] = []
    seen: set[str] = set()
    for tool_id in tool_ids:
        if tool_id in seen:
            continue
        seen.add(tool_id)
        try:
            tool = tool_registry.find(tool_id)
        except ToolNotFoundError:
            logger.warning("Selected turn tool disappeared from registry: %s", tool_id)
            continue
        tool_defs.append(tool.to_openai_tool())
    return tool_defs


def _latest_successful_tool_payload(messages: list[ChatMessage]) -> dict[str, object] | None:
    """Return the latest non-error tool-result JSON payload, if present."""

    for message in reversed(messages):
        if message.role != "tool" or not message.content:
            continue
        try:
            data = json.loads(message.content)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict) or data.get("kind") == "error":
            continue
        return cast("dict[str, object]", data)
    return None


def _latest_user_utterance(messages: list[ChatMessage]) -> str:
    """Return the latest citizen utterance, ignoring repair observations."""

    for message in reversed(messages):
        if message.role != "user" or not message.content:
            continue
        if message.content.startswith("[UMMAYA FINAL ANSWER OBSERVATION]"):
            continue
        return message.content
    return ""


def _should_repair_successful_tool_final_answer(text: str) -> bool:
    """Detect final prose that ignores an already successful tool result."""

    normalized = " ".join(text.strip().split())
    if not normalized:
        return True
    lowered = normalized.lower()
    retry_markers = (
        "다른 검색어로 재시도",
        "다른 검색어 / 다른 지역",
        "다른 지역으로 재시도",
        "재시도하시겠습니까",
        "다시 검색해",
        "try another search",
        "try a different search",
        "would you like me to retry",
    )
    if any(marker in lowered for marker in retry_markers):
        return True

    wrapper_markers = (
        "도구가 반환한 메시지",
        "컬렉션 아이템 배열",
        "공식 agency 채널 안내",
    )
    return any(marker in normalized for marker in wrapper_markers)


def _remove_unneeded_mock_disclosure(
    text: str,
    payload: dict[str, object] | None,
) -> str:
    """Strip mock disclosure text from live successful tool answers."""

    if _payload_contains_mock_marker(payload):
        return text
    if "실제 행정 영향" not in text and "시연(모의)" not in text:
        return text
    fragments = (
        "이 결과는 실제 행정 영향이 없는 시연(모의) 결과입니다.",
        "실제 행정 영향이 없는 시연(모의) 결과입니다.",
        "접수번호는 시연용이며 실제 기관 포털에서 조회되지 않습니다.",
    )
    cleaned = text
    for fragment in fragments:
        cleaned = cleaned.replace(fragment, "")
    lines = [
        line.rstrip() for line in cleaned.splitlines() if not ("시연" in line and "모의" in line)
    ]
    return "\n".join(lines).strip()


def _remove_generic_retry_footer(text: str) -> str:
    """Drop generic retry footer lines from an otherwise useful final answer."""

    fragments = (
        "다른 검색어 / 다른 지역 / 다른 도구로 재시도하시겠습니까?",
        "다른 검색어 / 다른 지역 / 다른 도구로 재시도하시겠습니까",
        "다른 검색어 / 다른 도구 / 다른 매개변수로 재시도하시겠습니까?",
        "다른 검색어 / 다른 도구 / 다른 매개변수로 재시도하시겠습니까",
        "다른 검색어로 재시도하시겠습니까?",
        "다른 검색어로 재시도하시겠습니까",
        "재시도하시겠습니까?",
    )
    cleaned = text
    for fragment in fragments:
        cleaned = cleaned.replace(fragment, "")
    lines = [
        line.rstrip() for line in cleaned.splitlines() if not _line_is_generic_retry_footer(line)
    ]
    return "\n".join(lines).strip()


def _line_is_generic_retry_footer(line: str) -> bool:
    """Return True when a single final-answer line is only a retry affordance."""

    normalized = " ".join(line.strip().split())
    if not normalized:
        return False
    return "재시도" in normalized and (
        "다른 검색어" in normalized
        or "다른 지역" in normalized
        or "다른 도구" in normalized
        or "다른 매개변수" in normalized
    )


def _payload_contains_mock_marker(value: object) -> bool:
    """Return True when a tool result carries mock-mode transparency evidence."""

    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"_mode", "transparency_mode"} and item == "mock":
                return True
            if key == "mock" and item is True:
                return True
            if _payload_contains_mock_marker(item):
                return True
    elif isinstance(value, list):
        return any(_payload_contains_mock_marker(item) for item in value)
    return False


def _final_answer_repair_message(
    *,
    payload: dict[str, object],
    latest_user_utterance: str,
) -> str:
    """Build a no-tools observation that forces answer synthesis from tool data."""

    payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    return (
        "[UMMAYA FINAL ANSWER OBSERVATION]\n"
        "The previous assistant turn produced a generic retry, handoff, raw-tool "
        "wrapper, or mock-disclosure answer after a successful tool_result. "
        "Do not call another tool. Do not ask the citizen to retry. Do not call "
        "a live public-data result a mock or simulation result. Produce a concise "
        "Korean final answer using only the latest successful tool_result JSON.\n"
        f"Citizen request: {latest_user_utterance}\n"
        f"Latest successful tool_result JSON: {payload_json}\n"
        "If items is empty, state that the API returned zero rows for the requested "
        "parameters. If items is non-empty, summarize concrete returned fields."
    )


# ---------------------------------------------------------------------------
# Concurrent tool dispatch (partition-sort algorithm, R-004)
# ---------------------------------------------------------------------------


async def dispatch_tool_calls(  # noqa: C901
    tool_calls: list[ToolCall],
    tool_registry: ToolRegistry,
    tool_executor: ToolExecutor,
    *,
    session_context: SessionContext | None = None,
) -> list[ToolResult]:
    """Dispatch multiple tool calls with concurrency optimization.

    Partition-sort algorithm:
    1. Look up each tool's ``is_concurrency_safe`` flag.
    2. Group consecutive concurrency-safe tools together.
    3. Execute each safe group concurrently via ``asyncio.TaskGroup``.
    4. Execute non-safe tools sequentially.
    5. Return results in the same order as the input ``tool_calls``.

    Args:
        tool_calls: List of ToolCall objects from the LLM response.
        tool_registry: Registry for looking up tool concurrency flags.
        tool_executor: Executor for dispatching individual calls.
        session_context: Optional session context (used for OTEL correlation).

    Returns:
        List of ToolResult objects, one per input tool_call, in order.
    """
    if not tool_calls:
        return []

    # Build (index, tool_call, is_safe) tuples
    indexed: list[tuple[int, ToolCall, bool]] = []
    for i, tc in enumerate(tool_calls):
        try:
            tool = tool_registry.find(tc.function.name)
            is_safe = tool.is_concurrency_safe
        except ToolNotFoundError:
            is_safe = False  # unknown tools dispatch sequentially (fail-closed)
        indexed.append((i, tc, is_safe))

    # Partition into consecutive groups of same concurrency type
    results: list[ToolResult | None] = [None] * len(tool_calls)
    group: list[tuple[int, ToolCall]] = []
    group_safe: bool | None = None

    async def _dispatch_one(tc: ToolCall) -> ToolResult:
        """Dispatch a single tool call via the executor."""
        if tc.function.name in {"find", "locate", "check", "send"}:
            return await _dispatch_root_primitive(
                tc,
                tool_registry,
                tool_executor,
                session_context=session_context,
            )
        try:
            tool = tool_registry.find(tc.function.name)
        except ToolNotFoundError:
            return await tool_executor.dispatch(tc.function.name, tc.function.arguments)
        gate = tool.policy.citizen_facing_gate if tool.policy is not None else None
        if gate in {None, "read-only"}:
            return await tool_executor.dispatch(
                tc.function.name,
                tc.function.arguments,
                tool_call_id=tc.id,
            )
        primitive = tool.primitive
        if primitive is None:
            return ToolResult(
                tool_id=tc.function.name,
                success=False,
                error=f"{tc.function.name} is missing primitive metadata for gated dispatch.",
                error_type="schema_mismatch",
            )
        return await _dispatch_concrete_adapter(
            tc,
            primitive,
            tool_executor,
            session_context=session_context,
        )

    async def _flush_group(items: list[tuple[int, ToolCall]], safe: bool) -> None:
        """Execute a group of tool calls, concurrently if safe."""
        if not items:
            return
        if safe and len(items) > 1:
            async with asyncio.TaskGroup() as tg:
                tasks = [(idx, tg.create_task(_dispatch_one(tc))) for idx, tc in items]
            for idx, task in tasks:
                results[idx] = task.result()
        else:
            for idx, tc in items:
                results[idx] = await _dispatch_one(tc)

    for i, tc, is_safe in indexed:
        if group_safe is not None and is_safe != group_safe:
            await _flush_group(group, group_safe)
            group = []
        group_safe = is_safe
        group.append((i, tc))

    # Flush remaining group
    if group and group_safe is not None:
        await _flush_group(group, group_safe)

    return [r for r in results if r is not None]


async def _dispatch_root_primitive(
    tc: ToolCall,
    tool_registry: ToolRegistry,
    tool_executor: ToolExecutor,
    *,
    session_context: SessionContext | None,
) -> ToolResult:
    """Fan out an LLM-visible primitive call to the selected adapter id."""

    primitive = tc.function.name
    try:
        primitive_tool = tool_registry.find(primitive)
    except ToolNotFoundError as exc:
        return ToolResult(
            tool_id=primitive,
            success=False,
            error=str(exc),
            error_type="not_found",
        )

    try:
        raw_args = json.loads(tc.function.arguments)
        validated = primitive_tool.input_schema.model_validate(raw_args)
    except (TypeError, json.JSONDecodeError, ValidationError) as exc:
        return ToolResult(
            tool_id=primitive,
            success=False,
            error=str(exc),
            error_type="validation",
        )

    target_tool_id = getattr(validated, "tool_id", None)
    params = getattr(validated, "params", None)
    if not isinstance(target_tool_id, str) or not isinstance(params, dict):
        return ToolResult(
            tool_id=primitive,
            success=False,
            error=f"{primitive} requires tool_id and params.",
            error_type="validation",
        )
    if target_tool_id == primitive:
        return ToolResult(
            tool_id=primitive,
            success=False,
            error=f"{primitive} cannot target itself.",
            error_type="validation",
        )
    params = _normalize_root_primitive_adapter_params(
        primitive=primitive,
        target_tool_id=target_tool_id,
        params=params,
    )

    request_id = tc.id or f"{primitive}-call"
    if primitive == "find":
        output = await tool_executor.invoke(
            target_tool_id,
            params,
            request_id=request_id,
            session_identity=session_context,
        )
    else:
        output = await tool_executor.invoke_raw(
            target_tool_id,
            params,
            request_id=request_id,
            session_identity=session_context,
        )

    data = _primitive_output_dict(output)
    if data.get("kind") == "error":
        return ToolResult(
            tool_id=primitive,
            success=False,
            error=str(data.get("message") or data),
            error_type="execution",
        )
    return ToolResult(tool_id=primitive, success=True, data=data)


def _normalize_root_primitive_adapter_params(
    *,
    primitive: str,
    target_tool_id: str,
    params: dict[str, object],
) -> dict[str, object]:
    """Remove wrapper metadata accidentally duplicated inside adapter params."""
    nested_tool_id = params.get("tool_id")
    if nested_tool_id == target_tool_id:
        return {key: value for key, value in params.items() if key != "tool_id"}
    if target_tool_id == primitive and isinstance(nested_tool_id, str):
        return {key: value for key, value in params.items() if key != "tool_id"}
    return params


async def _dispatch_concrete_adapter(
    tc: ToolCall,
    primitive: str,
    tool_executor: ToolExecutor,
    *,
    session_context: SessionContext | None,
) -> ToolResult:
    """Dispatch a directly model-facing concrete adapter call."""

    try:
        raw_args = json.loads(tc.function.arguments)
    except (TypeError, json.JSONDecodeError) as exc:
        return ToolResult(
            tool_id=tc.function.name,
            success=False,
            error=str(exc),
            error_type="validation",
        )
    if not isinstance(raw_args, dict):
        return ToolResult(
            tool_id=tc.function.name,
            success=False,
            error=f"{tc.function.name} requires a JSON object argument.",
            error_type="validation",
        )

    request_id = tc.id or f"{tc.function.name}-call"
    if primitive == "find":
        output = await tool_executor.invoke(
            tc.function.name,
            raw_args,
            request_id=request_id,
            session_identity=session_context,
        )
    else:
        output = await tool_executor.invoke_raw(
            tc.function.name,
            raw_args,
            request_id=request_id,
            session_identity=session_context,
        )

    data = _primitive_output_dict(output)
    if data.get("kind") == "error":
        return ToolResult(
            tool_id=tc.function.name,
            success=False,
            error=str(data.get("message") or data),
            error_type="execution",
        )
    return ToolResult(tool_id=tc.function.name, success=True, data=data)


def _primitive_output_dict(output: object) -> dict[str, object]:
    """Convert primitive facade output to ToolResult data."""

    model_dump = getattr(output, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        if isinstance(dumped, dict):
            return cast("dict[str, object]", dumped)
        return {"result": dumped}
    if isinstance(output, dict):
        return output
    return {"result": output}


# ---------------------------------------------------------------------------
# Public: per-turn query generator
# ---------------------------------------------------------------------------


async def query(ctx: QueryContext) -> AsyncIterator[QueryEvent]:  # noqa: C901
    """Execute one turn of the query loop.

    The loop:
    1. Create immutable message snapshot: ``list(ctx.state.messages)``
    2. Stream LLM completion with tool definitions
    3. Yield ``text_delta`` events as content streams
    4. Token usage is debited by ``LLMClient.stream()`` internally
    5. If tool_calls in response:
       a. Yield ``tool_use`` events for each call
       b. Dispatch via ``dispatch_tool_calls()``; safe groups run concurrently
       c. Yield ``tool_result`` events in stable input order
       d. Append tool results to ``ctx.state.messages``
       e. Yield ``usage_update``
       f. Continue loop (iteration += 1)
    6. If no tool_calls: yield ``usage_update``, yield ``stop``, return
    7. If iteration >= ``config.max_iterations``: yield ``stop(max_iterations_reached)``

    Args:
        ctx: Per-turn context with references to state, LLM client, tools, config.

    Yields:
        QueryEvent stream as described above.
    """
    # Open the parent OTel span manually (not via context manager) so that the
    # span lifetime covers the entire async-generator consumption, including
    # every yield point.  A context-manager approach would close the span at the
    # first ``yield``, which is incorrect for async generators.
    span = _tracer.start_span("invoke_agent ummaya-query")

    # Required attributes (contracts § Span 1)
    span.set_attribute(GEN_AI_OPERATION_NAME, "invoke_agent")
    span.set_attribute(GEN_AI_AGENT_NAME, "ummaya-query")

    # Conditional attribute: conversation ID — only when session_context is present.
    # FR-011: do NOT include user_message/query_text (PII).  session_id is a
    # random UUID and is not personal data under PIPA.
    if ctx.session_context is not None:
        span.set_attribute(GEN_AI_CONVERSATION_ID, str(ctx.session_context.session_id))

    # Attach the span as the current span in this asyncio context so that all
    # child coroutines (LLM client, tool executor) inherit the parent via
    # contextvars propagation.  Using context_api.attach/detach rather than
    # start_as_current_span avoids premature span closure at the first ``yield``,
    # which is the central problem with async generators and context managers.
    ctx_with_span = trace.set_span_in_context(span)
    token = _otel_context.attach(ctx_with_span)

    try:
        async for event in _query_inner(ctx):
            yield event
    except Exception as exc:
        # Map exception → ERROR status per contracts § Span 1 status mapping.
        span.set_status(Status(StatusCode.ERROR))
        span.record_exception(exc)
        span.set_attribute(ERROR_TYPE, exc.__class__.__name__)
        raise
    finally:
        # Detach then close span — always, regardless of normal exit, exception,
        # or mid-stream generator abandonment (generator.close() / .throw()).
        _otel_context.detach(token)
        span.end()


async def _query_inner(ctx: QueryContext) -> AsyncIterator[QueryEvent]:  # noqa: C901
    """Inner async generator: core query loop without span management.

    Separated so that ``query()`` can manage the OTel span lifetime across the
    full generator consumption while keeping the loop logic self-contained.
    """
    iteration = 0
    stream_interrupted_count = 0
    final_answer_repair_count = 0
    force_no_tools_next_turn = False
    pipeline = PreprocessingPipeline()

    while iteration < ctx.config.max_iterations:
        # --- Preprocessing: compress context if approaching window limit ---
        total_tokens = sum(estimate_tokens(m.content or "") for m in ctx.state.messages)
        token_threshold = int(ctx.config.context_window * ctx.config.preprocessing_threshold)
        if total_tokens > token_threshold:
            logger.info(
                "Preprocessing triggered: %d tokens > %d threshold",
                total_tokens,
                token_threshold,
            )
            ctx.state.messages[:] = pipeline.run(
                ctx.state.messages,
                ctx.config,
                # turn_count tracks completed turns; preprocessing runs during
                # the current in-progress turn after the user message is added.
                current_turn=ctx.state.turn_count + 1,
            )

        # --- Immutable snapshot for prompt cache stability (R-003) ---
        snapshot = list(ctx.state.messages)
        current_turn_messages = snapshot[ctx.turn_start_message_index :]
        latest_successful_tool_payload = _latest_successful_tool_payload(current_turn_messages)
        buffer_final_answer = latest_successful_tool_payload is not None

        # --- Export tool definitions (sorted for cache stability) ---
        suppress_tools_this_turn = force_no_tools_next_turn
        if suppress_tools_this_turn:
            tool_defs: list[ToolDefinition | dict[str, object]] | None = None
            force_no_tools_next_turn = False
        else:
            raw_defs = _export_turn_tool_definitions(
                ctx.tool_registry,
                ctx.turn_tool_ids,
            )
            if not raw_defs:
                raw_defs = ctx.tool_registry.export_core_tools_openai()
            if ctx.allowed_core_tool_ids is not None and not ctx.turn_tool_ids:
                raw_defs = [
                    tool_def
                    for tool_def in raw_defs
                    if _tool_definition_name(tool_def) in ctx.allowed_core_tool_ids
                ]
            tool_defs = list(raw_defs) or None

        # --- Stream LLM completion ---
        pending_calls: dict[int, _PendingToolCall] = {}
        content_parts: list[str] = []
        usage = None

        try:
            async for event in ctx.llm_client.stream(
                snapshot,
                tools=tool_defs,
            ):
                if event.type == "content_delta" and event.content is not None:
                    content_parts.append(event.content)
                    if not buffer_final_answer:
                        yield QueryEvent(type="text_delta", content=event.content)

                elif event.type == "tool_call_delta":
                    idx = event.tool_call_index if event.tool_call_index is not None else 0
                    if idx not in pending_calls:
                        pending_calls[idx] = _PendingToolCall(index=idx)
                    p = pending_calls[idx]
                    if event.tool_call_id:
                        p.tool_call_id = event.tool_call_id
                    if event.function_name:
                        p.function_name = event.function_name
                    if event.function_args_delta:
                        p.function_args += event.function_args_delta

                elif event.type == "usage":
                    usage = event.usage

        except BudgetExceededError:
            # LLMClient.stream() debits usage internally; budget overflow
            # raises BudgetExceededError during iteration.
            yield QueryEvent(
                type="stop",
                stop_reason=StopReason.api_budget_exceeded,
                stop_message="Token budget exceeded during stream",
            )
            return
        except StreamInterruptedError as exc:
            stream_interrupted_count += 1
            if stream_interrupted_count == 1:
                # First interruption: retry the stream once.
                # If partial content was already yielded to the consumer,
                # emit a visible restart signal so the output clearly
                # separates stale fragments from the fresh retry.
                logger.warning(
                    "LLM stream interrupted (attempt %d), retrying: %s",
                    stream_interrupted_count,
                    exc,
                )
                if content_parts:
                    yield QueryEvent(
                        type="text_delta",
                        content="\n[stream interrupted — retrying]\n",
                    )
                continue
            # Second interruption: unrecoverable
            logger.error(
                "LLM stream interrupted again (attempt %d), giving up: %s",
                stream_interrupted_count,
                exc,
            )
            yield QueryEvent(
                type="stop",
                stop_reason=StopReason.error_unrecoverable,
                stop_message=f"LLM stream interrupted: {exc}",
            )
            return
        except asyncio.CancelledError:
            raise  # propagate cancellation without masking
        except Exception as exc:
            logger.exception("LLM stream failed: %s", exc)
            yield QueryEvent(
                type="stop",
                stop_reason=StopReason.error_unrecoverable,
                stop_message=f"LLM stream error: {exc}",
            )
            return

        # Reset per-iteration retry counter so each new iteration gets its own
        # single-retry budget.  A successful stream clears any previous
        # interruption count; the counter only matters within a single attempt.
        stream_interrupted_count = 0

        # --- Assemble assistant message and append to history ---
        assembled_calls = _assemble_tool_calls(pending_calls) if pending_calls else []
        assistant_content = "".join(content_parts) or None

        ctx.state.messages.append(
            ChatMessage(
                role="assistant",
                content=assistant_content,
                tool_calls=assembled_calls or None,
            ),
        )

        if assembled_calls and suppress_tools_this_turn:
            if ctx.state.messages and ctx.state.messages[-1].role == "assistant":
                ctx.state.messages.pop()
            if latest_successful_tool_payload is not None and final_answer_repair_count < 3:
                final_answer_repair_count += 1
                force_no_tools_next_turn = True
                ctx.state.messages.append(
                    ChatMessage(
                        role="user",
                        content=_final_answer_repair_message(
                            payload=latest_successful_tool_payload,
                            latest_user_utterance=_latest_user_utterance(current_turn_messages),
                        )
                        + "\nThe previous assistant tried to call another tool during "
                        "final-answer repair. Answer directly from the provided JSON.",
                    )
                )
                logger.debug(
                    "Suppressed tool call during final-answer repair; retrying final "
                    "answer generation (%d/3)",
                    final_answer_repair_count,
                )
                continue

        # --- No tool calls: yield usage, stop, and return ---
        if not assembled_calls:
            if buffer_final_answer:
                final_text = _remove_unneeded_mock_disclosure(
                    assistant_content or "",
                    latest_successful_tool_payload,
                )
                final_text = _remove_generic_retry_footer(final_text)
                if ctx.state.messages and ctx.state.messages[-1].role == "assistant":
                    ctx.state.messages[-1] = ChatMessage(role="assistant", content=final_text)
                if (
                    _should_repair_successful_tool_final_answer(final_text)
                    and latest_successful_tool_payload is not None
                    and final_answer_repair_count < 2
                ):
                    final_answer_repair_count += 1
                    force_no_tools_next_turn = True
                    ctx.state.messages.append(
                        ChatMessage(
                            role="user",
                            content=_final_answer_repair_message(
                                payload=latest_successful_tool_payload,
                                latest_user_utterance=_latest_user_utterance(current_turn_messages),
                            ),
                        )
                    )
                    logger.debug(
                        "Rejected generic final answer after successful tool result; "
                        "retrying final answer generation (%d/2)",
                        final_answer_repair_count,
                    )
                    continue
                if final_text:
                    yield QueryEvent(type="text_delta", content=final_text)
            if usage:
                yield QueryEvent(type="usage_update", usage=usage)
            yield QueryEvent(type="stop", stop_reason=StopReason.end_turn)
            return

        # --- Yield tool_use events before dispatch ---
        for tc in assembled_calls:
            yield QueryEvent(
                type="tool_use",
                tool_name=tc.function.name,
                tool_call_id=tc.id,
                arguments=tc.function.arguments,
            )

        # --- Dispatch tools (concurrent when safe, sequential otherwise) ---
        tool_results = await dispatch_tool_calls(
            assembled_calls,
            ctx.tool_registry,
            ctx.tool_executor,
            session_context=ctx.session_context,
        )

        # --- Append results to history and yield tool_result events ---
        for tc, result in zip(assembled_calls, tool_results, strict=True):
            if result.success:
                result_content = json.dumps(result.data, ensure_ascii=False)
            else:
                result_content = result.error or "Unknown error"

            ctx.state.messages.append(
                ChatMessage(
                    role="tool",
                    content=result_content,
                    tool_call_id=tc.id,
                ),
            )

            yield QueryEvent(type="tool_result", tool_result=result)

        # --- Yield usage after all tool dispatches (event ordering contract) ---
        if usage:
            yield QueryEvent(type="usage_update", usage=usage)

        iteration += 1
        logger.debug(
            "Query loop iteration %d/%d completed",
            iteration,
            ctx.config.max_iterations,
        )

    # --- Max iterations reached ---
    yield QueryEvent(
        type="stop",
        stop_reason=StopReason.max_iterations_reached,
        stop_message=(f"Reached maximum {ctx.config.max_iterations} iterations per turn"),
    )
