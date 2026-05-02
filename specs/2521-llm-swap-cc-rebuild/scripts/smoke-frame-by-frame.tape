# SPDX-License-Identifier: Apache-2.0
# Spec 2521 — frame-by-frame TUI debugging scenario.
#
# Uses vhs 0.11+ `Output frames/` directive to dump every redraw frame as
# a separate PNG (cursor-stripped). The companion `Output ...gif` keeps the
# legacy single-file output for the 3+ keyframe rule, but the per-frame PNGs
# capture transient painting states (wrong-flow flashes, dead component
# mounts, spinner desync) that single-timestamp Screenshot directives miss.
#
# Pair with scripts/tui-scene-extract.sh on the .gif for an alternative
# scene-change extraction workflow when `Output frames/` is unavailable.

Output specs/2521-llm-swap-cc-rebuild/smoke-frame-by-frame.gif
Output specs/2521-llm-swap-cc-rebuild/frames-frame-by-frame/

Set Width 1400
Set Height 1000
Set FontSize 13
Set TypingSpeed 50ms

Type "cd tui && bun run tui"
Enter
Sleep 7s

Type "오늘 부산 날씨 어때?"
Enter
Sleep 30s

Ctrl+C
Sleep 500ms
Ctrl+C
