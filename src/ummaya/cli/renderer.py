# SPDX-License-Identifier: Apache-2.0
"""EventRenderer — converts QueryEvent stream into Rich-formatted terminal output.

Supports both plain incremental text rendering and an optional streaming
markdown mode that uses Rich's :class:`~rich.live.Live` display to re-render
the response as a :class:`~rich.markdown.Markdown` block while it is being
streamed.  Korean text is handled correctly because Rich renders full grapheme
clusters without mid-character splits.
"""

from __future__ import annotations

import logging

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.status import Status

from ummaya.cli.themes import Theme, load_theme
from ummaya.engine.events import QueryEvent, StopReason
from ummaya.llm.models import TokenUsage
from ummaya.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stop reason → citizen-facing Korean message
# ---------------------------------------------------------------------------

_STOP_REASON_MESSAGES: dict[StopReason, str] = {
    StopReason.task_complete: "작업이 완료되었습니다.",
    StopReason.end_turn: "",  # no extra message; just show the response
    StopReason.needs_citizen_input: "추가 정보가 필요합니다.",
    StopReason.needs_authentication: "인증이 필요합니다.",
    StopReason.api_budget_exceeded: "API 사용량 한도에 도달했습니다.",
    StopReason.max_iterations_reached: "최대 처리 횟수에 도달했습니다.",
    StopReason.error_unrecoverable: "처리 중 오류가 발생했습니다.",
    StopReason.cancelled: "요청이 취소되었습니다.",
}

# Minimum number of characters to accumulate before the first Live refresh.
# This avoids a jarring single-character flash at turn start.
_LIVE_MIN_CHARS_BEFORE_REFRESH = 10


class EventRenderer:
    """Render a stream of ``QueryEvent`` objects to a Rich ``Console``.

    The renderer maintains internal state across events within a single turn:
    - ``_text_buffer`` accumulates all ``text_delta`` content.
    - ``_usage`` accumulates the latest token usage snapshot.
    - ``_active_status`` holds the currently displayed spinner (if any).
    - ``_live`` holds an active :class:`~rich.live.Live` context when
      streaming-markdown mode is enabled.

    After each turn (``stop`` event), the renderer resets its state so it is
    ready for the next turn.

    Args:
        console: Rich console to write output to.
        registry: Optional tool registry for resolving Korean tool names.
        show_usage: Whether to display per-turn token usage after each
            response.  Totals are always tracked internally regardless of
            this flag.
        streaming_markdown: When ``True``, assistant text is rendered
            incrementally as a Markdown block via :class:`~rich.live.Live`.
            Defaults to ``False`` for compatibility with non-TTY output and
            test harnesses.  Set to ``True`` when running on a real terminal
            to enable Rich Markdown rendering.
        theme: Optional :class:`~ummaya.cli.themes.Theme` override; if
            ``None``, the theme is loaded from the environment via
            :func:`~ummaya.cli.themes.load_theme`.
    """

    def __init__(
        self,
        console: Console,
        registry: ToolRegistry | None = None,
        show_usage: bool = True,
        streaming_markdown: bool = False,
        theme: Theme | None = None,
    ) -> None:
        self._console = console
        self._registry = registry
        self._show_usage = show_usage
        self._streaming_markdown = streaming_markdown
        self._theme: Theme = theme if theme is not None else load_theme()
        self._text_buffer: str = ""
        self._usage: TokenUsage | None = None
        self._active_status: Status | None = None
        self._live: Live | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(self, event: QueryEvent) -> None:
        """Dispatch a single ``QueryEvent`` to the appropriate render method."""
        if event.type == "text_delta":
            self._render_text_delta(event)
        elif event.type == "tool_use":
            self._render_tool_use(event)
        elif event.type == "tool_result":
            self._render_tool_result(event)
        elif event.type == "usage_update":
            self._render_usage_update(event)
        elif event.type == "stop":
            self._render_stop(event)

    def reset(self) -> None:
        """Reset per-turn state.  Called automatically by ``_render_stop``."""
        self._text_buffer = ""
        self._usage = None
        self._stop_live()
        self._stop_active_status()

    # ------------------------------------------------------------------
    # Private render methods
    # ------------------------------------------------------------------

    def _render_text_delta(self, event: QueryEvent) -> None:
        """Append incremental text and render it to the console.

        In streaming-markdown mode the full accumulated buffer is re-rendered
        as a :class:`~rich.markdown.Markdown` block via a
        :class:`~rich.live.Live` context.  In plain mode each chunk is printed
        directly.
        """
        chunk = event.content or ""
        self._text_buffer += chunk

        if self._streaming_markdown:
            self._render_live_markdown()
        else:
            # Plain streaming: print each chunk immediately without markup
            self._console.print(chunk, end="", highlight=False, markup=False)

    def _render_live_markdown(self) -> None:
        """Update the Live display with the current text buffer as Markdown."""
        # Don't flash a Live context for tiny leading chunks
        if len(self._text_buffer) < _LIVE_MIN_CHARS_BEFORE_REFRESH and self._live is None:
            return

        if self._live is None:
            self._live = Live(
                console=self._console,
                refresh_per_second=12,
                vertical_overflow="visible",
            )
            self._live.start()

        self._live.update(Markdown(self._text_buffer))

    def _render_tool_use(self, event: QueryEvent) -> None:
        """Show a spinner with the tool's Korean name while it executes."""
        # Finalize any in-progress Live stream first
        self._stop_live()
        # Stop any previously active status first
        self._stop_active_status()

        # Resolve Korean name via registry
        tool_id = event.tool_name or ""
        korean_name = tool_id
        if self._registry is not None:
            try:
                try:
                    tool = self._registry.lookup(tool_id)
                except AttributeError:
                    tool = self._registry.find(tool_id)
                korean_name = tool.name_ko
            except Exception:  # noqa: BLE001
                logger.debug("Could not resolve Korean name for tool %r", tool_id)

        label = (
            f"[{self._theme.tool_call}]{escape(str(korean_name))}[/{self._theme.tool_call}]"
            " 조회 중..."
        )
        status = Status(label, console=self._console)
        status.start()
        self._active_status = status

    def _render_tool_result(self, event: QueryEvent) -> None:
        """Replace the spinner with a panel summarising the tool result."""
        self._stop_active_status()

        result = event.tool_result
        if result is None:
            return

        if result.success:
            adapter_source = _adapter_source_from_result_data(result.data)
            adapter_line = ""
            if adapter_source is not None and adapter_source != result.tool_id:
                adapter_line = f"\n  adapter={escape(repr(adapter_source))}"
            panel = Panel(
                f"[{self._theme.tool_result_ok}]성공[/{self._theme.tool_result_ok}]"
                f"  tool_id={escape(repr(result.tool_id))}"
                f"{adapter_line}",
                title=f"[{self._theme.tool_result_ok}]도구 결과[/{self._theme.tool_result_ok}]",
                border_style=self._theme.tool_result_ok,
            )
        else:
            panel = Panel(
                f"[{self._theme.tool_result_err}]오류[/{self._theme.tool_result_err}]"
                f"  {escape(str(result.error or ''))}\n"
                f"error_type={escape(repr(result.error_type))}  "
                f"tool_id={escape(repr(result.tool_id))}",
                title=f"[{self._theme.tool_result_err}]도구 오류[/{self._theme.tool_result_err}]",
                border_style=self._theme.tool_result_err,
            )
        self._console.print(panel)

    def _render_usage_update(self, event: QueryEvent) -> None:
        """Buffer the latest token usage snapshot."""
        if event.usage is not None:
            self._usage = event.usage

    def _render_stop(self, event: QueryEvent) -> None:
        """Finalise a turn: flush Live display, print stop reason and usage.

        When streaming-markdown mode is active the final :class:`Markdown`
        render is committed by stopping the :class:`~rich.live.Live` context.
        In plain mode a trailing newline is printed after the streamed text.
        """
        self._stop_active_status()

        if self._streaming_markdown:
            if self._live is not None and self._text_buffer:
                # Commit buffered content and close the Live context
                self._live.update(Markdown(self._text_buffer))
                self._stop_live()
            elif self._text_buffer:
                # Short reply never reached _LIVE_MIN_CHARS_BEFORE_REFRESH —
                # print the full buffer as Markdown without a Live context.
                self._stop_live()
                self._console.print(Markdown(self._text_buffer))
        else:
            # Plain streaming: print a trailing newline after streamed text
            if self._text_buffer:
                self._console.print()

        # Show stop reason message (Korean)
        reason = event.stop_reason
        if reason is not None:
            msg = _STOP_REASON_MESSAGES.get(reason, "")
            if msg:
                self._console.print(f"[{self._theme.info}]{msg}[/{self._theme.info}]")

        # Show per-turn usage summary only when the flag is enabled
        if self._show_usage and self._usage is not None:
            self._console.print(
                f"[{self._theme.info}]토큰 사용: 입력 {self._usage.input_tokens} "
                f"/ 출력 {self._usage.output_tokens} "
                f"/ 합계 {self._usage.total_tokens}[/{self._theme.info}]"
            )

        # Reset state for next turn
        self.reset()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _stop_active_status(self) -> None:
        """Stop the active spinner if one is running."""
        if self._active_status is not None:
            self._active_status.stop()
            self._active_status = None

    def _stop_live(self) -> None:
        """Stop the active Live display if one is running."""
        if self._live is not None:
            try:
                self._live.stop()
            except Exception:  # noqa: BLE001
                logger.debug("Error stopping Live display", exc_info=True)
            finally:
                self._live = None


def _adapter_source_from_result_data(data: object) -> str | None:
    """Return the adapter source id embedded in a primitive tool result."""

    if not isinstance(data, dict):
        return None
    meta = data.get("meta")
    if not isinstance(meta, dict):
        return None
    source = meta.get("source")
    return source if isinstance(source, str) and source else None
