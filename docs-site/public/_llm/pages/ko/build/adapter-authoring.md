---
title: 어댑터 작성
description: 하나의 공공서비스 채널을 하나의 증거 기반 UMMAYA 어댑터로 감싸는 방법입니다.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs/api/README.md
- docs/plugins/security-review.md
audience:
- adapter_author
- maintainer
- public_sector_evaluator
---

어댑터는 UMMAYA가 확장되는 기본 단위입니다. 하나의 어댑터는 하나의 공공서비스 채널, mock 가능한 정책 모양, 또는 공식 handoff 경로를 하나의 도구 항목으로 감싸고, schema, citation, state label, permission metadata를 함께 제공합니다.

어댑터 작성은 backend 작업만이 아닙니다. 어댑터는 문서가 무엇을 정직하게 주장할 수 있는지, 모델이 무엇을 호출할 수 있는지, 사용자가 어떤 권한 요청을 보게 되는지, 최종 답변이 어떤 근거를 인용할 수 있는지를 결정합니다.

## 먼저 올바른 상태를 고르기

코드를 작성하기 전에 채널의 현재 상태를 분류해야 합니다. 이 판단이 먼저 필요한 이유는 schema, 테스트, 권한 문구, 사용자 문서의 표현이 모두 달라지기 때문입니다.

| 상태 | 사용할 때 | 문서에 생기는 결과 |
|---|---|---|
| Live | 공식 호출 채널과 credential 경로가 존재할 때 | 문서는 범위 안에서 근거 있는 실행을 설명할 수 있습니다 |
| Mock | 채널 모양은 알려져 있거나 정책상 요구되지만 live 접근은 없을 때 | 문서는 반드시 simulation이라고 표시해야 합니다 |
| Handoff | 다음 단계가 불투명한 공식 서비스에 속할 때 | 문서는 경로를 준비시키고 멈춰야 합니다 |
| Planned | target-state 수요는 있지만 shape/evidence가 아직 준비되지 않았을 때 | 문서는 현재 기능이 아니라 roadmap으로만 설명해야 합니다 |

이 표는 마케팅 분류가 아니라 안전장치입니다. 예를 들어 인증서 발급 채널이 Mock이면 사용자는 흐름을 볼 수 있지만 실제 서류가 발급되었다고 말하면 안 됩니다. Handoff이면 UMMAYA는 준비한 정보와 공식 진입점을 보여주고, 사용자가 공식 서비스에서 계속해야 한다는 사실을 먼저 알려야 합니다.

## 필요한 내용

좋은 어댑터는 쿼리 엔진과 문서가 같은 사실을 말할 수 있을 만큼 구조적이어야 합니다. 필드가 부족하면 모델은 그럴듯하지만 잘못된 도구 호출을 만들 수 있고, 문서는 지원되지 않는 사용자 약속을 하게 됩니다.

| 요구사항 | 중요한 이유 |
|---|---|
| primitive | 어댑터를 `locate`, `find`, `check`, `send` 중 하나의 행동으로 묶습니다 |
| input/output schema | 가능한 호출과 불가능한 호출을 명확히 나눕니다 |
| Live/Mock/Handoff state | 사용자에게 말할 수 있는 권한 수준을 제어합니다 |
| permission tier | 공개 조회와 보호된 행동을 분리합니다 |
| public 또는 policy citation | UMMAYA가 임의로 권한을 만들지 못하게 합니다 |
| fixture 또는 artifact | Mock/Live 행동을 검토 가능한 증거로 남깁니다 |
| search hints | 시민 언어로 들어온 질의가 올바른 어댑터를 찾게 합니다 |

어댑터가 이 필드를 갖추지 못했다면 사용자 workflow의 근거로 홍보하면 안 됩니다. 이때의 올바른 문서는 "지원한다"가 아니라 "지원 준비 중이며 현재는 handoff 또는 scenario로 설명한다"입니다.

## 사용자 문서 요구사항

사용자-facing coverage에 영향을 주는 어댑터는 반드시 prose를 가져야 합니다. 그 prose는 어댑터가 지원하는 일, 지원하지 않는 일, 적용되는 상태 label, 안전한 답변 언어를 함께 말해야 합니다.

예를 들어 공공 날씨 어댑터는 Live 날씨 조회를 지원할 수 있습니다. 그러나 별도의 보호된 경로가 없으면 개인 재난지원금 자격 판정까지 지원한다고 말하면 안 됩니다. 문서는 날씨 조회, 위험 안내, 공식 신청 경로를 서로 다른 주장으로 나눠야 합니다.

이 원칙은 UMMAYA의 국가 인프라 AX 목적과 연결됩니다. 사용자는 하나의 쉬운 질의로 시작하지만, 시스템은 각 도메인의 실제 권한과 채널 모양을 지켜야 합니다. 어댑터 문서는 이 둘 사이의 계약서입니다.

## Live 승격 요구사항

Mock에서 Live로 승격할 때 필요한 것은 기대가 아니라 증거입니다. 프로젝트는 공식 endpoint 또는 채널 validation, credential 처리, schema validation, permission metadata, sanitized request/response artifact, 그리고 CI에서 live 시민 인프라를 호출하지 않는 테스트를 갖춰야 합니다.

승격 뒤에는 문서 표면을 다시 생성하고 영향받은 페이지를 검토합니다.

```bash
npm run docs:generate
npm run docs:check
```

생성된 adapter metadata가 바뀌면 사용자 문서와 LLM-readable docs도 함께 바뀌어야 합니다. 그렇지 않으면 사람은 Mock을 보고 있고 agent는 Live를 읽거나, 반대로 agent가 오래된 handoff 경계를 읽는 drift가 생깁니다.

## 실패 모드

가장 흔한 실패는 도구를 하나 추가한 뒤 넓은 마케팅 문장을 먼저 쓰는 것입니다. UMMAYA는 반대로 해야 합니다. 먼저 채널 모양을 증명하고, 경계를 정의하고, 그 증거가 허용하는 범위 안에서만 문서가 주장하게 만들어야 합니다.

이 순서를 지키면 어댑터는 단순한 코드 파일이 아니라 사용자 신뢰의 단위가 됩니다. 사용자는 UMMAYA가 어디까지 할 수 있고 어디서 멈춰야 하는지 이해하고, 기여자는 다음 어댑터를 같은 품질 기준으로 추가할 수 있습니다.
