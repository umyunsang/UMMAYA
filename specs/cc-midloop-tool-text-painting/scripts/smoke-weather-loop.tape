# SPDX-License-Identifier: Apache-2.0
# Layer 4 visual smoke for the 0.2.2 mid-loop painting regression.

Output specs/cc-midloop-tool-text-painting/captures/vhs/smoke-weather-loop.gif
Output specs/cc-midloop-tool-text-painting/captures/vhs/smoke-weather-loop.txt
Output specs/cc-midloop-tool-text-painting/captures/vhs/smoke-weather-loop.ascii
Set Shell "bash"
Set Width 1600
Set Height 900
Set FontSize 14
Set Theme "TokyoNightStorm"
Set TypingSpeed 30ms

Type "cd /Users/um-yunsang/UMMAYA/tui && bun run tui"
Enter
Sleep 5s
Screenshot specs/cc-midloop-tool-text-painting/captures/vhs/smoke-keyframe-1-boot.png

Type "부산 사하구 다대1동 현재 날씨와 오늘 저녁 예보 알려줘"
Enter
Sleep 22s
Screenshot specs/cc-midloop-tool-text-painting/captures/vhs/smoke-keyframe-2-preamble-or-tool.png

Sleep 18s
Screenshot specs/cc-midloop-tool-text-painting/captures/vhs/smoke-keyframe-3-followup-tool.png

Ctrl+C
Sleep 500ms
Ctrl+C
Sleep 1s
