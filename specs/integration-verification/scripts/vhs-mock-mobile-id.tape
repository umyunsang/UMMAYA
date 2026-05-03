# Mock: 모바일 신분증 verify
Output specs/integration-verification/frames/vhs-18-mock-mobile-id.gif
Output specs/integration-verification/frames/vhs-18-mock-mobile-id.txt
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
Screenshot specs/integration-verification/frames/vhs-18-keyframe-1-boot.png
Type "모바일 신분증으로 본인인증 시뮬레이션 해줘"
Enter
Sleep 35s
Screenshot specs/integration-verification/frames/vhs-18-keyframe-2-mid.png
Sleep 25s
Screenshot specs/integration-verification/frames/vhs-18-keyframe-3-final.png
Ctrl+C
Sleep 500ms
Ctrl+C
Sleep 1s
