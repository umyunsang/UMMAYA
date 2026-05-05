# SPDX-License-Identifier: Apache-2.0
# audit-prod § Audit 3 — Onboarding · Slash autocomplete · /help · /lang
# (+ markdown table · multi-turn ⎿ · Ctrl+O transcript · Shift+Tab modes)
#
# Fresh-memdir scenario.  Three env vars MUST be set by the runner so all three
# memdir code paths land in the audit jail (not the citizen's real ~/.kosmos):
#   HOME=/tmp/audit-3-home                 — DEFAULT_MEMDIR_ROOT (memdir/io.ts:33)
#                                            consent + ministry-scope writes
#   KOSMOS_MEMDIR_USER=/tmp/audit-3-home/.kosmos/memdir/user
#                                          — uiL2Memdir.ts:25 onboarding state
#                                            + a11y preference
#   KOSMOS_MEMDIR_ROOT=/tmp/audit-3-home/.kosmos/memdir
#                                          — ExportPDFTool root
#
# Helpers exported by tui-tmux-capture.sh:
#   wait_for_pane <regex> [deadline_seconds=30]
#   snapshot_pane <label>
#   send_text_pane <text>
#   send_enter_pane
#   send_keys_pane <key1> [key2...]
#   send_ctrlc_pane

set -uo pipefail   # -e disabled — we want timeout snapshots without exit

# ---------------------------------------------------------------------------
# 0. Wait for boot + Onboarding gate
# ---------------------------------------------------------------------------
wait_for_pane "환경 점검|preflight|Bun|KOSMOS|kosmos" 60 || true
snapshot_pane "01-boot-onboarding-gate"

# ---------------------------------------------------------------------------
# 1. Step 1 — preflight (Enter to advance)
# ---------------------------------------------------------------------------
sleep 1
send_enter_pane
wait_for_pane "테마|theme|Theme|Dark|Light" 20 || true
snapshot_pane "02-step2-theme"

# ---------------------------------------------------------------------------
# 2. Step 2 — theme (default selection, Enter to advance)
# ---------------------------------------------------------------------------
send_enter_pane
wait_for_pane "PIPA|개인정보|consent|동의" 20 || true
snapshot_pane "03-step3-pipa-consent"

# ---------------------------------------------------------------------------
# 3. Step 3 — PIPA consent (Y to consent + advance)
# ---------------------------------------------------------------------------
send_text_pane 'Y'
wait_for_pane "부처|Ministry|ministry-scope|동의 범위|API 사용 동의" 20 || true
snapshot_pane "04-step4-ministry-scope"

# ---------------------------------------------------------------------------
# 4. Step 4 — ministry-scope (Enter to accept defaults / submit empty opt-ins)
# ---------------------------------------------------------------------------
send_enter_pane
wait_for_pane "터미널|terminal-setup|접근성|Accessibility|글씨|reader" 20 || true
snapshot_pane "05-step5-terminal-setup"

# ---------------------------------------------------------------------------
# 5. Step 5 — terminal-setup (Enter to save defaults + finish onboarding)
# ---------------------------------------------------------------------------
send_enter_pane
wait_for_pane "KOSMOS v0\.|✻|kosmos|>" 30 || true
snapshot_pane "06-post-onboarding-repl"
sleep 2

# ---------------------------------------------------------------------------
# 6. Slash autocomplete — type `/` to open dropdown
# ---------------------------------------------------------------------------
send_text_pane '/'
sleep 1
snapshot_pane "07-slash-autocomplete-open"

# Filter to /lan to verify prefix match
send_text_pane 'lan'
sleep 1
snapshot_pane "08-slash-autocomplete-lan-filter"

# Backspace 4 chars to clear /lan
send_keys_pane BSpace BSpace BSpace BSpace
sleep 1
snapshot_pane "09-slash-autocomplete-cleared"

# ---------------------------------------------------------------------------
# 7. /help — should mount HelpV2Grouped (4 groups)
# ---------------------------------------------------------------------------
send_text_pane '/help'
send_enter_pane
wait_for_pane "도움말|Help|세션|권한|도구|저장|Session|Permission|Tool|Storage" 15 || true
snapshot_pane "10-help-overlay"

# Dismiss with Esc
send_keys_pane Escape
sleep 1
snapshot_pane "11-help-dismissed"

# ---------------------------------------------------------------------------
# 8. /lang en — switch to English
# ---------------------------------------------------------------------------
send_text_pane '/lang en'
send_enter_pane
wait_for_pane "Language|locale|en|Switched|English" 15 || true
snapshot_pane "12-lang-en-toast"

# Verify by reopening /help in English
send_text_pane '/help'
send_enter_pane
wait_for_pane "Session|Permission|Tool|Storage|Help" 15 || true
snapshot_pane "13-help-en-overlay"
send_keys_pane Escape
sleep 1

# ---------------------------------------------------------------------------
# 9. /lang ko — switch back to Korean
# ---------------------------------------------------------------------------
send_text_pane '/lang ko'
send_enter_pane
wait_for_pane "한국어|Korean|locale|ko|전환" 15 || true
snapshot_pane "14-lang-ko-toast"

# ---------------------------------------------------------------------------
# 10. Markdown table query (~80 s tolerance for K-EXAONE thinking)
# ---------------------------------------------------------------------------
send_text_pane '강남역 근처 내과 5곳을 찾아서 마크다운 표로 정리해줘. 컬럼: 이름 | 주소 | 전화'
send_enter_pane
wait_for_pane "│|┃|---|│ 이름 │|hira_hospital_search|병원|진료" 180 || true
snapshot_pane "15-markdown-table-result"
sleep 3

# ---------------------------------------------------------------------------
# 11. Multi-turn citation (⎿ followup)
# ---------------------------------------------------------------------------
send_text_pane '방금 표에서 첫 번째 병원의 운영시간을 알려줘'
send_enter_pane
wait_for_pane "운영|영업|시간|오전|오후|hours|⎿" 180 || true
snapshot_pane "16-multiturn-followup"
sleep 3

# ---------------------------------------------------------------------------
# 12. Ctrl+O — toggle transcript expand (alternate-screen)
# ---------------------------------------------------------------------------
send_keys_pane C-o
sleep 2
snapshot_pane "17-ctrlO-transcript-expand"
# Ctrl+O again to collapse
send_keys_pane C-o
sleep 2
snapshot_pane "18-ctrlO-transcript-collapse"

# ---------------------------------------------------------------------------
# 13. Shift+Tab × 4 — cycle permission modes
# default → auto-accept-edit → bypassPermissions → plan → default
# ---------------------------------------------------------------------------
send_keys_pane BTab
sleep 1
snapshot_pane "19-shifttab-1-auto-accept"

send_keys_pane BTab
sleep 1
snapshot_pane "20-shifttab-2-bypass"

send_keys_pane BTab
sleep 1
snapshot_pane "21-shifttab-3-plan"

send_keys_pane BTab
sleep 1
snapshot_pane "22-shifttab-4-back-to-default"

# ---------------------------------------------------------------------------
# 14. Final exit
# ---------------------------------------------------------------------------
send_ctrlc_pane
sleep 1
send_ctrlc_pane
sleep 2
snapshot_pane "23-final-exit"
