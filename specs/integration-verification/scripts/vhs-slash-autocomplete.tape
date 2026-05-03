# vhs Layer 4 — Slash command autocomplete dropdown
Output specs/integration-verification/frames/vhs-10-slash.gif
Output specs/integration-verification/frames/vhs-10-slash.txt
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
Screenshot specs/integration-verification/frames/vhs-10-keyframe-1-boot.png
Type "/"
Sleep 2s
Screenshot specs/integration-verification/frames/vhs-10-keyframe-2-dropdown.png
Type "lan"
Sleep 1s
Screenshot specs/integration-verification/frames/vhs-10-keyframe-3-filtered.png
Backspace 3
Sleep 500ms
Type "agen"
Sleep 1s
Screenshot specs/integration-verification/frames/vhs-10-keyframe-4-agents-filter.png
Ctrl+U
Sleep 500ms
Ctrl+C
Sleep 500ms
Ctrl+C
Sleep 1s
