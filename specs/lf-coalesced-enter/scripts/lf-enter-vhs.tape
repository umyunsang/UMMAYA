# SPDX-License-Identifier: Apache-2.0
# Layer 4 visual smoke for the login prompt after Enter submission.

Output specs/lf-coalesced-enter/vhs/lf-enter.gif
Output specs/lf-coalesced-enter/vhs/lf-enter.txt
Output specs/lf-coalesced-enter/vhs/lf-enter.ascii
Set Shell "bash"
Set FontSize 14
Set FontFamily "JetBrains Mono"
Set Width 1200
Set Height 720
Set Theme "TokyoNightStorm"

Hide
Type "env UMMAYA_BACKEND_CMD='sleep 60' ./bin/ummaya"
Enter
Sleep 3s
Show

Screenshot specs/lf-coalesced-enter/vhs/keyframe-1-boot.png
Type "/login"
Enter
Sleep 1s
Screenshot specs/lf-coalesced-enter/vhs/keyframe-2-login-modal.png

Ctrl+C
Sleep 500ms
Ctrl+C
Sleep 500ms
