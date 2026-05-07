# 플러그인 아키텍처 (Plugin Architecture)

> KOSMOS 플러그인이 host 와 어떻게 결합되는지 설명합니다. 기여자는 빠른 시작 직후 이 문서를 읽고 본격 작성에 들어가야 합니다 (quickstart.ko.md § 단계 3).
>
> 참고: [`docs/vision.md § Layer 2`](../vision.md), [Spec 022 BM25 retrieval](../../specs/022-mvp-main-tool/spec.md), active primitive harness notes in [`docs/onboarding/five-primitive-harness.md`](../onboarding/five-primitive-harness.md), [Migration tree § L1-B](../requirements/kosmos-migration-tree.md), [`AGENTS.md § New tool adapter`](../../AGENTS.md), [ADR-007 plugin namespace](../adr/ADR-007-plugin-tool-id-namespace.md).

---

## 큰 그림

KOSMOS 는 6-layer harness 입니다 (`docs/vision.md`). 플러그인은 **Layer 2 (Tool System)** 의 외부 진입점이며, host 는 본질적으로 다음 5개 책임을 가집니다:

1. **Manifest 검증** — `PluginManifest` Pydantic 스키마 + 5 cross-field validator (Spec 1636 T006).
2. **SLSA 서명 검증** — `slsa-verifier verify-artifact` 호출, exit 0 만 통과 (Spec 1636 T011 + R-3).
3. **레지스트리 결합** — `ToolRegistry.register()` 를 통해 Spec 022/024/025/031 의 V1-V6 + v1.2 dual-axis 불변량 chain 적용 (Spec 1636 T009).
4. **BM25 색인 재구성** — 등록 직후 `lookup(mode="search")` 가 즉시 결과 surface (Spec 1636 SC-004).
5. **동의 영수증 기록** — Spec 035 ledger 확장 (`plugin_install` / `plugin_uninstall`).

플러그인 작성자는 위 5단계 중 어느 하나도 직접 호출하지 않습니다. `manifest.yaml` + `adapter.py` + `schema.py` 만 작성하면 host 가 나머지를 자동 처리.

---

## Active plugin primitive 매핑

현재 플러그인이 binding 할 수 있는 active 동사:

| Primitive | 의미 | 대표 사용처 |
|---|---|---|
| `lookup` | 조회 | KOROAD 사고 검색, KMA 일기예보, HIRA 병원 검색, 모든 `lookup(mode="search/fetch")` |
| `submit` | 제출 (irreversible) | 정부24 민원 제출, 공동인증서 서명 후 제출 (Spec 024 V4 invariant 적용) |
| `verify` | 검증 | KEC 차량 검사 결과, 신원 인증 결과 read-back |

`subscribe` 는 국민비서/정부 앱/휴대폰 푸시 같은 별도 delivery runtime 이 필요하므로 현재 플러그인 verb 에서 비활성입니다.

> **resolve_location 은 plugin 이 override 할 수 없습니다** (Q8-NO-ROOT-OVERRIDE). 위치 해석은 host 가 소유한 built-in primitive 입니다.

플러그인의 `tool_id` 는 반드시 다음 정규식을 따라야 합니다 (ADR-007):

```regex
^plugin\.[a-z][a-z0-9_]*\.(lookup|submit|verify)$
```

예시:
- `plugin.busan_bike.lookup` ✓
- `plugin.gov24_petition.submit` ✓
- `plugin.busan_bike.fetch` ✗ (verb 미허용)
- `plugin.busan-bike.lookup` ✗ (하이픈 미허용)
- `plugin.busan_bike.resolve_location` ✗ (Q8-NO-ROOT-OVERRIDE)

---

## 모듈 계약 (`adapter.py` / `schema.py`)

Host 는 플러그인 모듈에서 정확히 두 개의 심볼을 찾습니다:

| 심볼 | 타입 | 책임 |
|---|---|---|
| `TOOL` | `kosmos.tools.models.GovAPITool` | 레지스트리 메타데이터. `id` 가 manifest 의 `adapter.tool_id` 와 byte-equal. |
| `adapter` 또는 `ADAPTER` | `async (validated_input) -> dict` | 실제 실행 로직. 입력은 `input_schema.model_validate()` 통과 후 전달, 반환 dict 는 `output_schema` 로 재검증. |

```python
# plugin_busan_bike/adapter.py
from kosmos.tools.models import GovAPITool
from .schema import LookupInput, LookupOutput

TOOL = GovAPITool(
    id="plugin.busan_bike.lookup",
    name_ko="부산 따릉이 조회",
    ministry="OTHER",
    # ... (전체 필드는 quickstart.ko.md § 단계 6 참고)
)

async def adapter(payload: LookupInput) -> dict:
    # ... 실제 호출 ...
    return {"stations": [...]}
```

**`schema.py`** 는 `LookupInput` (또는 primitive-별 입력) + `LookupOutput` 을 export. 모든 모델:
- `frozen=True, extra="forbid"` (Constitution §III)
- `Any` 금지
- 모든 `Field` 에 `description=` (Spec 019 input-discipline)

---

## 레지스트리 결합 흐름

```
manifest.yaml ──parse─▶ PluginManifest (Pydantic v2 frozen)
                              │
                              │  ① 5 cross-field validator
                              │     (mock_source / pipa_required /
                              │      pipa_hash / otel_attribute / namespace)
                              ▼
                       AdapterRegistration  ◀── embed
                              │
                              │  ② V1-V6 + v1.2 dual-axis
                              │     (Spec 024/025/031 모두 자동 적용)
                              ▼
                       register_plugin_adapter(manifest)
                              │
                              ├─ importlib.util.spec_from_file_location
                              │   → adapter.py (TOOL + adapter callable resolve)
                              ├─ ToolRegistry.register(TOOL)
                              │   ├─ V3 / V6 backstop (model_construct bypass 방어)
                              │   └─ retriever.rebuild(corpus) ── BM25 재색인
                              ├─ executor.register_adapter(tool_id, adapter_fn)
                              └─ OTEL span "kosmos.plugin.install"
                                  └─ kosmos.plugin.id = manifest.plugin_id
```

이 흐름은 다음 파일에 구현되어 있습니다:
- `src/kosmos/plugins/manifest_schema.py` — PluginManifest + PIPATrusteeAcknowledgment.
- `src/kosmos/plugins/registry.py` — `register_plugin_adapter` + `auto_discover` + `_rebuild_bm25_index_for`.
- `src/kosmos/plugins/installer.py` — 8-phase install (catalog → bundle → SLSA → manifest → consent → register → receipt).
- `src/kosmos/tools/registry.py` — Spec 022 ToolRegistry + Spec 1636 T010 shim.

---

## OTEL 발산 계약

플러그인 install/invoke 시 다음 span 이 자동 발산됩니다 (Spec 021 KOSMOS extension):

| Span | Trigger | 핵심 attribute |
|---|---|---|
| `kosmos.plugin.install` | `register_plugin_adapter` 진입 | `kosmos.plugin.id`, `kosmos.plugin.version`, `kosmos.plugin.tier`, `kosmos.plugin.tool_id`, `kosmos.plugin.permission_layer` |
| `execute_tool <tool_id>` | 어댑터 호출 | `gen_ai.tool.name`, `gen_ai.tool.type`, `kosmos.tool.adapter` |

manifest.yaml 의 `otel_attributes["kosmos.plugin.id"]` 는 **반드시 `plugin_id` 와 일치** 해야 합니다 (`_v_otel_attribute` validator 가 enforce). 이는 Langfuse / OTLP collector 가 plugin-별 trace 를 정확히 묶도록 보장합니다.

---

## 디렉토리 레이아웃

설치 후 host 는 플러그인을 다음 경로에 보관합니다 (`KOSMOS_PLUGIN_INSTALL_ROOT` 기본값):

```
~/.kosmos/memdir/user/plugins/
├── index.json                                   # 오프라인 카탈로그 캐시
└── <plugin_id>/                                 # 플러그인 1개당 디렉토리
    ├── manifest.yaml                            # 검증된 매니페스트 사본
    ├── adapter.py                               # 기여자가 작성한 어댑터 코드
    ├── schema.py                                # 입력/출력 Pydantic 스키마
    ├── tests/                                   # install-time sanity 용 (replayed)
    │   ├── test_adapter.py
    │   └── fixtures/<tool_id>.json
    ├── README.ko.md
    └── .signature/                              # SLSA 검증 산출물 (감사 보관)
        ├── bundle.tar.gz
        ├── provenance.intoto.jsonl
        └── verify-result.json
```

번들 다운로드 캐시 (`KOSMOS_PLUGIN_BUNDLE_CACHE` 기본 `~/.kosmos/cache/plugin-bundles/`) 와 vendored slsa-verifier (`KOSMOS_PLUGIN_VENDOR_ROOT` 기본 `~/.kosmos/vendor/`) 는 별도 경로 — install 실패 시에도 forensic 분석을 위해 번들이 보존됩니다.

---

## 외부 repo 매트릭스

| Repo | 역할 | 비고 |
|---|---|---|
| `kosmos-plugin-store/kosmos-plugin-template` | scaffold 템플릿 | "Use this template" 진입점 |
| `kosmos-plugin-store/index` | 카탈로그 인덱스 | `KOSMOS_PLUGIN_CATALOG_URL` 기본값 |
| `kosmos-plugin-store/kosmos-plugin-seoul-subway` | Live 예제 1 | 서울 지하철 도착 정보 |
| `kosmos-plugin-store/kosmos-plugin-post-office` | Live 예제 2 | 우정사업본부 택배 추적 |
| `kosmos-plugin-store/kosmos-plugin-nts-homtax` | Mock 예제 1 | 국세청 홈택스 (mock — 정부 partnership 부재) |
| `kosmos-plugin-store/kosmos-plugin-nhis-check` | Mock 예제 2 | 국민건강보험공단 건강검진 (mock) |

`kosmos-plugin-store` org 는 SLSA-provenance attribution 을 위한 canonical source URI prefix 입니다 (R-3). 외부 fork 도 가능하나 그 경우 `slsa_provenance_url` 이 fork 의 GitHub Releases 를 가리켜야 합니다.

---

## 보안 invariant chain

플러그인 manifest 는 host 의 기존 보안 spec 들과 자동으로 결합됩니다 — 별도 enforcement 없음:

| Spec | Invariant | 적용 지점 |
|---|---|---|
| Spec 024 V1 | `extra="forbid"` 모든 GovAPITool 필드 | `AdapterRegistration` embed |
| Spec 024 V2 | `pipa_class != non_personal ⇒ dpa_reference` 필수 | GovAPITool model_validator |
| Spec 024 V3 | `auth_level == TOOL_MIN_AAL[tool_id]` | GovAPITool model_validator + registry backstop |
| Spec 024 V4 | `is_irreversible ⇒ auth_level >= AAL2` | GovAPITool model_validator |
| Spec 025 V6 | `(auth_type, auth_level)` ∈ canonical 매핑 | GovAPITool model_validator + registry backstop |
| Spec 031 v1.2 | `published_tier_minimum` + `nist_aal_hint` 필수 | AdapterRegistration model_validator |
| Spec 1636 Q6 | `acknowledgment_sha256 == canonical hash` | PluginManifest._v_pipa_hash |
| Spec 1636 Q8 | `tool_id` namespace + verb 제한 | PluginManifest._v_namespace |

이는 곧 **플러그인 작성자가 보안 invariant 를 잊을 수 없음** 을 의미합니다. validator 가 fail-closed 로 거부하므로 잘못된 manifest 는 install 자체가 차단됩니다.

---

## Bilingual glossary

> 이 섹션은 9개 가이드 (`docs/plugins/*.md`) 모두에 동일한 형식으로 포함됩니다 (FR-006).

| 한국어 | English | 설명 |
|---|---|---|
| 어댑터 | adapter | 플러그인의 코어 모듈; `TOOL` + 비동기 callable 을 export. |
| 매니페스트 | manifest | `manifest.yaml`; `PluginManifest` Pydantic 스키마. |
| 권한 레이어 | permission layer | 1/2/3 — 시민 동의 강도. Spec 033 enforce. |
| 검색 힌트 | search hint | BM25 인덱스 토큰 (`search_hint_ko` / `_en`). Spec 022. |
| 카탈로그 | catalog | `kosmos-plugin-store/index/index.json`. |
| 수탁자 | trustee | PIPA §26 수탁 측. |
| 동의 영수증 | consent receipt | Spec 035 ledger 확장 (`plugin_install` / `plugin_uninstall`). |
| 프리미티브 | primitive | active plugin 동사 (`lookup`, `submit`, `verify`). `subscribe` 는 앱/푸시 런타임 전까지 비활성. |
| 1차 매핑 | byte mirror | `source_mode=OPENAPI`. |
| 2차 매핑 | shape mirror | `source_mode=OOS`. |
