#!/usr/bin/env bash
# 12 Live tool scenario stress — exercises every Live adapter back-to-back.
# Each query is a citizen-realistic phrasing tied to one tool category.
set -euo pipefail

wait_for_pane "KOSMOS|❯" 25
snapshot_pane 00-boot

run_query() {
  local label="$1"
  local query="$2"
  local wait_s="${3:-60}"
  send_text_pane "$query"
  sleep 1
  send_enter_pane
  sleep "$wait_s"
  snapshot_pane "$label"
}

# 1. KMA current observation (kma_current_observation)
run_query 01-kma-now "지금 부산 사하구 다대1동 날씨 어때" 70

# 2. KMA short-term forecast (kma_short_term_forecast)
run_query 02-kma-short "내일 서울 종로구 날씨 알려줘" 70

# 3. KMA ultra-short-term forecast (kma_ultra_short_term_forecast)
run_query 03-kma-ultra "1시간 뒤 인천 송도 비 올까" 70

# 4. KMA pre-warning (kma_pre_warning)
run_query 04-kma-prewarn "지금 발효 중인 기상특보 목록 알려줘" 60

# 5. KMA weather alert status (kma_weather_alert_status)
run_query 05-kma-alert "현재 호우경보 발표문 보여줘" 60

# 6. KMA forecast_fetch (lat/lon)
run_query 06-kma-fetch "강남역 오늘 시간대별 날씨" 70

# 7. KOROAD accident_search
run_query 07-koroad-acc "서울 강남구 교통사고 위험지역 알려줘" 70

# 8. KOROAD accident_hazard_search
run_query 08-koroad-haz "강남구 사고다발지역" 70

# 9. HIRA hospital_search
run_query 09-hira "강남역 근처 내과 알려줘" 70

# 10. NMC emergency_search
run_query 10-nmc "지금 서울 종로구에서 가까운 응급실" 70

# 11. NFA119 emergency_info_service
run_query 11-nfa "서울 강남구 119 구급 통계 알려줘" 70

# 12. MOHW welfare_eligibility_search
run_query 12-mohw "출산 보조금 알아보고 싶어" 70

snapshot_pane 99-final-scrollback

send_ctrlc_pane
sleep 1
send_ctrlc_pane
sleep 1
snapshot_pane 100-exit
