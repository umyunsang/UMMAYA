# Epic P5 · Plugin DX (Full 5-tier)

## Objective

부처·기관·시민개발자가 UMMAYA에 tool adapter 기여할 수 있도록 5-tier
Developer Experience 인프라 구축. 한국어 primary · PIPA 수탁자 책임 명시.

## Acceptance criteria

- [ ] `ummaya-plugin-template` GitHub 템플릿 저장소 공개
- [ ] `ummaya plugin init <name>` CLI 명령 작동
- [ ] `docs/plugins/` 한국어 가이드 7종 작성
- [ ] 예시 플러그인 4종 구현 (지하철 · 우체국 · 홈택스-Mock · 건강검진-Mock)
- [ ] PR validation workflow · 50-item checklist 통과시만 merge
- [ ] 중앙 레지스트리 `ummaya-plugin-store` (GitHub org) 카탈로그
- [ ] 플러그인 primitive 네임스페이스 `plugin.<id>.<verb>` 강제
- [ ] PIPA 수탁자 서약문 manifest 필드 필수

## File-level scope

### Tier 1 · 시작하기

#### `ummaya-plugin-template` (신규 저장소)
- `pyproject.toml` 템플릿
- `plugin.<name>/adapter.py` boilerplate
- `plugin.<name>/schema.py` Pydantic 모델
- `plugin.<name>/tests/test_adapter.py` fixture 재생
- `README.ko.md` quickstart

#### `tui/src/commands/plugin-init.ts`
- `ummaya plugin init <name>` CLI · scaffolding

### Tier 2 · Guide (docs/plugins/)

- `docs/plugins/README.md` — index (이미 있음, 확장)
- `docs/plugins/quickstart.ko.md` — 30분 quickstart
- `docs/plugins/architecture.md` — Tool.ts + primitive 매핑
- `docs/plugins/pydantic-schema.md` — 입출력 스키마 작성법
- `docs/plugins/search-hint.md` — 검색 힌트 Ko/En 가이드
- `docs/plugins/permission-tier.md` — Layer 1/2/3 결정 트리
- `docs/plugins/data-go-kr.md` — 공공데이터 포털 키 연동
- `docs/plugins/live-vs-mock.md` — Mock 어댑터 작성법
- `docs/plugins/testing.md` — pytest fixture · live 마크

### Tier 3 · Examples

- `ummaya-plugin-seoul-subway/` — 지하철 실시간 도착 (Live, Seoul Open Data Plaza)
- `ummaya-plugin-post-office/` — 우체국 택배 (Live, 우정사업본부)
- `ummaya-plugin-nts-homtax/` — 홈택스 (Mock, 권한 미보유)
- `ummaya-plugin-nhis-check/` — 건강검진 (Mock)

### Tier 4 · Submission

- `.github/ISSUE_TEMPLATE/plugin-submission.yml` (Python tools issue용)
- `.github/workflows/plugin-validation.yml` — JSON Schema · permission tier · search_hint 검증
- `docs/plugins/review-checklist.md` — 50 항목
- `docs/plugins/security-review.md` — L3 게이트 요구사항 + PIPA 수탁자 서약

### Tier 5 · Registry

- `ummaya-plugin-store` (신규 GitHub org) — 공식 카탈로그
- `tui/src/commands/plugin-install.ts` — `ummaya plugin install <name>` · SLSA 서명 검증
- `src/ummaya/plugins/registry.py` — 플러그인 auto-discovery · manifest 검증
- `src/ummaya/plugins/manifest_schema.py` — 매니페스트 Pydantic (primitive · permission · PIPA 서약)

### 핵심 규약

- 플러그인 primitive 네임스페이스: `plugin.<plugin_id>.<verb>`
  - Root 4개 (`find`/`locate`/`send`/`check`) **예약어** · 오버라이드 금지
- PIPA 수탁자 서약문은 모든 PII 처리 플러그인 필수
- 플러그인 OTEL span 강제 (`ummaya.plugin.id` attribute)
- 샌드박스 가이드라인: L2+ 플러그인은 sandbox-exec / firejail 권장

### Out of scope

이 Epic 완료 후 별개 Epic으로:
- 유료 플러그인 모델
- 플러그인간 의존성 그래프
- hot-reload 동적 로딩

### Dependencies

- Epic P0, P1+P2, P3 완료
- `src/ummaya/tools/registry.py` 에 self-classify 메타데이터 wired in (P3)

### Related decisions

`docs/requirements/ummaya-migration-tree.md § L1-B B8`
`docs/plugins/README.md`
