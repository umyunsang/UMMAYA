# vhs Layer 4 — /history (session search) + /export (PDF) overlays
Output specs/integration-verification/frames/vhs-11-history-export.gif
Output specs/integration-verification/frames/vhs-11-history-export.txt
Set Shell "bash"
Set FontSize 14
Set FontFamily "JetBrains Mono"
Set Width 1600
Set Height 900
Set Theme "TokyoNightStorm"
Hide
Type "cd /Users/um-yunsang/KOSMOS/tui && KOSMOS_ONBOARDING_AUTO_COMPLETE=1 bun run tui"
Enter
Sleep 5s
Show
Screenshot specs/integration-verification/frames/vhs-11-keyframe-1-boot.png
Type "/history"
Enter
Sleep 2s
Screenshot specs/integration-verification/frames/vhs-11-keyframe-2-history.png
Escape
Sleep 1s
Type "/export"
Enter
Sleep 2s
Screenshot specs/integration-verification/frames/vhs-11-keyframe-3-export.png
Escape
Sleep 500ms
Ctrl+C
Sleep 500ms
Ctrl+C
Sleep 1s
