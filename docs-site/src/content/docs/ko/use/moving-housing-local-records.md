---
title: "이사, 주거, 지역 기록"
description: "공식 기록을 바꾼 것처럼 말하지 않으면서 여러 기관에 걸친 이사와 주거 workflow를 준비합니다."
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

이사와 주거 작업은 UMMAYA가 왜 필요한지 잘 보여줍니다. 한 번의 이사는 지역 기록, 주소 해석, 공공요금 변경, 주거 서류, 차량이나 주차 규칙, 학교구역, 공식 기록 변경을 동시에 건드릴 수 있습니다. 사용자는 도움을 요청하기 전에 기관 지도를 먼저 알 필요가 없어야 합니다.

UMMAYA는 하나의 요청을 순서 있는 공공서비스 경로로 바꾸어 이 여정을 이해하기 쉽게 만들 수 있습니다. 하지만 live channel, credential, consent, receipt path가 증명되지 않는 한 공식 기록을 변경했다고 말하면 안 됩니다.

## 좋은 프롬프트

순서 있는 경로와 공식 경계를 함께 요청하세요.

```text
부산 사하구로 이사했어. 전입신고 전후로 확인해야 할 공공서비스 단계를 순서대로 정리하고, UMMAYA가 할 수 없는 공식 절차는 표시해줘.
```

이 프롬프트는 장소, life event, 원하는 출력 형식을 줍니다. 조용한 공식 제출이 아니라 준비와 boundary 표시를 요청합니다.

## 예상 흐름

이사 workflow는 user outcome에서 시작해 location을 해석한 뒤, 공개 안내와 보호된 기록 변경을 분리해야 합니다. 이후 단계가 주소와 관할에 의존하기 때문에 순서가 중요합니다.

```text
사용자가 이사를 설명
  -> `locate`가 주소 또는 행정구역을 해석
  -> `find`가 지역 공공서비스 안내를 조회
  -> `check`가 보호된 요구사항 또는 부족한 credential을 확인
  -> live official channel과 consent가 있을 때만 `send`
  -> 아니면 Handoff가 공식 continuation을 설명
```

UMMAYA가 location을 해석하지 못하면 기관 목록을 나열하기 전에 clarifying question을 물어야 합니다. 위치는 해석했지만 record change를 할 수 없다면 완료라고 말하지 말고 checklist와 official handoff를 제공해야 합니다.

## 유용한 답변의 구성

유용한 답변은 준비와 실행을 분리합니다. 준비 부분에는 가능한 task, 문서, 기관, timing이 들어갈 수 있습니다. 실행 부분은 무엇이 Live, Mock, Handoff인지 표시해야 합니다.

| 필요 | UMMAYA 역할 | 경계 |
|---|---|---|
| 주소 또는 관할 | `locate` | 지역 안내에 충분히 명확해야 함 |
| 공개 이사 checklist | `find` | 공개 정보 전용 |
| eligibility 또는 account-specific 확인 | `check` | consent와 credential 필요 가능 |
| 공식 기록 변경 | live authority가 있을 때만 `send` | 아니면 Handoff |

이 구조는 사용자가 checklist와 official filing을 혼동하지 않으면서 다음 행동을 알게 합니다.

## UMMAYA가 주장하면 안 되는 것

UMMAYA는 live adapter가 evidence를 반환하지 않는 한 전입신고, utility account, vehicle record, school record, housing record, local government record를 변경했다고 말하면 안 됩니다. 준비된 경로는 제출된 양식이 아닙니다. mock receipt는 agency receipt가 아닙니다.

안전한 마지막 문장은 명확해야 합니다. `UMMAYA prepared the moving path and identified official steps, but did not change an official record in this session.` 이런 문장은 덜 화려하지만 workflow를 신뢰 가능하게 만듭니다.

## 복구

workflow가 멈추면 UMMAYA는 progress를 막은 항목을 말해야 합니다. 주소 모호성, no adapter, credential missing, consent not granted, protected channel unavailable, official Handoff 중 무엇인지 알려야 합니다. 사용자는 이어갈 공식 서비스나 다음 turn에서 답해야 할 구체 질문을 얻어야 합니다.

이사 workflow는 길기 때문에 context가 중요합니다. 이후 turn에서 같은 작업을 재개할 때 UMMAYA는 resolved location, 이미 논의한 checklist, stop을 일으킨 protected step을 보존해야 합니다.
