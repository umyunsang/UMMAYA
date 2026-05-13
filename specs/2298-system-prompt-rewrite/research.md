# Phase 0 — Research

**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

This Epic introduces no new technology and no new dependency. The research scope is therefore (a) **reference mapping** for each design decision, (b) **schema-gap analysis** validating that prompt-only teaching is sufficient, (c) **AAL tier table** sourcing each family's canonical tier from the agency's published policy, and (d) **deferred-item validation** per Constitution § VI.

---

## R-1 Reference Mapping (Constitution § I — Reference-Driven Development)

Per Constitution § I, every design decision MUST trace to a concrete reference. The 6 decisions of this Epic and their references:

| Decision | Reference | Source verbatim |
|---|---|---|
| **D-1** Replace line-14 lock string with 5-tool catalog | `docs/requirements/ummaya-migration-tree.md § L1-C C4` | "system prompt에 primitive 서명만 + BM25 동적 제시" |
| **D-2** Preserve XML scaffolding `<role>` / `<core_rules>` / `<tool_usage>` / `<output_style>` | `specs/2152-system-prompt-redesign/spec.md` | XML-tag scaffolding source-of-truth (4-tag structure ratified 2026-04-26) |
| **D-3** Teach citizen verify→lookup→submit chain pattern with worked example | `specs/1979-plugin-dx-tui-integration/delegation-flow-design.md § 12.4` | "FINAL canonical AX-infrastructure caller" diagram (3rd correction final 2026-04-29) |
| **D-4** Teach scope grammar `<verb>:<adapter_family>.<action>` + comma-joined multi-scope | `specs/2296-ax-mock-adapters/contracts/delegation-token-envelope.md § 3` | Scope grammar canonical (Epic ε ships single-scope-per-call; comma-joined regex is forward-compatible) |
| **D-5** Recompute `prompts/manifest.yaml` SHA-256 entry; rely on Spec 026 boot fail-closed | `specs/026-cicd-prompt-registry/spec.md` | PromptLoader fail-closed boot invariant (any prompt edit forces manifest hash recompute, otherwise SystemExit(78)) |
| **D-6** Trigger shadow-eval workflow for fixture-only twin-run validation | `.github/workflows/shadow-eval.yml` | Fires on `prompts/**` PRs; emits `deployment.environment=main\|shadow` attribute pair |

**Claude Code restored-src consultation**: Not applicable. The rewrite is content-only on a UMMAYA-specific prompt; no equivalent construct exists in CC's developer-domain prompt. The CC reconstructed reference for prompt-cache + system-prompt assembly was already mined exhaustively for Spec 2152; Epic η extends Spec 2152 without creating new architecture.

**Escalation log** (per Constitution § I — "document the escalation in research.md"): None. All references are UMMAYA-internal specs.

---

## R-2 Reused-Not-Built Audit (Constitution § VI implicit)

Every component this Epic relies on already ships in `main`:

| Component | Status | Source |
|---|---|---|
| `PromptLoader` (manifest validation, fail-closed boot) | EXISTING | `src/ummaya/context/prompt_loader.py` (Spec 026) |
| `prompts/manifest.yaml` schema (3-entry list) | EXISTING | `prompts/manifest.yaml` (Spec 026) |
| Shadow-eval twin-run workflow | EXISTING | `.github/workflows/shadow-eval.yml` (Spec 026) |
| `ummaya.prompt.hash` OTEL attribute | EXISTING | `src/ummaya/observability/tracing.py` (Spec 026 + Spec 021) |
| 10 active verify mock adapters | EXISTING | `src/ummaya/tools/mock/verify_*.py` + `verify_module_*.py` (Spec 031 + Spec 2296) |
| 11-arm `AuthContext` discriminated union | EXISTING | `src/ummaya/primitives/verify.py:351-365` (Spec 031 + Spec 2296) |
| `verify(family_hint: str, ...)` dispatcher (plain `str` accepts unknown families) | EXISTING | `src/ummaya/primitives/verify.py:420-440` |
| `mock_lookup_module_hometax_simplified` + `mock_submit_module_hometax_taxreturn` | EXISTING | `src/ummaya/tools/mock/lookup_module_hometax_simplified.py` + `src/ummaya/tools/mock/submit_module_hometax_taxreturn.py` (Spec 2296) |
| Consent ledger 3-line append protocol per chain | EXISTING | `tests/integration/test_e2e_citizen_taxreturn_chain.py` (Spec 2296) |
| `<citizen_request>` injection-guard sentence | EXISTING | `prompts/system_v1.md:10` (Spec 2152) |
| vhs `Screenshot` directive support | EXISTING | vhs ≥ 0.11 (AGENTS.md § Layer 4) |

**Verdict**: Zero new infrastructure. The Epic is a content rewrite + 5 fixtures + 2 smoke scripts.

---

## R-3 Schema Gap Analysis — Why Prompt-Only Is Sufficient

**Finding (discovered Phase 0)**: `src/ummaya/primitives/verify.py:35-42` defines `FamilyHint` Literal with **6 values** — missing the 5 Epic ε families:

```python
FamilyHint = Literal[
    "gongdong_injeungseo",
    "geumyung_injeungseo",
    "ganpyeon_injeung",
    "digital_onepass",         # ← still present despite mock deletion
    "mobile_id",
    "mydata",
    # MISSING: simple_auth_module, modid, kec, geumyung_module, any_id_sso
]
```

**Question**: Will the LLM emitting `verify(family_hint="modid")` (the canonical US1 chain) actually work, or will Pydantic validation reject the call?

**Analysis** — three call-path candidates:

1. **`VerifyInput` model** (line 45–51): declares `family_hint: FamilyHint`. **Used by**: only the 6 OLD verify mocks (`verify_ganpyeon_injeung.py`, `verify_mobile_id.py`, `verify_gongdong_injeungseo.py`, `verify_geumyung_injeungseo.py`, `verify_mydata.py` — 5 of them; the 6th was `verify_digital_onepass.py` which was deleted) — they declare `input_model_ref="ummaya.primitives.check:VerifyInput"`. The 5 NEW `verify_module_*.py` mocks (Epic ε) explicitly do NOT declare `VerifyInput` as their input model — verified by `grep -nE "input_model_ref.*VerifyInput" src/ummaya/tools/mock/verify_module_*.py` returning 0 matches.
2. **`verify()` dispatcher** (line 420–440): takes `family_hint: str` (plain str, NOT Literal). Returns `AuthContext | VerifyMismatchError` from the full 11-arm union. **Used by**: every test in `test_verify_module_dispatch.py` and the citizen chain integration test.
3. **`VerifyOutput` model** (line 385–399): `result` field is a 6-arm Annotated union (5 OLD families + `VerifyMismatchError`). **Used by**: search returns no production callers — only `output_model_ref` declarations in the 5 OLD mocks. The 5 NEW Epic ε mocks do NOT use `VerifyOutput` either.

**Verdict**: The LLM's tool_call lands in path (2), which validates `family_hint` only against the dispatcher's `_VERIFY_ADAPTERS` registry — not against the `FamilyHint` Literal. Since all 10 active mocks register themselves into `_VERIFY_ADAPTERS` at import time (verified: `src/ummaya/tools/mock/verify_module_modid.py:163` `register_verify_adapter("modid", invoke)`), the dispatcher will correctly route `family_hint="modid"` and friends.

**Therefore**: prompt-only teaching is sufficient for the infinite-spinner fix. The schema gap is a hardening concern, not a functional blocker.

**Deferred to Epic ζ #2297** (per spec.md § Deferred Items table): expand `FamilyHint` Literal from 6 → 11 values; expand `VerifyOutput.result` discriminated union from 7 → 12 arms (11 contexts + `VerifyMismatchError`); align spec-driven tests for path (1) and (3) usage.

---

## R-4 AAL Tier Reference Table

Per FR-003, the rewritten prompt MUST hint each family's canonical AAL tier. UMMAYA does not invent these — the table cites the agency's published policy via `published_tier` enum values that already live in `src/ummaya/tools/registry.py:68-93` (the `PublishedTier` Literal of 18 entries — extended in Epic ε from 13).

| Family | LLM emits `family_hint` = | Canonical `published_tier` (registry) | NIST AAL hint | Real-domain reference |
|---|---|---|---|---|
| 공동인증서 (KOSCOM Joint Certificate) | `gongdong_injeungseo` | `gongdong_injeungseo_personal_aal3` (default) / `_corporate_aal3` / `_bank_only_aal2` | AAL3 / AAL3 / AAL2 | KOSCOM 공동인증서 (since 2020 NPKI rebrand) |
| 금융인증서 (KFTC Financial Certificate) | `geumyung_injeungseo` | `geumyung_injeungseo_personal_aal2` / `_business_aal3` | AAL2 / AAL3 | 금융결제원 (KFTC) cluster |
| 간편인증 (Simple-auth — Kakao/Naver/Toss/PASS/Bank/Samsung/Payco) | `ganpyeon_injeung` | `ganpyeon_injeung_<provider>_aal2` (× 7 providers) | AAL2 | 행안부 간편인증 정책 |
| 모바일 신분증 | `mobile_id` | `mobile_id_mdl_aal2` (모바일 운전면허) / `mobile_id_resident_aal2` (모바일 주민등록증) | AAL2 | 행안부 모바일 신분증 |
| 마이데이터 | `mydata` | `mydata_individual_aal2` | AAL2 | KFTC MyData v240930 (mTLS + OAuth 2.0) |
| 간편인증 모듈 (AX-channel) | `simple_auth_module` | `simple_auth_module_aal2` | AAL2 | Japan マイナポータル API analog |
| 모바일ID 모듈 (AX-channel) | `modid` | `modid_aal3` | AAL3 | EU EUDI Wallet analog |
| KEC 공동인증서 모듈 (AX-channel) | `kec` | `kec_aal3` | AAL3 | Singapore APEX analog |
| 금융인증서 모듈 (AX-channel) | `geumyung_module` | `geumyung_module_aal3` | AAL3 | Singapore Myinfo analog |
| Any-ID SSO | `any_id_sso` | `any_id_sso_aal2` | AAL2 | UK GOV.UK One Login analog |

**LLM default policy** (per FR-003): "lowest tier that satisfies the citizen's stated purpose". The rewritten prompt MUST state this default explicitly so the LLM does not pick AAL3 for a benign welfare lookup.

`digital_onepass` is intentionally absent (mock deleted per Spec 031 FR-004 — service termination 2025-12-30). The `DigitalOnepassContext` class still exists in `verify.py` for forward-compat but the rewritten prompt MUST NOT list it as a callable family.

---

## R-5 Worked-Example Chain Selection

The rewritten prompt MUST contain ONE worked chain example (per FR-004). Three candidates considered:

| Candidate | Pro | Con | Decision |
|---|---|---|---|
| **A. `verify(modid) → lookup(hometax_simplified) → submit(hometax_taxreturn)`** (US1 canonical) | Already covered by `test_e2e_citizen_taxreturn_chain.py` happy-path; receipt id format is the SC-001 test target; demonstrates 2-scope `scope_list` (`["find:hometax.simplified", "send:hometax.tax-return"]`). | Tax filing is a high-stakes example — risk of citizen confusion. | **CHOSEN** — the SC-001/SC-002 tests assert this exact chain; teaching a different chain would break smoke. |
| B. `verify(simple_auth_module) → submit(gov24_minwon)` (single-step) | Lower stakes; AAL2 default | Doesn't demonstrate lookup→submit ordering; doesn't exercise `delegation_context` carry-forward through 2 calls. | Rejected — under-teaches. |
| C. `verify(any_id_sso) → … → (no submit)` | Demonstrates SSO-only exception (FR-008) | No submit call to demonstrate full chain. | Rejected — demonstrates the negation case but not the positive pattern. |

**Selected**: Candidate A. The system prompt will explicitly walk through:

```text
시민: "내 종합소득세 신고해줘"
   ↓
LLM step 1: verify(family_hint="modid",
                   session_context={
                     "scope_list": ["find:hometax.simplified",
                                    "send:hometax.tax-return"],
                     "purpose_ko": "종합소득세 신고",
                     "purpose_en": "Comprehensive income tax filing"})
   → DelegationContext returned
LLM step 2: lookup(mode="fetch",
                   tool_id="mock_lookup_module_hometax_simplified",
                   params={"delegation_context": <ctx>})
   → 시민의 hometax 사전 신고 자료 returned
LLM step 3: submit(tool_id="mock_submit_module_hometax_taxreturn",
                   delegation_context=<ctx>,
                   params={...})
   → 접수번호 hometax-YYYY-MM-DD-RX-XXXXX returned
LLM step 4: 시민에게 한국어로 응답 (접수번호 인용 필수)
```

The `any_id_sso` exception (FR-008) is taught as a side-note in `<core_rules>` rather than as a competing chain example. This keeps the worked example crisp.

---

## R-6 Deferred Item Validation (Constitution § VI gate)

Per `/speckit-plan` Outline step 2 ("Validate Deferred Items"), every item in spec.md § "Deferred to Future Work" was checked:

| Item | Tracking | Status |
|---|---|---|
| `FamilyHint` Literal expansion + `VerifyOutput.result` union expansion | Epic ζ #2297 (existing OPEN issue) | OK — issue exists per gh issue verification (open status as of 2026-04-30 per next-session-prompt-v9-handoff.md line 4). To be resolved by `/speckit-taskstoissues` adding to ζ scope. |
| Multi-scope token comma-joining beyond US1 2-scope example | NEEDS TRACKING | OK — placeholder marker valid per spec template; resolved by `/speckit-taskstoissues`. |
| OTEL `ummaya.prompt.shadow_eval.version` attribute extension | NEEDS TRACKING | OK — placeholder valid. |
| Prompt versioning bump (`version: 1` → `version: 2`) | NEEDS TRACKING | OK — placeholder valid. |
| `digital_onepass` mock re-add if FR-004 reverses | NEEDS TRACKING | OK — placeholder valid. |
| Layer 5 tape with subscribe primitive | NEEDS TRACKING | OK — placeholder valid. |

**Spec body scan for unregistered deferral patterns** (`grep -i -E "(separate epic|future epic|phase [2-9]|v2|deferred to|later release|out of scope for v1)" specs/2298-system-prompt-rewrite/spec.md`): all matches occur inside the Deferred Items table itself — no orphan deferrals. Constitution § VI gate **PASS**.

---

## R-7 Constraint Validation

| Constraint | Verification approach | Pre-flight result |
|---|---|---|
| Prompt size budget ≤ 8 KB | `wc -c prompts/system_v1.md` after rewrite | Current 28-line file is 1.7 KB; expansion budget +50 lines / +4 KB → ~5.7 KB target. Within 8 KB ceiling. |
| Manifest hash recompute path is deterministic | `shasum -a 256 prompts/system_v1.md` matches `prompts/manifest.yaml` `entries[2].sha256` | Verified pre-Epic — current SHA `753ce06...` matches. Recompute path identical. |
| Zero new dependencies | `git diff main..HEAD -- pyproject.toml tui/package.json` produces no `+` lines | Will be verified in Phase 6 (PR finalization). |
| XML well-formedness preserved | `python -c "from xml.etree import ElementTree as ET; ET.fromstring('<root>' + open('prompts/system_v1.md').read() + '</root>')"` exits 0 | Current pre-rewrite file passes; rewrite must keep passing. |
| TUI no-change | `git diff main..HEAD -- tui/src/` produces 0 lines | Will be verified in Phase 6. |
| Spec 026 boot guard active | `uv run python -c "from pathlib import Path; from ummaya.context.prompt_loader import PromptLoader; PromptLoader(manifest_path=Path('prompts/manifest.yaml'))"` exits 0 | Will be verified in Phase 5 (smoke). |

---

## Phase 0 verdict

All NEEDS CLARIFICATION resolved (none surfaced). All 6 deferred items either tracked or marked NEEDS TRACKING for `/speckit-taskstoissues`. All 6 constitution principles PASS. All 7 constraints have verification paths. Ready to advance to Phase 1.
