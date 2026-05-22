# SPDX-License-Identifier: Apache-2.0
# Layer 4 visual replay for bracketed paste + immediate Enter login flow.

Output specs/lf-coalesced-enter/vhs/paste-enter-login.gif
Output specs/lf-coalesced-enter/vhs/paste-enter-login.txt
Output specs/lf-coalesced-enter/vhs/paste-enter-login.ascii
Set Shell "bash"
Set FontSize 14
Set FontFamily "JetBrains Mono"
Set Width 1200
Set Height 720
Set Theme "TokyoNightStorm"

Type "sed -n '1,80p' specs/lf-coalesced-enter/paste-enter-frames/paste-enter-keyframe-1-boot.txt"
Enter
Sleep 800ms
Screenshot specs/lf-coalesced-enter/vhs/paste-enter-keyframe-1-boot.png

Type "clear"
Enter
Type "sed -n '1,120p' specs/lf-coalesced-enter/paste-enter-frames/paste-enter-keyframe-2-login-dialog.txt"
Enter
Sleep 800ms
Screenshot specs/lf-coalesced-enter/vhs/paste-enter-keyframe-2-login-dialog.png

Type "clear"
Enter
Type "sed -n '1,120p' specs/lf-coalesced-enter/paste-enter-frames/paste-enter-keyframe-3-login-success.txt"
Enter
Sleep 800ms
Screenshot specs/lf-coalesced-enter/vhs/paste-enter-keyframe-3-login-success.png
