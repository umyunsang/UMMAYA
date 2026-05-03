# vhs Layer 4 — Live KOROAD traffic tool (envelope wrap fix verification)
Output specs/integration-verification/frames/vhs-06-traffic.gif
Output specs/integration-verification/frames/vhs-06-traffic.txt
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
Screenshot specs/integration-verification/frames/vhs-06-keyframe-1-boot.png
Type "서울 강남구 교통사고 위험지역 알려줘"
Sleep 1s
Enter
Sleep 15s
Screenshot specs/integration-verification/frames/vhs-06-keyframe-2-thinking.png
Sleep 25s
Screenshot specs/integration-verification/frames/vhs-06-keyframe-3-tool-result.png
Sleep 20s
Screenshot specs/integration-verification/frames/vhs-06-keyframe-4-final.png
Ctrl+C
Sleep 500ms
Ctrl+C
Sleep 1s
