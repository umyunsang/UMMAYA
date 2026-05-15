# Feature Specification: data.go.kr Verified Adapter Wave

**Feature Branch**: `feat/data-go-kr-verified-adapters`  
**Created**: 2026-05-16  
**Status**: Draft  
**Input**: User description: "Wrap the data.go.kr APIs that have already passed direct real-use curl verification first. The 30 newly scoped candidates are excluded for now because their applications are still within the two-hour approval window."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discover Verified Public Service Adapters (Priority: P1)

A citizen asks UMMAYA about a public-service domain covered by a directly verified API, and the system surfaces only adapters whose upstream endpoint, credential path, request parameters, and response shape have already been proven by saved curl evidence.

**Why this priority**: It prevents unverified candidate APIs from entering the tool-call surface while preserving UMMAYA's thesis that one official callable agency module becomes one registered tool adapter.

**Independent Test**: Can be fully tested by searching for each verified domain and confirming the routing surface returns only adapters backed by `LIVE-PROBE-RESULTS-2026-05-16.md` evidence.

**Acceptance Scenarios**:

1. **Given** a citizen asks for 부산 장례 비용 information, **When** UMMAYA searches available tools, **Then** it returns a 부산시설공단 장례비산출 `find` adapter backed by the saved `15157485` live probe.
2. **Given** a citizen asks for a domain from the 30 newly scoped but not-yet-authorized candidates, **When** UMMAYA searches available tools, **Then** no live adapter from that unauthorized set is registered in this feature.
3. **Given** an API was reachable but not callable in the probe report, **When** UMMAYA builds the adapter catalog, **Then** that API is documented as deferred and is not exposed as a callable adapter.

---

### User Story 2 - Fetch Read-Only Public Data Through `find` (Priority: P1)

A citizen asks for public read-only information from a verified API, and UMMAYA calls the matching `find` adapter without mutating agency state or requiring citizen identity proof beyond the agency's API-key access requirement.

**Why this priority**: All APIs in the first verified wave are read-only lookup/statistics/catalog APIs. They should enter the existing `find` primitive rather than reintroducing domain-specific verbs.

**Independent Test**: Can be fully tested by replaying recorded successful and error response fixtures for each included adapter without making live API calls in CI.

**Acceptance Scenarios**:

1. **Given** a verified API returns HTTP 200 with a normal service code in saved evidence, **When** its adapter receives valid search parameters, **Then** the adapter returns a normalized result envelope with source, query, result count, and item records.
2. **Given** the upstream returns a valid zero-result response, **When** the adapter receives parameters that match that response, **Then** the adapter returns an empty successful result rather than an error.
3. **Given** the upstream returns an authentication or service error shape, **When** the adapter parses the fixture, **Then** the adapter returns a fail-closed tool error with the upstream result code and sanitized reason.

---

### User Story 3 - Maintain Evidence-Gated Scope (Priority: P2)

A maintainer reviews the adapter wave and can trace every included API to a saved direct-call artifact, while excluded APIs have a concrete deferral reason.

**Why this priority**: UMMAYA's adapter surface must stay auditable. Intake notes alone do not authorize code; direct evidence and explicit scope boundaries do.

**Independent Test**: Can be fully tested by comparing the spec's included and deferred API tables against the saved probe report and candidate intake documents.

**Acceptance Scenarios**:

1. **Given** a reviewer opens the feature spec, **When** they inspect the included API list, **Then** every row references a direct successful probe artifact under `docs/api/data-go-kr-candidate-docs/<id>/probes/live-2026-05-16/`.
2. **Given** a reviewer opens the deferred list, **When** they inspect the reason for each deferral group, **Then** every excluded API has a blocker tied to authorization latency, missing key registration, gateway failure, live-call safety, or sample-data absence.

### Edge Cases

- The upstream returns HTTP 200 with an error payload such as invalid key, quota exceeded, or service not registered.
- The upstream returns XML for one operation and JSON for another within the same agency family.
- A saved successful probe has a valid zero-result body; this must not be treated as a failed adapter.
- A `LINK` API uses a provider-specific key rather than `UMMAYA_DATA_GO_KR_API_KEY`.
- A candidate API has a captured Swagger or guide but lacks direct successful curl evidence.
- A newly approved candidate becomes callable after this spec is reviewed; it remains out of scope until a follow-up Spec Kit cycle updates the evidence set.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST include only APIs listed as `Confirmed Callable` in `docs/api/data-go-kr-candidate-docs/LIVE-PROBE-RESULTS-2026-05-16.md` for this adapter wave.
- **FR-002**: System MUST register each included API under the active `find` primitive unless a later approved spec proves the API performs identity/status verification or state mutation.
- **FR-003**: System MUST NOT register any of the 30 newly scoped candidates from `SCOPED-NEW-30-manifest.json` in this feature because their service applications are still within the two-hour authorization window and lack direct successful probes.
- **FR-004**: System MUST NOT register APIs listed as `Reachable But Not Yet Callable` or `Not Live-Probed` in the live probe report as live adapters in this feature.
- **FR-005**: System MUST preserve the existing active primitive surface: `find`, `locate`, `send`, and `check`; no legacy domain verbs or `subscribe` surface may be introduced.
- **FR-006**: System MUST keep all included adapters read-only, idempotent, and free of agency-state mutation.
- **FR-007**: System MUST produce a documented adapter mapping for each included API, covering data.go.kr ID, Korean API name, owning institution, primitive, source mode, credential family, direct evidence artifact, and citizen-facing domain.
- **FR-008**: System MUST require recorded fixtures for successful, zero-result where available, and upstream error responses before a verified adapter is considered complete.
- **FR-009**: System MUST ensure default CI tests replay fixtures only and never call live data.go.kr, KEPCO, REB, TAGO, AirKorea, FTC, PPS, university, finance, or funeral-cost endpoints.
- **FR-010**: System MUST mark provider-key `LINK` APIs separately from data.go.kr service-key APIs so their credential source is not conflated.
- **FR-011**: System MUST show bilingual search hints for each included adapter, including Korean citizen phrasing, English glosses, institution names, and domain synonyms.
- **FR-012**: System MUST fail closed when required query parameters are missing, duplicated incompatibly, out of documented range, or not supported by the saved official contract.
- **FR-013**: System MUST document deferred candidates with a concrete blocker and must not silently omit blocked APIs from the implementation report.
- **FR-014**: System MUST keep permission classification adapter-level and cite the agency or portal source rather than inventing a UMMAYA-only permission policy.

### Included Verified API Set

| ID | API | Institution | Primitive | Inclusion Evidence |
|----|-----|-------------|-----------|--------------------|
| `15043459` | 금융위원회 기업 재무정보 | Financial Services Commission | `find` | `15043459/probes/live-2026-05-16/corporate-finance-summary.body.json` |
| `15073861` | AirKorea 대기오염정보 | 한국환경공단 / AirKorea | `find` | `15073861/probes/live-2026-05-16/airkorea-ctprvn.body.json` |
| `15091886` | 공정위 대규모기업집단 | Fair Trade Commission | `find` | `15091886/probes/live-2026-05-16/ftc-large-group.body.xml` |
| `15091910` | 공정위 사용 가능 공개년월 | Fair Trade Commission | `find` | `15091910/probes/live-2026-05-16/ftc-public-ym.body.xml` |
| `15098529` | TAGO 버스노선정보 | MOLIT / TAGO | `find` | `15098529/probes/live-2026-05-16/tago-bus-route.body.xml` |
| `15098530` | TAGO 버스도착정보 | MOLIT / TAGO | `find` | `15098530/probes/live-2026-05-16/tago-bus-arrival.body.xml` |
| `15098533` | TAGO 버스위치정보 | MOLIT / TAGO | `find` | `15098533/probes/live-2026-05-16/tago-bus-location.body.xml` |
| `15098534` | TAGO 버스정류소정보 | MOLIT / TAGO | `find` | `15098534/probes/live-2026-05-16/tago-bus-station.body.xml` |
| `15101360` | KEPCO 계약종별 전력사용량 | Korea Electric Power Corporation | `find` | `15101360/probes/live-2026-05-16/kepco-contract-type.body.json` |
| `15129394` | 조달청 나라장터 입찰공고정보 | Public Procurement Service | `find` | `15129394/probes/live-2026-05-16/pps-bid-service.body.json` |
| `15134761` | 한국부동산원 부동산통계 | Korea Real Estate Board | `find` | `15134761/probes/live-2026-05-16/reb-stat-table.body.json` |
| `15157485` | 부산시설공단 장례비산출 | Busan Facilities Corporation | `find` | `15157485/probes/live-2026-05-16/funeral-area-list.body.json` |
| `15158680` | 대학알리미 재정 현황 | Korean Council for University Education | `find` | `15158680/probes/live-2026-05-16/finance-regional-tuition.body.xml` |
| `15158684` | 대학정보공시 학생 현황 | Korean Council for University Education | `find` | `15158684/probes/live-2026-05-16/student-regional-foreign.body.xml` |

### Key Entities *(include if feature involves data)*

- **Verified API Candidate**: A public-service API with saved direct curl evidence proving endpoint, credential path, parameters, response status, and body shape.
- **Adapter Registration**: The tool catalog entry that binds one verified API module to an active primitive, discovery hints, credential family, and agency policy citation.
- **Evidence Artifact**: A sanitized saved response header or body file under `docs/api/data-go-kr-candidate-docs/<id>/probes/live-2026-05-16/`.
- **Fixture Set**: Replayable successful, zero-result, and error payloads used by tests so CI never calls live public APIs.
- **Deferred Candidate**: An API that has intake documentation but is not allowed in this feature because it lacks direct successful call evidence or safe live-call conditions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of included adapters are traceable to a saved direct successful probe artifact from 2026-05-16.
- **SC-002**: 0 APIs from `SCOPED-NEW-30-manifest.json` are registered as live adapters in this feature.
- **SC-003**: 100% of included adapters are registered under `find` and no new root primitive or legacy domain verb is introduced.
- **SC-004**: 100% of default test coverage for this feature uses fixtures and performs no live external citizen-infrastructure calls.
- **SC-005**: Each included adapter has bilingual discovery hints and at least one citizen-facing trigger phrase.
- **SC-006**: Each included adapter has an explicit deferral-safe error behavior for invalid key, upstream service error, malformed response, and empty result.
- **SC-007**: The adapter catalog and generated schema artifacts list every included adapter and omit every deferred candidate.

## Assumptions

- The saved direct probe artifacts are sufficient evidence to start specification and planning, but implementation tasks may still request targeted re-probes when a response shape is incomplete.
- All included APIs are read-only public or API-key-gated public data surfaces and therefore map to `find` in this feature.
- `15101360` and `15134761` are provider-key `LINK` APIs and must use their own credential family rather than the shared data.go.kr service key.
- The first implementation plan may group closely related operations, such as the four TAGO bus APIs or the two university APIs, while still preserving one clear adapter registration per callable agency module.
- The 30 newly scoped candidates can be reconsidered after their approval window passes and direct curl probes prove callable behavior.

## Scope Boundaries & Deferred Items *(mandatory)*

### Out of Scope (Permanent)

- Reintroducing legacy verbs such as `pay`, `issue_certificate`, `submit_application`, or `subscribe_alert` — the active harness surface is fixed to `find`, `locate`, `send`, and `check`.
- Mocking opaque citizen-transaction systems without a public callable contract — those remain scenario-only per UMMAYA's mock-vs-scenario rule.
- Calling live public APIs from default CI — public API contract checks may be local/manual or marked live only, never part of default test execution.

### Deferred to Future Work

| Item | Reason for Deferral | Target Epic/Phase | Tracking Issue |
|------|---------------------|-------------------|----------------|
| 30 candidates in `SCOPED-NEW-30-manifest.json` | Their data.go.kr applications are still within the two-hour authorization window and lack successful direct probes. | Follow-up wave under Epic #2797 | #2832 |
| `15000122` and `15000215` 법제처 SOAP services | WSDL is reachable, but the current key returns service-key registration errors. | Follow-up wave under Epic #2797 | #2833 |
| `15000241` EMS 행방조회 | Endpoint reacts to key presence, but no currently valid EMS tracking sample has proven a successful data response. | Follow-up wave under Epic #2797 | #2834 |
| `15081808` 국세청 사업자 상태조회 | Endpoint and POST body are known, but approved-key probes currently return upstream `-5`; classify later as `check` only after successful evidence. | Follow-up `check` adapter wave | #2835 |
| `15074634` MSIT business announcements | Approved and documented, but the official endpoint returned gateway blocking during direct probe. | Follow-up wave under Epic #2797 | #2836 |
| `15149906` MOJ stay-person counter | Approved and documented, but the gateway returned 502 and the direct backend redirected unexpectedly during direct probe. | Follow-up wave under Epic #2797 | #2837 |
| `15000032` EMS 신청 저장 서비스 | It is a `send` candidate with real submit/cancel behavior; no sandbox or safe test endpoint is proven. | Future `send` adapter wave | #2838 |
| `15056641` CareerNet job information | External CareerNet key approval is pending; no issued key was visible at capture time. | Follow-up external-key wave | #2839 |
| `15087442` KDCA health information | External KDCA registration status and supported endpoint version need reconciliation before wrapping. | Follow-up external-key wave | #2840 |
