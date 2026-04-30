# SPDX-License-Identifier: Apache-2.0
# Spec 2521 T025-extended — capture thinking visibility at multiple time windows.

Output specs/2521-llm-swap-cc-rebuild/smoke-thinking-fast.gif
Set Width 1200
Set Height 800
Set FontSize 14
Set TypingSpeed 50ms

Type "cd tui && bun run tui"
Enter
Sleep 7s

Type "오늘 부산 날씨 어때?"
Enter
Sleep 1s
Screenshot specs/2521-llm-swap-cc-rebuild/smoke-keyframe-fast-1s.png
Sleep 2s
Screenshot specs/2521-llm-swap-cc-rebuild/smoke-keyframe-fast-3s.png
Sleep 3s
Screenshot specs/2521-llm-swap-cc-rebuild/smoke-keyframe-fast-6s.png
Sleep 5s
Screenshot specs/2521-llm-swap-cc-rebuild/smoke-keyframe-fast-11s.png

Ctrl+C
Sleep 500ms
Ctrl+C
