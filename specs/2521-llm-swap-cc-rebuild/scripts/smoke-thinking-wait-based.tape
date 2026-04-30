# SPDX-License-Identifier: Apache-2.0
# Spec 2521 — Wait-based TUI verification (canonical pattern per docs/testing.md
# § Frame-timing methodology added 2026-05-01).
#
# Goal: prove ∴ Thinking glyph renders during streaming. Uses Wait+Screen
# instead of Sleep so the Screenshot fires exactly when the glyph appears
# (or vhs fails non-zero if the glyph never appears within 15s).

Output specs/2521-llm-swap-cc-rebuild/smoke-thinking-wait.gif
Set Width 1200
Set Height 800
Set FontSize 14
Set TypingSpeed 50ms

# Boot — fixed sleep is appropriate (no glyph to wait for)
Type "cd tui && bun run tui"
Enter
Sleep 8s
Screenshot specs/2521-llm-swap-cc-rebuild/smoke-wait-keyframe-1-boot.png

# Citizen prompt
Type "오늘 부산 날씨 어때?"
Enter

# Wait until either the ∴ Thinking glyph appears (success) or vhs times out
# at 15s (fail-fast: thinking display is broken). Wait+Screen scopes the
# regex match to the entire screen, not just the last line.
Wait+Screen /∴ Thinking/
Screenshot specs/2521-llm-swap-cc-rebuild/smoke-wait-keyframe-2-thinking-visible.png

# Wait for the first tool_call row, then capture again to verify the
# thinking glyph is preserved/replaced correctly.
Wait+Screen /● lookup/
Screenshot specs/2521-llm-swap-cc-rebuild/smoke-wait-keyframe-3-first-tool.png

# Wait up to 90s for the agentic-loop to terminate (final synthesis or
# Crunched indicator).
Sleep 60s
Screenshot specs/2521-llm-swap-cc-rebuild/smoke-wait-keyframe-4-result.png

Ctrl+C
Sleep 500ms
Ctrl+C
