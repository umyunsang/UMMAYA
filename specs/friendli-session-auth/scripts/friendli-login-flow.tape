# SPDX-License-Identifier: Apache-2.0
# Layer 4 vhs visual smoke for FriendliAI session-scoped /login and /logout.

Output specs/friendli-session-auth/vhs/friendli-login-flow.gif
Output specs/friendli-session-auth/vhs/friendli-login-flow.txt
Output specs/friendli-session-auth/vhs/friendli-login-flow.ascii
Set Shell "bash"
Set FontSize 14
Set FontFamily "JetBrains Mono"
Set Width 1600
Set Height 900
Set Theme "TokyoNightStorm"

Hide
Type "cd $(git rev-parse --show-toplevel)/tui && env KOSMOS_FRIENDLI_TOKEN= KOSMOS_FRIENDLI_SESSION_ACTIVE= KOSMOS_ONBOARDING_AUTO_COMPLETE=1 KOSMOS_BACKEND_CMD='sleep 60' NODE_ENV=test IS_DEMO=1 bun run tui"
Enter
Sleep 5s
Show

Screenshot specs/friendli-session-auth/vhs/keyframe-1-boot-no-key.png
Sleep 500ms

Type "/login"
Enter
Sleep 2s
Screenshot specs/friendli-session-auth/vhs/keyframe-2-login-dialog.png

Sleep 500ms
Type@200ms "1234567890"
Sleep 1s
Screenshot specs/friendli-session-auth/vhs/keyframe-3-login-masked.png

Enter
Sleep 2s
Screenshot specs/friendli-session-auth/vhs/keyframe-4-login-success.png

Type "/logout"
Enter
Sleep 2s
Screenshot specs/friendli-session-auth/vhs/keyframe-5-logout-success.png

Ctrl+C
Sleep 500ms
Ctrl+C
Sleep 1s
