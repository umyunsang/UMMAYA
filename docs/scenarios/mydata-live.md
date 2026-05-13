# 마이데이터 Live 데이터 — KFTC MyData OPAQUE-도메인 시나리오

> **Scope**: 시민이 UMMAYA 에서 "내 통장 거래내역 가져와" 또는 "신용 정보 조회" 같은 마이데이터 Live 데이터 요청을 했을 때의 hand-off 흐름.
> **Originating spec**: Epic ζ #2297.
> **Authoritative source**: AGENTS.md § L1-B B3.

## 어댑터를 만들지 않는 이유

마이데이터는 KFTC (금융결제원) 가 운영하는 본인신용정보관리업 표준 API 로, 시민이 (a) 마이데이터 사업자에게 본인 동의 + 인증, (b) KFTC 통합인증센터에서 데이터 제공기관 별 access_token 발급, (c) 사업자가 데이터 제공기관 (은행/카드/증권/보험 등) API 호출, (d) 시민에게 데이터 제공 — 의 4단계로 구성된다. 단계 (a)+(b) 는 시민이 마이데이터 사업자 자체 UI (앱 또는 웹) 를 통해서만 가능 — KFTC 표준은 사업자 SDK 가 아닌 사업자 본 앱 안에서 ceremony 를 완료할 것을 요구한다 (시민 자기결정권 보장). 또한 KFTC 통합인증센터의 OAuth 2.0 endpoint 는 사업자별 client_id 등록 + 마이데이터 사업 라이선스가 있어야 호출 가능하며, UMMAYA 는 사업자가 아니다. 따라서 UMMAYA 는 마이데이터 Live 데이터 어댑터를 운영하지 않고, **(a) 검증된 mock 데이터 demo** (`mock_verify_mydata` + `mock_lookup_module_mydata_*`) 까지만 제공하며, 실제 시민의 Live 데이터는 시민 본인이 마이데이터 사업자 앱을 통해 직접 조회하도록 hand-off.

## Citizen narrative

1. **시민 발화**: "내 통장 거래내역 보여줘" 또는 "내 신용카드 사용내역 가져와" 또는 "마이데이터로 내 자산 한 번에".
2. **UMMAYA 응답 (Mock-mode demo)**: LLM 이 `verify(tool_id="mock_verify_mydata", params={scope_list: ["find:mydata.bank-account"], purpose_ko: "거래내역 조회"})` → `lookup(mode="fetch", tool_id="mock_lookup_module_mydata_bank_account", params={delegation_context})` 를 emit, 합성 거래내역 데이터를 반환. **이 데이터는 fixture 이지 시민의 실제 데이터가 아님** — 시민에게 명시적으로 안내.
3. **Live-mode 전환**: UMMAYA 는 "실제 마이데이터 조회는 UMMAYA 가 사업자 라이선스가 없어 대행할 수 없습니다. 본인이 직접 사용하시는 마이데이터 사업자 앱 (NH NongHyup, Kakao Pay, Toss, Bank Salad 등) 에서 조회해주세요" 안내 + 사업자 목록 URL.
4. **시민 작업 (마이데이터 사업자 앱 내)**: 시민이 사용 중인 마이데이터 사업자 앱 설치/접속 → 본인인증 (PASS / 공동인증서 / 금융인증서 — UMMAYA 의 verify 영수증과 별개) → 마이데이터 사업자 별 동의 절차 → KFTC 통합인증센터 redirect → 데이터 제공기관 (은행/카드/증권 등) 별로 access_token 발급 + 데이터 조회. 실제 거래내역/자산현황 데이터는 사업자 앱 안에서 시민에게 표시.
5. **시민이 UMMAYA 로 복귀**: 사업자 앱에서 본 데이터를 UMMAYA 에 다시 입력하거나, 사업자 앱이 제공하는 export/공유 기능으로 UMMAYA 에 데이터 일부 가져옴 (사업자별 지원 여부 다름). Consent ledger 에 "Live 데이터는 hand-off, mock demo 만 UMMAYA chain" 의 분리 + 사업자 이름이 기록됨.

## UMMAYA ↔ real system handoff point

시민이 UMMAYA 의 chain 한계를 넘어 실제 시스템으로 이동하는 지점. UMMAYA 는 client-side reference implementation 이며, 아래 URL 은 시민이 실제 작업을 마무리하는 정부 운영 채널입니다.

## Hand-off URL

- KFTC 마이데이터 종합포털 (시민용 안내): https://www.mydatacenter.or.kr:3441/
- 마이데이터 사업자 명단 (금융위원회): https://www.fsc.go.kr/no010101/82203
- 대표 사업자 — NH NongHyup MyData: https://mydata.nonghyup.com/
- 대표 사업자 — Kakao Pay MyData: https://www.kakaopay.com/
- 대표 사업자 — Toss MyData: https://toss.im/
- 대표 사업자 — Bank Salad: https://banksalad.com/
