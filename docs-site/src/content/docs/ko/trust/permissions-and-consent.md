---
title: "Permissions And Consent"
description: "UMMAYA가 public lookup과 protected public-service action을 분리하는 방식입니다."
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - specs/033-permission-v2-spectrum-consent-ledger/spec.md
  - docs/api/README.md
---

Permissions and consent는 사용자를 invisible authority jump에서 보호합니다. UMMAYA는 공개 정보를 직접 가져올 수 있지만, protected action은 진행 전에 visible decision이 필요합니다.

규칙은 간단합니다. public lookup은 편리할 수 있지만 protected action은 명시적이어야 합니다. identity, certificate, payment, filing, account-specific data, welfare submission, official record change는 일반 search result처럼 다룰 수 없습니다.

## Public Lookup

Public lookup은 가장 낮은 risk path입니다. adapter와 source가 지원하면 UMMAYA는 location을 해석하고, weather를 fetch하고, road information을 가져오고, public guidance를 요약할 수 있습니다.

public lookup도 grounding이 필요합니다. 답변은 어떤 source나 adapter가 result를 만들었고 어떤 uncertainty가 남는지 말해야 합니다. public은 unlimited가 아니라 user's protected authority를 요구하지 않는다는 뜻입니다.

## Protected Actions

Protected action은 identity, money, benefit, record, right에 영향을 줄 수 있으므로 더 강한 gate가 필요합니다. UMMAYA는 action class, adapter mode, credential requirement, user consent를 확인해야 합니다.

조건이 빠졌다면 올바른 결과는 Mock 또는 Handoff입니다. 사용자가 직접 요청했다는 이유로 protected action을 confident sentence로 바꾸면 안 됩니다.

## Consent Records

consent record는 네 질문에 답해야 합니다. 어떤 action을 허용하는가, 왜 필요한가, 어떤 adapter 또는 official path가 관련되는가, 어떤 result가 만들어지는가입니다. 이 detail이 없으면 consent는 장식이 됩니다.

평가자는 consent record가 mode와 stop reason에 연결되는지 확인해야 합니다. completion을 주장하는 protected flow는 live authority와 evidence를 보여야 합니다. mock flow는 mock으로 남았음을 보여야 합니다.

## Safe Defaults

permission이 모호하면 UMMAYA는 fail closed해야 합니다. 추측하지 말고 clarification을 묻거나, 멈추거나, handoff해야 합니다. identity, payment, certificate, tax, welfare application, record change에서는 특히 중요합니다.

safe default는 제품을 느리게 보이게 할 수 있지만 inspectable하게 만듭니다. 사용자는 시스템이 왜 멈췄는지와 어떤 official path가 남았는지 볼 수 있습니다.

## 사용자가 봐야 하는 것

사용자는 protected work 이후가 아니라 이전에 permission을 봐야 합니다. 답변은 protected action, consent reason, status label, consent나 authority가 없을 때의 next step을 말해야 합니다.

UI나 final answer가 이 정보를 숨기면 문서는 이를 trust gap으로 취급해야 합니다. UMMAYA의 가치는 visible boundary에 달려 있습니다.
