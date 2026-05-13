# 권한 위임 흐름 (Delegation Flow) — UMMAYA One-Stop AX 설계

**Status**: 리서치 산출물 + Mock 아키텍처 설계 (정정됨 2026-04-29 오후)
**Date**: 2026-04-29

> ⚠️ **TRIPLE CORRECTION HISTORY** — 사용자가 세 번 정정. 최종 canonical은 **§12 (3차 정정 final)** 참조.
>
> - **1차 잘못**: UMMAYA-original 권한 시스템 발명 (Spec 033 5-mode 등) → ✅ 삭제 완료 (Wave 1-3)
> - **2차 잘못 (§5-§9)**: UMMAYA가 protocol pioneer로 기관에 새 protocol 제안 → §11에서 정정
> - **2차 정정 (§11)도 부정확**: "기관 시스템 변경 X, browser substitute" 가정이 **국가인공지능전략위원회 정책 timing 무시** → §12에서 final 정정
> - **3차 정정 final (§12)**: UMMAYA = **한국 국가AX 인프라가 만들 LLM-accessible 보안 wrapping 통로의 client-side reference implementation**. 정부 자체 시스템 개편 동력 = 국가AI전략위원회 (2025-09 출범) + 행동계획 2026-2028 (2026-02 확정, 99 과제) + 공공AX 분과 + 범정부 AI 공통기반.
>
> §1-§4 (리서치 발견)는 여전히 유효. §5-§11은 historical, §12가 canonical.

**Trigger**: 사용자 비전 (2026-04-29) — 시민이 hometax.go.kr / gov.kr 직접 접속 안 해도 LLM 대화 한 번으로 행정일 처리. 인증 도메인(간편인증/공동인증서/금융인증서/모바일신분증)은 기존 시스템 그대로 trigger; 행정 도메인(홈택스/정부24)도 기존 web/mobile UX 그대로, 단지 LLM이 시민 대신 navigate.

**Authority**: AGENTS.md § CORE THESIS (도구 래핑 = 작업 단위) + domain-harness-design.md (16-도메인 매트릭스) + cc-source-migration-plan.md (CC 원본 단위 마이그레이션)

---

## 0. 한 문단 결론

UMMAYA의 권한 위임 비전은 **기술적으로 conventional**. OAuth 2.0 + RFC 8693 Token Exchange + OpenID for Verifiable Presentations (OID4VP) + W3C Verifiable Credentials를 정부 도메인에 적용한 것 — Singapore Myinfo, Japan JPKI + マイナポータル API, EU EUDI Wallet (2026-09 출시 예정), UK HMRC MTD가 이미 운영 중. **한국의 blocker는 protocol이 아니라 statutory + agency roadmap**: KOMSCO 모바일 신분증은 wallet을 가지고 있고, 금결원/한국신용정보원은 동의 인프라를 운영하며, 표준은 RFC + W3C로 존재. 누락된 것은 (a) 표준동의서의 action-scope claim, (b) 행정 도메인의 write API, (c) 전자정부법 / 새 행정마이데이터법의 행위위임권 명시화. **UMMAYA의 역할은 이 누락된 protocol surface를 mock으로 byte/shape mirror하여, 정책 입안자와 기관 아키텍트가 만져볼 수 있는 reference artifact를 제공하는 것**. AI Action Plan 2026-2028 §원칙 8 (공공AX) + 디지털플랫폼정부 2025-2027 마스터플랜이 요구하는 정확히 그것.

---

## 1. 권한 위임 가능성 매트릭스 (시간 horizon)

| Horizon | 가능성 | 근거 |
|---|---|---|
| **오늘 (2026)** | ❌ action / ⚠️ read | 어떤 한국 기관도 OAuth2/OIDC bearer token으로 **write** 권한 부여 안 함. 마이데이터는 read-only by design (정보전송요구권 = 읽기). |
| **2-3년 (2028-29)** | 🟡 PROBABLE | 모바일 신분증 VC/VP 작동 + Any-ID federation 시작. 좁은 submit (연말정산 간소화 자료 제출, 민원 발급)부터. AI Action Plan §원칙 8/9 이행 단계. |
| **5년 (2030-31)** | 🟢 LIKELY | 전자정부법 §X 개정 + 본인확인법 §6 carve-out + 공공마이데이터법 통과. Singapore/Japan/Estonia 모두 5-7년 statutory 작업 후 완성. |

---

## 2. 한국 권한 위임 인프라 현실 (R1)

### 2.1 마이데이터 (금융위 / 한국신용정보원 / 금결원 finAuth) — **유일한 production-grade 위임 패턴**

```
[시민]                  [활용기관 = UMMAYA-analog]      [통합인증 = 금결원]      [정보제공자 = 은행]
   │ (1) 가입             │                                 │                      │
   │ ───────────────────►│                                  │                      │
   │                     │ (2) 표준동의서 redirect          │                      │
   │ ◄───────────────────────────────────────────────────►│                       │
   │ (3) 인증+동의 (1년 max)│                              │                      │
   │ ──────────────────────────────────────────────────►│                          │
   │                     │ (4) 인증코드                    │                       │
   │                     │ ◄──────────────────────────────│                       │
   │                     │ (5) Access Token (OAuth2)        │                      │
   │                     │ ◄──────────────────────────────│                       │
   │                     │ (6) 표준 API GET + Bearer        │                      │
   │                     │ ────────────────────────────────────────────────────►│
   │                     │ (7) 정보 응답 (JSON)             │                     │
   │                     │ ◄────────────────────────────────────────────────────│
```

**핵심 속성**:
- **Token issuer**: 금결원 통합인증 (RFC 6749 authorization server)
- **Lifetime**: 90일 access token + 1년 refresh token (신용정보법 시행령 §28-3)
- **Scope**: 표준동의서 = `[기관 × 정보항목 × 목적 × 보유기간]` 매트릭스
- **Audit**: 종합포털 통합인증 로그 + 한국신용정보원 중계기관 호출 로그
- **Revocation**: 정보전송요구 철회 API (신용정보법 §33-2 ④, 의무)

**확장성 평가**:
- ✅ 행안부 **공공마이데이터** (2021-12 launch, 한국지역정보개발원 운영) — 정확히 이 stack을 행정정보 (가족관계증명서, 주민등록등본, 사업자등록증, ~100 항목)에 적용
- ✅ 보건복지부 **의료마이데이터** — 의료데이터 활용 종합계획 2023 pilot
- 📋 **교육마이데이터** — 디지털플랫폼정부 roadmap
- ❌ **action / write 권한 위임은 어떤 마이데이터에도 없음** — 신용정보법 §33-2 자체가 read-scoped
- 📜 **공공마이데이터법(안)** — 행안부 2024 입법예고, NA 통과 대기 중 (2026-04 기준) → action-scope 추가 가능 vehicle

**Verdict**: UMMAYA는 이 envelope를 verbatim mock하면 됨. write extension이 입법되는 순간 UMMAYA의 mock surface는 그대로 적용 가능.

### 2.2 정부 통합인증 (Any-ID) — SSO이지 delegation 아님

- 디지털원패스 (2018-2025-12-30 종료) → Any-ID (2026-01 launch)
- **Browser session-stamping**, OAuth2 bearer 토큰 발급 X
- "한 번 인증하면 gov.kr 산하 사이트에 로그인 유지" — 시민 대상 SSO
- **OIDC identity-assertion side는 가능** ("이 사람이 홍길동이다")
- **API-authorization side는 per-agency, 정의되지 않음**
- UMMAYA가 필요한 token endpoint (`scope=send:hometax.tax-return`) — **부재**

**Verdict**: Any-ID에 RFC 8693 Token Exchange 추가가 필요. 1-2년 정책 작업.

### 2.3 모바일 신분증 (KOMSCO DID-based VC/VP) — **architecturally cleanest**

- W3C Verifiable Credentials Data Model 1.1 stack (2022-)
- DIDComm-style presentation requests
- 2022 모바일 운전면허증, 2024 모바일 주민등록증 발급 중

```
[UMMAYA RP]                [시민 wallet = 모바일신분증 앱]       [Issuer = 행안부/KOMSCO]
   │ (1) Presentation Request                  │                              │
   │   {credential_type, claims, purpose}      │                              │
   │ ─────────────────────────────────────────►│                              │
   │                                           │ (2) Citizen confirms +       │
   │                                           │     biometric unlock         │
   │ (3) Verifiable Presentation               │                              │
   │     (signed by citizen DID key)           │                              │
   │ ◄─────────────────────────────────────────│                              │
   │ (4) Verify against issuer DID                                            │
   │ ─────────────────────────────────────────────────────────────────────────►
   │ (5) DID-doc + revocation status                                          │
   │ ◄─────────────────────────────────────────────────────────────────────── │
```

**Critical extensibility**: VP는 임의의 signed claim을 carry 가능. 만약 국세청이 `TaxReturnAuthorizationCredential` VC type을 issue하면, 시민은 UMMAYA에게 그것을 present → UMMAYA가 그 VP의 audit anchor로 신고 — **이게 정확히 OID4VP (draft 21) 패턴**.

**Today's blocker**: action authorization VC type을 issue하는 기관 부재. 현재 identity VC만 (license, 주민증).

**Verdict**: KOMSCO + 국세청이 협력하면 6개월 안에 pilot 가능. EU EUDI ARF v1.4.0 ("PID + QEAA")에 이미 architecturally 존재.

### 2.4 간편인증 (NTS oacx) — **API delegation 불가**

- 카카오페이 / PASS / 네이버 / 토스 / KB / 삼성패스 / 카카오뱅크 / 페이코
- Phone-app ceremony — push notification + PIN/biometric → hometax 세션 upgrade
- **Server-to-server SAML-like assertion** (provider ↔ 한국정보인증/코스콤 federation hub) → hometax session cookie
- **third-party app에 bearer 토큰 발급 X**
- UMMAYA Confidential Client가 assertion replay 불가

**Verdict**: 간편인증은 UMMAYA delegation primitive로 사용 불가. provider가 OAuth2 client-credentials + token-exchange endpoint를 expose 해야 함 (현재 X).

### 2.5 금융결제원 yessign — **document-bound, not scope-bound**

- 전자서명법 (2020-12 전면개정) framework
- 서명생성: 시민 private key가 document hash 서명
- 서명검증 API: server가 signature + document → finAuth가 valid/invalid + signer identity

**할 수 없는 것**: "이 서명은 principal X가 시민 Z를 위해 N분 동안 API Y를 호출할 수 있도록 권한 부여"라는 형태의 bearer 토큰 발급. 서명은 forensically **specific document blob에 bound**, **delegation scope에 bound 아님**.

**아키텍처 노트**: JWT 의미론 없이 JWS만 — `iss`, `aud`, `exp`, `scope` 부재. Primitive 일 뿐 protocol 아님.

**Verdict**: yessign 그대로는 unsuitable. JWT-shaped wrapper가 필요한데 그건 새 표준.

---

## 3. 국제 비교 (R2)

### 3.1 Singapore Myinfo — **Gold standard, UMMAYA가 가장 가까이 학습할 것**

```
[Business app]              [SingPass IdP]            [Myinfo API]
   │ /authorize?scope=name,nric,uinfin&purpose=loan_app │
   │ ─────────────────────────────────────────────────►  │
   │ (citizen authenticates + per-claim consent)         │
   │ authorization_code                                  │
   │ ◄────────────────────────────────────────────────── │
   │ /token (PKCE) → access_token (purpose-bound)        │
   │ ◄─────────────────────────────────────────────────  │
   │ GET /person/{uinfin}/?attributes=...                │
   │ ───────────────────────────────────────────────────────────────►
   │ Signed + encrypted JWE/JWS payload                              │
   │ ◄───────────────────────────────────────────────────────────────
```

**Singapore-distinct property**: Myinfo Business + APEX는 **write-back** 지원 (예: GST registration auto-fill submission via Form-Filling API). **이게 정부 scope에서 production하는 유일한 large-scale delegation-write 시스템**.

### 3.2 Japan JPKI + マイナポータル API — **문화·규제 측면 가장 가까운 analog**

```
[App]──사인 요청──►[マイナンバーカード] ─PIN─► JWS 서명
   │ JPKI 検証サービス → valid + identity
   ▼
[マイナポータル API] ─JPKI assertion 첨부─► 税情報照会, 年金照会, 確定申告連携
```

- 2017년 launch, 2023-2024 50+ endpoints로 확장
- **AI agent → JPKI 서명 → API → action**을 effectively 합법화
- 단점: 시민이 each action마다 카드를 물리적으로 tap (long-lived bearer token 없음)

### 3.3 EU EUDI Wallet — **2026-09 launch, UMMAYA와 architecturally 동일**

- Regulation EU 2024/1183 (eIDAS 2.0)
- OID4VC/OID4VP + mDL (ISO/IEC 18013-5) + W3C VC
- PID (Person Identification Data) + QEAA (Qualified Electronic Attestation of Attributes)
- Levels Low / Substantial / High → action class mapping
- **EU는 정확히 UMMAYA 비전을 union scale로 진행 중**

### 3.4 UK HMRC Making Tax Digital — **production OAuth2 delegation for 세무**

```
[Tax SaaS] ──/authorize?scope=write:vat──► [GOV.UK One Login]
   │ access_token (HMRC issued, scoped)
   ▼
[HMRC MTD API] /vat/returns + Bearer ──filing executed
```

- VAT-filing SaaS가 access_token 받아 HMRC API에 신고
- **이게 production에서 가장 가까운 UMMAYA-vision 시스템**

---

## 4. 한국 법적 blocker 정밀 (R3)

### 4.1 세무사법 §2 (세무대리)

```
세무사법 §2: 세무대리 = 세무사·공인회계사·세무대리인 등록자만 가능
세무사법 §22: 무자격 세무대리는 형사처벌

§2 ② carve-out: 본인이 직접 작성한 신고서를 단순 전산입력 대행하는
                 행위는 세무대리에 해당하지 않음 ★★★
```

**UMMAYA의 frame**: "시민 본인이 작성한 신고서를 UMMAYA가 단순 전송" — §2 ② carve-out 적용 가능. 단 judicial test 안 됨 → 법무 검토 필수.

### 4.2 본인확인법 (정보통신망법 §23-3)

- 본인확인기관 designation은 KOMSCO, 한국정보인증, 금결원, 코스콤 등에 한정
- UMMAYA는 자체 본인확인 수행 X
- **반드시 designated 본인확인기관에 의존** (verify primitive를 통해)

### 4.3 전자서명법 §3 ② — **가장 깨끗한 legal path**

```
전자서명법 §3 ②: 전자서명의 효력 — 시민의 전자서명은 서명자 동일성 효력
```

**해석**: UMMAYA가 시민-side 서명 ceremony를 trigger하면 (KOMSCO 모바일 신분증 통해), 서명된 payload는 **legally 시민-originated**. UMMAYA 자체는 서명 X, ceremony trigger만.

### Verdict

UMMAYA 운영 방침:
1. ✅ 시민-side signature ceremony만 trigger (자체 서명 X)
2. ✅ 모든 신고를 "citizen-authored return transmission"으로 frame (세무사법 §2 ② carve-out)
3. ✅ designated 본인확인기관에만 통합 (KOMSCO/한국정보인증/금결원/코스콤)

---

## 5. UMMAYA 권한 위임 Mock 아키텍처

### 5.1 Mock의 목적 재정의

기존 mock은 단순히 "fixture replay" — 응답 envelope를 흉내. **새 mock은 protocol surface 전체를 실 표준에 맞게 byte/shape mirror** — 정책 입안자 + 기관 아키텍트가 manipulate해서 "이게 진짜 작동하면 어떻게 보이는가"를 검증할 수 있는 reference artifact.

### 5.2 Mock primitives 매핑

| Primitive | Real-world counterpart | Mock 구현 |
|---|---|---|
| `verify(method="modid_vp", ...)` | KOMSCO OID4VP-style VP request | `mock_verify_modid_vp.py` — fake VP envelope `{vp_jwt, delegation_token, exp}` |
| `verify(method="mydata_consent", ...)` | 마이데이터 표준동의서 + 접근토큰 | `mock_verify_mydata_consent.py` — OAuth2 authorization_code flow + access_token |
| `submit(target, auth=token, ...)` | 가상 OPAQUE 행정 도메인 write API | `mock_submit_hometax_taxreturn.py`, `mock_submit_gov24_minwon.py` — token 검증 + 가짜 접수번호 |
| `lookup(...)` | 기존 마이데이터 표준 API GET | 기존 KMA/KOROAD/HIRA/NMC 등 그대로 |

### 5.3 권한 위임 mock flow 예시

**시나리오**: 시민이 "내 종합소득세 신고해줘" 요청 → UMMAYA 한 turn으로 처리

```
[시민]──"종합소득세 신고해줘"──►[UMMAYA LLM]
                                 │
                                 │ (1) 세무신고 = submit class 인지
                                 │     OPAQUE 도메인이므로 verify 선행 필요
                                 ▼
                            tool_call: verify(
                              method="modid_vp",
                              scope="send:hometax.tax-return",
                              purpose="2024 귀속 종합소득세 신고",
                              expires_at_max="+24h"
                            )
                                 │
                                 ▼
                          [mock_verify_modid_vp adapter]
                                 │ (2) Presentation Request emit
                                 ▼
                          [TUI shows]: "모바일신분증 앱에서 확인해주세요"
                                 │     (시뮬레이션: 자동 timer 3초 후 자동 confirm)
                                 ▼
                          [Mock returns delegation_token]:
                            {
                              "vp_jwt": "eyJhbGc...",
                              "delegation_token": "del_abc123",
                              "scope": "send:hometax.tax-return",
                              "expires_at": "2026-04-30T...",
                              "issuer_did": "did:web:mobileid.go.kr",
                              "_mode": "mock"
                            }
                                 │
                                 ▼
                            [LLM stores token in context]
                            tool_call: lookup(
                              tool_id="hometax_tax_simplified_data",  ← 가상 endpoint
                              params={"year": 2024},
                              auth=delegation_token
                            )
                                 │
                                 ▼
                          [mock_lookup_hometax_simplified adapter]
                                 │ token verify → fake 간소화 자료 반환
                                 │   {수입금액, 공제항목, ...}
                                 ▼
                            [LLM analyzes data + composes return]
                            tool_call: submit(
                              tool_id="mock_submit_hometax_taxreturn",
                              params={...신고내용...},
                              auth=delegation_token
                            )
                                 │
                                 ▼
                          [mock_submit_hometax_taxreturn adapter]
                                 │ (3) token + scope 검증
                                 │ (4) "처리됨" + 가짜 접수번호 발급
                                 │ (5) 영수증 ledger entry
                                 ▼
                          {
                            "status": "submitted",
                            "receipt_id": "hometax-2026-04-30-XXXX",
                            "delegation_token_used": "del_abc123",
                            "_mode": "mock"
                          }
                                 │
                                 ▼
                            [LLM 시민에게]: "신고 완료되었습니다.
                                            접수번호: hometax-2026-04-30-XXXX"
```

**핵심 invariant**:
1. ⏱️ **One biometric tap** at step (2) — 마이데이터/Singapore Myinfo와 동일
2. 📜 **Three-way reconcilable audit**: UMMAYA memdir + KOMSCO ledger + 행정 도메인 ledger (모두 mock에서도 logging)
3. 🎯 **Purpose-bound token** — `scope=send:hometax.tax-return` 외 호출 시 거부
4. ⏰ **Short-lived** — 24h max, 단발 action용
5. 🔄 **Revocable** — `/consent revoke <token>` 슬래시 명령어
6. 📌 **Transparent**: 모든 응답에 `_mode: "mock"` field — 시민/LLM 모두 mock 인지

### 5.4 신규 Mock 어댑터 작성 (Phase ε 후속)

| 어댑터 | Domain | Grade | LOC | 우선순위 |
|---|---|---|---|---|
| `mock_verify_modid_vp` | KOMSCO 모바일신분증 OID4VP | 4 (shape-mirror) | ~150 | High — 원본 patternw |
| `mock_verify_mydata_consent` | 마이데이터 표준동의서 OAuth2 | 5 (byte-mirror) | ~200 | High — 유일한 prod-grade analog |
| `mock_submit_hometax_taxreturn` | 가상 홈택스 신고 endpoint | 3 (spec-mirror) | ~100 | Medium — vision artifact |
| `mock_submit_gov24_minwon` | 가상 정부24 민원 제출 | 3 (spec-mirror) | ~100 | Medium |
| `mock_lookup_hometax_simplified` | 가상 홈택스 간소화 조회 | 3 (spec-mirror) | ~100 | Medium |
| `mock_lookup_mydata_account` | 마이데이터 계좌 조회 | 5 (byte-mirror) | ~80 | Low — 이미 mydata_application 존재 |

### 5.5 기존 mock 삭제 / 수정

- ❌ `mock_verify_digital_onepass` — 서비스 종료 2025-12-30
- ➕ `mock_verify_any_id_sso` — Any-ID 후속 stub (SSO only, delegation X)
- 🔄 `mock_traffic_fine_pay_v1`, `mock_welfare_application_submit_v1` — `delegation_token` 받도록 schema 확장

### 5.6 Pydantic schema (신규)

```python
# src/ummaya/primitives/delegation.py
from pydantic import BaseModel, Field
from datetime import datetime

class DelegationToken(BaseModel):
    """OID4VP-style delegation token issued by verify primitive."""
    model_config = {"frozen": True}

    vp_jwt: str = Field(description="Verifiable Presentation as JWS")
    delegation_token: str = Field(description="Opaque token for submit primitive")
    scope: str = Field(description="purpose-bound scope, e.g. 'send:hometax.tax-return'")
    issuer_did: str = Field(description="Identity issuer DID, e.g. 'did:web:mobileid.go.kr'")
    issued_at: datetime
    expires_at: datetime
    _mode: str = Field(default="mock")

class DelegationContext(BaseModel):
    """Passed from verify → submit through LLM context."""
    model_config = {"frozen": True}

    token: DelegationToken
    citizen_did: str | None = None  # 시민 측 DID (VP signer)
    purpose_ko: str
    purpose_en: str
```

### 5.7 영수증 ledger 통합 (Spec 035 reuse)

위임 token의 issuance + use + revocation은 모두 `~/.ummaya/memdir/user/consent/` JSONL ledger에 append. Format:

```jsonl
{"ts":"2026-04-29T10:00:00Z","kind":"delegation_issued","token":"del_abc123","scope":"send:hometax.tax-return","expires_at":"2026-04-30T10:00:00Z","issuer":"did:web:mobileid.go.kr","_mode":"mock"}
{"ts":"2026-04-29T10:00:15Z","kind":"delegation_used","token":"del_abc123","tool_id":"mock_lookup_hometax_simplified"}
{"ts":"2026-04-29T10:00:30Z","kind":"delegation_used","token":"del_abc123","tool_id":"mock_submit_hometax_taxreturn","receipt_id":"hometax-2026-04-30-XXXX"}
{"ts":"2026-04-29T11:00:00Z","kind":"delegation_revoked","token":"del_abc123","reason":"citizen_request"}
```

---

## 6. 표준 매핑 (R5 결론)

| Standard | UMMAYA 채택 | 한국 채택 |
|---|---|---|
| OAuth 2.0 (RFC 6749) | ✅ verify/submit base | ✅ 마이데이터 |
| **OAuth 2.0 Token Exchange (RFC 8693)** | ✅ verify→submit token swap | ❌ 미채택 (UMMAYA pilot의 핵심 추가) |
| OpenID Connect Core | ✅ identity assertion | ⚠️ Any-ID 부분 |
| OpenID for Identity Assurance (OIDC4IDA) | ✅ verified_claims | ❌ 미채택 |
| **OID4VP (OpenID for Verifiable Presentations)** | ✅ KOMSCO mock의 base | 🟡 KOMSCO 내부만 |
| **OID4VCI (OpenID for VC Issuance)** | ✅ 가상 행정 VC issuance mock | 🟡 KOMSCO 진화 방향 |
| W3C VC Data Model 1.1 | ✅ VC schema | ✅ KOMSCO |
| mDL (ISO/IEC 18013-5) | ✅ 모바일 운전면허증 mock | ✅ 운영 중 |
| PKCE (RFC 7636) | ✅ mobile flow | ✅ 마이데이터 모바일 |
| 한국형 ZeroTrust 1.0/2.0 | ✅ Spec 024/035 정합 | ✅ 행안부 산하 의무 |

**Critical 누락 (UMMAYA pilot이 demonstrate)**:
1. **RFC 8693 Token Exchange** — KOMSCO VP를 홈택스 action-scope token으로 swap (시민이 두 번 인증 안 해도 되도록)
2. **OIDC4IDA verified_claims** — 마이데이터 표준동의서보다 풍부한 claim semantics
3. **공개 OID4VP RP-facing spec** — KOMSCO가 internal만 사용, public spec 부재

---

## 7. 기관 제안 전략

### 7.1 Primary target: 국세청 (NTS)

**이유**:
- 종합소득세 / 연말정산 = 시민 pain density 최고
- 홈택스 OpenAPI v2 이미 운영 (간소화자료 제출 via 세무대리인)
- 세무대리인 ERP 통합 케이스 = UMMAYA pattern과 가장 유사

**제안 angle**:
> "마이데이터 표준 extension pilot — 종합소득세 신고를 UMMAYA가 활용기관으로, KOMSCO 모바일신분증 VP를 delegation grant로 사용하는 reference implementation"

### 7.2 Secondary target: 행정안전부 디지털정부국 (공공마이데이터 운영주관)

**이유**:
- 공공마이데이터 framework이 statutory home for 행위위임 extension
- 디지털플랫폼정부 마스터플랜 2025-2027 Phase 2 (2026 H2) "AI 기반 선제적 행정서비스" — UMMAYA가 정확히 그 reference

**제안 angle**:
> "공공마이데이터 표준동의서 확장 — action-scope claim 추가, UMMAYA가 reference open-source 활용기관 client로 LLM-mediated 위임의 안전성 demonstrate"

### 7.3 대화 hook (양 기관 공통)

```
디지털플랫폼정부 2025-2027 마스터플랜 §AI 기반 선제적 행정서비스
+ AI Action Plan 2026-2028 §원칙 8 (공공AX) + §원칙 9 (시민AX)
= 2027 milestone 이전에 reference implementation이 필요
= UMMAYA가 그 missing piece (학부생 student project + Apache-2.0 + 즉시 audit 가능)
```

### 7.4 절대 하지 말 것

- ❌ 간편인증 통합 시도 — session-stamping이 agentic loop과 incompatible
- ❌ yessign 서명을 long-lived token으로 저장 — document-bound, scope-bound 아님
- ❌ UMMAYA를 "세무대리 서비스"로 pitch — frame은 "citizen-authored return transmission" (세무사법 §2 ② carve-out)
- ❌ Any-ID가 bearer token 발급한다고 가정 — identity SSO만, API authorization 아님

---

## 8. 실행 sequence (구체)

### Phase ε.1 — Mock primitives 신설 (2 sprints)

| Task | 산출물 | 의존 |
|---|---|---|
| ε.1-1 | `src/ummaya/primitives/delegation.py` (DelegationToken + DelegationContext Pydantic 모델) | — |
| ε.1-2 | `src/ummaya/tools/mock/verify_modid_vp.py` (KOMSCO OID4VP shape-mirror) | ε.1-1 |
| ε.1-3 | `src/ummaya/tools/mock/verify_mydata_consent.py` (마이데이터 OAuth2 byte-mirror) | ε.1-1 |
| ε.1-4 | `src/ummaya/tools/mock/submit_hometax_taxreturn.py` (가상 홈택스 endpoint) | ε.1-1 |
| ε.1-5 | `src/ummaya/tools/mock/submit_gov24_minwon.py` (가상 정부24 endpoint) | ε.1-1 |
| ε.1-6 | `src/ummaya/tools/mock/lookup_hometax_simplified.py` (가상 간소화 조회) | ε.1-1 |
| ε.1-7 | Spec 035 ledger에 delegation_issued / used / revoked 이벤트 추가 | — |
| ε.1-8 | `/consent revoke <token>` 슬래시 명령어 | ε.1-7 |

### Phase ε.2 — End-to-end smoke (1 sprint)

| Task | 산출물 |
|---|---|
| ε.2-1 | PTY scenario script: 시민 "종합소득세 신고해줘" → verify → lookup → submit → 접수번호 |
| ε.2-2 | E2E test: bun test + uv pytest 통과 |
| ε.2-3 | Vision demo gif (ummaya-migration-tree § L1-A 4-tier OTEL trace 포함) |

### Phase ε.3 — 기관 제안 패키지 (1 sprint)

| Task | 산출물 |
|---|---|
| ε.3-1 | `proposals/nts-mydata-pilot.md` — 국세청 마이데이터 extension 제안 (한국어 공문 + 영문 spec) |
| ε.3-2 | `proposals/mois-public-mydata-action-scope.md` — 행안부 공공마이데이터 행위위임 제안 |
| ε.3-3 | machine-readable spec — `proposals/mydata-action-scope.openapi.yaml` (OpenAPI 3.1) |
| ε.3-4 | `proposals/komsco-oid4vp-rp-spec.md` — KOMSCO 모바일신분증 RP-facing OID4VP spec 제안 |

---

## 9. 리스크 및 완화

| 리스크 | 완화책 |
|---|---|
| 기관 제안 실패 — "학부생 프로젝트가 무슨 권한으로?" | demo가 즉시 작동 + apache-2.0 오픈소스 + AI Action Plan §원칙 8 인용. 정책 바람을 타고 들어감. |
| 세무대리 위반 우려 | 세무사법 §2 ② carve-out 명시, 모든 신고를 "시민 작성 return의 단순 전송"으로 frame. 법무 검토 의무. |
| Mock이 너무 단순해 정책 입안자에게 비현실적 | byte-mirror grade-5 (마이데이터)와 spec-mirror grade-3 (가상 endpoint) 명확히 구분. proposal 패키지에 양 grade 모두 포함. |
| KOMSCO가 OID4VP RP-facing spec 비공개 유지 | UMMAYA pilot이 정확히 그 압력 (open-source RP가 spec 요구) — 정책적으로 의미 있는 leverage. |
| `delegation_token`이 LLM context에 leak | system prompt rule: token을 시민에게 echo 금지. memdir에만 저장, conversation 표면에 show 안 함. |
| 5년 horizon — 우리가 그 때까지 UMMAYA 유지? | KSC 2026 + 졸업 후에도 student maintainer 풀 유지 가능 (Apache-2.0 + plugin DX = 외부 기여 받기 쉬움). |

---

## 10. 근거 (citations)

(domain-harness-design.md §8 참조 + 추가)

- 신용정보법 §33-2 (정보전송요구권) — 마이데이터 statutory base
- 금융분야 마이데이터 기술 가이드라인 v2.0 (금융보안원, 2022-01)
- 발달자 공공마이데이터 포털 https://www.mydatagov.go.kr
- 행안부 공공마이데이터 추진계획 (2021-12)
- 디지털원패스 종료 + Any-ID 전환 안내 (행안부 2025-12-29)
- KOMSCO Mobile ID Developer Guide v1.2 https://www.mobileid.go.kr
- W3C Verifiable Credentials Data Model 1.1 https://www.w3.org/TR/vc-data-model/
- OpenID for Verifiable Presentations draft 21 https://openid.net/specs/openid-4-verifiable-presentations-1_0.html
- 전자서명법 (법률 제17354호, 2020-12-10 시행) §3 ②
- 세무사법 §2 ② (단순 전산입력 대행 carve-out)
- 정보통신망법 §23-3 (본인확인기관 지정)
- Singapore Myinfo + APEX https://api.singpass.gov.sg
- Japan JPKI https://www.jpki.go.jp + マイナポータル API https://api.myna.go.jp
- Regulation EU 2024/1183 (eIDAS 2.0)
- EUDI ARF v1.4.0 https://github.com/eu-digital-identity-wallet/eudi-doc-architecture-and-reference-framework
- HMRC Making Tax Digital API https://developer.service.hmrc.gov.uk
- RFC 8693 OAuth 2.0 Token Exchange https://datatracker.ietf.org/doc/html/rfc8693
- OIDC for Identity Assurance 1.0 https://openid.net/specs/openid-connect-4-identity-assurance-1_0.html
- ISO/IEC 18013-5:2021 mDL
- 디지털플랫폼정부 마스터플랜 2025-2027 https://www.dpg.go.kr
- AI Action Plan 2026-2028 (과기정통부 + 디지털플랫폼정부위원회, 2025-12)
- 공공마이데이터법(안) (행안부 2024 입법예고)
- 한국형 ZeroTrust 가이드라인 1.0/2.0 (KISA)

---

## 11. (SUPERSEDED) Browser-Substitute Harness — see §12 for the canonical 3rd correction

### 11.1 핵심 차이

| §5-§9 (이전, 잘못 이해) | §11 (정정, 사용자 진짜 의도) |
|---|---|
| UMMAYA가 새 protocol 제안 (RFC 8693, OID4VP RP spec 등) | UMMAYA는 기존 도메인 시스템 변경 요청 X |
| 기관에 "이렇게 API 공개하세요" 공문 발송 | 기관 시스템 변경 요청 X |
| Bearer token으로 행정 API 직접 호출 | LLM이 시민 대신 기존 web/mobile UX navigate |
| OPAQUE 도메인이 UMMAYA에 protocol 풀어줘야 작동 | OPAQUE 도메인은 그대로 OPAQUE — LLM이 시민처럼 navigate |
| AX = "기관이 변하면 가능" | AX = "오늘 바로 가능, LLM이 시민의 hands and eyes 역할" |

### 11.2 정정된 architecture

UMMAYA의 진짜 모델은 **agentic browser substitute**:

```
[시민] ──"종합소득세 신고해줘"──► [UMMAYA LLM]
                                    │
                                    │ (1) 신고 절차 인지 → hometax.go.kr 필요
                                    │
                                    │ (2) verify primitive: 기존 간편인증 흐름 trigger
                                    ▼
                            [mock/live verify_kakao_simple_auth]
                                    │
                                    │ "카카오페이 앱에서 푸시 확인해주세요"
                                    │
                                    │ (3) 시민 모바일에 푸시 → 시민 본인인증
                                    ▼
                            [hometax 세션/쿠키 발급] (기존 시스템 그대로)
                                    │
                                    │ (4) submit primitive: 받은 세션으로 navigate
                                    ▼
                            [mock/live navigate_hometax_taxreturn]
                                    │
                                    │ [Live] Playwright로 hometax form 자동 작성·제출
                                    │ [Mock] fixture로 가짜 신고·접수번호
                                    ▼
                            [LLM에게 접수번호 전달]
                                    │
                                    ▼
                            [시민에게] "신고 완료. 접수번호: hometax-2026-04-30-XXXX"
```

**핵심**:
- 인증 도메인 (간편인증/공동/금융/모바일신분증) — **기존 시스템 그대로 trigger**, 시민이 평소 hometax에서 쓰던 방식과 동일
- 행정 도메인 (홈택스/정부24) — **기존 web/mobile UX 그대로**, LLM이 시민처럼 navigate
- Mock의 역할 — "기존 interaction surface의 mirror" (새 protocol 흉내 X)
- 시민 입장 — hometax 직접 접속 X, LLM 대화만으로 일 처리

### 11.3 비교 reference

이건 다음과 같은 패턴들의 **한국 정부 도메인 버전**:
- **Anthropic Claude for Computer Use** (2024-) — LLM이 시민의 desktop browser를 통제
- **OpenAI Operator** (2025-) — LLM이 web sites navigate해서 task 수행
- **Google Project Mariner** (2024-) — Gemini가 Chrome으로 web action 수행
- **Adept ACT-1** — agent web automation

UMMAYA = 위 패턴들이지만 한국 정부 도메인 + 한국어 시민 + 5-primitive 표면.

### 11.4 정정된 mock 어댑터 (Phase ε.1 재작성)

이전 §5.4의 mock 정의를 다음으로 교체:

| 어댑터 | 역할 | mock 내용 |
|---|---|---|
| `mock_verify_kakao_simple_auth` | 카카오페이 간편인증 | push 알림 시뮬레이션 → 3초 후 confirm → hometax-style 세션 cookie 반환 |
| `mock_verify_pass_simple_auth` | PASS 간편인증 | 〃 |
| `mock_verify_naver_simple_auth` | 네이버 간편인증 | 〃 |
| `mock_verify_modid_app` | 모바일신분증 앱 | KOMSCO 앱 push → biometric → DID/VC presentation |
| `mock_verify_kec_certificate` | 공동인증서 (KEC) | 인증서 패스워드 prompt 시뮬레이션 → 서명 |
| `mock_verify_geumyung_certificate` | 금융인증서 | yessign cloud 인증서 시뮬레이션 |
| `mock_navigate_hometax_taxreturn` | 홈택스 종합소득세 신고 navigation | form fill 시뮬레이션 → 가짜 접수번호 |
| `mock_navigate_hometax_simplified_view` | 홈택스 간소화자료 조회 | 가짜 자료 fixture |
| `mock_navigate_gov24_minwon_apply` | 정부24 민원 신청 | form fill → 가짜 접수번호 |
| `mock_navigate_gov24_certificate_issue` | 정부24 등본/초본 발급 | PDF fixture 반환 |

**모든 mock에 공통**:
- `_mode: "mock"` 투명성 필드
- `_existing_system: true` — 기존 시스템 navigate 시뮬레이션임을 명시
- `_real_navigation_url`: 실제 시민이 직접 접속한다면 갈 URL (e.g., `https://www.hometax.go.kr/...`)
- 세션/쿠키/토큰 형태는 **각 도메인이 실제로 발급하는 형태**를 mirror

### 11.5 정정된 production 경로

mock → live 전환 시 두 가지 옵션:

**Option A: Browser automation (Playwright/Puppeteer)**
- UMMAYA Python 백엔드에 `playwright` 의존성 추가 (단, AGENTS.md hard rule "신규 runtime 의존성 0" 검토 필요)
- 각 어댑터가 Playwright로 hometax/gov24 navigate
- 인증 ceremony는 시민 모바일에서 (push 확인)
- 위험: 정부 site의 anti-bot 측정, 학부생 권한으로 충분한지

**Option B: Mobile companion app pattern**
- UMMAYA가 시민의 모바일 인증 결과를 통해 세션 발급받음
- 행정 도메인은 UMMAYA의 모바일 SDK 또는 deep link로 호출
- 이 경우 Browser automation 없이 가능
- 위험: 도메인이 mobile SDK 공개 안 함 (대부분 hometax/gov24가 자체 앱만)

**Option C: 끝까지 mock 유지 (가장 안전)**
- UMMAYA는 demo + reference implementation으로 가동
- "이런 식으로 LLM이 행정 일처리 가능합니다"의 살아있는 example
- 실 production은 (a) 정부 partnership, (b) 졸업 후 startup, (c) 별도 epic

**Verdict**: 학부생 단계에서는 **Option C** — mock으로 흐름 demo, 졸업 후 startup/partnership 가능성 열어두기.

### 11.6 정정된 기관 제안 메시지 (이전 §7 정정)

이전 §7의 "API 공개해주세요" 제안은 사용자 비전과 맞지 않음. 정정된 메시지:

> **이런 UMMAYA 방향성은 기관에 변경 요청 X**. 시민이 hometax 직접 접속하던 것을 LLM 대화로 대체하는 것. 만약 기관과 협력할 수 있다면 단지 "테스트 계정 / API 키 / dev sandbox 접근"만 요청 — 그 외 기관 시스템 변경 X.

기관 제안의 본질은:
1. 학부생 UMMAYA demo 보여주기 (browser automation으로 작동하는 것)
2. "정부24 dev sandbox 접근권 주세요" — 기존 sandbox에 UMMAYA 연결
3. 기존 시스템 변경 요청 0건

### 11.7 결론 — 정정된 UMMAYA 정체성

UMMAYA = **시민의 web browser를 대신 운영하는 LLM agent + 한국어 + 한국 정부 도메인 specialized**.

- 시민 입장: hometax/gov24 안 들어가도 LLM 대화로 일 처리
- 기관 입장: 기존 시스템 변경 0건 — UMMAYA는 그냥 시민이 평소 하던 일을 자동화
- 학부생 입장: AGENTS.md § CORE THESIS와 정합 — "각 기관 API/UX 1개를 도구 1개로 래핑". 단 "API"는 좁게는 REST API, 넓게는 web UX flow.
- Mock 역할: 기존 interaction surface의 byte/shape mirror. 새 protocol 발명 X.

**현실 점수 (정정)**:
- 오늘 바로 가능한가? — Mock 흐름은 즉시 가능. Live 흐름은 Playwright + 정부 site anti-bot 작업 필요.
- 학부생 권한으로 — Mock 흐름 + demo. Live는 졸업 후 / startup / partnership.
- 핵심 — UMMAYA는 protocol pioneer가 아니라 **LLM agent productization** project.

이게 사용자 vision과 정확히 일치 — "기존 시스템 그대로, LLM이 시민 대신 navigate".

---

## 12. (FINAL CANONICAL) AX Infrastructure Caller — 사용자 3차 정정 2026-04-29 저녁

### 12.1 사용자 정정 원문

> "컴퓨터 use나 모바일use가 아니라 기존 도메인에서 사용중인 내부 api들이 있을거야 cli가 있을수도 잇고 sdk일수도 있고 하지만 그건 공개되어있지 않고 권한도 없어 하지만 이번에 국가인공지능전략위원회에서 ax 인프라 발표를 해서 국기기관에서 ax를 위해 대대적인 시스템 개편을 하거야 따라서 공개하지않던 내부 api나 sdk를 전체적으로 공개는 안하지만 일부 보안레이어로 랩핑해서 llm이 접근할 통로를 만들면 ax가 가능하잖아 물론 기존의 인증서비스들도 똑같아 사용하겠지 인증서비스들도 llm이 rest처럼 호출하듯이 모듈을 호출할수있게 시스템개편을 하면 내가 말했던 ax 행정 인프라가 완성되잖아"

### 12.2 정정의 필연성 — §11이 또 부정확했던 이유

§11 ("Browser substitute") 가정 = "기관 시스템은 절대 변하지 않는다 → UMMAYA는 시민의 web browser를 대신 운영". 이건 정책 timing 무시. **국가인공지능전략위원회가 2025-09-08 출범** + **인공지능 행동계획 2026-2028이 2026-02-24 확정 (99 과제, 326 권고)** + **공공AX 분과 + 범정부 AI 공통기반 (2025-11~)** = 한국 정부가 **이미 시스템 개편 중**. 따라서 UMMAYA는 browser-side scraper가 아니라 **국가 AX 인프라가 만들 LLM-accessible 보안 wrapping 통로의 client-side reference implementation**.

### 12.3 정정 매트릭스 — 1차 → 2차 → 3차

| 차원 | 1차 (이전 잘못) | 2차 ("browser substitute") | **3차 (FINAL CANONICAL)** |
|---|---|---|---|
| 기관 변경 | UMMAYA가 새 protocol 제안 → 기관에 공문 | 기관 시스템 변경 X | **기관이 자체적으로 시스템 개편 (국가AX 인프라 정책 동력). UMMAYA는 caller** |
| UMMAYA 역할 | Protocol pioneer | Browser/Mobile use agent | **AX 인프라 client-side reference implementation** |
| Mock 의미 | 미래 새 protocol mirror | 기존 web/mobile UX mirror | **국가AX 보안 wrapping 통로의 reference shape** |
| 호출 방식 | Bearer token으로 행정 API 직접 | Playwright/browser-automation | **LLM이 REST처럼 호출 (보안 레이어 뒤의 SDK/모듈)** |
| 인증 도메인 | OID4VP RP spec 제안 | 기존 시스템 push 알림 trigger | **인증 서비스도 LLM-callable 모듈로 시스템 개편 — UMMAYA는 그것 호출** |
| 정책 hook | 학부생이 정책 입안자에 제안 | 정책 무관 demo | **국가인공지능전략위원회·DPG·공공AX의 reference impl** |

### 12.4 진짜 UMMAYA architecture (FINAL)

```
[국가 AX 인프라 (정책)]
  국가인공지능전략위원회 + DPG + 행안부 + 과기정통부
  → 각 기관(홈택스/정부24/...)이 내부 API/SDK를
     보안 레이어 (OAuth2 + mTLS + audit + scope) 뒤에 wrapping
  → LLM 전용 endpoint 노출 (전체 공개 X, 부분 공개)
                │
                │ ※ UMMAYA가 demonstrate하려는 것 = 이 통로의 reference shape
                ▼
[시민] ──"종합소득세 신고해줘"──► [UMMAYA LLM]
                                   │
                                   │ (1) verify primitive
                                   ▼
                          [LLM-callable 인증 모듈]
                          (간편인증/공동/금융/모바일신분증의 보안 wrapping API)
                                   │
                                   │ (2) 시민 모바일 push 또는 인증 ceremony
                                   │     (시민이 평소 hometax에서 쓰던 방식 동일)
                                   ▼
                          [scope-bound delegation token 발급]
                                   │
                                   │ (3) submit primitive (with token)
                                   ▼
                          [LLM-callable 행정 모듈]
                          (홈택스 신고 SDK / 정부24 민원 SDK의 보안 wrapping API)
                                   │
                                   │ (4) 신고 처리 (기관 내부 API가 보안 레이어 뒤에서 실행)
                                   ▼
                          [접수번호 + 영수증 ledger]
                                   │
                                   ▼
                          [LLM이 시민에게 한국어 응답]
```

**핵심**:
- UMMAYA는 **5-primitive (lookup/submit/verify/subscribe + resolve_location) → boundaries → 보안 wrapping 통로 → 기관 내부 API**의 client-side caller
- Mock은 그 통로가 어떻게 보일지의 reference shape (공공마이데이터 표준 + Singapore APEX 패턴 base)
- **Browser automation 불필요** (정부 gateway spec이 정형화되면 REST/SDK 호출만)
- 정책 timing — 국가AX 인프라 발표가 UMMAYA-style architecture를 합법화

### 12.5 가장 닮은 international reference

리서치 결과 (Phase A 산출물): **Singapore APEX (Government API Exchange)** = **★★★★★ 가장 닮음**

- Zone-bridging gateway (인트라넷↔인터넷)
- OAuth 2.1 + mTLS + JWT + Corppass federation
- "Agency-built API + central platform delivery" 분담
- UMMAYA의 `permissions live at adapter layer only` (`docs/requirements/ummaya-migration-tree.md § L1-C C5`)와 1:1 mapping

다음 닮은 시스템:
- **Estonia X-Road** (★★★★) — 각 기관 앞 Security Server, PKI signed assertion + non-repudiation. UMMAYA Spec 024 audit ledger와 정합
- **EU EUDI Wallet** (★★★) — VC presentation. UMMAYA는 wallet 계층 미보유 (학부생 단계 OOS)
- **Japan マイナポータル API** (★★★) — Digital Agency 단일 게이트웨이. third-party app 통합 절차가 UMMAYA plugin DX와 유사

### 12.6 한국 현재 상황 — UMMAYA의 정확한 빈자리

리서치 결과:

| 인프라 | 운영 | AI agent 확장성 |
|---|---|---|
| **공공데이터포털 data.go.kr** | 행안부 + NIA | ★★★★ — 이미 OpenAPI 키 + REST 게이트웨이 backbone. UMMAYA Phase 1 어댑터 운영 중. **AI agent 전용 확장 (rate limit, scope, agent-id audit) 미정** |
| **디지털플랫폼정부 (DPG)** | DPG위원회 | ★★★ — 가이드라인 2.0 (2025-04-16) wrapping·격리·개인정보 분리 권고. **단일 통합 게이트웨이 spec 미공개** |
| **공공마이데이터** | 행안부 + KLID | ★★★ — read 167종 (2025-12 확대). **write extension 미규정** ← UMMAYA submit primitive가 정확히 채울 수 있는 빈자리 |
| **NIA / KISA / 행정정보 공유센터** | 진흥원 / 보안 / 공동이용 | ★★ — 단일 agent gateway 미공개 |
| **범정부 AI 공통기반** | 행안부 + 과기정통부 | ★★★★ — 행정망↔민간 AI wrapping 게이트웨이 (2025-11~). **사용자가 말한 "보안 레이어 wrapping" 모델의 정부 측 implementation** |

**UMMAYA의 차별 포인트 (리서치 결론)**: "한국에는 AI agent 단독을 위한 정부 API 게이트웨이가 아직 정형화되지 않음". UMMAYA는 client-side harness로 정확히 그 빈자리를 메움.

### 12.7 정확한 mock 어댑터 디자인 (§5.4 + §11.4 통합 정정)

Mock의 목적 = "**국가AX 인프라가 시스템 개편 후 LLM-callable 보안 wrapping 통로가 어떻게 보일지의 reference shape**".

| 어댑터 카테고리 | 호출 모양 (mirror할 reference) | 예시 |
|---|---|---|
| **인증 모듈 LLM 호출** | OAuth 2.1 authorization_code + scope-bound access_token (Singapore APEX 패턴) | `mock_verify_module_simple_auth`, `mock_verify_module_modid` |
| **행정 모듈 LLM 호출** | scope-bound bearer token + REST POST + 접수번호 응답 | `mock_submit_module_hometax_taxreturn`, `mock_submit_module_gov24_minwon` |
| **조회 모듈 LLM 호출** | scope-bound bearer token + REST GET + JSON 응답 | `mock_lookup_module_hometax_simplified` |
| **공공마이데이터 write extension** | 마이데이터 표준동의서 envelope 확장 (action-scope claim) | `mock_submit_public_mydata_action` |

**모든 mock 응답 transparency 필드**:
```json
{
  "_mode": "mock",
  "_reference_implementation": "ax-infrastructure-callable-channel",
  "_actual_endpoint_when_live": "https://api.gateway.ummaya.gov.kr/v1/...",
  "_security_wrapping_pattern": "OAuth2.1 + mTLS + scope=send:hometax.tax-return",
  "_policy_authority": "국가AI전략위원회 행동계획 2026-2028 §공공AX",
  "_international_reference": "Singapore APEX",
  ...실제 응답 데이터...
}
```

### 12.8 UMMAYA positioning — "client-side reference implementation"

리서치 권고 (Phase A R4 결론): UMMAYA는 다음 4개 OSS 가시화 채널로 정책 reference 진입 가능:
1. DPG 「공공 AI 서비스 실증 사례집」 등재
2. 공공데이터 활용 경진대회
3. NIA·KISA 보안가이드 reference 부록
4. 행동계획 공공AX 분과 시민의견 channel

학부생 단독 정책 인용 사례는 [research-blocked]이지만 Estonia X-Road · EU EUDI ARF 처럼 **표준 spec과 OSS impl이 동반 진화**하는 국제 패턴이 존재. UMMAYA = "client-side reference impl"로 자리잡으면 정부 gateway spec이 정형화될 때 adapter 갈아끼우는 전략이 안전.

### 12.9 학부생 권한 한계 → 3가지 운영 모드

| Mode | 의미 | 위험 |
|---|---|---|
| **Mock-only (현재)** | 모든 통로를 reference shape로 mirror. demo + 정책 reference 목적 | 0 — 학부생 권한 충분 |
| **Mock + Live data.go.kr** | 공개된 data.go.kr 어댑터는 Live, 비공개 통로는 Mock | 낮음 — UMMAYA Phase 1 이미 운영 중 |
| **Full Live (졸업 후 / partnership)** | 정부 gateway spec 정형화 후 UMMAYA adapter를 live 통로에 연결 | 높음 — 학부생 단계 OOS |

**Verdict**: 학부생 단계는 **Mock-only or Mock + Live data.go.kr**. Full Live는 정부 gateway spec 정형화 + UMMAYA partnership이 전제.

### 12.10 §11 vs §12 — Browser automation은 어디로?

§11에서 제시한 Playwright/browser-automation은 **국가 AX 인프라 spec이 안 나올 경우의 fallback**. §12 canonical path는:
- **Primary**: LLM이 보안 wrapping된 REST/SDK 통로 호출 (정부 gateway 정형화 후)
- **Bridge**: 정부 gateway 정형화 전까지 Mock으로 reference shape demo
- **Fallback**: Mock으로 부족하면 (특정 use case) Playwright로 시민 browser 대신 운영 — 단 이건 secondary, 학부생 단계에서는 옵션

### 12.11 진짜 결론 (3차 정정 final)

**UMMAYA = 한국 국가AX 인프라가 만들 LLM-accessible 보안 wrapping 통로의 client-side reference implementation**.

- 시민 입장: LLM 대화 한 번으로 행정일 처리 (변함없음)
- 기관 입장: 자체적으로 시스템 개편 (국가AI전략위원회 행동계획 동력) — UMMAYA는 변경 요구 X, 단지 reference shape 제공
- UMMAYA 입장: 5-primitive client + Mock reference + 정부 gateway spec 정형화 시 즉시 adapter swap
- Mock 입장: 보안 wrapping 통로의 architectural shape mirror (Singapore APEX + 공공마이데이터 base)
- 학부생 입장: client-side reference impl + OSS 가시화 + KSC 2026 portfolio
- 정책 입안자 입장: 행동계획 §공공AX의 살아있는 reference artifact

**1차 → 2차 → 3차 정정의 통합 thesis**:
- ✅ UMMAYA는 권한 시스템 발명 X (1차)
- ✅ UMMAYA는 새 protocol 발명 X (2차 정정)
- ✅ UMMAYA는 **국가AX 인프라가 정형화할 보안 wrapping 통로의 client-side caller** (3차 final)

이게 AGENTS.md § CORE THESIS와 완전히 정합 — **각 기관의 LLM-callable 모듈 1개를 도구 1개로 래핑**. "API"는 좁게는 REST API, **넓게는 보안 wrapping된 SDK/CLI/모듈 호출 표면**.
