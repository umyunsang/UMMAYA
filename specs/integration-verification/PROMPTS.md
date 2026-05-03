# 33 vhs e2e 시나리오 — 사용자 프롬프트 카탈로그

> 2026-05-04 integration-verification. AGENTS.md § TUI verification Layer 4 mandate. 각 시나리오는 `Bun.spawn` PTY 가 아닌 vhs `.tape` 로 진짜 user keystroke 시뮬레이션 + `.txt` golden + 3+ PNG keyframe + GIF 박제.

## 자연어 prompt (LLM 호출 22건)

| # | 시나리오 | 프롬프트 | 도구 / 검증 대상 |
|---|---|---|---|
| 03 | chat-greeting | `안녕하세요` | K-EXAONE 한국어 인사 + 공공서비스 도우미 정체성 |
| 04 | tool-weather | `서울 날씨 알려줘` | KMA forecast (Live) + Markdown 표 + nx=60/ny=127 |
| 05 | tool-hospital | `강남역 근처 내과 병원 알려줘` | HIRA hospital_search (Live) + injection FP fix verify |
| 06 | tool-traffic | `서울 강남대로 교통사고 위험도 알려줘` | KOROAD accident_search (Live) + envelope wrap fix |
| 07 | tool-emergency | `서울 응급실 정보 알려줘` | NMC emergency (Live) + endpoint+freshness fix |
| 12 | kma-current | `서울 현재 기온 실시간 알려줘` | KMA current_observation (실시간 t1h=14.4°C) |
| 13 | kma-pre-warn | `서울 호우주의보 발효 가능성 알려줘` | KMA pre_warning |
| 14 | mohw-welfare | `기초생활수급자 신청 자격 알려줘` | MOHW welfare_eligibility_search |
| 15 | nfa119 | `서울 강남구 화재 정보 알려줘` | NFA119 emergency_info_service |
| 16 | mock-gov24-cert | `주민등록등본 발급 가능한지 알려줘` | Mock 정부24 certificate (lookup) |
| 17 | mock-hometax | `홈택스 종합소득세 신고 도와줘` | Mock 홈택스 (verify chain + submit) |
| 18 | mock-mobile-id | `모바일 신분증으로 본인인증 시뮬레이션 해줘` | Mock 모바일 신분증 verify |
| 19 | resolve-location | `부산 해운대구 위경도 알려줘` | resolve_location (Kakao geocoding) |
| 20 | multiline | `오늘 서울 날씨 어떤지\n  알려줘` | 한국어 IME multi-line input |
| 22 | kma-ultra | `서울 1시간 후 강수 알려줘` | KMA ultra_short_term_forecast |
| 23 | kma-pre-warn (alt) | `서울 호우주의보 발효 가능성 알려줘` | KMA pre-warning (다른 prompt 변형) |
| 24 | koroad-hazard | `서울 강남구 사고 다발 위험지역 알려줘` | KOROAD accident_hazard_search (별도 endpoint) |
| 25 | resolve-busan | `부산 해운대 좌표 알려줘` | resolve_location (좌표 want) |
| 26 | resolve-jeju | `제주도 한라산 위경도 알려줘` | resolve_location (POI) |
| 27 | mock-mydata | `마이데이터 본인인증 시뮬레이션 해줘` | Mock 마이데이터 verify |
| 28 | mock-kec | `전자서명 KEC 인증 시뮬레이션 해줘` | Mock KEC 전자서명 verify |
| 29 | mock-modid | `모바일 ID 발급 시뮬레이션 해줘` | Mock 모바일 ID verify |
| 30 | mock-simple | `간편인증 카카오 시뮬레이션 해줘` | Mock 간편인증 verify |
| 31 | mock-gongdong | `공동인증서 시뮬레이션 해줘` | Mock 공동인증서 verify |
| 32 | mock-geumyung | `금융인증서 시뮬레이션 해줘` | Mock 금융인증서 verify |
| 33 | error-envelope | `INVALID_QUERY_!!!@@@` | LLM graceful 처리 (hallucination guard) |

## Slash command 시퀀스 (UI 검증, 7건)

| # | 시나리오 | 키 입력 시퀀스 | 검증 대상 |
|---|---|---|---|
| 01 | help-roundtrip | `/help` → `Esc` → `/lang en` → `/help` → `Esc` → `/lang ko` → `/help` | HelpV2 ko↔en round-trip + Esc dismiss + lang re-render |
| 02 | agents | `/agents` → `Esc` → `/agents --detail` → `Esc` | 부처 에이전트 list + detail (SLA/건강) |
| 09 | consent-config-plugins | `/consent list` → `Esc` → `/plugins` → `Esc` → `/config` → `Esc` | 3 overlay open/dismiss |
| 11 | history-export | `/history` → `Esc` → `/export` → `Esc` | 세션 search + PDF export |

## 인터랙션 시뮬레이션 (4건)

| # | 시나리오 | 키 입력 | 검증 대상 |
|---|---|---|---|
| 08 | onboarding | (state.json wipe) → boot 5s | 5-step preflight 첫 화면 (env check ✓/✗) |
| 10 | slash-autocomplete | `/` → `lan` → Backspace×3 → `agen` → Ctrl+U | dropdown filter 동작 |
| 21 | shift-tab-mode | Tab × 3 (mode cycle) | default → auto-accept → bypass → default |

## boot prefix (모든 시나리오 공통)

```
cd /Users/um-yunsang/KOSMOS/tui && KOSMOS_ONBOARDING_AUTO_COMPLETE=1 bun run tui
```
- 예외: vhs-08 onboarding 은 `rm -rf ~/.kosmos/memdir/user/onboarding && cd … && bun run tui` (env 변수 없이)

## 시나리오별 산출물 (4종 박제)

각 vhs `.tape` 가 다음 4종 자동 emit:

```
specs/integration-verification/frames/vhs-NN-<slug>.gif       — 애니메이션
specs/integration-verification/frames/vhs-NN-<slug>.txt       — LLM-readable golden
specs/integration-verification/frames/vhs-NN-keyframe-N-…png  — 시각 frame (3-4)
```

총 33 .tape × (1 GIF + 1 .txt + 3-4 PNG) = 33 GIF + 33 .txt + **106 PNG keyframes**.

## Verification 명령

```bash
# 단일 시나리오
vhs specs/integration-verification/scripts/vhs-04-tool-weather.tape

# 키워드 grep (LLM 응답 검증)
grep -E "기온|°C" specs/integration-verification/frames/vhs-04-weather.txt
grep -E "lookup\(" specs/integration-verification/frames/vhs-12-kma-current.txt

# PNG 시각 검증 (Read tool)
# Lead Opus 가 each PNG 를 Read 로 검증 (AGENTS.md mandate)
```

## Coverage 매트릭스

10 slash · 4 primitive · 14 Live tool · 11 Mock surface · 5-step onboarding · 한국어 IME · UI overlay 4종 · keybinding 3종 · error envelope = **모든 shipped feature 박제**.
