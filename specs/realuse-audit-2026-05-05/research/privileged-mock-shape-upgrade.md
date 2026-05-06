# Privileged Mock Shape Upgrade Research

**Date**: 2026-05-05
**Scope**: Evidence-grade mock upgrade for privileged `verify`, `submit`, and personal-data
`lookup` adapters. Public read-only `lookup` adapters may stay Live when public API keys exist.

## Constraint

KOSMOS is a student portfolio project. For Hometax, Government24 electronic documents,
public MyData, Mobile ID, and simple-auth relay flows, official channels exist or are
policy-mandated, but KOSMOS does not hold the institutional approval, API key, server
certificate, DID registration, or legal delegation needed to call those channels live.

Therefore these adapters must remain Mock. The mock may infer a private-domain payload shape
only when it marks the evidence grade, lists official sources, and states the inference
boundary in the adapter response.

## Evidence Sources

| Domain | Source | Facts usable for mock shape |
|---|---|---|
| Public MyData | https://www.mydata.go.kr/pc/intro/serviceIntro.do?tab=tab_3&type=A | Public MyData is a subject-right service; API service lets a using institution replace required document submission by a citizen's provision request. The service sends only needed certificate items through the public MyData distribution system. |
| Public MyData operations guide | https://adm.mydata.go.kr/images/guide.pdf | Bundle information exists to minimize items into a use-specific set. This supports `bundle_policy`, `data_minimization`, and distribution trace fields in mocks. |
| Hometax simplified data consent | https://mob.tbys.hometax.go.kr/jsonAction.do?actionId=UTBYSFAA02F001 | Hometax simplified data has consent, cancellation, company recipient, purpose, dependent-data, exclusion, and retention semantics. |
| NTS e-filing guide | https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?cntntsId=7713&mi=2304 | Hometax electronic filing exists, can validate simple calculation errors, and can accept supporting documents online. |
| Mobile ID onboarding | https://dev.mobileid.go.kr/mip/dfs/apiuse/apiusestep.do | A relying institution must apply, receive approval, register development DID, use test credentials/app, build and test SP server, submit scenario video, register operation DID, then operate. |
| Mobile ID verifier modes | https://dev.mobileid.go.kr/mip/dfs/useguide/apiusemethod.do | Mobile ID supports library and daemon integration; daemon mode is API-based and language-agnostic. |
| Mobile ID daemon API | https://dev.mobileid.go.kr/mip/dfs/useguide/mdGuide.do?guide=demonapiguide | The verifier daemon exposes transaction start, profile, image, VP verification, error, status, and re-verification APIs. |
| Electronic document wallet API | https://www.dpaper.kr/ewp/smm/intrcn.do | Standard API use requires server certificate, portal ID, API key, membership, development key, test-result registration, and operation API key. |
| Electronic document wallet terms | https://www.dpaper.kr/ewp/busiAccountUrl.do | The service handles certificate application, issuance, receipt, storage, viewing, and transfer through a wallet address. |
| KISA electronic signature recognition | https://www.kisa.or.kr/1051203 | KISA recognizes electronic-signature service providers through evaluation and certification; this supports provider-result verification as a required simple-auth concept. |
| Simple-auth hub reference | https://www.ez-iok.com/guide/eziok_intro/ and https://www.ez-iok.com/guide/eziok_std_guide/ | Public hub docs show a JSON-based simple-auth/sign request model with service ID, encrypted transaction ID, service type, and result API verification. This is not a government source, so use as implementation-pattern evidence only. |
| Singapore APEX | https://www.apex.gov.sg/ | APEX is a government API hub with lifecycle portal, monitoring, security, credential rotation, and version control. Use as API-hub analog. |
| Singapore Myinfo | https://docs.developer.singpass.gov.sg/docs/legacy-myinfo-v3-v4/technical-specifications/myinfo-v4 | Myinfo uses authorize, token, and person APIs with explicit user consent and short-lived access token. Use as consented personal-data retrieval analog. |
| Estonia X-Road | https://x-road.global/data-exchange | X-Road exchanges data directly between service consumer and provider through signed, logged, mTLS-protected security servers. Use as government data-exchange analog. |
| EU EUDI Wallet | https://digital-strategy.ec.europa.eu/en/library/european-digital-identity-wallet-architecture-and-reference-framework | EUDI ARF provides interoperable wallet specifications. Use as digital-wallet identity analog. |

## Evidence Grades

| Grade | Meaning | Allowed usage |
|---|---|---|
| `A-official-api-published` | Official API or integration endpoints are publicly visible. | Mock can mirror endpoint sequence and major request/response concepts, while marking cryptography and credentials as fixture-only. |
| `B-official-flow-private-spec-inferred` | Official service/API onboarding or user flow is public, but detailed payload spec is partner-gated. | Mock can model lifecycle fields, receipts, and audit states; field names must be marked inferred. |
| `C-policy-mandated-inferred` | The policy or portal flow exists, but no callable partner API spec is public. | Mock can only model high-level transaction lifecycle and must keep private payload details generic. |

## Applied Adapter Decisions

| Adapter | Grade | Shape additions |
|---|---|---|
| `mock_verify_module_modid` | `A-official-mobile-id-verifier-api-published` | Evidence metadata now cites Mobile ID onboarding, verifier modes, daemon APIs, and EUDI Wallet analog. The AuthContext still does not claim real VP verification. |
| `mock_verify_module_simple_auth` | `B-official-policy-private-hub-api-inferred` | Evidence metadata now cites KISA recognition and public hub request/result patterns. The mock keeps result validity fixture-only. |
| `mock_verify_mydata` | `B-public-mydata-standard-private-credential-required` | Evidence metadata now cites public MyData service and Myinfo analog. The context remains a fixture identity/consent envelope. |
| `mock_lookup_module_hometax_simplified` | `B-official-consent-flow-private-payload-inferred` | Payload now includes consent receipt, retrieval flow, bundle minimization, and source-document summary fields. |
| `mock_submit_module_hometax_taxreturn` | `C-official-portal-flow-private-submit-api-inferred` | Receipt now includes preflight validation, submission flow, status history, idempotency key, and separate-payment next action. |
| `mock_lookup_module_gov24_certificate` | `B-official-api-onboarding-private-spec-inferred` | Payload now includes electronic document wallet lifecycle, integrity placeholder, API onboarding flow, and wallet address placeholder. |
| `mock_submit_module_gov24_minwon` | `B-official-api-onboarding-private-submit-spec-inferred` | Receipt now includes 민원 lifecycle, server/API credential assumptions, wallet delivery, and status history. |
| `mock_submit_module_public_mydata_action` | `B-official-public-mydata-flow-action-extension-inferred` | Receipt now includes consent action, bundle policy, distribution trace refs, and state-transition history. |

## Guardrails

1. Do not present private API fields as official unless an official schema is cited.
2. Do not call these live domains in CI or student-tier real-use tests.
3. Keep the public primitive envelope stable so Live promotion replaces only adapter internals.
4. Every privileged mock response should expose `_mock_fidelity_grade` and `_mock_evidence`.
5. `lookup` remains the only primitive class allowed to use Live public read-only APIs when credentials and terms permit it.
