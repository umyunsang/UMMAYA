# SPDX-License-Identifier: Apache-2.0
# Spec 2521 — Layer 4 vhs verification for the d11c835 commit
# (citation-missing tier-1 + plugin handle + turn-order + pacing).
#
# 4-keyframe rule (AGENTS.md § TUI verification, 2026-04-29 promotion):
#  1. boot   — KOSMOS branding + tool_registry: 14 entries verified
#  2. input  — citizen prompt accepted in REPL
#  3. tool   — first ● lookup(...) row
#  4. answer — Korean answer streaming visible (강수/기온/구름 etc.)

Output specs/2521-llm-swap-cc-rebuild/smoke-post-d11c835.gif
Set Width 1400
Set Height 900
Set FontSize 14
Set TypingSpeed 50ms

Type "cd tui && bun run tui"
Enter
Sleep 7s
Screenshot specs/2521-llm-swap-cc-rebuild/smoke-post-d11c835-1-boot.png

Type "오늘 서울 날씨 알려줘"
Enter
Sleep 4s
Screenshot specs/2521-llm-swap-cc-rebuild/smoke-post-d11c835-2-input.png

Wait+Screen /● lookup\(/
Screenshot specs/2521-llm-swap-cc-rebuild/smoke-post-d11c835-3-tool.png

Wait+Screen /기온|강수|맑음|구름|날씨/
Sleep 4s
Screenshot specs/2521-llm-swap-cc-rebuild/smoke-post-d11c835-4-answer.png

Sleep 1s
Ctrl+C
Sleep 500ms
Ctrl+C
