---
description: "Task list for Tool surface v4 — agency-faithful contracts + description-rich + chain-free"
---

# Tasks: Tool surface v4

**Input**: Design documents from `/Users/um-yunsang/KOSMOS-w-2522/specs/2522-tool-surface-v4/`
**Prerequisites**: spec.md (7 user stories) · plan.md (10d Phase plan) · research.md (5 decisions) · data-model.md (5 entities) · contracts/README.md · quickstart.md (7 시나리오)

**Tests**: TDD 패턴 — 각 user story 의 pytest live + unit test 가 implementation 과 동일 phase 에 포함. TUI PTY smoke 는 Polish phase.

**Organization**: Tasks 는 user story 별 그룹화 (P1 → P2 → P3 우선순위 순). Phase 1 Setup / Phase 2 Foundational 이 모든 user story 의 prerequisite.

## Format: `[ID] [P?] [Story] Description with absolute path`

- **[P]**: 다른 file + 의존 X → 병렬 가능
- **[USx]**: User Story x 매핑 (US1-US7, spec.md § User Scenarios)
- 모든 path 는 worktree absolute (`/Users/um-yunsang/KOSMOS-w-2522/...`)

## Path Conventions (worktree)

- backend: `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/`
- tests: `/Users/um-yunsang/KOSMOS-w-2522/tests/`
- docs: `/Users/um-yunsang/KOSMOS-w-2522/docs/api/`
- spec: `/Users/um-yunsang/KOSMOS-w-2522/specs/2522-tool-surface-v4/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Worktree 정합 + pre-flight 검증. branch / spec / dependency 모두 사전 OK.

- [ ] T001 Verify worktree state at `/Users/um-yunsang/KOSMOS-w-2522/` — branch=`feat/2522-tool-surface-v4`, `git status` clean, `uv sync --frozen` PASS, `bun --cwd tui install --frozen-lockfile` PASS.
- [ ] T002 [P] Verify env keys present in `/Users/um-yunsang/KOSMOS-w-2522/.env` — `KOSMOS_DATA_GO_KR_API_KEY`, `KOSMOS_KAKAO_API_KEY`, `KOSMOS_FRIENDLI_TOKEN`. Document missing keys (e.g., `KOSMOS_JUSO_CONFM_KEY`, `KOSMOS_SGIS_KEY` — optional, JUSO/SGIS skip).
- [ ] T003 [P] Verify spec ready — `/Users/um-yunsang/KOSMOS-w-2522/specs/2522-tool-surface-v4/{spec,plan,research,data-model,quickstart}.md` exist + `contracts/README.md` exist + `checklists/requirements.md` PASS.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Description 5-섹션 골격 helper + short reference text generator + chain dependency 제거. 모든 user story 가 이 phase 의 산출물에 의존.

**⚠️ CRITICAL**: Phase 3+ 시작 전 Phase 2 완료 필수.

- [X] T004 [P] Create description 5-섹션 string template helper in `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/_description_template.py` — function `build_description_v4(purpose, input_quirk, short_reference, domain_quirk, self_contained_decl) -> str` per data-model.md `DescriptionSection`. Token budget validator (≤ 500 tokens 도구당, ≤ 100 tokens 섹션당).
- [X] T005 [P] Generate KMA grid 17 광역시도 short reference text — extract from existing `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/kma/grid_coords.py:REGION_TO_GRID` dict, format as inline table (`서울=(60,127) 부산=(98,76) ...`) ≤ 200 tokens. Output: helper function in same module.
- [X] T006 [P] Generate KMA station 17 광역시도 short reference text — extract from `/tmp/kosmos-domain-docs/kma_asos.txt § 첨부 지점 코드` (108=서울, 159=부산 등 17개 광역). Output: text constant in `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/kma/_short_references.py`.
- [X] T007 [P] Generate KOROAD siDo 17 광역시도 + NFA 시도본부 17개 short reference texts — extract from `/tmp/kosmos-domain-docs/koroad.txt § 3.2 siDo` (서울="11", 부산="12", ...) + `/tmp/kosmos-domain-docs/nfa_station.csv` 시도본부 unique values. Output: constants in `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/koroad/_short_references.py` + `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/nfa119/_short_references.py`.
- [X] T008 [P] Generate MOHW 7 enum (life_array) short reference text — extract from `/tmp/kosmos-domain-docs/mohw_codes.txt § 코드표 (생애주기)` (`001=영유아 / 002=아동 / 003=청소년 / 004=청년 / 005=중장년 / 006=노년 / 007=임신·출산`). Output: constant in `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/mohw/_short_references.py`.
- [X] T009 Correct `models.py:577` chain dependency LLM 지시 in `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/models.py:577` — replace existing wrong text ("후속 도구에 nx/ny 가 필요하면 'coords' 충분 — KMA 도구는 nx/ny 를 좌표 → grid 변환해서 별도 받음") with corrected phrasing per research.md Decision 4 ("후속 도구별 input schema 는 각 도구의 description 참조. 각 도구는 self-contained — KOSMOS 가 cross-domain chain 강제하지 않음.").
- [X] T010 [P] Verify `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/ipc/stdio.py:_build_available_adapters_suffix` ORDERING 지시 정합 — 5-섹션 골격 적용된 description 이 존재하는 도구는 ORDERING 지시 emit 생략 (description 의 섹션 4·5 가 이미 quirk + chain 권장 표현). T004 helper 사용. Future-task note: `specs/2522-tool-surface-v4/research-stdio-ordering.md`.

**Checkpoint**: Foundation 완료. T004-T010 통과 후 Phase 3+ 시작 가능.

---

## Phase 3: User Story 1 — 부산 날씨 (Priority: P1) 🎯 MVP

**Goal**: 시민이 "부산 날씨 알려줘" 발화 시 invalid_params 없이 KMA 6 도구 응답. Spec 2521 회귀 직접 fix.

**Independent Test**: pytest live `kma_current_observation(nx=98, ny=76, base_date=오늘, base_time=직전정시)` 성공 + TUI smoke "부산 날씨" frames-busan-weather/ 캡처.

### Implementation for User Story 1

- [ ] T011 [P] [US1] Rewrite `kma_current_observation` description 5-섹션 골격 in `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/kma/kma_current_observation.py:KMA_CURRENT_OBSERVATION_TOOL.llm_description` — T004 helper 사용. base_time validator 강화 (매 정시, :40 이후 안정). data-model.md § "llm_description string assembly" 패턴 채택.
- [ ] T012 [P] [US1] Rewrite `kma_short_term_forecast` description + base_time 8-시각 (`0200/0500/0800/1100/1400/1700/2000/2300`) validator in `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/kma/kma_short_term_forecast.py`.
- [ ] T013 [P] [US1] Rewrite `kma_ultra_short_term_forecast` description + HH30 (`0030/0130/.../2330`) validator in `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/kma/kma_ultra_short_term_forecast.py`.
- [ ] T014 [P] [US1] Rewrite `kma_forecast_fetch` description (이미 lat/lon 받음, projection.py 내부 변환 그대로) in `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/kma/forecast_fetch.py`. 도메인 quirk: lat/lon → nx/ny 어댑터 내부 변환 자동 명시.
- [ ] T015 [P] [US1] Fix `kma_pre_warning` endpoint typo + rewrite description in `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/kma/kma_pre_warning.py` — `getPreWrnList` (404) → `getWthrWrnList` (live). evidence: `/tmp/kosmos-evidence/kma-evidence.md`.
- [ ] T016 [US1] Refactor `kma_weather_alert_status` to require `stn_id` or `tmFc` + rewrite description with autonomous chain note in `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/kma/kma_weather_alert_status.py` — `KmaWeatherAlertStatusInput` model_validator: `stn_id` 와 `tmFc` 둘 다 None 이면 ValueError. description 섹션 5 에 "turn 1 = `kma_pre_warning`, turn 2 = 이 도구 (autonomous chain, 강제 X)" 명시.
- [ ] T017 [US1] Add KMA pytest live tests in `/Users/um-yunsang/KOSMOS-w-2522/tests/tools/kma/test_v4_live.py` — 6 도구 별 1+ 케이스 (`@pytest.mark.live`). Spec 2521 회귀 fix 회귀 테스트 (`test_busan_current_observation_no_invalid_params`).
- [ ] T018 [US1] Add KMA unit tests for description token budget + ORDERING absence in `/Users/um-yunsang/KOSMOS-w-2522/tests/tools/kma/test_v4_unit.py` — 6 도구 description ≤ 500 tokens, 5 섹션 헤더 모두 포함, T010 의 ORDERING 지시 부재 검증.

**Checkpoint**: KMA 6 도구 모두 description 5-섹션 + 1줄 fix 적용. pytest live + unit PASS. US1 단독 deploy 가능.

---

## Phase 4: User Story 2 — 강남구 병원 (Priority: P2)

**Goal**: 시민 "강남구 병원" → HIRA 어댑터 응답. `_type=json` param 정정.

**Independent Test**: pytest live `hira_hospital_search(xPos=127.047, yPos=37.517, radius=2000)` JSON 응답 (XML 아님).

### Implementation for User Story 2

- [ ] T019 [P] [US2] Fix HIRA `_type=json` param + rewrite description 5-섹션 in `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/hira/hospital_search.py` — adapter HTTP request 의 `type=json` (XML 반환) → `_type=json` (실제 JSON). description 입력 quirk 섹션에 xPos=경도(lon)/yPos=위도(lat) 명시 + WGS84.
- [ ] T020 [P] [US2] Add HIRA pytest live + unit tests in `/Users/um-yunsang/KOSMOS-w-2522/tests/tools/hira/test_v4.py` — `_type=json` 응답 schema 검증 + 단일 도시 (강남구) 병원 ≥ 3건 검증.
- [ ] T021 [US2] Sync HIRA docs/api 7-section in `/Users/um-yunsang/KOSMOS-w-2522/docs/api/hira/hospital_search.md` — Spec 1637 7-section 골격 (Overview / Envelope / Search hints / Endpoint / Permission tier rationale / Worked example / Constraints). v4 변경사항 (`_type=json`, description 5-섹션) 명시.

**Checkpoint**: US2 독립 동작.

---

## Phase 5: User Story 3 — 서울 응급실 (Priority: P2)

**Goal**: 시민 "서울 응급실" → NMC 어댑터 응답. URL encoding 자동화.

**Independent Test**: pytest live `nmc_emergency_search(lat=37.5665, lon=126.9780, limit=3)` HTTP 200 + Spec 023 freshness gate.

### Implementation for User Story 3

- [ ] T022 [P] [US3] Refactor NMC URL encoding to use `httpx.params={}` dict + rewrite description 5-섹션 in `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/nmc/emergency_search.py` — string interpolation 제거, params dict 자동 인코딩. description 입력 quirk 섹션에 한국어 query param URL 인코딩 quirk 명시.
- [ ] T023 [P] [US3] Add NMC pytest live + unit tests in `/Users/um-yunsang/KOSMOS-w-2522/tests/tools/nmc/test_v4.py` — Spec 023 freshness 정합 (`hvidate` 5분 이내 fresh / 그 외 stale_data) + URL encoding regression.
- [ ] T024 [US3] Sync NMC docs/api 7-section in `/Users/um-yunsang/KOSMOS-w-2522/docs/api/nmc/emergency_search.md` — v4 변경 (URL encoding 자동화, description 5-섹션) 명시.

**Checkpoint**: US3 독립 동작.

---

## Phase 6: User Story 4 — 임신·출산 복지 (Priority: P3)

**Goal**: 시민 "임신·출산 복지" → MOHW 어댑터 응답. handle() stub 진짜 구현.

**Independent Test**: pytest live `mohw_welfare_eligibility_search(life_array="007", search_wrd="출산")` ≥ 21건 응답.

### Implementation for User Story 4

- [ ] T025 [P] [US4] Implement MOHW `handle()` real function (replace Layer3GateViolation stub) in `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/mohw/welfare_eligibility_search.py` — UTF-8 XML response 파싱 (`xml.etree.ElementTree` stdlib), camelCase wire param serialization (snake_case → camelCase: `life_array` → `lifeArray`).
- [ ] T026 [P] [US4] Auto-inject `callTp=L` + `srchKeyCode=003` in MOHW adapter request in `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/mohw/welfare_eligibility_search.py:_request()` — pydantic input 에 노출 X, 어댑터 내부 자동 주입. evidence: `/tmp/kosmos-evidence/koroad-mohw-evidence.md`.
- [ ] T027 [US4] Rewrite MOHW description 5-섹션 with 7 enum (life_array) inline in `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/mohw/welfare_eligibility_search.py:MOHW_WELFARE_ELIGIBILITY_SEARCH_TOOL.llm_description` — T008 의 short reference 사용 (`001=영유아 ... 007=임신·출산`).
- [ ] T028 [US4] Add MOHW pytest live + unit tests in `/Users/um-yunsang/KOSMOS-w-2522/tests/tools/mohw/test_v4.py` — `lifeArray=007` happy path + camelCase serialize + XML 파싱 + `callTp=L` 자동 주입 검증.
- [ ] T029 [US4] Create + sync MOHW docs/api 7-section in `/Users/um-yunsang/KOSMOS-w-2522/docs/api/mohw/welfare_eligibility_search.md` — Spec 1637 골격 (현재 stub 라 docs 없음 가정). v4 진짜 구현 결과 반영.

**Checkpoint**: US4 독립 동작 (stub → 진짜 구현).

---

## Phase 7: User Story 5 — 강남소방서 구급통계 (Priority: P3)

**Goal**: 시민 "강남소방서 1월 구급통계" → NFA 어댑터 응답. handle() stub 진짜 구현.

**Independent Test**: pytest live `nfa_emergency_info_service(operation="getEmgencyActivityInfo", sido_hq_ogid_nm="서울특별시", rsac_gut_fstt_ogid_nm="강남소방서", stmt_ym="202501")` 통계 응답.

### Implementation for User Story 5

- [ ] T030 [US5] Investigate NFA wire param spec via data.go.kr portal + documentation crosscheck — wire param 정확명 (`stmtYm` vs `stmt_ym` etc), endpoint 정확 URL, 6 sub-operation (`getEmgencyActivityInfo` / `getEmgPatientTransferInfo` / `getEmgPatientConditionInfo` / `getEmgPatientFirstaidInfo` / `getEmgVehicleDispatchInfo` / `getEmgVehicleInfo`) 별 응답 schema. evidence: data.go.kr 포털 + `/tmp/kosmos-domain-docs/nfa_emg.txt`. 산출물: `specs/2522-tool-surface-v4/research-nfa-wire.md` (private).
- [ ] T031 [US5] Implement NFA `handle()` real function with 6 sub-operation dispatch in `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/nfa119/emergency_info_service.py` — T030 산출물 기반. Layer3GateViolation stub 제거. operation discriminator (input 의 `operation` field) 로 6 sub-endpoint 분기. 각 sub-operation 별 output schema (Pydantic v2 strict).
- [ ] T032 [US5] Rewrite NFA description 5-섹션 + 17 시도본부 short reference inline in `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/nfa119/emergency_info_service.py:NFA_EMERGENCY_INFO_SERVICE_TOOL.llm_description` — T007 의 NFA 시도본부 short reference 사용. 자세한 station 명 (1145 row) 은 inline X (LLM 한계).
- [ ] T033 [US5] Add NFA pytest live + unit tests in `/Users/um-yunsang/KOSMOS-w-2522/tests/tools/nfa119/test_v4.py` — 6 sub-operation 각 happy path + error path. evidence: T030 결과.
- [ ] T034 [US5] Create + sync NFA docs/api 7-section in `/Users/um-yunsang/KOSMOS-w-2522/docs/api/nfa119/emergency_info_service.md` — 6 sub-operation 별 worked example 포함.

**Checkpoint**: US5 독립 동작 (stub → 진짜 구현).

---

## Phase 8: User Story 6 — 서울 강남구 교통사고 (Priority: P3)

**Goal**: 시민 "서울 강남구 교통사고 위험지역" → KOROAD 2 도구 응답. siDo/guGun 코드체계 정정.

**Independent Test**: pytest live `koroad_accident_search(searchYearCd=2023, siDo="11", guGun="680")` HTTP 200 + JSON 응답 (4-digit 1100/1116 NODATA 와 비교).

### Implementation for User Story 6

- [ ] T035 [P] [US6] Fix `koroad_accident_search` siDo/guGun docs description (4-digit → 2+3 digit) in `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/koroad/accident_search.py` — `KoroadAccidentSearchInput.siDo` / `guGun` field description 정정 ("2-digit 광역시도" / "3-digit 시군구"). description 5-섹션 적용. T007 의 KOROAD short reference 사용.
- [ ] T036 [P] [US6] Implement `koroad_accident_hazard_search` `geom_json` Polygon strip + rewrite description in `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/koroad/accident_hazard_search.py` — `_strip_geom_json()` helper 가 응답의 each item 의 `geom_json` 필드 (~500자 Polygon) 제거 후 LLM emit. description 5-섹션 적용.
- [ ] T037 [P] [US6] Add KOROAD pytest live + unit tests in `/Users/um-yunsang/KOSMOS-w-2522/tests/tools/koroad/test_v4.py` — 2 도구 happy path + 2+3-digit code 정확도 (`siDo="11"` PASS, `siDo="1100"` NODATA) + geom_json strip 검증.
- [ ] T038 [US6] Sync KOROAD docs/api 7-section in `/Users/um-yunsang/KOSMOS-w-2522/docs/api/koroad/{accident_search,accident_hazard_search}.md` — v4 변경 (siDo/guGun 2+3 digit, geom_json strip) 명시.

**Checkpoint**: US6 독립 동작.

---

## Phase 9: User Story 7 — Chain 독립 + resolve_location 표준화 (Priority: P2)

**Goal**: KOSMOS 가 cross-domain chain 강제하지 않음 + resolve_location 출력 4종 필드 표준.

**Independent Test**: 13 도구 description 모두 "self-contained, do not chain" 명시 검증 + `resolve_location` 출력 4종 필드 (`lat, lon, b_code, address_name`) 검증.

### Implementation for User Story 7

- [ ] T039 [US7] Refactor `resolve_location` output to ResolveLocationOutput v4 standard in `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/resolve_location.py` + `/Users/um-yunsang/KOSMOS-w-2522/src/kosmos/tools/models.py` — 신모델 `ResolveLocationOutput(lat, lon, b_code, address_name, confidence, source)` 정의 (`extra="forbid"`, `frozen=True`). Kakao 백엔드의 `documents[0]` → 4 필드 매핑. JUSO/SGIS optional fallback (env 키 없으면 skip).
- [ ] T040 [US7] Add resolve_location pytest live (Kakao 단독) + unit tests in `/Users/um-yunsang/KOSMOS-w-2522/tests/tools/test_resolve_location_v4.py` — 4 시나리오 (geocoding-evidence.md 의 서울 강남구 / 부산 / 제주 / 존재하지않는주소) + 4종 필드 검증.
- [ ] T041 [US7] Sync resolve_location docs/api in `/Users/um-yunsang/KOSMOS-w-2522/docs/api/resolve_location/index.md` — 4종 필드 출력 표준 + Kakao 단독 백엔드 충분성 명시.

**Checkpoint**: US7 (chain 독립 + resolve_location 표준) 완료. 13 도구 + 1 meta-tool 모두 v4 ready.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: TUI PTY smoke 7 시나리오 검증 + docs 일괄 동기화 + Constitution post-design check.

- [ ] T042 [P] TUI PTY smoke scenario 1 — 부산 날씨 (US1) capture in `/Users/um-yunsang/KOSMOS-w-2522/specs/2522-tool-surface-v4/scripts/smoke-busan-weather.expect` + `frames-busan-weather/`. `bash scripts/tui-tmux-capture.sh ...` 패턴 (memory `feedback_debug_infra_rebuild`). single-tool success 검증.
- [ ] T043 [P] TUI PTY smoke scenario 2 — 강남구 병원 (US2) in `frames-gangnam-hospital/`. autonomous turn 1 = resolve_location, turn 2 = HIRA 검증.
- [ ] T044 [P] TUI PTY smoke scenario 3 — 서울 응급실 (US3) in `frames-seoul-er/`. URL encoding 회귀 + freshness gate 검증.
- [ ] T045 [P] TUI PTY smoke scenario 4 — 임신·출산 복지 (US4) in `frames-imsin-welfare/`. lifeArray=007 + camelCase serialize 검증.
- [ ] T046 [P] TUI PTY smoke scenario 5 — 강남소방서 구급통계 (US5) in `frames-gangnam-119/`. 6 sub-operation 중 `getEmgencyActivityInfo` 검증.
- [ ] T047 [P] TUI PTY smoke scenario 6 — 서울 강남구 교통사고 (US6) in `frames-gangnam-accident/`. siDo="11"/guGun="680" + geom_json strip 검증.
- [ ] T048 [P] TUI PTY smoke scenario 7 — chain 독립 자율 호출 (US7) in `frames-chain-independence/`. KOSMOS 가 chain 강요하지 않는지 + LLM autonomous chain 동작 검증.
- [ ] T049 Sync all docs/api/* 7-section + run `python /Users/um-yunsang/KOSMOS-w-2522/scripts/build_schemas.py --check` PASS — 13 도구 + resolve_location 의 JSON Schema Draft 2020-12 export drift 0 검증. Spec 1637 호환.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1, T001-T003)**: 즉시 시작 가능
- **Foundational (Phase 2, T004-T010)**: Setup 완료 후 시작. ALL user story 시작 전 완료 필수
- **User Stories (Phase 3-9)**: Foundational 완료 후 병렬 가능. 우선순위 순서 = P1 → P2 → P3
  - US1 (P1) — KMA 6 도구 = MVP
  - US2 (P2) / US3 (P2) / US7 (P2) — 병렬 가능
  - US4 / US5 / US6 (P3) — 병렬 가능
- **Polish (Phase 10, T042-T049)**: 모든 user story 완료 후

### User Story Dependencies (서로 독립)

- **US1 (부산 날씨)**: Foundational 완료 후 즉시 — KMA 6 도구
- **US2 (강남구 병원)**: Foundational 완료 후 — HIRA 1 도구
- **US3 (서울 응급실)**: Foundational 완료 후 — NMC 1 도구
- **US4 (임신 복지)**: Foundational 완료 후 — MOHW 1 도구 (stub 진짜 구현)
- **US5 (강남소방서)**: Foundational 완료 후 — NFA 1 도구 (stub 진짜 구현)
- **US6 (서울 강남구 사고)**: Foundational 완료 후 — KOROAD 2 도구
- **US7 (chain 독립)**: Foundational 완료 후 — `resolve_location` 출력 표준화. 다른 US 의 description 변경은 무관 (각 description 의 self-contained 선언 = US7 의 일부)

### Within Each User Story

- description 갈아엎기 → adapter 구현 fix → pytest live → docs/api 동기화
- stub 도구 (US4 / US5): wire param 조사 → handle() 구현 → description → tests → docs

### Parallel Opportunities

- **Phase 1 (T001-T003)**: T002 / T003 병렬
- **Phase 2 (T004-T010)**: T004 / T005 / T006 / T007 / T008 / T010 병렬 (T009 만 sequential — `models.py` 단일 file)
- **Phase 3 (T011-T018)**: T011 / T012 / T013 / T014 / T015 모두 병렬 (다른 KMA 도구 file). T016 (kma_weather_alert_status) 도 별도 file 이라 병렬. T017 / T018 은 sequential (테스트는 implementation 후)
- **Phase 4-8**: 각 phase 내부 [P] 마커 task 병렬
- **Phase 10 Polish (T042-T048)**: TUI smoke 7 시나리오 모두 병렬 (각 다른 frames/ 디렉토리)

---

## Parallel Example: User Story 1 (KMA 6 도구)

```bash
# Sonnet teammate dispatch (Lead Opus 가 dispatch-tree.md 작성 후):
sonnet-kma-current: T011 [P] [US1] kma_current_observation description + base_time
sonnet-kma-short:   T012 [P] [US1] kma_short_term_forecast description + 8-시각 validator
sonnet-kma-ultra:   T013 [P] [US1] kma_ultra_short_term_forecast description + HH30 validator
sonnet-kma-fetch:   T014 [P] [US1] kma_forecast_fetch description (lat/lon)
sonnet-kma-warn:    T015 [P] [US1] kma_pre_warning endpoint typo + description
sonnet-kma-alert:   T016 [US1] kma_weather_alert_status stn_id/tmFc + description (sequential after T015 reference)

# After all 6 implementation done:
sonnet-kma-test: T017 + T018 (pytest live + unit, sequential)
```

---

## Implementation Strategy

### MVP First (User Story 1 = KMA 6 도구)

1. Phase 1 Setup (T001-T003)
2. Phase 2 Foundational (T004-T010)
3. Phase 3 US1 (T011-T018) — KMA 6 도구 + pytest
4. **STOP / VALIDATE**: pytest live + TUI smoke "부산 날씨"
5. Spec 2521 회귀 fix 확인 → MVP deploy 가능 (`v0.1-alpha-rc`)

### Incremental delivery (P1 → P2 → P3)

1. Setup + Foundational + US1 → MVP (KMA 6 도구)
2. US2 (HIRA) + US3 (NMC) + US7 (chain 독립) 병렬 — P2 묶음
3. US4 (MOHW stub) + US5 (NFA stub) + US6 (KOROAD) 병렬 — P3 묶음
4. Polish (TUI smoke 7 + docs/api 동기화) 마지막
5. 단일 PR 생성 (사용자 디렉티브 "single Epic single PR")

### Parallel team strategy (Lead Opus + Sonnet teammates)

1. Phase 1-2 = Lead Opus solo
2. Phase 3-9 = Lead Opus dispatch tree:
   - sonnet-foundational: T004-T010 (Phase 2)
   - sonnet-us1-kma: T011-T018 (Phase 3, KMA 6 도구)
   - sonnet-us2-hira: T019-T021 (Phase 4, HIRA)
   - sonnet-us3-nmc: T022-T024 (Phase 5, NMC)
   - sonnet-us4-mohw: T025-T029 (Phase 6, MOHW stub 진짜)
   - sonnet-us5-nfa: T030-T034 (Phase 7, NFA stub 진짜) — T030 (wire 조사) 가 critical path
   - sonnet-us6-koroad: T035-T038 (Phase 8, KOROAD)
   - sonnet-us7-resolve: T039-T041 (Phase 9, resolve_location)
3. Phase 10 Polish = Lead Opus dispatch:
   - sonnet-smoke-1 ~ sonnet-smoke-7: T042-T048 (TUI PTY smoke 시나리오 7개 병렬)
   - sonnet-docs-sync: T049 (docs/api 동기화 + schema check)
4. Lead Opus 가 push / PR / CI / Codex review handle (sequential, AGENTS.md 룰)

---

## Notes

- **Total task 수**: 49 (T001-T049). 100 cap 안전 (예산 90 한도 안, ~45 = 약 50% margin).
- [P] tasks = different files / no dependencies → 병렬 가능
- [USx] label = user story 매핑
- 모든 path 절대 (worktree `/Users/um-yunsang/KOSMOS-w-2522/` 기준)
- TDD 패턴 — 각 user story 마다 implementation + test 동일 phase. test 가 implementation 보다 먼저 작성되는 것이 권장 (메모리 `feedback_pr_pre_merge_interactive_test`)
- Commit after each task or logical group (conventional commit)
- Stop / validate at each Phase checkpoint
- Phase 분할 분리 PR X — 단일 Epic single PR (사용자 디렉티브)

## Pre-emit budget check

- 49 tasks ≤ 90 cap ✅
- 7 deferred items (spec.md § Scope Boundaries) NEEDS TRACKING — `/speckit-taskstoissues` 가 placeholder 발행. 49 + 7 = 56 sub-issue, 100 cap margin 44.
- Epic + 49 tasks + 7 deferred + 1 placeholder buffer = 58 sub-issue. **PASS**.
