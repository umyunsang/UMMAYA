# SPDX-License-Identifier: Apache-2.0
# Layer 4 vhs visual smoke for the empty_registry fix.
#
# Captures 3 LLM-reviewable PNG keyframes that prove the rendered UI flow:
#   1. boot — KOSMOS branding settles
#   2. input — citizen prompt accepted, REPL echoes
#   3. action — lookup tool_result render shows KMA candidates (post-fix)
#                or "검색 결과가 없습니다" (pre-fix; would mark regression)
#
# vhs ≥ 0.11.0. Screenshot directive natively supported.

Output specs/empty-registry-fix/smoke-busan-weather.gif
Set Width 1200
Set Height 800
Set FontSize 14
Set TypingSpeed 50ms

Type "cd tui && bun run tui"
Enter
Sleep 8s
Screenshot specs/empty-registry-fix/smoke-keyframe-1-boot.png

Type "오늘 부산 날씨 어땠어?"
Enter
Sleep 4s
Screenshot specs/empty-registry-fix/smoke-keyframe-2-input.png

Sleep 60s
Screenshot specs/empty-registry-fix/smoke-keyframe-3-action.png

Ctrl+C
Sleep 500ms
Ctrl+C
