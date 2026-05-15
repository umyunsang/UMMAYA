# KDCA National Health Information Portal OpenAPI Submission

Candidate: `15087442` / `질병관리청_국가건강정보포털`

Date: 2026-05-16 KST

Submission route:

- `https://health.kdca.go.kr/healthinfo/biz/health/portalUseGuidance/openApiReqst/openApiReqstRegist.do`
- User completed KDCA/Digital OnePass login in Chrome.
- OpenAPI service option used: `건강정보`.

Form values submitted:

- 사용자 정보: `개인`
- 사용 목적: `웹사이트 개발`
- 사용 URL: `https://github.com/umyunsang/UMMAYA`
- 활용 용도:

```text
UMMAYA 프로젝트의 공공데이터 기반 한국 행정 공공서비스 API 래핑 모듈 검증 및 개발 목적입니다. 신청 API의 요청 응답 구조를 확인하고, 사용자 질의에 따라 공식 공개 데이터만 조회 요약하는 프로토타입 도구를 구현하기 위한 개발 테스트 용도로 활용합니다. 원본 데이터를 변경하거나 재판매하지 않으며, 활용 시 제공기관과 출처를 명시하겠습니다.
```

- 콘텐츠 선택: `고혈압`

Observed result:

- Browser alert: `정상적으로 등록되었습니다.`
- After confirming the alert, the site returned to the first OpenAPI request
  consent screen.
- The submission screen did not show an issued token, approval status, or
  post-submission request identifier.

Wrapping follow-up:

- Confirm whether KDCA approves automatically or requires review before token
  issuance.
- Confirm whether the post-approval token applies to the HWP-documented
  `https://api.kdca.go.kr/api/provide/healthInfo` endpoint, the newer
  `/healthinfo/openapi/svcNew/healthSearchListApi.do` endpoint, or both.
