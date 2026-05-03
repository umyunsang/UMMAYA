# Mock: 홈택스 종합소득세 신고 시뮬레이션 (verify chain + submit)
Output specs/integration-verification/frames/vhs-17-mock-hometax.gif
Output specs/integration-verification/frames/vhs-17-mock-hometax.txt
Set Shell "bash"
Set FontSize 14
Set Width 1600
Set Height 900
Set Theme "TokyoNightStorm"
Hide
Type "cd /Users/um-yunsang/KOSMOS/tui && KOSMOS_ONBOARDING_AUTO_COMPLETE=1 bun run tui"
Enter
Sleep 5s
Show
Screenshot specs/integration-verification/frames/vhs-17-keyframe-1-boot.png
Type "홈택스 종합소득세 신고 도와줘"
Enter
Sleep 35s
Screenshot specs/integration-verification/frames/vhs-17-keyframe-2-thinking.png
Sleep 25s
Screenshot specs/integration-verification/frames/vhs-17-keyframe-3-final.png
Ctrl+C
Sleep 500ms
Ctrl+C
Sleep 1s
