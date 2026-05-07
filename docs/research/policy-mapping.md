# KOSMOS 어댑터 ↔ 국제 AX-Gateway 매핑

> **Bilingual reference doc** — 한국어 primary / English fallback per AGENTS.md § Source Code Language.
> **Originating spec**: Epic ζ #2297 (`specs/2297-zeta-e2e-smoke/spec.md` FR-017 + SC-009).
> **Last verified**: 2026-04-30 (link probe via `specs/2297-zeta-e2e-smoke/scripts/probe_policy_links.sh`).

## Thesis (한국어)

KOSMOS 의 정체성은 **한국 국가 AX-인프라 의 client-side reference implementation** 이다 (AGENTS.md § CORE THESIS). 국가인공지능전략위원회 + 행동계획 2026-2028 + 공공AX + 범정부 AI 공통기반 정책은 각 부처 / 기관이 자체 시스템을 LLM-callable 한 보안-wrapping 통로로 노출하도록 강제한다 — KOSMOS 는 그 통로를 시민 대신 호출하는 caller 이다. 이 모델은 한국 고유의 발명이 아니다: Singapore APEX, Estonia X-Road, EU EUDI Wallet, Japan マイナポータル API 모두 같은 thesis 의 다른 구현이다. 따라서 KOSMOS 의 어댑터 카탈로그는 이 4개 국제 reference 와 row-by-row 대응 가능해야 하며, 그 대응 표가 본 doc 이다. KOSMOS 의 어떤 어댑터도 "한국 만의 발명" 이 아니라 4개 reference 중 하나의 한국 적응이라는 것을 증명함으로써, KOSMOS 의 client-side caller 패턴이 국제적으로 통용되는 design 임을 보인다.

## Thesis (English)

KOSMOS positions itself as the **client-side reference implementation for Korea's national AX infrastructure** (AGENTS.md § CORE THESIS). The Korean policy stack — National AI Strategy Committee + Action Plan 2026–2028 + Public AX + Whole-of-Government AI Shared Infrastructure — drives each ministry/agency to expose its own systems as LLM-callable secure-wrapped channels; KOSMOS is the caller invoking those channels on the citizen's behalf. This model is not a Korean invention. Singapore APEX, Estonia X-Road, EU EUDI Wallet, and Japan マイナポータル API are all different implementations of the same thesis. Therefore the KOSMOS adapter catalog should map row-by-row to these four international references, and that mapping is documented below. By proving every KOSMOS adapter has at least one foreign-spec analog, this doc demonstrates that the client-side caller pattern is an internationally established design — not a Korea-only experiment.

## Mapping table

| KOSMOS adapter family / primitive | Singapore APEX [^1] | Estonia X-Road [^2] | EU EUDI Wallet [^3] | Japan マイナポータル API [^4] |
|---|---|---|---|---|
| `verify` primitive (delegation ceremony) | APEX OAuth 2.0 + Singpass NDI | X-Road **MISP** Member Identity Service + eID auth | EUDI Wallet → PID Issuance + Trust Framework | マイナンバーカード認証 (公的個人認証サービス JPKI) |
| `mock_verify_module_modid` (Mobile-ID Module) | Singpass NDI mobile token | mID (eID mobile profile) | EUDI Wallet PID (mobile-bound) | マイナンバーカード スマホ搭載機能 |
| `mock_verify_module_kec` (Corporate certificate) | CorpPass | Riigiportaal eID Corporate | LEI (Legal Entity Identifier) + EUDI corporate wallet | 法人共通認証基盤 (gBizID) |
| `mock_verify_module_geumyung` (Financial certificate) | MyInfo Financial Attribute | X-Road Financial Service Provider | EUDI Wallet Financial Attestation | 金融機関共同認証 (全銀協) |
| `mock_verify_module_simple_auth` (Simple Auth — KFTC) | APEX MyInfo basic | X-Road **AdES-T** Simplified Auth | EUDI Wallet Low Assurance Tier | 公的個人認証サービス 簡易認証 |
| `mock_verify_module_any_id_sso` (SSO IdentityAssertion) | Singpass SSO (no token) | X-Road **TARA** SSO + SAML | EUDI Wallet PID-only (no chained scope) | GBizID SSO (no chained scope) |
| `mock_verify_gongdong_injeungseo` (Joint cert.) | n/a (Singapore retired joint cert) | n/a (Estonia uses ID-card) | EUDI Wallet QSC (Qualified Sig. Certificate) | 公的個人認証サービス JPKI 署名証明書 |
| `mock_verify_geumyung_injeungseo` (KFTC Financial cert.) | MyInfo Banking | n/a | EUDI Wallet QC for Finance | 全銀協 金融認証 |
| `mock_verify_ganpyeon_injeung` (PASS / Kakao / Naver simple auth) | n/a (Singpass-only) | n/a (mID-only) | EUDI Wallet Low Assurance | 民間認証アプリ (LINE, Yahoo!) |
| `mock_verify_mobile_id` (mDL — ISO/IEC 18013-5) | NDI mDL pilot | n/a (Estonia mID supersedes) | EUDI Wallet mDL (ISO/IEC 18013-5 native) | 運転免許証 mDL (警察庁 PoC) |
| `mock_verify_mydata` (KFTC MyData v240930) | MyInfo Open Banking | X-Road Banking Service Provider | EUDI Wallet Open Finance | 全銀協 Open API + 個人金融情報移転 |
| `lookup` primitive (read-only data pull) | APEX MyInfo / Whole-of-Gov data API | X-Road Pull-style data exchange | EUDI Wallet Verifiable Credential Presentation | マイナポータル ぴったりサービス API |
| `submit` primitive (write-transaction) | APEX File Submission API | X-Road Push-style transaction (signed) | EUDI Wallet Verifiable Presentation + Signing | e-Gov 電子申請 / マイナポータル ぴったり申請 |
| Deferred notification/app-push runtime (not an active primitive) | APEX Event Subscription | X-Road MSG queue (asynchronous) | EUDI Wallet Notification Service | 防災行政無線 / Lアラート CBS |
| OPAQUE-forever — hometax-tax-filing | n/a (Singapore IRAS uses APEX) | n/a (EMTA on X-Road) | n/a (national tax authority on EUDI) | e-Tax 国税電子申告 (separate ceremony) |
| OPAQUE-forever — gov24 minwon-submit | n/a (Singapore Whole-of-Gov on APEX) | n/a (riik.ee on X-Road) | n/a (national portal on EUDI) | e-Gov 電子申請 (separate ceremony) |

## Citations

[^1]: **Singapore APEX** — Singapore Government Technology Agency (GovTech) API Exchange platform under the Whole-of-Government Digital Identity (WOG-DID) framework. Singpass NDI National Digital Identity (canonical citizen-facing entry point): https://www.singpass.gov.sg/main . MyInfo / CorpPass partner sites under Singpass umbrella: https://www.singpass.gov.sg/main/individuals/ . CorpPass: https://www.corppass.gov.sg/ . APEX product details (currently behind a region-locked GovTech site at developer.tech.gov.sg — the Singpass main page is the publicly accessible canonical entry).

[^2]: **Estonia X-Road** — Estonian and Finnish governments' shared data exchange layer (operated by NIIS — Nordic Institute for Interoperability Solutions). Canonical doc: https://x-road.global/ . eID + mID: https://www.id.ee/en/ . TARA SSO and broader RIA (Estonian Information System Authority) services: https://www.ria.ee/en .

[^3]: **EU EUDI Wallet** — European Digital Identity Wallet under eIDAS 2.0 (Regulation EU 2024/1183). Architecture and Reference Framework canonical doc: https://eu-digital-identity-wallet.github.io/eudi-doc-architecture-and-reference-framework/ . Source repo (issues + spec PRs): https://github.com/eu-digital-identity-wallet/eudi-doc-architecture-and-reference-framework . European Commission EU Digital Identity Wallet policy page: https://digital-strategy.ec.europa.eu/en/policies/eu-digital-identity-wallet . mDL ISO/IEC 18013-5: https://www.iso.org/standard/69084.html .

[^4]: **Japan マイナポータル API** — マイナポータル (Mynaportal) Open API operated by Cabinet Office Digital Agency (デジタル庁). Citizen-facing portal: https://myna.go.jp/ . Auth flow reference: https://myna.go.jp/SCK0101_03_001/SCK0101_03_001_InitDiscRef.form . デジタル庁 root (マイナンバーカード policy hub): https://www.digital.go.jp/ . gBizID 法人共通認証: https://gbiz-id.go.jp/ .

> **Note on tracking** — Singapore APEX, Estonia X-Road, EU EUDI, and Japan マイナポータル API are all moving targets. URL stability above was verified at the date in the doc header via `probe_policy_links.sh`. If a future link probe fails for any URL, update both the table cell and the citation footnote in the same PR.
