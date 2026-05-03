Output specs/integration-verification/frames/vhs-12-kma-current.gif
Output specs/integration-verification/frames/vhs-12-kma-current.txt
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
Screenshot specs/integration-verification/frames/vhs-12-keyframe-1-boot.png
Type "서울 현재 기온 실시간 알려줘"
Enter
Sleep 30s
Screenshot specs/integration-verification/frames/vhs-12-keyframe-2-mid.png
Sleep 25s
Screenshot specs/integration-verification/frames/vhs-12-keyframe-3-final.png
Ctrl+C
Sleep 500ms
Ctrl+C
Sleep 1s
