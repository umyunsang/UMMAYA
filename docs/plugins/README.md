# KOSMOS Plugin System

부처·기관·지자체·시민 기여자가 KOSMOS 의 tool 어댑터를 추가하는 플러그인 시스템. Korean-primary 가이드.

> Spec 1636 P5 Plugin DX 5-tier 완료. 모든 인프라 + 4 examples + 50-item validation 활성.
> Canonical 근거: [Migration tree § B8](../requirements/kosmos-migration-tree.md), [`docs/vision.md`](../vision.md), [Spec 1636](../../specs/1636-plugin-dx-5tier/spec.md).

## Five-tier developer-experience package

| Tier | Deliverable | Status |
|---|---|---|
| **Tier 1 · Start** | [`kosmos-plugin-template`](https://github.com/kosmos-plugin-store/kosmos-plugin-template) (is_template) · `kosmos plugin init <name>` (TUI) · `uvx kosmos-plugin-init` (Python fallback) · [quickstart.ko.md](quickstart.ko.md) | ✅ shipped |
| **Tier 2 · Guide** | [architecture.md](architecture.md) · [pydantic-schema.md](pydantic-schema.md) · [search-hint.md](search-hint.md) · [permission-tier.md](permission-tier.md) · [data-go-kr.md](data-go-kr.md) · [live-vs-mock.md](live-vs-mock.md) · [testing.md](testing.md) · [security-review.md](security-review.md) | ✅ shipped |
| **Tier 3 · Examples** | [seoul-subway](https://github.com/kosmos-plugin-store/kosmos-plugin-seoul-subway) (Live) · [post-office](https://github.com/kosmos-plugin-store/kosmos-plugin-post-office) (Live) · [nts-homtax](https://github.com/kosmos-plugin-store/kosmos-plugin-nts-homtax) (Mock) · [nhis-check](https://github.com/kosmos-plugin-store/kosmos-plugin-nhis-check) (Mock) | ✅ shipped |
| **Tier 4 · Submit** | [plugin_submission.yml](../../.github/ISSUE_TEMPLATE/plugin_submission.yml) · [plugin-validation.yml](../../.github/workflows/plugin-validation.yml) (reusable) · [review-checklist.md](review-checklist.md) (50 items) · [security-review.md](security-review.md) (PIPA §26) | ✅ shipped |
| **Tier 5 · Registry** | [kosmos-plugin-store/index](https://github.com/kosmos-plugin-store/index) (catalog) · `/plugin install <name>` (TUI) · SLSA v1.0 verification · OTEL `kosmos.plugin.id` 발산 · 동의 영수증 | ✅ shipped |

## 시작하기 (Quickstart)

```bash
# 옵션 A — GitHub "Use this template" 버튼
# 옵션 B — TUI (Bun + Ink)
kosmos plugin init my_plugin --non-interactive --tier live --layer 1 --no-pii

# 옵션 C — Python fallback
uvx kosmos-plugin-init my_plugin --tier live --layer 1 --no-pii
```

자세한 9단계 walkthrough: [`quickstart.ko.md`](quickstart.ko.md). SC-001 budget: ≤ 30분.

## Plugin contract (요약)

모든 플러그인은:

1. **`Tool.ts` 호환 GovAPITool 등록** — TS + Python 양쪽 자동 (`adapter.py` 의 `TOOL` 심볼 + `register_plugin_adapter` 호출). 필드: `id`, `name_ko`, `primitive`, `permission_layer`, `ministry`, `tier`, `input_schema`, `output_schema`, `search_hint`, `pipa_class`, `auth_level` 등 ([architecture.md](architecture.md)).
2. **Reserved-name discipline** — active plugin primitive (`lookup` / `submit` / `verify`) 만 허용. tool_id 형식: `plugin.<plugin_id>.<verb>` ([ADR-007](../adr/ADR-007-plugin-tool-id-namespace.md)). `subscribe` 는 앱/푸시 런타임이 생길 때까지 신규 플러그인 verb 로 받지 않습니다.
3. **권한 Layer 어댑터-레벨 선언** — 1 (green) / 2 (orange) / 3 (red). primitive default 없음 ([permission-tier.md](permission-tier.md)).
4. **`manifest.yaml` 게시** — `PluginManifest` Pydantic 스키마 통과 필수. tier, PII 처리, PIPA §26 trustee acknowledgment, OTEL attributes, search hints, SLSA provenance URL 모두 포함.
5. **PIPA §26 trustee acknowledgment** — `processes_pii: true` 일 때 필수. canonical SHA-256 일치 ([security-review.md](security-review.md)).
6. **50-item validation** — [`plugin-validation.yml`](../../.github/workflows/plugin-validation.yml) reusable workflow 가 매트릭스로 50개 항목 모두 검증 후 PR 머지 가능 ([review-checklist.md](review-checklist.md)).

## 문서 가이드 (9개)

| 가이드 | 대상 | 핵심 내용 |
|---|---|---|
| [`quickstart.ko.md`](quickstart.ko.md) | 첫 기여자 | 9단계 walkthrough · 30분 예산 · Bilingual glossary |
| [`architecture.md`](architecture.md) | 모든 기여자 | host 결합 · 4 primitive · 보안 invariant chain |
| [`pydantic-schema.md`](pydantic-schema.md) | 모든 기여자 | model_config · Field description · 흔한 안티 패턴 |
| [`search-hint.md`](search-hint.md) | 모든 기여자 | BM25 검색 친화적 hint · Kiwipiepy 명사 ≥ 3 · 부처 화이트리스트 |
| [`permission-tier.md`](permission-tier.md) | 모든 기여자 | Layer 1/2/3 결정 트리 · Spec 033 · Spec 024 V4 invariant |
| [`data-go-kr.md`](data-go-kr.md) | Live tier | 키 발급 · KOSMOS_* env · rate-limit · fixture 기록 · 부처 특수 사항 |
| [`live-vs-mock.md`](live-vs-mock.md) | 모든 기여자 | 5점 척도 매트릭스 · 의사결정 트리 · 전환 절차 |
| [`security-review.md`](security-review.md) | PII / Layer 3 | PIPA §26 5단계 · L3 gate · L2+ sandboxing |
| [`testing.md`](testing.md) | 모든 기여자 | block_network · @pytest.mark.live · fixture replay |

추가:
- [`review-checklist.md`](review-checklist.md) — 50-item 매트릭스 (auto-generated from YAML)

## Documentation language policy

**Korean primary, English secondary** (FR-006 Bilingual glossary 9개 가이드 모두 적용).

근거: 공공기관 기여자 대상. 코드 식별자 (`plugin_id`, `tool_id`, 함수명 등) 는 영어 (FR-025), 설명/메시지는 한국어. 9개 가이드 모두 `## Bilingual glossary` 섹션으로 핵심 용어 ko↔en 매핑.

## See also

- [`../vision.md`](../vision.md) § Layer 2 (Tool System) — 6-layer harness 위치
- [`../tool-adapters.md`](../tool-adapters.md) — built-in 어댑터 필드 reference
- [`../api/`](../api/) — 등록된 부처별 어댑터 spec
- [`../../AGENTS.md` § New tool adapter](../../AGENTS.md) — KOSMOS host 측 contributor 진입점
- [Spec 1636 plugin DX 5-tier](../../specs/1636-plugin-dx-5tier/spec.md) — 본 시스템 spec
