# vhs Layer 4 — KOSMOS /help Korean ↔ English round-trip + Esc dismiss.
# AGENTS.md § TUI verification: emits GIF + 3+ PNG keyframes for visual review.

Output specs/integration-verification/frames/vhs-01-help-roundtrip.gif
Output specs/integration-verification/frames/vhs-01-help-roundtrip.txt
Output specs/integration-verification/frames/vhs-01-help-roundtrip.ascii
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

Screenshot specs/integration-verification/frames/vhs-01-keyframe-1-boot.png
Sleep 500ms

Type "/help"
Enter
Sleep 2s

Screenshot specs/integration-verification/frames/vhs-01-keyframe-2-help-ko.png
Sleep 500ms

Escape
Sleep 1s

Type "/lang en"
Enter
Sleep 2s

Type "/help"
Enter
Sleep 2s

Screenshot specs/integration-verification/frames/vhs-01-keyframe-3-help-en.png
Sleep 500ms

Escape
Sleep 1s

Type "/lang ko"
Enter
Sleep 2s

Type "/help"
Enter
Sleep 2s

Screenshot specs/integration-verification/frames/vhs-01-keyframe-4-help-ko-roundtrip.png
Sleep 500ms

Escape
Sleep 500ms

Ctrl+C
Sleep 500ms
Ctrl+C
Sleep 1s
