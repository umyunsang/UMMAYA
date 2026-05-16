# Feature Specification: data.go.kr Live Expansion

**Feature Branch**: `2798-data-go-kr-live-expansion`
**Created**: 2026-05-16
**Status**: Draft
**Originating Epic**: #2832
**Input**: User description: "3건을 제외하고 30개의 live api들을 tool call 할 수 있게 적절한 primitive의 어댑터로 wrapping 하여 등록하고, 터미널에서 UMMAYA를 실행해 LLM이 스스로 tool call하는지 오류와 비정상 흐름을 검증하고 디버깅한다."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Expose the 30 Callable APIs (Priority: P1)

A citizen asks about one of the approved public-service data domains, and UMMAYA can discover and invoke the correct live adapter through the active tool-call surface. The three APIs whose approved key is still rejected by the provider backend are not exposed as live tools.

**Why this priority**: The approved batch has direct curl evidence for 30 callable public-service APIs. UMMAYA's unit of work is one official callable agency module wrapped as one registered adapter, while evidence-blocked channels must remain out of the live surface.

**Independent Test**: Can be tested by comparing the registered adapter catalog against the 30 callable rows in `docs/api/data-go-kr-candidate-docs/LIVE-API-CALL-MATRIX-2026-05-16.md` and confirming the three blocked IDs are absent.

**Acceptance Scenarios**:

1. **Given** the 30 callable APIs in the live matrix, **When** the adapter registry is built, **Then** each callable API is represented by one live adapter with evidence, policy citation, bilingual search hints, and an executable schema.
2. **Given** API IDs `15038392`, `15058923`, and `15063444`, **When** the adapter registry is built, **Then** no live adapter for those IDs is registered and the deferral reason is documented.
3. **Given** a citizen asks "최근 과기정통부 AI 관련 사업공고 찾아줘", **When** UMMAYA selects an adapter, **Then** it calls the MSIT business-announcement adapter with the documented request shape and does not fabricate a generic web answer.

---

### User Story 2 - Preserve Correct Primitive Semantics (Priority: P1)

A citizen does not need to know agency-specific endpoints or parameters. UMMAYA chooses the active primitive that matches current runtime semantics, then calls the target adapter with the documented parameter names.

**Why this priority**: The current UMMAYA runtime routes public-data lookup, list, statistics, and public status facts through the `find({"tool_id": ..., "params": ...})` adapter fetch path. `locate` is a resolver for coordinates, addresses, and administrative codes. `check` is identity-delegation oriented and must not be reused for public read-only status facts without a separate primitive-semantics change.

**Independent Test**: Can be tested by injecting citizen prompts that mention location, status, statistics, medicines, transport, jobs, and support notices, then inspecting the terminal run to verify the selected root tool and adapter IDs.

**Acceptance Scenarios**:

1. **Given** a citizen asks "종로구 자동심장충격기 위치 알려줘", **When** UMMAYA needs region normalization, **Then** it may call `locate` first for region conversion, but the official AED data adapter is invoked through the public-data adapter path.
2. **Given** a citizen asks "대전역에서 시청역까지 지하철 요금과 시간 알려줘", **When** UMMAYA has station-code parameters, **Then** it calls the Daejeon metro adapter without using the identity-oriented `check` primitive.
3. **Given** a citizen asks about public jobs, SME support notices, or immigration aggregate statistics, **When** UMMAYA answers, **Then** it performs a tool call and cites official returned fields rather than answering from model memory.

---

### User Story 3 - Prove Real UMMAYA Tool-Call Behavior (Priority: P1)

After adapters are registered, a maintainer runs UMMAYA in a terminal, enters representative Korean citizen prompts, and inspects the conversation/tool-call flow for missing tools, wrong primitive selection, malformed parameters, repeated failed calls, permission misclassification, or fallback hallucination.

**Why this priority**: Passing fixture tests is not enough for this request. The user explicitly asked to verify that the LLM itself chooses and calls the tools in the live UMMAYA terminal flow.

**Independent Test**: Can be tested with a recorded terminal smoke that includes at least one safety-location prompt, one medical/drug prompt, one government-notice prompt, one transport prompt, and one statistics prompt.

**Acceptance Scenarios**:

1. **Given** UMMAYA is run locally with the required live credentials, **When** representative prompts are entered, **Then** the terminal transcript shows successful root primitive calls with the expected adapter IDs.
2. **Given** an adapter returns a normal zero-result response, **When** UMMAYA receives it, **Then** the answer explains that no matching official records were returned instead of treating it as a tool failure.
3. **Given** the LLM emits an invalid parameter or wrong primitive call, **When** the runtime rejects it, **Then** the agentic loop recovers to a valid call or reports the exact blocker without fabricating data.

---

### User Story 4 - Keep Evidence and Safety Auditable (Priority: P2)

A reviewer can trace every live adapter to direct probe evidence and can see why each excluded API remains blocked.

**Why this priority**: Live public-service adapters carry real user trust. Every included adapter must be tied to direct endpoint, parameter, and response evidence, while blocked services must not disappear silently.

**Independent Test**: Can be tested by checking documentation, schemas, fixtures, and probe references for all included and excluded API IDs.

**Acceptance Scenarios**:

1. **Given** a reviewer opens the adapter docs, **When** they inspect any included API, **Then** they can find its portal URL, evidence artifact, parameter map, credential family, response format, and citizen-facing boundary.
2. **Given** a reviewer opens the blocked list, **When** they inspect IDs `15038392`, `15058923`, and `15063444`, **Then** the document states the provider/key mapping blocker and points to the resolution probe evidence.

### Edge Cases

- The upstream returns HTTP 200 with `resultCode=99`, `SERVICE ACCESS DENIED ERROR`, or "등록되지 않은 서비스키입니다".
- The upstream returns a normal zero-result payload.
- The upstream requires a non-default transport detail, such as `15149906` uppercase `ServiceKey`, `15074634` browser-like `User-Agent`, or `15121954` HTTP gateway evidence.
- A prompt contains a city or district name, but the selected adapter schema does not require coordinates or administrative codes.
- A prompt asks for diagnosis, legal advice, emergency dispatch, application submission, purchase, payment, reservation, or identity-bound access that the approved read-only API cannot perform.
- A credential environment variable is missing in local terminal smoke.
- The LLM repeats the same failing tool call within one turn instead of recovering from validation feedback.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose exactly the 30 callable APIs documented in `LIVE-API-CALL-MATRIX-2026-05-16.md` as the target live public-data set for this feature.
- **FR-002**: System MUST preserve the 14 existing verified adapters from `specs/2797-data-go-kr-verified-adapters/` and add the 16 newly callable adapters listed in this spec.
- **FR-003**: System MUST NOT register live adapters for `15038392`, `15058923`, or `15063444` in this feature because direct control probes show provider/key mapping blockers.
- **FR-004**: System MUST bind these read-only public-data adapters to the active runtime primitive semantics: public lookup, list, statistics, and public status facts are adapter fetches, with `locate` used only as a preceding resolver when coordinates or administrative codes are required.
- **FR-005**: System MUST NOT route this batch through `send`, and MUST NOT use the identity-delegation `check` primitive for public read-only status facts in this feature.
- **FR-006**: System MUST include direct evidence references for every included adapter, using the sanitized probe artifacts under `docs/api/data-go-kr-candidate-docs/<id>/probes/live-2026-05-16-direct-check/` or `live-2026-05-16-blocker-resolution/`.
- **FR-007**: System MUST implement the documented transport quirks as adapter contract behavior: uppercase `ServiceKey` for `15149906`, browser-like `User-Agent` for `15074634`, and scheme-specific evidence for `15121954`.
- **FR-008**: System MUST keep provider-key APIs separate from the shared data.go.kr key family; provider credentials may not be conflated with `UMMAYA_DATA_GO_KR_API_KEY`.
- **FR-009**: System MUST define strict Pydantic v2 input and output schemas for each new adapter, with no `Any` in public tool I/O.
- **FR-010**: System MUST use typed agency metadata for newly introduced institutions, or explicitly document any temporary `OTHER` use as a blocker before implementation review.
- **FR-011**: System MUST add bilingual Korean/English search hints and citizen trigger examples for every included adapter.
- **FR-012**: System MUST add fixture replay coverage for successful, zero-result where available, and upstream error responses without calling live public APIs in default tests.
- **FR-013**: System MUST fail closed when required parameters are missing, unsupported, incompatible, or outside the documented upstream contract.
- **FR-014**: System MUST generate or update adapter documentation and JSON Schema artifacts for every included adapter.
- **FR-015**: System MUST run a real local terminal UMMAYA smoke with representative prompts and record the observed tool-call behavior, abnormal-flow findings, and fixes.
- **FR-016**: System MUST inspect terminal smoke for wrong adapter selection, wrong primitive selection, repeated failed calls, fabricated fallback answers, permission misclassification, and malformed parameter recovery.
- **FR-017**: System MUST keep all saved probe and smoke artifacts free of plaintext secrets.

### Included API Set

The implementation target is 30 callable APIs: the 14 already wrapped in Spec 2797 plus the 16 additional callable APIs proven by the 2026-05-16 direct-check and blocker-resolution evidence.

#### Existing 14 Adapters To Preserve

| ID | Adapter | Status |
|----|---------|--------|
| `15043459` | `fsc_corporate_finance_summary` | Preserve live adapter |
| `15073861` | `airkorea_ctprvn_air_quality` | Preserve live adapter |
| `15091886` | `ftc_large_group_status` | Preserve live adapter |
| `15091910` | `ftc_public_ym_list` | Preserve live adapter |
| `15098529` | `tago_bus_route_search` | Preserve live adapter |
| `15098530` | `tago_bus_arrival_search` | Preserve live adapter |
| `15098533` | `tago_bus_location_search` | Preserve live adapter |
| `15098534` | `tago_bus_station_search` | Preserve live adapter |
| `15101360` | `kepco_contract_power_usage` | Preserve live adapter |
| `15129394` | `pps_bid_public_info` | Preserve live adapter |
| `15134761` | `reb_real_estate_stat_table` | Preserve live adapter |
| `15157485` | `bfc_funeral_area_fee` | Preserve live adapter |
| `15158680` | `kcue_finance_regional_tuition` | Preserve live adapter |
| `15158684` | `kcue_student_regional_foreign` | Preserve live adapter |

#### New 16 Adapters To Add

| ID | Candidate Adapter | Citizen Coverage |
|----|-------------------|------------------|
| `15121954` | `moj_village_lawyer_lookup` | Local village lawyer and responsible official lookup |
| `15073554` | `mois_facility_safety_info_lookup` | Facility safety information search |
| `15001699` | `hira_medical_institution_detail` | Medical institution detail after hospital identification |
| `15155046` | `mois_emergency_call_box_lookup` | Emergency call box location metadata |
| `15158794` | `djtc_subway_segment_fare_time_check` | Daejeon metro fare, time, and distance |
| `15096040` | `gyeryong_assistive_device_charging_place_locate` | Assistive-device charging places in Gyeryong |
| `15000652` | `nmc_aed_site_locate` | National AED site lookup |
| `15127779` | `mof_ocean_water_quality_check` | Realtime marine water-quality readings |
| `15075057` | `mfds_easy_drug_info_lookup` | Official easy drug information |
| `15156780` | `mpm_public_job_lookup` | Public job announcement search |
| `15129471` | `pps_shopping_mall_product_lookup` | Public procurement shopping mall product search |
| `15158905` | `ksd_financial_term_lookup` | Korea Securities Depository financial terms |
| `15157820` | `mss_sme_support_notice_lookup` | SME and small-business support notices |
| `15140950` | `ccourt_publication_documents` | Constitutional Court publication search |
| `15149906` | `moj_stay_person_counter` | Monthly short/long stay foreigner aggregate counts |
| `15074634` | `msit_business_announcement_lookup` | MSIT business and R&D announcement search |

#### Excluded 3 APIs

| ID | Candidate Adapter | Exclusion Reason |
|----|-------------------|------------------|
| `15038392` | `kcue_academyinfo_finance_lookup` | Provider recognizes the key as real but denies service access for this legacy service; newer KCUE `15158680` remains callable. |
| `15058923` | `ekape_animal_trace_lookup` | Official sample calls and fake-key controls return the same unregistered-key error. |
| `15063444` | `data_go_kr_uiryeong_civil_defense_shelters` | Provider endpoint is reachable, but approved and fake keys both return the same unregistered-key envelope. |

### Key Entities *(include if feature involves data)*

- **Callable API Evidence**: Sanitized direct-call artifact proving endpoint, credential family, parameters, response status, response body shape, and any gateway quirk.
- **Live Public-Data Adapter**: One registered tool that wraps one official callable agency module and exposes a strict schema, search hints, policy citation, and fixture-backed behavior.
- **Primitive Routing Decision**: The selected active root primitive and adapter ID that the LLM uses for a citizen prompt.
- **Terminal Smoke Transcript**: A recorded local UMMAYA run containing representative citizen prompts, root tool calls, adapter IDs, outputs, and any abnormal-flow notes.
- **Blocked API Record**: A candidate API excluded from live registration because direct evidence proves a provider/key mapping problem that local parameter changes cannot fix.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The live public-data adapter set contains all 30 callable IDs and excludes the three blocked IDs.
- **SC-002**: 100% of the 16 newly added adapters have evidence references, strict schemas, bilingual hints, policy citations, and fixture replay tests.
- **SC-003**: 0 default tests call live data.go.kr, provider, government, health, transport, procurement, or other external citizen-infrastructure endpoints.
- **SC-004**: Terminal UMMAYA smoke demonstrates successful LLM-initiated tool calls for at least five representative prompts across safety, medical/drug, support notice, transport, and statistics domains.
- **SC-005**: Terminal smoke inspection records 0 unresolved abnormal flows for wrong primitive selection, wrong adapter selection, repeated failed calls, malformed parameter recovery, permission misclassification, or fabricated fallback answers.
- **SC-006**: The blocked API documentation states why `15038392`, `15058923`, and `15063444` are excluded and points to the blocker-resolution evidence.
- **SC-007**: Secret scans over new probe, fixture, schema, docs, and smoke artifacts report no plaintext credential occurrences.

## Assumptions

- The saved 2026-05-16 direct probes and blocker-resolution probes are sufficient to define adapter contracts for this feature.
- All 30 included APIs are read-only public-data or API-key-gated public-data surfaces. None mutates agency state or accesses a citizen's private record.
- The correct runtime interpretation of "appropriate primitive" follows current UMMAYA semantics: public-data adapter calls use the adapter fetch path, while `locate` only normalizes place input when an adapter schema needs location-derived fields.
- This feature can avoid editing `tui/src/**`; if implementation touches TUI source, the mandatory TUI verification chain in `AGENTS.md` applies.
- Local terminal smoke may require `UMMAYA_DATA_GO_KR_API_KEY` and provider-specific credentials that are already managed outside Git.

## Scope Boundaries & Deferred Items *(mandatory)*

### Out of Scope (Permanent)

- Emergency dispatch, medical diagnosis, legal advice, eligibility final decisions, payment, procurement purchase, application submission, reservation, or identity-bound access. The approved APIs in this feature are read-only information channels.
- Replacing UMMAYA's active primitive set or reintroducing domain-specific root verbs such as `pay`, `issue_certificate`, `reserve_slot`, or `submit_application`.
- Calling live public APIs from CI or default test runs.

### Deferred to Future Work

| Item | Reason for Deferral | Target Epic/Phase | Tracking Issue |
|------|---------------------|-------------------|----------------|
| Live wrapping for `15038392` | Provider/service mapping denies the current approved key for the legacy AcademyInfo finance service. | Provider-mapping repair under Epic #2832 | #2877 |
| Live wrapping for `15058923` | EKAPE provider backend returns unregistered-key errors for documented sample calls and fake-key controls. | Provider-mapping repair under Epic #2832 | #2878 |
| Live wrapping for `15063444` | Uiryeong provider backend returns the same unregistered-key envelope for approved and fake keys. | Provider-mapping repair under Epic #2832 | #2879 |
| Root `locate` output reclassification for public facility datasets | Current runtime treats `locate` as a resolver, not as the public-data collection adapter path. Changing that would alter primitive semantics and requires a separate design decision. | Primitive semantics review | #2880 |
| Live adapter health monitoring and automatic re-probe scheduling | This feature focuses on wrapping and terminal smoke; ongoing monitoring needs separate operational design. | Adapter operations follow-up | #2881 |
