#!/usr/bin/env bash
# Fresh-session capture of the 3 scenarios that token-overflowed in scn-all-live-12.
# Verifies Lead-F (NMC ER hours strip) + Lead-C (NFA/MOHW fabrication fix).
set -euo pipefail

wait_for_pane "KOSMOS|❯" 25
snapshot_pane 00-boot

run_query() {
  local label="$1"
  local query="$2"
  local wait_s="${3:-90}"
  send_text_pane "$query"
  sleep 1
  send_enter_pane
  sleep "$wait_s"
  snapshot_pane "$label"
}

# 10. NMC emergency search — verify er_24h_operating + outpatient_hours_display split
run_query 10-nmc "지금 서울 종로구에서 가까운 응급실" 90

# 11. NFA — verify Lead-C fix (sptMvmnDtc float drift + instructive error)
run_query 11-nfa "서울 강남구 119 구급 통계 알려줘" 90

# 12. MOHW — verify Lead-C fix (wantedList envelope + fabrication directive)
run_query 12-mohw "출산 보조금 알아보고 싶어" 90
