# UMMAYA Domain Harness Architecture — Research-Driven Redesign

**Status**: Research deliverable (informs follow-up epic)
**Date**: 2026-04-29
**Trigger**: User direction — UMMAYA does NOT invent domain permission policy; UMMAYA is a *harness* that calls real Korean public-service domains (정부24, 홈택스, 의약품안전나라, KOROAD, KMA, HIRA, NMC, NFA119, MOHW, MFDS, 마이데이터 등). Student team has no live API credentials, so mocks mirror the real shape and the harness flow runs end-to-end identically.
**Research basis**: `feedback_harness_not_reimplementation`, `feedback_mock_evidence_based`, `feedback_mock_vs_scenario`, `feedback_ummaya_scope_cc_plus_two_swaps`. Domain-specific authoritative sources cited inline.

---

## 0. Thesis (one paragraph)

UMMAYA is **not a domain implementer**. It is a Claude Code-style harness with two swaps from CC-original: (a) the LLM is K-EXAONE on FriendliAI, (b) the main-tool surface is the citizen-centric 5-primitive set (`lookup` / `submit` / `verify` / `subscribe` + `resolve_location`). Every tool the LLM calls represents a **real Korean public-service domain endpoint** that the agency itself operates and governs. UMMAYA' job is to (1) discover the right adapter, (2) honor whatever permission gate the agency itself publishes, (3) call the live endpoint when credentials are present, and (4) fall back to a shape-compatible mock when credentials are absent — *without altering the harness flow that the LLM and citizen observe*. UMMAYA never invents a permission classification; the adapter declares the real-domain policy and the harness routes accordingly.

---

## 1. Domain inventory (reality grade)

Authoritative public sources for each domain. Full citations in the research deliverable; see "Sources" appendix.

### 1.1 Live API — byte-mirrorable (data.go.kr REST)

These domains publish JSON/XML schemas, accept a `serviceKey` query param, and return deterministic envelopes. Mocks can byte-mirror the response.

| Domain | Endpoint family | Quota (dev) | UMMAYA adapter status |
|---|---|---|---|
| **KOROAD 도로교통공단** | `B552061/frequentzoneLg` 사고다발지역 | 10,000/day | **Live** — `koroad_accident_search`, `koroad_accident_hazard_search` |
| **KMA 기상청** | `1360000/VilageFcstInfoService_2.0` 단기·초단기·중기·특보·사전영향 | 10,000/day | **Live × 6** |
| **HIRA 건강보험심사평가원** | `B551182` 병원정보서비스 | 10,000/day | **Live** — `hira_hospital_search` (`ykiho` is encrypted/opaque) |
| **NMC 국립중앙의료원 (E-GEN)** | `15000563` 응급의료기관 정보 | 1,000,000/day | **Live** — `nmc_emergency_search` (freshness SLO via Spec 023) |
| **NFA119 소방청** | `15099423` 구급정보 (집계 통계 only) | 10,000/day | **Live** — `nfa_emergency_info_service` |
| **MOHW/SSIS 보건복지부** | `15083323` 복지서비스 카탈로그 | 10,000/day | **Live** — `mohw_welfare_eligibility_search` (catalog only) |
| **MFDS 의약품안전나라 NEDrug** | `15057639` 낱알식별 외 (data.mfds.go.kr 별도) | 10,000/day | **No adapter yet** — candidate for future Live tool |

### 1.2 Live API — read-only / asymmetric

Read endpoints public; write/submit endpoints closed.

| Domain | Read (public) | Write/submit (closed) |
|---|---|---|
| **CBS 재난문자방송** | `15091495` 재난문자 history (subscribe) | LTE Cell Broadcast — only MOIS/지자체/KMA can send |
| **NFA119 119 dispatch** | aggregate stats only | live dispatch is voice/SMS only, no API |
| **정부24 (Government24)** | `15113968` 공공서비스 카탈로그 (lookup) | 민원 발급/신청 — citizen web flow only, no API |

### 1.3 OPAQUE — scenario-only (no byte-mirror possible)

These domains expose no public spec for the operation in question, or the operation requires possession of a private credential that is unobservable from outside. **Per `feedback_mock_vs_scenario`**: these never become Live adapters; mock-shape is permitted only when public reference (SDK guide, spec PDF) describes the API surface.

| Domain | OPAQUE operation | Public surface (mockable) | Why OPAQUE |
|---|---|---|---|
| **NTS 홈택스** | 신고/납부 (filing) | None | NO official Open API for filing exists. Every market provider is cert-delegated scraping (PIPA §26 + 전자서명법 risk). |
| **정부24 민원 제출** | 등본/초본/가족관계 발급, 민원 신청 | catalog 15113968 (read) | 본인인증 + 행정망 연계, payload 비공개 |
| **모바일 신분증** | VC/VP 발급, 제시 | dev.mobileid.go.kr API surface (post-NDA) | DID exchange + TEE/SE binding, KOMSCO-controlled |
| **공동인증서 / KEC 서명** | per-tx signing | KISA HTML5 PKI guideline, cert-chain validation | Local key + per-tx PIN, signing flow gated |
| **금융인증서 (yessign)** | 전자서명 | KFTC openapi.kftc.or.kr surface (post-application) | 1:1 비공개 procurement, cloud cert ops gated |
| **마이데이터 (금융위)** | live 표준 API 호출 | developers.mydatakorea.org spec, 표준동의서 UX | 신용정보업 허가 + 기능적합성 심사 + mTLS — UMMAYA student tier cannot legally call live |
| **디지털원패스 SSO** | (retired 2025-12-30) | — | **Dead infrastructure**. Successor: 정부 통합인증 (Any-ID). |

---

## 2. Mock fidelity grading (5-point scale per `feedback_mock_evidence_based`)

Grade each adapter on byte/shape mirror feasibility:

- **5 — Byte-mirror**: response schema fully published, adapter can return fixture bytes that pass real-API parser
- **4 — Shape-mirror**: API surface published, but field-level fixtures cannot be authoritatively constructed without a sample; safe for happy-path test
- **3 — Spec-mirror**: protocol described in public spec PDF, but no live observation; mock honors envelope shape only
- **2 — Scenario-only**: only narrative documentation exists; mock is illustrative, not parsable
- **1 — Forbidden**: spec is non-public or operation is regulated; never mock

| Adapter `tool_id` | Domain | Grade | Justification |
|---|---|---|---|
| `koroad_accident_search` | KOROAD | **5** | Schema in 활용가이드.docx + real responses observable with dev key |
| `koroad_accident_hazard_search` | KOROAD | **5** | 〃 |
| `kma_*` (×6) | KMA | **5** | 단기예보 활용가이드 fully published; XML+JSON schema |
| `hira_hospital_search` | HIRA | **5** *with caveat* | All fields byte-mirrorable; `ykiho` must remain opaque (1:1 encrypted, no decode published) |
| `nmc_emergency_search` | NMC E-GEN | **5** | Real-time field set fully documented |
| `nfa_emergency_info_service` | NFA119 | **5** for stats; **1** for live dispatch | Aggregate stats schema public; 119 dispatch has no external ingress |
| `mohw_welfare_eligibility_search` | MOHW catalog | **5** for catalog; **2** for eligibility-check | Catalog dataset public; live eligibility 본인인증-gated |
| `mock_verify_digital_onepass` | 디지털원패스 | **0 — DEAD** | Service retired 2025-12-30. Replace with Any-ID stub when ADR opens. |
| `mock_verify_mobile_id` | KOMSCO 모바일ID | **3** | API surface at dev.mobileid.go.kr published; live VC/VP flow gated |
| `mock_verify_gongdong_injeungseo` | KISA KEC | **3** | KISA HTML5 PKI guideline public; signing payload OPAQUE |
| `mock_verify_geumyung_injeungseo` | 금결원 yessign | **3** | yessign API guide public; signing OPAQUE |
| `mock_verify_ganpyeon_injeung` | 간편인증 (NTS oacx) | **3** | Surface described in NTS 매뉴얼; impl gated |
| `mock_verify_mydata` | 마이데이터 | **4** | 표준 API 기본규격 + 표준동의서 fully public; live access requires license |
| `mock_traffic_fine_pay_v1` | 도로교통공단 (납부) | **3** | Submit semantics inferred from public 위반차량조회 surface |
| `mock_welfare_application_submit_v1` | 정부24/복지로 submit | **2** | OPAQUE submit surface; scenario-only |
| `mock_cbs_disaster_v1` | CBS read | **5** | 15091495 schema fully public |
| `mock_rss_public_notices_v1` | 일반 RSS | **5** | RSS 2.0 standard |
| `mock_rest_pull_tick_v1` | 일반 REST polling | **5** | Generic |

**Recommendation**: All grade-3+ mocks stay; grade-2 mocks (welfare submit, traffic fine pay) move to `docs/scenarios/` per `feedback_mock_vs_scenario`; grade-0 (디지털원패스) deleted with successor stubbed.

---

## 3. Harness architecture (CC-pattern + 2 swaps)

### 3.1 Flow (citizen request → response)

```
Citizen prompt
  │
  ▼
LLM (K-EXAONE on FriendliAI)
  │  EXAONE native function calling
  │  ↓ emits tool_call(tool_id="kma_short_term_forecast", params={...})
  ▼
ToolRegistry (BM25 + dense retrieval)
  │  ↓ resolves tool_id → adapter module
  ▼
Adapter metadata read
  │  ↓ adapter declares: { domain, real_auth_type, real_classification, mode }
  │     domain         = "KMA"
  │     real_auth_type = "data_go_kr_rest_key"
  │     real_classification = "공공데이터 일반공개"
  │     mode           = "live" | "mock"
  ▼
Permission gate (CC PermissionRequest pipeline)
  │  ↓ asks the adapter: "what does THE AGENCY require?"
  │     For data.go.kr public datasets: dev key only → no citizen prompt
  │     For mydata: 표준동의서 UI from agency's published flow
  │     For OPAQUE submits: scenario-only (LLM informs citizen, does not execute)
  ▼
Adapter.execute()
  │  IF mode=live AND credential present → real HTTPS call
  │  IF mode=live AND credential absent  → adapter raises "missing-credential"
  │                                         which renders the same shape as a
  │                                         mock fixture (graceful degrade)
  │  IF mode=mock                         → fixture replay
  ▼
Response envelope (PrimitiveOutput, identical shape regardless of mode)
  │
  ▼
LLM continuation
  │  ↓ summarizes for citizen in Korean
  ▼
Citizen sees response
```

### 3.2 Adapter declares real-domain policy (not UMMAYA-invented)

Replace the previous `permission_tier=1/2/3` + `pipa_class=일반/민감/...` invented schema with a **descriptive metadata block** that quotes the agency's own policy:

```python
class AdapterRealDomainPolicy(BaseModel):
    domain_owner: str                     # e.g. "KMA 기상청"
    domain_role: Literal["agency_self", "data_go_kr_proxy", "third_party"]
    real_auth: AuthMechanism              # see below
    real_classification: str              # citation from agency, e.g.
                                          # "공공데이터포털 전체개방 (15084084)"
    real_classification_url: HttpUrl      # citation URL
    citizen_facing_gate: CitizenGate      # see below
    rate_limit_per_tool_per_day: int      # not per-key — per tool_id (finding #9)
    last_verified: datetime               # research date

class AuthMechanism(BaseModel):
    kind: Literal[
        "none",                     # dev key embedded server-side
        "data_go_kr_rest_key",      # KOROAD, KMA, HIRA, NMC, NFA, MOHW, CBS, MFDS
        "agency_dev_key",           # data.mfds.go.kr separate key
        "oauth2_federated",         # 정부 통합인증 (Any-ID; 디지털원패스 후속)
        "kftc_signed_request",      # 금융인증서 yessign API
        "mtls_mydata",              # 마이데이터 표준
        "did_vc_vp",                # 모바일 신분증 KOMSCO
    ]
    citation_url: HttpUrl

class CitizenGate(BaseModel):
    kind: Literal[
        "none_developer_only",      # data.go.kr public datasets
        "mobile_self_auth",         # 휴대폰 본인인증
        "ipin_or_pass",             # 아이핀 / PASS
        "kec_certificate",          # 공동인증서
        "geumyung_certificate",     # 금융인증서
        "any_id_sso",               # 정부 통합인증 (전 디지털원패스)
        "mobile_id_did",            # 모바일 신분증 (DID/VC/VP)
        "mydata_consent",           # 마이데이터 표준동의서
        "scenario_only",            # OPAQUE — LLM informs citizen; no exec
    ]
    citation_url: HttpUrl
    description_ko: str              # citizen-facing description from agency docs
```

### 3.3 Permission gauntlet binds to CC `<PermissionRequest>` (no UMMAYA invention)

The harness uses CC's canonical `<PermissionRequest>` pipeline (already byte-identical with CC restored-src per Spec 1979 Class A audit). When an adapter is about to execute, the harness asks:

```
adapter.real_domain_policy.citizen_facing_gate.kind
  └→ render appropriate CC permission UI
     - none_developer_only → no UI, auto-allow (e.g. KMA weather lookup)
     - mobile_self_auth    → CC FallbackPermissionRequest with description_ko
     - mydata_consent      → CC PermissionPrompt + 표준동의서 receipt UI
     - scenario_only       → LLM tells citizen "이 작업은 정부24/홈택스 웹에서 직접 진행해주세요"
                             and does NOT call adapter.execute()
```

Note: The previous UMMAYA-invented `Layer 1 green / 2 orange / 3 red` colour scheme can stay as a **visual hint** in the gauntlet UI, but it derives from `citizen_facing_gate.kind` (a small lookup table), not from a separate "permission_tier" field. The gauntlet's *trust boundary* is the citation URL — everything in the receipt traces back to the agency's own published policy.

### 3.4 Live-vs-mock mode switch

```python
@dataclass(frozen=True)
class AdapterMode:
    """Per-adapter runtime mode resolved at boot from env vars."""
    requested: Literal["live", "mock", "auto"]   # UMMAYA_<TOOL>_MODE
    actual: Literal["live", "mock"]              # what we will use this session

def resolve_mode(adapter, env) -> AdapterMode:
    requested = env.get(f"UMMAYA_{adapter.tool_id.upper()}_MODE", "auto")
    if requested == "live":
        if not has_credential(adapter, env):
            raise RuntimeError(f"{adapter.tool_id} requires credential; set "
                               f"{adapter.credential_env_var}")
        return AdapterMode("live", "live")
    if requested == "mock":
        return AdapterMode("mock", "mock")
    # auto: prefer live if credential is present, else mock
    if has_credential(adapter, env):
        return AdapterMode("auto", "live")
    return AdapterMode("auto", "mock")
```

**Critical invariant**: response envelope shape is **identical** in `live` and `mock` modes. The LLM, citizen, and downstream tools cannot distinguish them by structure (only by metadata field `_mode: "mock"` for transparency).

### 3.5 Per-tool rate-limit bucket (research finding #9)

`data.go.kr` quotas are **per-API**, not per-key. UMMAYA rate limiting must index on `tool_id`:

```python
class ToolRateLimiter:
    """Per-tool-id rolling-window limiter; mirrors data.go.kr per-API quotas."""

    def __init__(self, defaults: dict[str, int]):
        # defaults[tool_id] = quota_per_day
        # KOROAD/KMA/HIRA/NFA/MOHW/CBS = 10000
        # NMC E-GEN = 1000000
        ...

    async def acquire(self, tool_id: str) -> None: ...
```

This is a new contract; current `LLMClient` semaphore (Spec 019) is global.

---

## 4. Mock pipeline architecture

### 4.1 Mock-grade-5 adapters (byte-mirror)

Implementation: fixture file checked into repo, JSON Schema validation against the real spec, deterministic hash:

```
src/ummaya/tools/mock/<domain>/<tool>/
  ├── adapter.py                # implements 5-primitive interface
  ├── fixtures/
  │   ├── happy_path.json       # byte-identical to real API response
  │   ├── empty_result.json
  │   ├── error_no_data.json
  │   └── README.md             # cites real spec URL + last_verified date
  └── schema.json               # JSON Schema Draft 2020-12, mirrors real spec
```

CI validates: fixture × schema × every adapter call returns byte-identical bytes after `json.dumps(sort_keys=True)`.

### 4.2 Mock-grade-3-4 adapters (shape-mirror)

API surface published but no live observation. Fixture follows the documented shape but values are illustrative:

```
src/ummaya/tools/mock/<domain>/<tool>/
  ├── adapter.py
  ├── fixtures/<scenario>.json  # shape-conforming, values illustrative
  ├── shape_contract.md         # cites public spec PDF/page sections
  └── schema.json               # what we believe the shape is (delta to real)
```

The adapter docstring **must** carry: "This adapter is shape-mirror only; live values are not authoritatively known. Citizen output should be marked as illustrative."

### 4.3 OPAQUE (grade 1-2) — scenario-only

These do **not** become adapters. They live in `docs/scenarios/<domain>.md` as narrative-only documentation:

```markdown
# Scenario: 홈택스 종합소득세 신고

UMMAYA does not call NTS 홈택스 directly because no official Open API for
filing exists (research note 2026-04-29). When a citizen asks UMMAYA to
"종합소득세 신고", the LLM should respond with a step-by-step guide directing
them to hometax.go.kr / 손택스 with their 간편인증 / 공동인증서.

Reference: 국세청 「국세기본법 §81-13」 비밀유지, hometax 인증센터.
```

The LLM's system prompt teaches it to recognize OPAQUE domains and respond with a hand-off rather than invoking a tool.

---

## 5. Concrete redesign actions (proposal)

The following changes implement this design. **Each item is a candidate sub-issue under a new Epic** (working title: "Domain harness — research-driven adapter realignment").

### A. Schema / metadata redesign

| ID | Change | Risk |
|---|---|---|
| A1 | Define `AdapterRealDomainPolicy` Pydantic model (replaces deleted Spec 033 invented schema) | Low |
| A2 | Annotate every existing adapter with `policy.real_classification_url` + `policy.last_verified` | Low |
| A3 | Migrate adapter metadata from `permission_tier=N` to `citizen_facing_gate.kind` lookup | Medium |
| A4 | `compute_permission_tier()` becomes a thin find: `kind → 1/2/3 hint for UI colour only` | Low |
| A5 | Remove `pipa_class` / `auth_level` enums from adapter model — replace with `real_classification: str` (free-form citation) | Medium |

### B. Adapter cleanup based on research findings

| ID | Change | Risk |
|---|---|---|
| B1 | **Delete** `mock_verify_digital_onepass` — service retired 2025-12-30 | Low |
| B2 | **Add** `mock_verify_any_id_sso` — successor stub for 정부 통합인증 (research stub spec) | Low |
| B3 | Move `mock_welfare_application_submit_v1` to `docs/scenarios/` — submit surface OPAQUE | Medium |
| B4 | Move `mock_traffic_fine_pay_v1` to `docs/scenarios/` — submit surface OPAQUE for now | Medium |
| B5 | Add explicit "shape-mirror only" disclaimer to all grade-3 mocks (verify family) | Low |
| B6 | Add `_mode: "mock"` field to every mock response envelope for transparency | Low |

### C. Rate-limit redesign

| ID | Change | Risk |
|---|---|---|
| C1 | Implement `ToolRateLimiter` keyed by `tool_id` | Medium |
| C2 | Seed defaults from research matrix (KOROAD/KMA = 10k, NMC = 1M, CBS = 10k) | Low |
| C3 | Surface per-tool quota status in `/tools` slash command | Low |

### D. Permission gauntlet binding

| ID | Change | Risk |
|---|---|---|
| D1 | New `CitizenGate.kind`-keyed dispatch in CC `<PermissionRequest>` consumer | Medium |
| D2 | LLM system-prompt rule: when tool's `gate.kind == "scenario_only"`, hand off without calling | Low |
| D3 | Audit receipt format includes `real_classification_url` (full traceability) | Low |

### E. Documentation

| ID | Change | Risk |
|---|---|---|
| E1 | Rewrite `docs/api/<adapter>.md` template — add "Real-domain policy" section with citation | Low |
| E2 | New `docs/scenarios/` index for OPAQUE domains (홈택스, 정부24-submit, 모바일ID, KEC sign, 금융 sign, mydata-live) | Low |
| E3 | Update `docs/vision.md § Reference materials` to cite this research deliverable | Low |
| E4 | ADR — "UMMAYA does not invent permission policy; adapters cite agency policy" | Low |

### F. CI gates

| ID | Change | Risk |
|---|---|---|
| F1 | New CI check: every adapter must have non-empty `policy.real_classification_url` | Low |
| F2 | New CI check: byte-mirror grade-5 mocks must produce JSON identical to fixture (sort_keys hash) | Low |
| F3 | New CI check: scenario-only domains have no adapter file under `src/ummaya/tools/` | Low |

---

## 6. What this design rejects (for clarity)

- ❌ UMMAYA-invented `PermissionMode` 5-mode spectrum (`default/plan/acceptEdits/bypassPermissions/dontAsk`) — already deleted (Spec 1979 Wave 3).
- ❌ UMMAYA-invented `pipa_class` enum (`일반/민감/고유식별/특수`) — replace with free-form citation.
- ❌ UMMAYA-invented NIST AAL hint (`AAL1/AAL2/AAL3`) — agencies don't publish AAL hints; use `citizen_facing_gate.kind` instead.
- ❌ UMMAYA-invented PIPA §15(2) `ConsentDecision` 4-tuple — agencies dictate their own consent shape (e.g. 마이데이터 표준동의서).
- ❌ Building any tool that calls 홈택스 / 정부24 submit endpoints — OPAQUE, scenario-only.
- ❌ Replicating 디지털원패스 — service retired; needs Any-ID successor stub.
- ❌ Inventing colour-coded permission tiers for citizen-facing UI without traceability — every visible permission UI must trace back to a citation URL.

---

## 7. What this design preserves

- ✅ CC's canonical `<PermissionRequest>` pipeline (Class A files, Spec 1979 Wave audit confirmed byte-identical).
- ✅ 5-primitive surface (`lookup` / `submit` / `verify` / `subscribe` + `resolve_location` meta).
- ✅ EXAONE native function calling, FriendliAI Tier 1.
- ✅ Existing 12 Live adapters (KOROAD/KMA/HIRA/NMC/NFA/MOHW catalog/CBS read).
- ✅ data.go.kr REST key as the umbrella auth for all data.go.kr domains.
- ✅ The Spec 027 mailbox replay-unread pattern for OPAQUE long-running flows (when the citizen needs to physically go to gov.kr/hometax.go.kr).

---

## 8. Sources (research deliverable, 2026-04-28/29)

All citations are public Korean government dev portals or open-data listings. Full URLs in research deliverable; condensed list:

- 공공데이터포털 (data.go.kr) — KOROAD 15057467, KMA 15084084, HIRA 15001698, NMC 15000563, NFA 15099423, SSIS 15083323, CBS 15091495, MFDS 15057639, 정부24 카탈로그 15113968.
- 기관별 dev portal — apihub.kma.go.kr, opendata.hira.or.kr, e-gen.or.kr/nemc/open_api.do, opendata.koroad.or.kr, dev.mobileid.go.kr, openapi.kftc.or.kr, developers.mydatakorea.org, gov.kr/openapi.
- KISA — rootca.kisa.or.kr (HTML5 PKI guideline, accredited CA list).
- 디지털원패스 종료 공지 — docu.gdoc.go.kr/cmm/popup/popup_t.do?nttId=41896.
- NTS 간편인증 매뉴얼 PDF — hometax.speedycdn.net.
- KOMSCO 모바일신분증 — komsco.com/kor/contents/162, mois.go.kr/frt/sub/a06/b04/mobileId.
- 금결원 yessign — yeskey.or.kr.

---

## 9. Next step

If user approves, open Epic "Domain harness research-driven adapter realignment" with sub-issues A1–F3 above. Recommend Phase A (schema redesign A1–A5) as immediate next sprint; B-F follow.

Until then, this document is the **canonical research basis** for any future adapter or permission UX decision and should be cited per `feedback_check_references_first`.
