---
title: "데이터, 자격 증명, 로컬 세션"
description: "UMMAYA가 local에 무엇을 저장하고 credential이 무엇을 의미하며 session evidence가 어떻게 inspect 가능해야 하는지 설명합니다."
llm_index: true
audience:
  - citizen_user
  - public_sector_evaluator
  - maintainer
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - specs/033-permission-v2-spectrum-consent-ledger/spec.md
  - docs/vision.md
---

UMMAYA는 data, credentials, session state를 이해 가능하게 만들어 user trust를 지켜야 합니다. 국가 인프라 assistant는 무엇이 local인지, 무엇이 provider에 속하는지, 무엇이 official service로 보내지지 않았는지 사용자가 알 때만 유용합니다.

이 페이지는 user level의 trust model을 설명합니다. secret-storage specification은 아니지만 protected workflow 전에 던져야 할 질문을 제공합니다.

## 첫 로그인의 의미

첫 login 또는 provider setup은 UMMAYA가 model provider에 접근하게 합니다. government authority, identity credential, certificate access, payment right, official record change permission을 주는 것이 아닙니다.

이 구분은 중요합니다. provider access와 public-service authority는 다른 layer입니다. model session이 정상이어도 public-service step이 official login이나 consent를 요구하면 Handoff에서 멈출 수 있습니다.

## Credentials

credential은 convenience string이 아니라 scoped authority로 다뤄야 합니다. workflow가 agency login, identity verification, certificate signing, payment authorization, account-specific data를 요구하면 UMMAYA는 진행 전에 boundary를 보여야 합니다.

문서는 UMMAYA가 hidden credential을 갖고 있다고 암시하면 안 됩니다. credential path가 configured and validated되지 않았다면 올바른 표현은 Mock, Handoff, Planned입니다.

## Local Sessions

local session은 UMMAYA가 긴 workflow의 context를 보존하게 합니다. request text, resolved location, selected adapter, status labels, tool summaries, permission state, stop reason, final answer가 포함될 수 있습니다.

local session state는 inspection을 도와야 합니다. 사용자나 maintainer가 무슨 일이 있었는지, 어떤 evidence가 반환되었는지, 무엇이 consent되었는지, workflow가 어디서 멈췄는지 답할 수 있어야 합니다.

## Protected Flow 전에 확인할 것

protected flow 전에 세 가지를 확인하세요.

| 질문 | 중요한 이유 |
|---|---|
| 이 단계가 Live, Mock, Handoff 중 무엇인가? | fake completion 방지 |
| 어떤 credential 또는 consent가 필요한가? | UMMAYA가 authority를 갖는지 보여줌 |
| 어떤 receipt 또는 evidence가 남는가? | result를 inspect 가능하게 만듦 |

어떤 답이 불분명하면 더 안전한 action은 멈추거나 official service에서 계속하는 것입니다.

## 복구

session, credential, receipt state가 불분명하면 UMMAYA는 language를 낮춰야 합니다. path를 prepared, found, explained했다고 말할 수는 있지만 visible evidence 없이 filed, paid, verified, issued, changed라고 말하면 안 됩니다.

Trust는 답변이 helpful하게 들리는 것만으로 생기지 않습니다. 답변 이후에도 boundary를 inspect할 수 있어야 합니다.
