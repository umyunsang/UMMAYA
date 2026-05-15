---
title: "Live, Mock, Handoff"
description: "UMMAYA가 실제로 할 수 있는 일을 정직하게 표시하는 status label입니다."
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs-site/src/data/generated/adapters.json
  - docs/api/README.md
---

Live, Mock, Handoff는 UMMAYA의 trust language입니다. 시스템이 configured channel을 실제로 호출했는지, 알려진 workflow shape를 simulation했는지, 다음 단계가 official service에 속해 멈췄는지를 사용자에게 알려줍니다.

이 label은 implementation detail이 아닙니다. UMMAYA가 evidence보다 더 authoritative하게 들리지 않게 만드는 장치입니다.

## Live

Live는 UMMAYA가 configured public-service channel을 호출하고 returned result에 grounded하게 답할 수 있다는 뜻입니다. Live answer는 관련 source나 adapter를 말하고, result를 요약하고, result가 증명하는 범위 안에 머물러야 합니다.

Live가 domain의 모든 action을 의미하지는 않습니다. weather lookup은 Live일 수 있지만 user-specific disaster-support application은 Handoff일 수 있습니다. hospital public lookup은 Live일 수 있지만 medical triage는 UMMAYA 밖에 남습니다.

## Mock

Mock은 UMMAYA가 official agency result를 만들지 않고 workflow shape를 demonstration할 수 있다는 뜻입니다. Mock은 live credential이나 official access 전에 tool calling, schemas, permission prompts, receipts, UX를 테스트할 때 유용합니다.

Mock은 official처럼 들릴 때 위험합니다. mock payment는 paid가 아닙니다. mock certificate는 issued가 아닙니다. mock identity check는 identity verification이 아닙니다. Mock이라는 단어는 developer-only metadata가 아니라 result 가까이에 보여야 합니다.

## Handoff

Handoff는 UMMAYA가 path를 준비하거나 설명할 수 있지만 사용자가 official service에서 계속해야 한다는 뜻입니다. identity, payment, certificate issuance, tax filing, official record change 또는 UMMAYA가 갖지 않은 authority가 필요할 때 올바른 결과입니다.

좋은 Handoff는 여전히 유용합니다. official service나 category, UMMAYA가 준비한 것, 수행하지 않은 것, live path가 되려면 필요한 evidence나 credential을 말해야 합니다.

## Status Label 읽는 법

답변으로 행동하기 전에 label을 먼저 보세요.

| Label | 일어난 일 | 결과를 다루는 법 |
|---|---|---|
| Live | configured channel이 evidence를 반환 | stated scope 안에서 사용 |
| Mock | 알려진 workflow shape가 simulation됨 | official output이 아니라 demonstration으로 취급 |
| Handoff | official boundary에서 멈춤 | official service에서 이어감 |
| Planned | target state에 포함됨 | current capability로 취급하지 않음 |

중요한 workflow인데 label이 보이지 않으면 행동하기 전에 UMMAYA에 state clarification을 요청하세요.

## 사용자 규칙

유창함보다 boundary를 믿어야 합니다. `Handoff required`라고 말하는 짧은 답변이 hidden government access를 암시하는 fluent answer보다 안전합니다.

시스템이 visible하게 멈출 때 제품은 정상 동작하는 것입니다. 국가 인프라 AX는 official authority를 제거하는 것이 아니라 authority가 필요한 지점까지 혼란을 줄이는 것입니다.
