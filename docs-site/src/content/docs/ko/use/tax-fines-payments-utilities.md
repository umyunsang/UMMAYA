---
title: "세금, 과태료, 납부, 공공요금"
description: "Mock path와 official completion을 혼동하지 않으면서 중요한 납부와 신고 workflow를 준비합니다."
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

세금, 과태료, 납부, 공공요금은 UMMAYA의 target state를 설득력 있게 보여주는 예시입니다. 흔하고, 중요하며, 여러 기관에 흩어져 있기 때문입니다. 그러나 checklist, estimate, mock, handoff가 official filing이나 payment처럼 들리면 위험합니다.

유용한 UMMAYA는 이 구분을 숨기지 않습니다. 공식 경로를 설명하고, 공개 안내를 조회하고, 필요한 정보를 준비하고, consent나 official login이 필요한 지점을 보여줄 수 있습니다. 하지만 live official channel이 evidence를 반환하지 않는 한 돈이 납부되었거나 세금 신고가 제출되었거나 official record가 변경되었다고 말하면 안 됩니다.

## 좋은 프롬프트

좋은 프롬프트는 경로 준비와 boundary 표시를 요청합니다.

```text
자동차 과태료를 납부해야 하는지 확인하려고 해. 어떤 공식 경로와 준비물이 필요한지 정리하고, 실제 납부가 필요한 단계는 Handoff로 표시해줘.
```

```text
종합소득세 신고를 준비하려고 해. UMMAYA가 확인할 수 있는 공개 정보와 공식 홈택스에서 해야 하는 단계를 나눠서 알려줘.
```

이 프롬프트는 preparation과 execution을 분리합니다. 사용자가 즉시 납부나 신고를 요청하면 UMMAYA는 `send` 전에 live authority, credential, consent, receipt evidence를 요구해야 합니다.

## 예상 흐름

납부와 신고 workflow는 공개 설명에서 시작해 빠르게 protected state로 이동합니다. UMMAYA는 이 layer를 분리해야 합니다.

```text
사용자가 tax, fine, payment, utility 작업을 질문
  -> `find`가 공개 안내 또는 일반 경로를 조회
  -> `check`가 user-specific state에 authority가 필요함을 드러낼 수 있음
  -> `send`는 live official channel과 consent가 있을 때만 허용
  -> 다음 단계가 official service에서만 가능하면 Handoff
```

올바른 stop은 실패가 아닙니다. live official channel이 없으면 UMMAYA는 path를 준비했지만 신고, 납부, 기록 변경은 하지 않았다고 말해야 합니다.

## 안전한 결과 형태

final answer는 네 부분으로 나뉘어야 합니다. UMMAYA가 찾은 것, user-specific으로 남은 것, 이어가야 할 official service, UMMAYA가 하지 않은 것입니다.

| 필요 | 안전한 UMMAYA 출력 | 위험한 출력 |
|---|---|---|
| 공개 신고 안내 | 단계, 준비 문서, 공식 서비스 이름 | `신고 완료` |
| user-specific 금액 | consent-gated `check` 또는 Handoff | 추정 금액 단정 |
| 납부 실행 | live `send`와 receipt evidence | mock payment를 paid처럼 설명 |
| receipt | Live receipt 또는 명확히 labeled mock receipt | unlabeled confirmation |

이 언어는 사용자가 가짜 완료를 믿고 행동하는 것을 막습니다. 평가자에게도 기준이 됩니다. 모든 completion verb는 tool evidence로 뒷받침되어야 합니다.

## 왜 강한 언어가 필요한가

이 영역의 false answer는 실제 피해를 만들 수 있습니다. 사용자가 기한을 놓치거나, 과태료가 납부되었다고 믿거나, 신고가 접수되었다고 생각하거나, 잘못된 곳에 credential을 공유할 수 있습니다. 그래서 UMMAYA는 인상적인 문장보다 명확한 boundary wording을 우선해야 합니다.

`prepared`, `identified`, `requires official login`, `not submitted`, `continue through the official service` 같은 표현을 사용하세요. live result가 증명하지 않으면 `paid`, `filed`, `accepted`, `approved`, `changed`는 피해야 합니다.

## 복구

보호된 납부나 신고 flow가 멈추면 답변은 여전히 유용해야 합니다. 사용자가 열어야 할 official service, 준비할 정보, 빠진 consent나 credential, 미래에 UMMAYA가 live로 수행하려면 필요한 evidence를 알려야 합니다.

target state는 납부 경계를 없애는 것이 아닙니다. official authority를 보이게 유지하면서 경로를 이해하기 쉽게 만드는 것입니다.
