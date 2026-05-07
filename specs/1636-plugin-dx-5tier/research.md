# Phase 0 — Research & Decisions

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-04-25

This file resolves every NEEDS CLARIFICATION carried into Phase 0 (none — spec was clean), maps every plan decision to a canonical reference per Constitution §I, derives the 50-item review checklist from authoritative KOSMOS sources (Assumption A8), and validates the Deferred Items table per Constitution §VI.

---

## R-0 · Reference mapping (Constitution §I obligation)

Every design decision in `plan.md` traces to one of the following sources from `docs/vision.md § Reference materials` or a prior KOSMOS Spec.

| Plan decision | Reference source | Notes |
|---|---|---|
| Pydantic v2 manifest schema with discriminated nested PIPA block | **Pydantic AI** (`pydantic/pydantic-ai`, MIT) — schema-driven tool registry pattern | We adopt the *pattern* (declarative typed registration with discriminated unions). The actual manifest fields are KOSMOS-specific (`processes_pii`, `pipa_trustee_acknowledgment`). |
| Auto-discovery loader scanning installed plugins at boot | **Claude Agent SDK** (`anthropics/claude-agent-sdk-python`, MIT) — agent-definition discovery + Claude Code `builtinPlugins.ts` (`registerBuiltinPlugin` at startup) | CC uses `Map<string, BuiltinPluginDefinition>` populated by an `initBuiltinPlugins()` call. KOSMOS uses `importlib` walk over `~/.kosmos/memdir/user/plugins/` because plugins are user-installed, not bundled. |
| Plugin namespace `plugin.<plugin_id>.<verb>` and root-primitive reservation | **Spec 031** (`specs/031-five-primitive-harness/spec.md` § 4 `AdapterRegistration`) and migration tree § L1-C C7 (`plugin.<id>.<verb>` namespace explicitly named) | Reuses the existing `AdapterRegistration` class — plugins are GovAPITool instances behind the same registry. |
| Fail-closed manifest defaults (4 fields) | **Constitution §II** + `docs/tool-adapters.md` adapter-shape table | Identical defaults to existing GovAPITool. The scaffold CLI emits the strict defaults verbatim. |
| `auth_level` / `pipa_class` / `is_irreversible` / `dpa_reference` fields required | **Spec 024** (`specs/024-tool-security-v1`) + **Spec 025** (`specs/025-tool-security-v6`) — V1–V6 invariants enforced by Pydantic `@model_validator` on GovAPITool | Plugins inherit these fields by virtue of being GovAPITool instances. The 50-item checklist has dedicated items for each. |
| Permission Layer 1/2/3 decision tree in `docs/plugins/permission-tier.md` | **Spec 033** (`specs/033-permission-v2-spectrum/spec.md`) — PermissionMode spectrum + ConsentDecision schema | Doc page is a contributor-facing decision tree mapping adapter properties to a Layer; the runtime enforcement remains in Spec 033's pipeline. |
| `kosmos.plugin.id` OTEL span attribute | **Spec 021** (`specs/021-observability-otel-genai`) — GenAI semantic-conventions extension via `kosmos.*` prefix | New attribute under existing `kosmos.*` namespace; emission is enforced at adapter invocation time by the registry wrapper, not by individual plugins. |
| Manifest `tier: live | mock` and `mock_source_spec` requirement | Memory `feedback_mock_evidence_based` + memory `feedback_mock_vs_scenario` (byte/shape mirror only when public spec exists) | Encoded in `docs/plugins/live-vs-mock.md` and enforced by validation-workflow lint. |
| TUI commands (`/plugin init` / `/plugin install` / `/plugin list`) using Ink + React | **Spec 287** (`specs/287-tui-ink-react-bun`) — TUI stack + memory `project_tui_architecture` (`.references/claude-code-sourcemap/restored-src/` as primary migration source) | Reuses existing command dispatcher and Ink prompt patterns. |
| Consent receipt for `kosmos plugin install` action written to memdir | **Spec 035** (`specs/035-onboarding-brand-port`) consent ledger at `~/.kosmos/memdir/user/consent/` | New action type `plugin_install`; existing append-only ledger format unchanged. |
| Korean-primary documentation policy in 9 guides | Memory `feedback_output_language` + AGENTS.md "All source text in English. Korean domain data is the only exception." + existing `docs/plugins/README.md` already in Korean-primary format | Code identifiers stay English; only `description_ko` / `search_hint_ko` / `*.ko.md` carry Korean. |
| 50-item review checklist as canonical source-of-truth feeding the workflow | **Memory `feedback_no_hardcoding`** (LLM-driven, not static keyword) — applied here as: each checklist item is mechanical *but the human-readable Markdown is the source-of-truth*, the workflow derives executable checks from a manifest mapping (see § R-1). | This is the source-of-truth-once principle, identical to how Spec 026 made `prompts/manifest.yaml` the SHA-256-keyed source-of-truth feeding the runtime PromptLoader. |

---

## R-1 · 50-item review checklist derivation (Assumption A8)

Per spec Assumption A8, the 50 items are derived from the union of: AGENTS.md `docs/tool-adapters.md` PR checklist (9 items) + Constitution §I–VI obligations (~12 items mapped) + Spec 024 V1–V4 invariants (4) + Spec 025 V6 invariant (1) + Spec 022/031 `AdapterRegistration` invariants (~6) + Spec 033 permission-decision shape (~3) + Spec 021 OTEL emission (~2) + KOSMOS-specific PIPA + Korean-primary doc rules (~13). Final count: 50 (verified item-by-item below).

Each item has: `id`, Korean description, English description, Source rule, Mechanical check (lint / unit test / workflow step). The `docs/plugins/review-checklist.md` page (FR-013) is the human-readable Markdown rendering of this same data; the YAML manifest at `tests/fixtures/plugin_validation/checklist_manifest.yaml` (created during implementation) drives the workflow's executable step matrix so they cannot drift.

### Q1 — Schema integrity (10 items)

| ID | Korean | English | Source | Mechanical check |
|---|---|---|---|---|
| Q1-PYV2 | Pydantic v2 BaseModel 사용 | Pydantic v2 BaseModel | Constitution §III | Static AST check on `schema.py` |
| Q1-NOANY | `Any` 타입 금지 | No `Any` types | Constitution §III | `mypy --strict` + AST scan |
| Q1-FIELD-DESC | 모든 Field 에 description | Every Field has `description=` | Spec 019 input discipline | AST scan |
| Q1-INPUT-MODEL | input_schema 존재 + 비어 있지 않음 | input_schema present + non-empty | docs/tool-adapters.md | Pydantic introspection in unit test |
| Q1-OUTPUT-MODEL | output_schema 존재 + 비어 있지 않음 | output_schema present + non-empty | docs/tool-adapters.md | Pydantic introspection in unit test |
| Q1-MANIFEST-VALID | manifest.yaml schema 검증 통과 | manifest.yaml validates against PluginManifest | FR-019 | `manifest_schema.py` model_validate |
| Q1-FROZEN | manifest 모델 frozen=True | model_config frozen=True | Spec 027/032 pattern | Pydantic introspection |
| Q1-EXTRA-FORBID | manifest 추가 필드 금지 | model_config extra=forbid | Spec 024 V1 | Pydantic introspection |
| Q1-VERSION-SEMVER | version SemVer 형식 | version is SemVer | FR-019 | Regex |
| Q1-PLUGIN-ID-REGEX | plugin_id snake_case [a-z][a-z0-9_]* | plugin_id matches snake_case regex | Spec 022 tool_id pattern | Regex (mirrors AdapterRegistration line 91) |

### Q2 — Fail-closed defaults (6 items)

| ID | Korean | English | Source | Mechanical check |
|---|---|---|---|---|
| Q2-AUTH-DEFAULT | requires_auth 기본 True | requires_auth default True | Constitution §II | AST default-value scan |
| Q2-PII-DEFAULT | is_personal_data 기본 True | is_personal_data default True | Constitution §II | AST default-value scan |
| Q2-CONCURRENCY-DEFAULT | is_concurrency_safe 기본 False | is_concurrency_safe default False | Constitution §II | AST default-value scan |
| Q2-CACHE-DEFAULT | cache_ttl_seconds 기본 0 | cache_ttl_seconds default 0 | Constitution §II | AST default-value scan |
| Q2-RATE-LIMIT-CONSERVATIVE | rate_limit_per_minute ≤ 30 | rate_limit_per_minute ≤ 30 | docs/tool-adapters.md guidance | AST literal scan |
| Q2-AUTH-EXPLICIT | auth_level / pipa_class / is_irreversible / dpa_reference 명시 | All 4 Spec-024 fields explicitly declared | Spec 024 + docs/tool-adapters.md | Pydantic required-field check |

### Q3 — Security V1–V6 invariants (5 items)

| ID | Korean | English | Source | Mechanical check |
|---|---|---|---|---|
| Q3-V1-NO-EXTRA | V1 extra=forbid 통과 | Spec 024 V1 (extra=forbid) | Spec 024 | model_validate negative test |
| Q3-V2-DPA | V2 dpa_reference non-null when pipa_class != non_personal | Spec 024 V2 | Spec 024 | model_validate negative test |
| Q3-V3-AAL-MATCH | V3 auth_level matches TOOL_MIN_AAL row | Spec 024 V3 | Spec 024 | Lookup TOOL_MIN_AAL + assert match |
| Q3-V4-IRREVERSIBLE-AAL | V4 is_irreversible=True ⇒ auth_level ≥ AAL2 | Spec 024 V4 | Spec 024 | model_validate negative test |
| Q3-V6-AUTH-LEVEL-MAP | V6 auth_type ↔ auth_level allow-list | Spec 025 V6 | Spec 025 | Lookup `_AUTH_TYPE_LEVEL_MAPPING` + assert |

### Q4 — Discovery & docs (8 items)

| ID | Korean | English | Source | Mechanical check |
|---|---|---|---|---|
| Q4-HINT-KO | search_hint_ko 비어 있지 않음 | search_hint_ko non-empty | docs/tool-adapters.md | String length check |
| Q4-HINT-EN | search_hint_en 비어 있지 않음 | search_hint_en non-empty | docs/tool-adapters.md | String length check |
| Q4-HINT-NOUNS | search_hint_ko 한국어 명사 ≥ 3개 | search_hint_ko ≥ 3 Korean nouns | docs/tool-adapters.md guidance | Kiwipiepy tokenizer (existing Spec 022) |
| Q4-HINT-MINISTRY | search_hint includes ministry / agency | search_hint includes ministry name | docs/tool-adapters.md | Substring match against ministry list |
| Q4-NAME-KO | name_ko 비어 있지 않음 | name_ko non-empty | docs/tool-adapters.md | String length |
| Q4-CITE | guide page references at least one canonical source | Each docs/plugins/*.ko.md cites at least one ref | Constitution §I + FR-007 | Markdown link/citation regex |
| Q4-README-KO | README.ko.md 존재 (template + each example) | README.ko.md present | FR-001 / FR-010 | File-exists check |
| Q4-README-MIN-LEN | README.ko.md ≥ 500 chars | README.ko.md ≥ 500 chars | Author-effort floor | Char count |

### Q5 — Permission tier (3 items)

| ID | Korean | English | Source | Mechanical check |
|---|---|---|---|---|
| Q5-LAYER-DECLARED | permission_layer ∈ {1,2,3} 선언 | permission_layer in {1,2,3} | Spec 033 | Literal-set check |
| Q5-LAYER-MATCHES-PII | permission_layer = 3 if processes_pii=True && handles AAL3-only data | Layer ≥ 2 when processes_pii=True | Spec 033 + heuristic | Cross-field validator |
| Q5-LAYER-DOC | docs/plugins/permission-tier.md 결정 트리 따름 (rationale in README.ko.md) | Layer rationale in README.ko.md | FR-010 | Markdown section regex |

### Q6 — PIPA §26 trustee (4 items)

| ID | Korean | English | Source | Mechanical check |
|---|---|---|---|---|
| Q6-PIPA-PRESENT | pipa_trustee_acknowledgment block 존재 (processes_pii=True 일 때) | Block present when processes_pii=True | FR-014 + Constitution §V | Pydantic conditional required |
| Q6-PIPA-HASH | acknowledgment_sha256 == canonical SHA-256 | Hash matches canonical text | FR-014 | hashlib.sha256 compare |
| Q6-PIPA-ORG | trustee_org_name + trustee_contact 비어 있지 않음 | trustee_org + contact non-empty | FR-014 | String length |
| Q6-PIPA-FIELDS-LIST | pii_fields_handled 명시 (1개 이상) | pii_fields_handled non-empty list | FR-014 | List length |

### Q7 — Tier classification + mocking discipline (5 items)

| ID | Korean | English | Source | Mechanical check |
|---|---|---|---|---|
| Q7-TIER-LITERAL | tier ∈ {live, mock} | tier in {live, mock} | FR-019 | Literal-set check |
| Q7-MOCK-SOURCE | tier=mock 일 때 mock_source_spec 비어 있지 않음 | mock_source_spec non-empty when tier=mock | FR-019 + memory feedback_mock_evidence_based | Conditional Pydantic required |
| Q7-LIVE-USES-NETWORK | tier=live 어댑터 코드에 httpx/aiohttp import 존재 | Live adapters import httpx or aiohttp | Heuristic from feedback_mock_evidence_based | AST import scan |
| Q7-MOCK-NO-EGRESS | tier=mock 어댑터 테스트 중 outbound socket = 0 | Mock adapters: outbound socket count = 0 | Constitution §IV | pytest socket-block fixture (block_network) |
| Q7-LIVE-FIXTURE | tier=live 도 fixture 가짐 (CI 는 live API 호출 금지) | Live tier also ships fixture; CI replays | Constitution §IV | File-exists check + pytest live-mark gate |

### Q8 — Reserved-name & namespace (3 items)

| ID | Korean | English | Source | Mechanical check |
|---|---|---|---|---|
| Q8-NAMESPACE | tool_id 가 plugin.<plugin_id>.<verb> 형식 | tool_id matches plugin.<id>.<verb> regex | FR-022 + migration tree § L1-C C7 | Regex |
| Q8-NO-ROOT-OVERRIDE | tool_id 가 active plugin primitive (lookup/submit/verify) 와 충돌 안 함 | tool_id is not a bare active plugin primitive name | FR-022 | String set check |
| Q8-VERB-IN-PRIMITIVES | verb 부분이 active plugin primitive 중 하나 | verb subpart is one of the active plugin primitives | FR-004 + migration tree § L1-C C1 | Regex group + set check |

### Q9 — OTEL emission (2 items)

| ID | Korean | English | Source | Mechanical check |
|---|---|---|---|---|
| Q9-OTEL-ATTR | otel_attributes 에 kosmos.plugin.id 포함 | otel_attributes contains kosmos.plugin.id | FR-021 + Spec 021 | Dict-key check |
| Q9-OTEL-EMIT | invocation 시 span 에 kosmos.plugin.id 가 실제로 attach | Span actually carries kosmos.plugin.id at runtime | FR-021 | Test-time fake-OTLP collector assertion |

### Q10 — Tests & fixtures (4 items)

| ID | Korean | English | Source | Mechanical check |
|---|---|---|---|---|
| Q10-HAPPY-PATH | happy-path unit test 1개 이상 | ≥ 1 happy-path test | docs/tool-adapters.md | pytest collection count |
| Q10-ERROR-PATH | error-path unit test 1개 이상 | ≥ 1 error-path test | docs/tool-adapters.md | pytest collection count + assertion-style scan |
| Q10-FIXTURE-EXISTS | fixture 파일 존재 + JSON 로드 가능 | Fixture file exists + valid JSON | docs/tool-adapters.md | File-exists + json.loads |
| Q10-NO-LIVE-IN-CI | @pytest.mark.live 마커가 live-only 테스트에 부착 | live tests gated by @pytest.mark.live | Constitution §IV | pytest marker introspection |

### Total: 50 items mapped (10 + 6 + 5 + 8 + 3 + 4 + 5 + 3 + 2 + 4 = 50). Source-of-truth file pattern (one YAML row per item) — the workflow's matrix iterates over rows, not over hand-written `if`/`else` branches, so the count + items remain auditable from a single Markdown page (`docs/plugins/review-checklist.md`).

---

## R-2 · Example-plugin repo layout (Assumption A2)

**Decision**: Standalone repositories under the new `kosmos-plugin-store` GitHub organization. One repo per example: `kosmos-plugin-seoul-subway`, `kosmos-plugin-post-office`, `kosmos-plugin-nts-homtax` (Mock), `kosmos-plugin-nhis-check` (Mock).

**Rationale**:
1. **Authentic dogfooding** — external contributors will publish their plugins as standalone repos under `kosmos-plugin-store`. The 4 examples following the same convention is the highest-fidelity demonstration. A mono-repo of examples teaches contributors to do the wrong thing.
2. **SLSA provenance per artifact** — `slsa-github-generator` works at the *repository level* (one OIDC identity per repo, one provenance trail per release). Mono-repo would force every example to share a single provenance trail, breaking traceability.
3. **Independent versioning** — each example evolves at its own pace (e.g., the Seoul subway adapter may need to track the city's API revisions while the post-office adapter is stable).
4. **Spec 026 release-manifest precedent** — Spec 026 already established per-component release manifests (`docs/release-manifests/<sha>.yaml`). Per-repo provenance fits the same pattern.

**Alternatives considered**:
- *Sub-directories under a single `kosmos-plugin-examples` repo*: simpler initial setup, but breaks SLSA-per-artifact and creates an awkward asymmetry between examples and contributor plugins. Rejected.
- *Sub-directories under the main KOSMOS repo (`examples/plugins/`)*: keeps everything close, but would push generated example code into the main repo and conflict with the "external contribution path" the examples are demonstrating. Rejected.

**Cost of decision**: 4 new GitHub repos to create (one-time scripted via `gh repo create`), 4 separate CI configurations to maintain (mitigated by all four sharing the canonical `plugin-validation.yml` from this repo, fetched as a reusable workflow via `uses: umyunsang/KOSMOS/.github/workflows/plugin-validation.yml@<sha>`).

**Documented in**: `docs/plugins/quickstart.ko.md` step 6 ("저장소 생성") + `docs/plugins/architecture.md`.

---

## R-3 · SLSA provenance chain (Assumption A2)

**Decision**: Use `slsa-github-generator` (`slsa-framework/slsa-github-generator`, Apache-2.0) for provenance generation in each example-plugin and template-plugin release workflow. Use `slsa-verifier` (`slsa-framework/slsa-verifier`, Apache-2.0) as a **vendored binary** shelled out from the Python `installer.py` for verification at install time.

**Rationale**:
1. **Industry standard** — `slsa-github-generator` is the reference implementation cited in the SLSA v1.0 spec (`slsa.dev`). Using it gets us SLSA Build L3 (hosted, signed, non-falsifiable) on day one.
2. **No new Python deps** — verification runs as a subprocess (`slsa.py` wraps `subprocess.run([slsa_verifier_path, ...])`). Zero `pip install` impact (AGENTS.md hard rule preserved).
3. **No JS dep either** — alternatives like `npm install @slsa-framework/slsa-verifier-js` would add a new TS dep. Vendored binary keeps both stacks clean.
4. **Cross-platform** — `slsa-verifier` ships pre-built binaries for darwin/amd64, darwin/arm64, linux/amd64, linux/arm64. The `installer.py` resolves the right binary from `~/.kosmos/vendor/slsa-verifier/<platform>/slsa-verifier` (downloaded once at first install or pre-fetched at TUI bootstrap).

**Verification flow**:
```
kosmos plugin install seoul-subway
  → installer.py:
      1. Fetch catalog index from kosmos-plugin-store/index.json
      2. Resolve "seoul-subway" → bundle URL + provenance URL
      3. Download bundle (.tar.gz) + provenance (.intoto.jsonl)
      4. subprocess: slsa-verifier verify-artifact --provenance-path <prov> \
                       --source-uri github.com/kosmos-plugin-store/kosmos-plugin-seoul-subway \
                       <bundle.tar.gz>
      5. Verify exit code 0
      6. Validate manifest (manifest_schema.py)
      7. Stage to ~/.kosmos/memdir/user/plugins/seoul-subway/
      8. Append consent receipt to ~/.kosmos/memdir/user/consent/
      9. Notify backend via stdio IPC: registry.reload_plugin("seoul-subway")
     10. Backend rebuilds BM25 index entry for the new tool_id
```

**Alternatives considered**:
- *Re-implement provenance verification in Python* — would be ~300 LOC of crypto + spec-conformance tests, no security benefit, drift risk every time SLSA spec evolves. Rejected.
- *Use `cosign` instead of `slsa-verifier`* — `cosign` verifies signatures but not the full SLSA provenance graph; the spec calls for SLSA, not just signed artifacts. Rejected.
- *Skip verification and trust the registry curation alone* — violates Constitution §II (fail-closed). Rejected.

**Cost of decision**: ~10 MB binary download per platform on first install (one-time, cached). Documented in `docs/plugins/security-review.md` § "SLSA verification" + `contracts/plugin-install.cli.md`.

---

## R-4 · PIPA §26 trustee acknowledgment text canonical location + SHA-256 (FR-014)

**Decision**: The canonical trustee acknowledgment text lives in `docs/plugins/security-review.md` under a `<!-- CANONICAL-PIPA-ACK-START -->` / `<!-- CANONICAL-PIPA-ACK-END -->` HTML comment block. The text content between those markers (after stripping leading/trailing whitespace and normalizing line endings to `\n`) is hashed with SHA-256 to produce the canonical hash. The hash itself is published in two places: (a) at the top of `docs/plugins/security-review.md` for human-readable reference; (b) as a `CANONICAL_ACKNOWLEDGMENT_SHA256` constant in `src/kosmos/plugins/canonical_acknowledgment.py` (computed at module load by hashing the text extracted from the docs file, so the two cannot drift).

**Rationale**:
1. **Source-of-truth-once** — the same Spec 026 pattern that made `prompts/manifest.yaml` SHA-256-keyed. One file holds the text; the hash is derived, never typed.
2. **Auditable** — the markdown markers make the canonical span explicit so reviewers can see exactly what is part of the acknowledgment vs surrounding prose.
3. **Versioning** — when the legal team approves a new acknowledgment text, the markers move and the hash naturally changes; previously-merged plugins now report stale hashes (caught by the deferred drift-audit workflow per spec OOS table row 7).

**Acknowledgment block in plugin manifest** (Pydantic v2 nested model):
```python
class PIPATrusteeAcknowledgment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    trustee_org_name: str = Field(min_length=1, description="수탁자 조직명")
    trustee_contact: str = Field(min_length=1, description="문의처 (이메일 또는 전화)")
    pii_fields_handled: list[str] = Field(min_length=1, description="처리하는 개인정보 필드 목록")
    legal_basis: str = Field(min_length=1, description="처리 법적 근거")
    acknowledgment_sha256: str = Field(pattern=r"^[a-f0-9]{64}$", description="canonical 텍스트 SHA-256")
```

**Validation flow** (in `manifest_schema.py`):
```python
@model_validator(mode="after")
def _validate_acknowledgment_hash(self) -> "PluginManifest":
    if not self.processes_pii:
        if self.pipa_trustee_acknowledgment is not None:
            raise ValueError("pipa_trustee_acknowledgment must be None when processes_pii=False")
        return self
    if self.pipa_trustee_acknowledgment is None:
        raise ValueError("pipa_trustee_acknowledgment is required when processes_pii=True (PIPA §26)")
    expected = canonical_acknowledgment.CANONICAL_ACKNOWLEDGMENT_SHA256
    actual = self.pipa_trustee_acknowledgment.acknowledgment_sha256
    if actual != expected:
        raise ValueError(
            f"acknowledgment_sha256 mismatch: expected {expected}, got {actual}. "
            f"Re-read docs/plugins/security-review.md and update."
        )
    return self
```

**Alternatives considered**:
- *Keep canonical text in Python source* — couples legal text to code, harder for legal team to review. Rejected.
- *Store canonical hash in a YAML config* — extra indirection, drift risk between YAML and Markdown. Rejected.

**Documented in**: `contracts/pipa-acknowledgment.md` + `docs/plugins/security-review.md`.

---

## R-5 · TUI commands layer (Spec 287 Ink + Bun) integration

**Decision**: Three new commands under `tui/src/commands/`: `plugin-init.ts`, `plugin-install.ts`, `plugin-list.ts`. Registered into the existing command dispatcher (`tui/src/commands/index.ts`). UI uses `@inkjs/ui` `Select` and `TextInput` (already in P4 stack) for the init scaffold prompts. `plugin-install` shells out to the Python backend's `installer.py` via the existing stdio IPC envelope (Spec 032) — the TUI never directly writes to `~/.kosmos/memdir/user/plugins/`; that's the backend's responsibility.

**Rationale**:
1. **Spec 287 stack reuse** — Ink + Bun stack is already shipped, P4 added 9 surfaces (`PluginBrowser`, `OnboardingFlow`, `PermissionGauntlet`, etc.). Adding 3 commands is a straightforward extension.
2. **Backend ownership of state** — installation writes to memdir, rebuilds the BM25 index, and emits OTEL spans. All three are backend concerns. The TUI's job is the prompts + the IPC call + rendering progress.
3. **Existing IPC envelope** — Spec 032 defines a stdio JSONL envelope with `correlation_id` / `transaction_id`. New frame variant `plugin_install_request` / `plugin_install_progress` / `plugin_install_complete` slots into the existing 19-arm discriminated union (one new arm = `plugin_op` covering install/uninstall/list).

**Ink command shape** (`plugin-init.ts` skeleton):
```typescript
import React from 'react';
import {Box, Text} from 'ink';
import {Select, TextInput} from '@inkjs/ui';
// 1. Prompt: plugin name (TextInput, validated against ^[a-z][a-z0-9_]*$)
// 2. Prompt: tier (Select between "live" / "mock")
// 3. Prompt: permission_layer (Select between 1 / 2 / 3)
// 4. Prompt: search_hint_ko / search_hint_en (TextInput)
// 5. Prompt: processes_pii (Select yes/no)
//    if yes → spawn the PIPA acknowledgment sub-flow (R-4)
// 6. Emit files: pyproject.toml + adapter.py + schema.py + manifest.yaml + tests/test_adapter.py + README.ko.md
// 7. Print "✓ 플러그인 [name] 생성 완료. uv run pytest 실행해 보세요."
```

**`plugin-install.ts` shape**:
```typescript
// 1. Send IPC frame: {type: "plugin_op", op: "install", name: "<name>", correlation_id}
// 2. Render progress overlay (existing pattern from PluginBrowser):
//    - "📡 카탈로그 조회 중…"
//    - "🔐 SLSA 서명 검증 중…"
//    - "📦 매니페스트 검증 중…"
//    - "🔄 등록 + BM25 색인 중…"
//    - "✓ 설치 완료"
// 3. On error: render Korean error + the rejected check ID.
```

**Documented in**: `contracts/plugin-init.cli.md` + `contracts/plugin-install.cli.md`.

---

## R-6 · Pydantic v2 manifest schema ↔ Spec 022/031 self-classify metadata join (Special order #6)

**Decision**: The new `PluginManifest` (Pydantic v2 model, `src/kosmos/plugins/manifest_schema.py`) is a **superset** of the existing `AdapterRegistration` (Spec 031) — every plugin manifest contains an embedded `AdapterRegistration` instance via composition (not inheritance, to keep the existing `AdapterRegistration` clean). The plugin-specific fields (`processes_pii`, `pipa_trustee_acknowledgment`, `tier`, `mock_source_spec`, `slsa_provenance_url`, `pipa_class`, `auth_level`, `is_irreversible`, `dpa_reference`) live alongside the embedded `AdapterRegistration`.

**Why composition not inheritance**: `AdapterRegistration` has 8 required fields; subclassing would force a redundant re-declaration of every field. Composition keeps the parent untouched and makes the relationship explicit.

**Manifest shape** (high-level, full schema in `data-model.md`):
```python
class PluginManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    # --- identity (plugin-only) ---
    plugin_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=64)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")  # SemVer
    # --- the embedded AdapterRegistration ---
    adapter: AdapterRegistration  # from kosmos.tools.registry
    # --- plugin-specific tier ---
    tier: Literal["live", "mock"]
    mock_source_spec: str | None = None  # required if tier=="mock", checked by validator
    # --- plugin-specific PIPA ---
    processes_pii: bool = True  # fail-closed default per Constitution §II
    pipa_trustee_acknowledgment: PIPATrusteeAcknowledgment | None = None  # required if processes_pii=True
    # --- plugin-specific provenance ---
    slsa_provenance_url: str = Field(pattern=r"^https://github\.com/")
    # --- plugin-specific OTEL ---
    otel_attributes: dict[str, str]  # must contain "kosmos.plugin.id"
    # --- search hints (mirrors GovAPITool but redeclared because they're plugin-presentation, not adapter-internal) ---
    search_hint_ko: str = Field(min_length=1)
    search_hint_en: str = Field(min_length=1)
    # --- plugin-derived permission layer (informational; Spec 033 is enforcement) ---
    permission_layer: Literal[1, 2, 3]
```

**Join with `tools/registry.py` BM25 index**: at install time, `installer.py` constructs the `AdapterRegistration` from `manifest.adapter`, calls `ToolRegistry.register_plugin_adapter(adapter, source=manifest)`, which (a) validates against the existing Spec 022/024/025/031/033 invariant chain (free reuse — no new validators), (b) inserts the tool into the in-memory registry, (c) calls `BM25Index.add_or_update(adapter.tool_id, search_hint_ko + " " + search_hint_en)`, (d) emits the install OTEL span with `kosmos.plugin.id=<plugin_id>`. The backend exports a single new function `register_plugin_adapter()` — everything else is reuse.

**Alternatives considered**:
- *Inheritance* — `class PluginManifest(AdapterRegistration)`: rejected because it would require either re-declaring required fields (no schema benefit) or making `AdapterRegistration` fields default-able (breaks Spec 031 contract).
- *Side-by-side without composition* — keep `PluginManifest` and `AdapterRegistration` fully separate, with a `to_adapter_registration()` mapping function: rejected because the mapping function becomes a drift surface.

**Documented in**: `data-model.md` + `contracts/manifest.schema.json`.

---

## R-VALIDATION · Deferred items validation (Constitution §VI gate)

Per Constitution §VI, every "Scope Boundaries & Deferred Items" entry must have a tracking issue OR be marked `NEEDS TRACKING` for `/speckit-taskstoissues` to resolve. Verified `2026-04-25`.

### Existing tracking issues (verified OPEN via GraphQL Sub-Issues API v2)

| Issue | Title | State | Coverage |
|---|---|---|---|
| #1820 | [Deferred] Plugin marketplace store UI itself (the a-keybinding destination) | OPEN | Citizen-facing in-TUI marketplace browser (post-P5) |
| #1812 | [Deferred] docs/api and docs/plugins reference docs | OPEN | Phase P6 documentation site (post-P5) |

Both verified via `gh api graphql -f query='{repository{issue(number:N){state}}}'` during the spec phase.

### NEEDS TRACKING entries (resolved by `/speckit-taskstoissues` later)

| Item | Phase target |
|---|---|
| Paid plugin model (revenue share, pricing, payment integration) | Post-portfolio commercialization Epic |
| Plugin-to-plugin dependency graph (one plugin requires another) | Post-P5 if real-world need materializes |
| Hot-reload dynamic loading of edited plugin source without restart | Post-P5 if developer tooling demand materializes |
| Migration of 4 example plugins from sub-directories to standalone repos | OBVIATED by R-2 (we ship standalone from day 1; this row can be removed in spec edit) |
| Acceptance-text drift audit workflow re-checking installed plugins | Post-P5 first acknowledgment-text update |

**Action**: After `/speckit-tasks` completes, update spec.md to remove the now-obviated row (R-2 decided standalone repos from day 1, so the migration item is moot). Tracked as a follow-up edit; not a blocker for `/speckit-tasks`.

### Pattern scan for unregistered deferral phrases

Scanned spec.md for `separate epic`, `future epic`, `Phase [2+]`, `v2`, `deferred to`, `later release`, `out of scope for v1`. All matches:
- "별개 후속 Epic" — appears in spec § "Out of Scope (Permanent)" preamble + 4 Deferred-table rows; all rows are registered in the table. PASS.
- "Phase P6" — appears in 1 Deferred-table row → #1812 (registered). PASS.
- "post-P5" / "post-portfolio" — appear in Deferred-table rows; all registered. PASS.
- "v2" — does not appear anywhere in spec.md. PASS.
- "later release" — does not appear. PASS.

**Verdict**: §VI gate PASS. No unregistered deferrals. `/speckit-taskstoissues` will materialize 5 new placeholder issues for the NEEDS TRACKING entries (potentially 4 after the R-2 obviation cleanup edit).

---

## Summary

All NEEDS CLARIFICATION resolved (none in spec). All 6 special orders decided. 50-item checklist derived from authoritative KOSMOS sources with full traceability. Constitution §VI deferred-items gate PASS. Phase 0 complete — proceed to Phase 1 (data-model.md, contracts/, quickstart.md).
