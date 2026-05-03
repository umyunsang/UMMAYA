# Korean IME multi-line input + complex query
Output specs/integration-verification/frames/vhs-20-multiline.gif
Output specs/integration-verification/frames/vhs-20-multiline.txt
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
Screenshot specs/integration-verification/frames/vhs-20-keyframe-1-boot.png
Type "오늘 서울 날씨 어떤지"
Sleep 1s
Screenshot specs/integration-verification/frames/vhs-20-keyframe-2-line1.png
Type@10ms "  알려줘"
Sleep 1s
Screenshot specs/integration-verification/frames/vhs-20-keyframe-3-typed.png
Ctrl+C
Sleep 500ms
Ctrl+C
Sleep 1s
