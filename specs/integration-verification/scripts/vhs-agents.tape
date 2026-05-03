# vhs Layer 4 — KOSMOS /agents + /agents --detail.
Output specs/integration-verification/frames/vhs-02-agents.gif
Output specs/integration-verification/frames/vhs-02-agents.txt
Output specs/integration-verification/frames/vhs-02-agents.ascii
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
Screenshot specs/integration-verification/frames/vhs-02-keyframe-1-boot.png
Sleep 500ms
Type "/agents"
Enter
Sleep 2s
Screenshot specs/integration-verification/frames/vhs-02-keyframe-2-agents.png
Sleep 500ms
Escape
Sleep 1s
Type "/agents --detail"
Enter
Sleep 2s
Screenshot specs/integration-verification/frames/vhs-02-keyframe-3-agents-detail.png
Sleep 500ms
Escape
Sleep 500ms
Ctrl+C
Sleep 500ms
Ctrl+C
Sleep 1s
