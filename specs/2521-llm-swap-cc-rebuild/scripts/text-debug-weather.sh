#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Spec 2521 — text-debug scenario: 사용자 정상 흐름 (서울 날씨 질의).
#
# Sourced by scripts/tui-text-debug.sh — uses helpers exposed there:
#   send_keys / send_enter / send_ctrlc / snapshot / wait_seconds / wait_for
#
# Capture intent:
#   1. boot snapshot (이미 tui-text-debug.sh 가 자동 capture)
#   2. branding 확인 — KOSMOS / ✻ glyph
#   3. 사용자 입력 "오늘 서울 날씨 알려줘"
#   4. 입력 직후 (도구 ui 없어야 함, internal BM25 hide 검증)
#   5. reasoning 단계 (* Symbioting / Crunched 등 spinner)
#   6. 도구 호출 시작 (● lookup(fetch:resolve_location) 등장)
#   7. 도구 결과 도착 후 reasoning 재개
#   8. 한국어 답변 streaming
#   9. 답변 완료 → /quit 으로 정상 종료

# 1. 부팅 검증 — KOSMOS 브랜딩이 보일 때까지 polling.
wait_for "KOSMOS|✻" "branding"

# 2. 사용자 입력. literal 로 한 글자씩 보내야 IME / paste burst 회귀를 피함.
send_keys "오늘 서울 날씨 알려줘"
snapshot "input-typed"

# 3. Enter 제출 → 직후 frame.
send_enter
snapshot "input-submitted"

# 4. internal search hide 검증 — 도구 ui 가 즉시 등장하면 안 됨.
#    0.5s × 4 = 2s 동안 sliding snapshot.
wait_seconds 2

# 5. reasoning / spinner 등장 polling.
wait_for "Symbioting|Crunched|Thinking|⏵" "reasoning-or-spinner"

# 6. 도구 호출 ui 등장 polling (CC 의 ● tool 표기).
wait_for "● lookup|● fetch|● resolve_location|● kma_" "first-tool-call"

# 7. 도구 결과 후 답변 streaming polling — 한국어 한 글자라도 나오면 OK.
wait_for "강수|날씨|기온|하늘|구름|맑|흐림" "answer-streaming"

# 8. 답변 안정화 시간.
wait_seconds 6
snapshot "answer-stable"

# 9. 정상 종료.
send_keys "/quit"
send_enter
wait_seconds 1
snapshot "quit-typed"
