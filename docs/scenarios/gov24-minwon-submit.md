# 정부24 민원 제출 — gov24 OPAQUE-도메인 시나리오

> **Scope**: 시민이 UMMAYA 에서 "정부24 민원 신청해줘" (예: 주민등록 등본 발급, 사업자 등록증 발급, 인감 증명서) 라고 요청했을 때의 hand-off 흐름.
> **Originating spec**: Epic ζ #2297.
> **Authoritative source**: AGENTS.md § L1-B B3.

## 어댑터를 만들지 않는 이유

정부24 의 1300+ 종 민원은 각각 다른 부처가 운영하는 백엔드 시스템에 연결되어 있다. 정부24 자체는 **단일 진입 포털 + ID 통합 + 결제 통합 + 출력물 발급** 의 4가지 횡단 기능만 책임지고, 실제 민원 처리 로직은 부처 시스템에 위임된다. UMMAYA 가 어댑터를 1300개 이상 만드는 것은 비현실적이며, 부처별 OPAQUE 정책 (예: 보건복지부의 복지급여 신청은 별도 PKI 요구) 도 어댑터화 비용 대비 시민 가치가 낮다. 따라서 UMMAYA 는 **(a) 본인인증** 까지만 chain 으로 처리하고 (`verify(tool_id="mock_verify_module_simple_auth", ...)`), 실제 민원 폼 작성 + 제출은 정부24 본 UI 로 hand-off. (Mock-mode demo 는 `mock_submit_module_gov24_minwon` 으로 합성 접수번호 만 반환.)

## Citizen narrative

1. **시민 발화**: "주민등록등본 발급해줘" 또는 "사업자 등록증 신청" 같은 정부24-class 민원 요청.
2. **UMMAYA 응답 (Mock-mode)**: LLM 이 `verify(tool_id="mock_verify_module_simple_auth", params={scope_list: ["send:gov24.minwon"], purpose_ko: "주민등록등본 발급"})` → `submit(tool_id="mock_submit_module_gov24_minwon", params={delegation_context, document_type: "resident_registration_extract"})` 를 emit. 합성 접수번호 + 안내 메시지 표시.
3. **Live-mode 전환**: UMMAYA 는 verify 단계까지만 자체 처리. submit 단계에서 정부24 의 민원별 deep-link 를 시민에게 안내 (예: 주민등록등본 = `https://www.gov.kr/portal/serviceInfo/B5500000038`). TUI 가 "정부24 에서 본인인증을 한번 더 진행하고 발급을 마무리해주세요" 메시지 + URL 출력.
4. **시민 작업 (정부24 UI 내)**: 정부24 본 사이트로 이동, 간편 인증 또는 공동인증서로 본인인증 (UMMAYA 의 verify 영수증과 별개의 ceremony — 정부24 가 자체 세션을 발급), 민원 폼 작성, 제출. 즉시 발급 가능한 민원은 PDF 다운로드 (예: 등본), 처리 시간이 필요한 민원 (예: 사업자 등록증) 은 이메일/SMS 알림 으로 결과 수령.
5. **시민이 UMMAYA 로 복귀**: 발급된 민원번호 또는 처리 결과를 UMMAYA 에 입력하면 향후 lookup 에 사용 가능. Consent ledger 에 hand-off 시점 기록.

## UMMAYA ↔ real system handoff point

시민이 UMMAYA 의 chain 한계를 넘어 실제 시스템으로 이동하는 지점. UMMAYA 는 client-side reference implementation 이며, 아래 URL 은 시민이 실제 작업을 마무리하는 정부 운영 채널입니다.

## Hand-off URL

- 정부24 메인: https://www.gov.kr/
- 주민등록등본 발급: https://www.gov.kr/portal/serviceInfo/B5500000038
- 사업자 등록증 발급: https://www.gov.kr/portal/serviceInfo/PTR000050349
- 인감 증명서 발급: https://www.gov.kr/portal/serviceInfo/PTR000050327
