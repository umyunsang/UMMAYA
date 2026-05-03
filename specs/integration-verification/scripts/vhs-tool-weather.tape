# vhs Layer 4 — Live KMA forecast tool call.
Output specs/integration-verification/frames/vhs-04-weather.gif
Output specs/integration-verification/frames/vhs-04-weather.txt
Output specs/integration-verification/frames/vhs-04-weather.ascii
Set Shell "bash"
Set FontSize 14
Set FontFamily "JetBrains Mono"
Set Width 1600
Set Height 1000
Set Theme "TokyoNightStorm"
Hide
Type "cd /Users/um-yunsang/KOSMOS/tui && KOSMOS_ONBOARDING_AUTO_COMPLETE=1 bun run tui"
Enter
Sleep 5s
Show
Screenshot specs/integration-verification/frames/vhs-04-keyframe-1-boot.png
Sleep 500ms
Type "서울 날씨 알려줘"
Sleep 1s
Enter
Sleep 10s
Screenshot specs/integration-verification/frames/vhs-04-keyframe-2-thinking.png
Sleep 12s
Screenshot specs/integration-verification/frames/vhs-04-keyframe-3-tool-result.png
Sleep 18s
Screenshot specs/integration-verification/frames/vhs-04-keyframe-4-final.png
Sleep 500ms
Ctrl+C
Sleep 500ms
Ctrl+C
Sleep 1s
