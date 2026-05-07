# Epic P6 · Docs/API specs + Smoke

## Objective

(a) KOSMOS에 등록된 모든 tool adapter의 명세서를 `docs/api/` 에 Markdown +
JSON Schema + OpenAPI 참조 형태로 작성. (b) 통합 bun test 회귀 없음 확인
+ `bun run tui` 사용자 시각 검증 + 단일 PR 발행.

## Acceptance criteria

- [ ] `docs/api/README.md` 인덱스 — 부처별 · primitive별 matrix
- [ ] 15+ Live/Mock adapter 각 Markdown spec 작성 (Pydantic schema 참조)
- [ ] 각 adapter spec: 분류(Live/Mock) · 입출력 envelope · search_hint (ko/en) · data.go.kr 엔드포인트 · 권한 등급 · 예시 호출 · 제약
- [ ] JSON Schema Draft 2020-12 별도 export (`docs/api/schemas/`)
- [ ] OpenAPI 3.0 참조 (선택, meta-tool 래퍼용)
- [ ] `bun test` ≥ 576 pass / 0 fail (Epic P0 baseline 복원)
- [ ] `bun run tui` 사용자 시각 확인 + 5 UI state 동작 확인
- [ ] 단일 통합 PR 발행 (Closes #<Initiative>)

## File-level scope

### `docs/api/` (신규 디렉터리)

#### 인덱스
- `docs/api/README.md` — matrix + 규약

#### 부처별 spec (Live)
- `docs/api/koroad/accident_search.md`
- `docs/api/koroad/accident_hazard_search.md`
- `docs/api/kma/current_observation.md`
- `docs/api/kma/short_term_forecast.md`
- `docs/api/kma/ultra_short_term_forecast.md`
- `docs/api/kma/weather_alert_status.md`
- `docs/api/kma/pre_warning.md`
- `docs/api/kma/forecast_fetch.md`
- `docs/api/hira/hospital_search.md`
- `docs/api/nmc/emergency_search.md` (Layer 3 gated)
- `docs/api/nmc/freshness.md`

#### 부처별 spec (Mock)
- `docs/api/nfa119/emergency_info_service.md`
- `docs/api/mohw_ssis/welfare_eligibility_search.md`

#### 공통 Mock (verify · submit)
- `docs/api/verify/digital_onepass.md`
- `docs/api/verify/mobile_id.md`
- `docs/api/verify/gongdong_injeungseo.md`
- `docs/api/verify/geumyung_injeungseo.md`
- `docs/api/verify/ganpyeon_injeung.md`
- `docs/api/verify/mydata.md`
- `docs/api/submit/fines_pay.md`
- `docs/api/submit/welfare_application.md`

#### resolve_location
- `docs/api/resolve_location/index.md` (juso · sgis · kakao)

> Historical note: an earlier draft of this scope listed a composite adapter under `docs/api/composite/`. That adapter was removed in Epic #1634 per migration tree § L1-B B6 and is no longer in P6 scope.

#### JSON Schema export
- `docs/api/schemas/<tool_id>.json` — JSON Schema Draft 2020-12
- `scripts/build_schemas.py` — Pydantic → JSON Schema 자동 빌드 스크립트

### Smoke 테스트

#### `bun test` 회귀 수정
- Baseline target: 576 pass (P0 달성 상태)
- 깨진 테스트 수정 또는 삭제 (기존 KOSMOS-only 테스트 · CC 포팅 테스트 구분)
- 통합 snapshot 갱신

#### 통합 bun run tui
- 온보딩 5-step 수동 clickthrough
- Active primitive LLM 호출 시나리오 (lookup · submit mock · verify mock). Subscribe is deferred until KOSMOS has an app/push-notification runtime.
- `/agents` · `/plugins` · `/consent list` · `/help` 검증
- Error envelope 3종 수동 유발 테스트
- PDF inline render 검증 (Kitty/iTerm2 환경)

#### PR 발행
- Conventional Commits: `feat: KOSMOS migration (Initiative #X)`
- Body: `Closes #<Initiative>` + 주요 변경 요약 + 시각 확인 체크리스트
- 연결된 sub-issue(Epic)들은 merge 후 close

### 관련 문서 업데이트

- `docs/vision.md § L1-A/B/C` 마이그레이션 결과 반영
- `CLAUDE.md § Active Technologies` 업데이트
- `CHANGELOG.md` KOSMOS v0.1-alpha 항목

### Out of scope

외부 기여 플러그인의 docs/api 엔트리 (별개 Epic에서 Plugin DX 완료 후 진행)

### Dependencies

- Epic P0 ~ P5 완료

### Related decisions

`docs/requirements/kosmos-migration-tree.md § L1-B B7` + `§ P6`
