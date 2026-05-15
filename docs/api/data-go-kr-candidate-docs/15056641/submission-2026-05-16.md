# CareerNet OpenAPI Key Application Submission

Candidate: `15056641` / `교육부_커리어넷 직업정보`

Date: 2026-05-16 KST

Submission route:

- `https://www.career.go.kr/cnet/front/openapi/openApiApply02Center.do`
- User completed CareerNet/Career OnePass login in Chrome.

Form values submitted:

- 회원 유형: `개인회원`
- 서비스명: `UMMAYA`
- 서비스유형: `PC웹`, `모바일 웹`, `모바일 앱(APP)`
- 서비스 URL 주소: `https://github.com/umyunsang/UMMAYA`
- 서비스 설명:

```text
UMMAYA는 한국 행정 공공서비스 API를 대화형 도구로 래핑하는 프로젝트입니다. 커리어넷 직업정보 API의 요청 응답 구조를 검증하고, 사용자 질의에 따라 공식 직업 정보를 조회 요약하는 프로토타입을 개발 테스트하는 용도로 활용합니다. 원본 데이터를 변경하거나 재판매하지 않으며, 활용 시 커리어넷과 제공기관 출처를 명시하겠습니다.
```

- 사용 이유: `서비스 연계를 통한 진로정보 제공`, `데이터 분석 및 연구`
- 사용 API: `직업정보`
- API 연계 주기: `실시간`

Observed result:

- Confirmation dialog: `등록되었습니다.`
- Completion page: `오픈API 인증키 발급신청 완료`
- Completion page text said the request will be reviewed by an administrator
  and the result will be sent by email.
- Application-status page:
  - `인증현황`: `대기`
  - `사이트 URL`: `https://github.com/umyunsang/UMMAYA`
- No API key was visible before approval.

Wrapping follow-up:

- Wait for administrator approval or email result.
- After approval, capture the issued CareerNet `apiKey` outside tracked source
  files and validate it with the already documented no-key probe endpoint:
  `https://www.career.go.kr/cnet/openapi/getOpenApi.json`.
