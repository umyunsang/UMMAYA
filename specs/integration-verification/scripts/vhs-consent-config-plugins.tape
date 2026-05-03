# vhs Layer 4 — /consent list, /config, /plugins overlays
Output specs/integration-verification/frames/vhs-09-consent-config-plugins.gif
Output specs/integration-verification/frames/vhs-09-consent-config-plugins.txt
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
Screenshot specs/integration-verification/frames/vhs-09-keyframe-1-boot.png
Type "/consent list"
Enter
Sleep 2s
Screenshot specs/integration-verification/frames/vhs-09-keyframe-2-consent.png
Escape
Sleep 1s
Type "/plugins"
Enter
Sleep 2s
Screenshot specs/integration-verification/frames/vhs-09-keyframe-3-plugins.png
Escape
Sleep 1s
Type "/config"
Enter
Sleep 2s
Screenshot specs/integration-verification/frames/vhs-09-keyframe-4-config.png
Escape
Sleep 500ms
Ctrl+C
Sleep 500ms
Ctrl+C
Sleep 1s
