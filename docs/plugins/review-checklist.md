# 50-Item Plugin Review Checklist

> Auto-generated from [`tests/fixtures/plugin_validation/checklist_manifest.yaml`](../../tests/fixtures/plugin_validation/checklist_manifest.yaml).
> 수동 편집하지 말고, YAML 을 갱신한 뒤 `uv run python scripts/render_checklist.py` 로 재생성하세요.

Total: **50** items.

## Q1 — Schema integrity (10)

| ID | Korean | English | Source | Check type | Implementation |
|---|---|---|---|---|---|
| `Q1-PYV2` | Pydantic v2 BaseModel 사용 | Pydantic v2 BaseModel | Constitution §III | static | `kosmos.plugins.checks.q1_schema:check_pyv2` |
| `Q1-NOANY` | `Any` 타입 금지 | No `Any` types | Constitution §III | static | `kosmos.plugins.checks.q1_schema:check_noany` |
| `Q1-FIELD-DESC` | 모든 Field 에 description | Every Field has `description=` | Spec 019 input discipline | static | `kosmos.plugins.checks.q1_schema:check_field_desc` |
| `Q1-INPUT-MODEL` | input_schema 클래스 존재 | input_schema class present | docs/tool-adapters.md | static | `kosmos.plugins.checks.q1_schema:check_input_model` |
| `Q1-OUTPUT-MODEL` | output_schema 클래스 존재 | output_schema class present | docs/tool-adapters.md | static | `kosmos.plugins.checks.q1_schema:check_output_model` |
| `Q1-MANIFEST-VALID` | manifest.yaml 이 PluginManifest 검증 통과 | manifest.yaml validates against PluginManifest | FR-019 | unit | `kosmos.plugins.checks.q1_schema:check_manifest_valid` |
| `Q1-FROZEN` | model_config(frozen=True) 선언 | model_config(frozen=True) | Spec 027/032 pattern | static | `kosmos.plugins.checks.q1_schema:check_frozen` |
| `Q1-EXTRA-FORBID` | model_config(extra=...) 명시 | model_config(extra=...) declared | Spec 024 V1 | static | `kosmos.plugins.checks.q1_schema:check_extra_forbid` |
| `Q1-VERSION-SEMVER` | version 이 SemVer 형식 | version is SemVer | FR-019 | unit | `kosmos.plugins.checks.q1_schema:check_version_semver` |
| `Q1-PLUGIN-ID-REGEX` | plugin_id 가 snake_case [a-z][a-z0-9_]* | plugin_id matches snake_case regex | Spec 022 tool_id pattern | unit | `kosmos.plugins.checks.q1_schema:check_plugin_id_regex` |

## Q2 — Fail-closed defaults (6)

| ID | Korean | English | Source | Check type | Implementation |
|---|---|---|---|---|---|
| `Q2-AUTH-DEFAULT` | requires_auth 기본 True | requires_auth default True | Constitution §II | unit | `kosmos.plugins.checks.q2_failclosed:check_auth_default` |
| `Q2-PII-DEFAULT` | is_personal_data 와 processes_pii 일치 | is_personal_data matches processes_pii | Constitution §II | unit | `kosmos.plugins.checks.q2_failclosed:check_pii_default` |
| `Q2-CONCURRENCY-DEFAULT` | is_concurrency_safe / is_irreversible 모순 없음 | is_concurrency_safe and is_irreversible are not contradictory | Constitution §II | unit | `kosmos.plugins.checks.q2_failclosed:check_concurrency_default` |
| `Q2-CACHE-DEFAULT` | cache_ttl_seconds ≥ 0 | cache_ttl_seconds ≥ 0 | Constitution §II | unit | `kosmos.plugins.checks.q2_failclosed:check_cache_default` |
| `Q2-RATE-LIMIT-CONSERVATIVE` | rate_limit_per_minute ≤ 30 | rate_limit_per_minute ≤ 30 | docs/tool-adapters.md guidance | unit | `kosmos.plugins.checks.q2_failclosed:check_rate_limit_conservative` |
| `Q2-AUTH-EXPLICIT` | auth_level / pipa_class / dpa_reference 명시 | auth_level / pipa_class / dpa_reference explicitly declared | Spec 024 + docs/tool-adapters.md | unit | `kosmos.plugins.checks.q2_failclosed:check_auth_explicit` |

## Q3 — Security V1–V6 invariants (5)

| ID | Korean | English | Source | Check type | Implementation |
|---|---|---|---|---|---|
| `Q3-V1-NO-EXTRA` | manifest 에 정의되지 않은 키 금지 | no unknown keys in manifest | Spec 024 V1 | unit | `kosmos.plugins.checks.q3_security:check_v1_no_extra` |
| `Q3-V2-DPA` | pipa_class != non_personal ⇒ dpa_reference 비어 있지 않음 | pipa_class != non_personal ⇒ dpa_reference non-null | Spec 024 V2 | unit | `kosmos.plugins.checks.q3_security:check_v2_dpa` |
| `Q3-V3-AAL-MATCH` | auth_level 이 TOOL_MIN_AAL 과 일치 | auth_level matches TOOL_MIN_AAL row | Spec 024 V3 | unit | `kosmos.plugins.checks.q3_security:check_v3_aal_match` |
| `Q3-V4-IRREVERSIBLE-AAL` | is_irreversible=True ⇒ auth_level ≥ AAL2 | is_irreversible=True ⇒ auth_level ≥ AAL2 | Spec 024 V4 | unit | `kosmos.plugins.checks.q3_security:check_v4_irreversible_aal` |
| `Q3-V6-AUTH-LEVEL-MAP` | auth_type ↔ auth_level 허용 매핑 | auth_type ↔ auth_level allow-list | Spec 025 V6 | unit | `kosmos.plugins.checks.q3_security:check_v6_auth_level_map` |

## Q4 — Discovery & docs (8)

| ID | Korean | English | Source | Check type | Implementation |
|---|---|---|---|---|---|
| `Q4-HINT-KO` | search_hint_ko 비어 있지 않음 | search_hint_ko non-empty | docs/tool-adapters.md | unit | `kosmos.plugins.checks.q4_discovery:check_hint_ko` |
| `Q4-HINT-EN` | search_hint_en 비어 있지 않음 | search_hint_en non-empty | docs/tool-adapters.md | unit | `kosmos.plugins.checks.q4_discovery:check_hint_en` |
| `Q4-HINT-NOUNS` | search_hint_ko 한국어 명사 ≥ 3 개 | search_hint_ko ≥ 3 Korean nouns | docs/tool-adapters.md guidance | unit | `kosmos.plugins.checks.q4_discovery:check_hint_nouns` |
| `Q4-HINT-MINISTRY` | search_hint_ko 에 부처 / 기관 이름 포함 | search_hint_ko mentions ministry / agency name | docs/tool-adapters.md | unit | `kosmos.plugins.checks.q4_discovery:check_hint_ministry` |
| `Q4-NAME-KO` | search_hint_ko 에 한국어 텍스트 포함 | search_hint_ko includes Korean script | docs/tool-adapters.md | unit | `kosmos.plugins.checks.q4_discovery:check_name_ko` |
| `Q4-CITE` | README.ko.md 에 참조 URL 1개 이상 | README.ko.md cites at least one URL | Constitution §I + FR-007 | static | `kosmos.plugins.checks.q4_discovery:check_cite` |
| `Q4-README-KO` | README.ko.md 파일 존재 | README.ko.md present | FR-001 / FR-010 | static | `kosmos.plugins.checks.q4_discovery:check_readme_ko` |
| `Q4-README-MIN-LEN` | README.ko.md ≥ 500 자 | README.ko.md ≥ 500 chars | Author-effort floor | static | `kosmos.plugins.checks.q4_discovery:check_readme_min_len` |

## Q5 — Permission tier (3)

| ID | Korean | English | Source | Check type | Implementation |
|---|---|---|---|---|---|
| `Q5-LAYER-DECLARED` | permission_layer ∈ {1, 2, 3} | permission_layer in {1, 2, 3} | Spec 033 | unit | `kosmos.plugins.checks.q5_permission:check_layer_declared` |
| `Q5-LAYER-MATCHES-PII` | processes_pii=True ⇒ permission_layer ≥ 2 | processes_pii=True ⇒ permission_layer ≥ 2 | Spec 033 | unit | `kosmos.plugins.checks.q5_permission:check_layer_matches_pii` |
| `Q5-LAYER-DOC` | README.ko.md 에 layer 근거 설명 | README.ko.md explains layer rationale | FR-010 | static | `kosmos.plugins.checks.q5_permission:check_layer_doc` |

## Q6 — PIPA §26 trustee (4)

| ID | Korean | English | Source | Check type | Implementation |
|---|---|---|---|---|---|
| `Q6-PIPA-PRESENT` | processes_pii=True ⇒ pipa_trustee_acknowledgment 블록 존재 | block present when processes_pii=True | FR-014 + Constitution §V | unit | `kosmos.plugins.checks.q6_pipa:check_pipa_present` |
| `Q6-PIPA-HASH` | acknowledgment_sha256 == canonical SHA-256 | acknowledgment_sha256 matches canonical hash | FR-014 | unit | `kosmos.plugins.checks.q6_pipa:check_pipa_hash` |
| `Q6-PIPA-ORG` | trustee_org_name + trustee_contact 비어 있지 않음 | trustee_org + contact non-empty | FR-014 | unit | `kosmos.plugins.checks.q6_pipa:check_pipa_org` |
| `Q6-PIPA-FIELDS-LIST` | pii_fields_handled 1개 이상 | pii_fields_handled non-empty list | FR-014 | unit | `kosmos.plugins.checks.q6_pipa:check_pipa_fields_list` |

## Q7 — Tier classification + mocking discipline (5)

| ID | Korean | English | Source | Check type | Implementation |
|---|---|---|---|---|---|
| `Q7-TIER-LITERAL` | tier ∈ {live, mock} | tier in {live, mock} | FR-019 | unit | `kosmos.plugins.checks.q7_tier:check_tier_literal` |
| `Q7-MOCK-SOURCE` | tier=mock ⇒ mock_source_spec 비어 있지 않음 | tier=mock ⇒ mock_source_spec non-empty | FR-019 + memory feedback_mock_evidence_based | unit | `kosmos.plugins.checks.q7_tier:check_mock_source` |
| `Q7-LIVE-USES-NETWORK` | tier=live 어댑터는 httpx / aiohttp / requests 중 하나 import | tier=live adapter imports httpx / aiohttp / requests | Heuristic from feedback_mock_evidence_based | static | `kosmos.plugins.checks.q7_tier:check_live_uses_network` |
| `Q7-MOCK-NO-EGRESS` | tier=mock 어댑터는 HTTP 클라이언트 import 금지 | tier=mock adapter must not import HTTP clients | Constitution §IV | static | `kosmos.plugins.checks.q7_tier:check_mock_no_egress` |
| `Q7-LIVE-FIXTURE` | tests/fixtures/ 에 *.json 1개 이상 | tests/fixtures/ has at least one *.json | Constitution §IV | static | `kosmos.plugins.checks.q7_tier:check_live_fixture` |

## Q8 — Reserved-name & namespace (3)

| ID | Korean | English | Source | Check type | Implementation |
|---|---|---|---|---|---|
| `Q8-NAMESPACE` | tool_id 가 plugin.<id>.<verb> 형식 | tool_id matches plugin.<id>.<verb> | FR-022 + migration tree § L1-C C7 | unit | `kosmos.plugins.checks.q8_namespace:check_namespace` |
| `Q8-NO-ROOT-OVERRIDE` | tool_id verb 가 host 예약 (resolve_location) 과 충돌 안 함 | tool_id verb is not a host-reserved primitive | FR-022 | unit | `kosmos.plugins.checks.q8_namespace:check_no_root_override` |
| `Q8-VERB-IN-PRIMITIVES` | verb ∈ active plugin primitive (lookup/submit/verify) | verb is one of the active plugin primitives | FR-004 + migration tree § L1-C C1 | unit | `kosmos.plugins.checks.q8_namespace:check_verb_in_primitives` |

## Q9 — OTEL emission (2)

| ID | Korean | English | Source | Check type | Implementation |
|---|---|---|---|---|---|
| `Q9-OTEL-ATTR` | otel_attributes['kosmos.plugin.id'] = plugin_id | otel_attributes['kosmos.plugin.id'] = plugin_id | FR-021 + Spec 021 | unit | `kosmos.plugins.checks.q9_otel:check_otel_attr` |
| `Q9-OTEL-EMIT` | kosmos.plugin.install span 에 attribute 가 실제로 emit 됨 | kosmos.plugin.install span actually emits attribute | FR-021 | unit | `kosmos.plugins.checks.q9_otel:check_otel_emit` |

## Q10 — Tests & fixtures (4)

| ID | Korean | English | Source | Check type | Implementation |
|---|---|---|---|---|---|
| `Q10-HAPPY-PATH` | happy-path 테스트 1개 이상 | ≥ 1 happy-path test | docs/tool-adapters.md | unit | `kosmos.plugins.checks.q10_tests:check_happy_path` |
| `Q10-ERROR-PATH` | error-path 테스트 1개 이상 (pytest.raises 포함) | ≥ 1 error-path test (uses pytest.raises) | docs/tool-adapters.md | unit | `kosmos.plugins.checks.q10_tests:check_error_path` |
| `Q10-FIXTURE-EXISTS` | tests/fixtures/*.json 이 valid JSON | tests/fixtures/*.json files are valid JSON | docs/tool-adapters.md | unit | `kosmos.plugins.checks.q10_tests:check_fixture_exists` |
| `Q10-NO-LIVE-IN-CI` | @pytest.mark.live 마커가 live-only 테스트에 부착 | live-only tests are gated by @pytest.mark.live | Constitution §IV | unit | `kosmos.plugins.checks.q10_tests:check_no_live_in_ci` |

## Failure messages

When a check fails the workflow surfaces both Korean and English failure
messages on the PR comment + step summary. The bilingual messages live in
the YAML rows below — see `failure_message_ko` / `failure_message_en`.
