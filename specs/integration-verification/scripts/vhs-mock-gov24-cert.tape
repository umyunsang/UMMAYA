# Mock: 정부24 증명서 발급 시뮬레이션 (Mock fixture replay)
Output specs/integration-verification/frames/vhs-16-mock-gov24.gif
Output specs/integration-verification/frames/vhs-16-mock-gov24.txt
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
Screenshot specs/integration-verification/frames/vhs-16-keyframe-1-boot.png
Type "주민등록등본 발급 가능한지 알려줘"
Enter
Sleep 30s
Screenshot specs/integration-verification/frames/vhs-16-keyframe-2-mid.png
Sleep 30s
Screenshot specs/integration-verification/frames/vhs-16-keyframe-3-final.png
Ctrl+C
Sleep 500ms
Ctrl+C
Sleep 1s
