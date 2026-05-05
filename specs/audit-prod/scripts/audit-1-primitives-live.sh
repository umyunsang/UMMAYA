# SPDX-License-Identifier: Apache-2.0
# audit-prod § Audit 1 — 5 Primitives + 12 Live adapters production smoke
#
# Scenario covers:
#   - resolve_location (geocoding) chain prerequisite
#   - lookup primitive against 12 Live adapter tool_ids
#       KMA × 6: current_observation / short_term_forecast /
#                ultra_short_term_forecast / pre_warning /
#                weather_alert_status / forecast_fetch
#       KOROAD × 2: accident_search / accident_hazard_search
#       HIRA × 1: hospital_search
#       NMC × 1: emergency_search
#       NFA × 1: emergency_info_service
#       MOHW × 1: welfare_eligibility_search
#   - verify primitive (Layer 1 ⓵, mock fallback to gongdong_injeungseo)
#   - submit primitive (Layer 2 ⓶, mock fallback to gov24_minwon)
#   - subscribe primitive (Layer 2 ⓶, mock fallback)
#
# Helpers exported by tui-tmux-capture.sh:
#   wait_for_pane <regex> [deadline_seconds=30]
#   snapshot_pane <label>
#   send_text_pane <text>
#   send_enter_pane

set -uo pipefail   # -e disabled — we want to capture timeout snapshots without exit

# ---------------------------------------------------------------------------
# Wait for boot + KOSMOS branding
# ---------------------------------------------------------------------------
wait_for_pane "KOSMOS|kosmos" 60 || true
snapshot_pane boot

# ---------------------------------------------------------------------------
# 1. resolve_location — chain prerequisite (geocoding)
# ---------------------------------------------------------------------------
send_text_pane '서울 강남구 좌표 알려줘'
send_enter_pane
wait_for_pane "resolve_location|좌표|coords|강남" 90 || true
snapshot_pane t01-resolve_location

# Drain to clear context
sleep 2

# ---------------------------------------------------------------------------
# 2. KMA × 6
# ---------------------------------------------------------------------------
send_text_pane '서울 지금 날씨 알려줘'
send_enter_pane
wait_for_pane "kma_current_observation|기온|°C|관측" 120 || true
snapshot_pane t02-kma_current_observation
sleep 2

send_text_pane '부산 단기예보 (lat lon 입력) 보여줘'
send_enter_pane
wait_for_pane "kma_forecast_fetch|단기예보|forecast|예보" 120 || true
snapshot_pane t03-kma_forecast_fetch
sleep 2

send_text_pane '서울 오후 단기예보 알려줘'
send_enter_pane
wait_for_pane "kma_short_term_forecast|단기|TMP|POP" 120 || true
snapshot_pane t04-kma_short_term_forecast
sleep 2

send_text_pane '서울 초단기예보 보여줘'
send_enter_pane
wait_for_pane "kma_ultra_short_term_forecast|초단기|예보" 120 || true
snapshot_pane t05-kma_ustf
sleep 2

send_text_pane '지금 발효 중인 기상특보 있어?'
send_enter_pane
wait_for_pane "kma_pre_warning|특보|발효|warning" 120 || true
snapshot_pane t06-kma_pre_warning
sleep 2

send_text_pane '서울(108) 기상특보 발표문 상세 보여줘'
send_enter_pane
wait_for_pane "kma_weather_alert_status|발표문|특보|108" 120 || true
snapshot_pane t07-kma_weather_alert_status
sleep 2

# ---------------------------------------------------------------------------
# 3. KOROAD × 2
# ---------------------------------------------------------------------------
send_text_pane '강남구 교통사고 위험지점 조회해줘'
send_enter_pane
wait_for_pane "koroad_accident|위험지점|hazard|사고|adm_cd" 120 || true
snapshot_pane t08-koroad_accident_hazard_search
sleep 2

send_text_pane '서울특별시 강남구 사고다발구역 통계 보여줘'
send_enter_pane
wait_for_pane "koroad_accident_search|사고다발|위험지역" 120 || true
snapshot_pane t09-koroad_accident_search
sleep 2

# ---------------------------------------------------------------------------
# 4. HIRA × 1
# ---------------------------------------------------------------------------
send_text_pane '강남역 근처 병원 찾아줘'
send_enter_pane
wait_for_pane "hira_hospital_search|병원|hospital|진료" 120 || true
snapshot_pane t10-hira_hospital_search
sleep 2

# ---------------------------------------------------------------------------
# 5. NMC × 1
# ---------------------------------------------------------------------------
send_text_pane '강남 근처 응급실 위치 알려줘'
send_enter_pane
wait_for_pane "nmc_emergency_search|응급실|emergency|병상" 120 || true
snapshot_pane t11-nmc_emergency_search
sleep 2

# ---------------------------------------------------------------------------
# 6. NFA × 1
# ---------------------------------------------------------------------------
send_text_pane '강남구 119 출동 통계 알려줘'
send_enter_pane
wait_for_pane "nfa_emergency_info_service|119|출동|EMS" 120 || true
snapshot_pane t12-nfa_emergency_info_service
sleep 2

# ---------------------------------------------------------------------------
# 7. MOHW × 1
# ---------------------------------------------------------------------------
send_text_pane '임산부 출산 보조금 복지서비스 알려줘'
send_enter_pane
wait_for_pane "mohw_welfare_eligibility_search|복지|보조금|MOHW|welfare" 120 || true
snapshot_pane t13-mohw_welfare_eligibility_search
sleep 2

# ---------------------------------------------------------------------------
# 8. verify primitive — Layer 1 ⓵ (mock gongdong_injeungseo)
# ---------------------------------------------------------------------------
send_text_pane '공동인증서로 본인 인증해줘'
send_enter_pane
wait_for_pane "verify|인증|gongdong_injeungseo|레이어 1|⓵" 120 || true
snapshot_pane t14-verify_layer1
sleep 3

# Some verify mocks open a permission modal; press Y to approve if present.
send_text_pane 'Y'
sleep 1
snapshot_pane t14b-verify_after_decision

# ---------------------------------------------------------------------------
# 9. submit primitive — Layer 2 ⓶ (mock gov24_minwon)
# ---------------------------------------------------------------------------
send_text_pane '정부24에 등본 발급 신청 제출해줘'
send_enter_pane
wait_for_pane "submit|제출|gov24|민원|레이어 2|⓶" 120 || true
snapshot_pane t15-submit_layer2
sleep 3
send_text_pane 'Y'
sleep 1
snapshot_pane t15b-submit_after_decision

# ---------------------------------------------------------------------------
# 10. subscribe primitive — Layer 2 ⓶ (mock disaster CBS)
# ---------------------------------------------------------------------------
send_text_pane '재난문자 알림 구독해줘'
send_enter_pane
wait_for_pane "subscribe|구독|재난|CBS|⓶" 120 || true
snapshot_pane t16-subscribe_layer2
sleep 3
send_text_pane 'Y'
sleep 1
snapshot_pane t16b-subscribe_after_decision

# ---------------------------------------------------------------------------
# Final exit
# ---------------------------------------------------------------------------
send_text_pane '/exit'
send_enter_pane
sleep 2
snapshot_pane final
