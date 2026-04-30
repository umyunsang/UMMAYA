# SPDX-License-Identifier: Apache-2.0
# Spec 2521 PR #2578 — Layer 4 visual smoke for the byte-copy of
# tui/src/services/api/claude.ts (3419 LOC) + 3 swap commits. Per
# AGENTS.md hard rule, every PR touching tui/src/** must commit a vhs
# scenario emitting LLM-reviewable PNG keyframes.
#
# This scenario captures three canonical keyframes:
#   1-boot       — KOSMOS branding paints (post-boot, pre-input)
#   2-help       — /help slash command surface renders
#   3-question   — citizen prompt input echo (no module-load crash)
#
# Verifies that the byte-copied claude.ts (which has zero callers in
# tui/src) does not break TUI boot or interactive surface. Run with:
#   vhs specs/2521-llm-swap-cc-rebuild/scripts/smoke-bytecopy.tape

Output specs/2521-llm-swap-cc-rebuild/smoke-bytecopy.gif
Set Width 1200
Set Height 800
Set FontSize 14
Set TypingSpeed 60ms

Type "cd tui && bun run tui"
Enter
# Allow Ink the time it actually needs to negotiate raw-mode + paint the
# initial KOSMOS REPL frame. PR #2577's tape used 7s here; this scenario
# follows the same convention so the keyframe captures the rendered UI
# rather than the bare boot log.
Sleep 12s
Screenshot specs/2521-llm-swap-cc-rebuild/smoke-bytecopy-keyframe-1-boot.png

Type "/help"
Sleep 1s
Enter
Sleep 4s
Screenshot specs/2521-llm-swap-cc-rebuild/smoke-bytecopy-keyframe-2-help.png

Escape
Sleep 1s
Type "오늘 부산 날씨 어때?"
Sleep 1s
Screenshot specs/2521-llm-swap-cc-rebuild/smoke-bytecopy-keyframe-3-question.png

Ctrl+C
Sleep 1s
Ctrl+C
