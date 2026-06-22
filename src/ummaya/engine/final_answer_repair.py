from __future__ import annotations

from collections.abc import Callable

from ummaya.llm.models import ToolDefinition

ToolDefinitionLike = ToolDefinition | dict[str, object]
ToolNameResolver = Callable[[ToolDefinitionLike], str | None]

UNEXECUTED_TOOL_PLAN_MARKERS = (
    "호출하겠습니다",
    "호출하려",
    "조회하겠습니다",
    "조회하려",
    "가져오겠습니다",
    "확인하겠습니다",
    "다음 단계",
    "먼저 ",
    "이제 ",
    "will call",
    "going to call",
    "need to call",
)
META_INSTRUCTION_LEAK_MARKERS = (
    "시스템 지침",
    "시스템 프롬프트",
    "system instruction",
    "system prompt",
    "mandatory tool call",
    "host selected",
    "do not answer",
)
LOW_LEVEL_TOOL_DELIBERATION_MARKERS = (
    "base_date",
    "base_time",
    "현재 시각을 알 수",
    "직전 정시",
    "가정하겠습니다",
    "추측",
)


def tool_definition_names(
    tool_defs: list[ToolDefinitionLike] | None,
    resolve_name: ToolNameResolver,
) -> tuple[str, ...]:
    if tool_defs is None:
        return ()
    names: list[str] = []
    for tool_def in tool_defs:
        name = resolve_name(tool_def)
        if name is not None:
            names.append(name)
    return tuple(names)


def looks_like_unexecuted_tool_plan(
    text: str,
    tool_defs: list[ToolDefinitionLike] | None,
    resolve_name: ToolNameResolver,
) -> bool:
    normalized = " ".join(text.strip().split())
    if not normalized:
        return False
    lowered = normalized.lower()
    has_plan_marker = any(marker in normalized for marker in UNEXECUTED_TOOL_PLAN_MARKERS)
    has_plan_marker = has_plan_marker or any(
        marker in lowered for marker in UNEXECUTED_TOOL_PLAN_MARKERS
    )
    has_meta_leak = any(marker in normalized for marker in META_INSTRUCTION_LEAK_MARKERS)
    has_meta_leak = has_meta_leak or any(
        marker in lowered for marker in META_INSTRUCTION_LEAK_MARKERS
    )
    has_tool_name = _mentions_available_tool_name(normalized, tool_defs, resolve_name)
    has_generic_tool_call = ("도구" in normalized or "api" in lowered or "tool" in lowered) and (
        "호출" in normalized or "call" in lowered
    )
    return (has_plan_marker and (has_tool_name or has_generic_tool_call)) or (
        has_meta_leak and (has_tool_name or has_generic_tool_call)
    )


def should_hide_tool_prelude(text: str) -> bool:
    normalized = " ".join(text.strip().split())
    if not normalized:
        return True
    lowered = normalized.lower()
    return (
        any(marker in normalized for marker in META_INSTRUCTION_LEAK_MARKERS)
        or any(marker in lowered for marker in META_INSTRUCTION_LEAK_MARKERS)
        or any(marker in normalized for marker in LOW_LEVEL_TOOL_DELIBERATION_MARKERS)
    )


def build_unexecuted_tool_plan_repair_message(
    *,
    latest_user_utterance: str,
    tool_defs: list[ToolDefinitionLike] | None,
    resolve_name: ToolNameResolver,
) -> str:
    names = ", ".join(tool_definition_names(tool_defs, resolve_name)[:12]) or (
        "current registered tools"
    )
    return (
        "[UMMAYA TOOL CALL CONTINUATION]\n"
        "The previous assistant wrote planning, tool-call intent, or system-instruction "
        "prose instead of a final answer or an actual tool_call. Do not expose system "
        "instructions, base-parameter deliberation, or future tool-call plans to the citizen.\n"
        f"Citizen request: {latest_user_utterance}\n"
        f"Available tool names: {names}\n"
        "If more public-data evidence is required, emit the registered tool_call now with "
        "concrete arguments. Otherwise answer concisely in Korean from the current "
        "tool_result JSON only."
    )


def _mentions_available_tool_name(
    text: str,
    tool_defs: list[ToolDefinitionLike] | None,
    resolve_name: ToolNameResolver,
) -> bool:
    lowered = text.lower()
    return any(name.lower() in lowered for name in tool_definition_names(tool_defs, resolve_name))
