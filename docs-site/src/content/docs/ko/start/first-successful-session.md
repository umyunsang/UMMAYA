---
title: "첫 성공 세션"
description: "첫 실행이 무엇을 보여야 하고 무엇을 주장하면 안 되는지 설명합니다."
llm_index: true
audience:
  - new_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs-site/src/data/generated/adapters.json
---

첫 성공 UMMAYA session은 좁지만 중요한 path를 증명합니다. packaged command가 실행되고, model provider에 접근할 수 있고, query engine이 citizen request를 처리하고, 답변이 Live, Mock, Handoff state를 정직하게 유지하는지 확인합니다.

모든 protected public-service action을 완료할 수 있다는 뜻은 아닙니다. 첫 실행은 safe public lookup으로 harness를 테스트해야 하며 identity, payment, certificate issuance, tax filing, official record change로 시작하면 안 됩니다.

## 첫 세션 timeline

성공한 첫 session은 사용자가 무슨 일이 일어났는지 이해할 만큼 보여야 합니다. 정확한 UI는 바뀔 수 있지만 sequence는 이해 가능해야 합니다.

```text
1. `ummaya` command가 시작됨
2. 필요하면 provider setup 또는 sign-in 가능
3. 사용자가 public-service question을 입력
4. UMMAYA가 query engine으로 request를 route
5. public adapter가 실행되거나 safe live action이 없는 이유를 설명
6. final answer가 result, state, boundary, next action을 요약
```

중요한 것은 animation이나 branding이 아닙니다. visible answer가 tool-backed path 또는 clear stop reason으로 trace될 수 있어야 합니다.

## 좋은 첫 프롬프트

유용하지만 low-risk인 prompt를 사용하세요.

```text
동아대 승학캠퍼스 근처 응급실이나 야간 진료 정보를 공식 정보 기준으로 찾아줘.
```

이 prompt는 장소를 주고, 공개 정보를 요청하며, official/public grounding을 요구합니다. identity verification, payment, certificate issuance, filing, account-specific data를 요구하지 않습니다.

## 답변이 보여야 하는 것

답변은 사용자가 다음 step을 믿을 수 있을 만큼 구조를 보여야 합니다. public-service path, 단계가 Live/Mock/Handoff 중 무엇인지, answer를 뒷받침하는 source 또는 adapter result, next action이 포함되어야 합니다.

UMMAYA가 live public path를 찾지 못해도 Handoff는 올바른 결과일 수 있습니다. official access를 발명하지 않는 것이 정직한 동작입니다.

## 일어나면 안 되는 것

첫 session은 UMMAYA가 certificate를 발급했거나, identity를 verified했거나, bill을 paid했거나, tax return을 submitted했거나, official record를 changed했거나, personal account data에 접근했다고 주장하면 안 됩니다. 그런 action은 official callable channel, credential, explicit consent, evidence가 필요합니다.

답변은 모호한 authority도 피해야 합니다. `officially completed`, `verified`, `submitted`, `paid` 같은 표현은 live proof가 필요합니다. proof가 없으면 `prepared`, `found`, `explained`, `handed off`가 더 안전합니다.

## 첫 세션이 실패하면

symptom으로 다음 move를 결정하세요. command가 없으면 Quickstart로 돌아갑니다. sign-in이 실패하면 provider setup을 고칩니다. prompt가 Mock 또는 Handoff를 반환하면 failure로 취급하기 전에 state label을 읽습니다. public lookup이 실패하면 더 명확한 location과 하나의 public information need를 시도합니다.

첫 session은 가장 어려운 protected action을 완료한 것처럼 보일 때가 아니라, UMMAYA가 정직하고 inspectable할 때 성공입니다.

## 다음으로 갈 곳

첫 public lookup 후 [What You Can Ask](/ko/start/what-you-can-ask/)를 읽고 prompt를 개선하세요. 그 다음 protected workflow를 시도하기 전에 [Live, Mock, And Handoff](/ko/trust/live-mock-handoff/)를 읽으세요.
