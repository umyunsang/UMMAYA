---
title: "UMMAYA 문서"
description: "대한민국 국가 인프라 AX harness로서 UMMAYA를 사용하고, 평가하고, 확장하기 위한 문서입니다."
llm_index: true
audience:
  - non_user
  - considering_user
  - new_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs/research/ummaya-docs-audience-audit-2026-05-15.md
  - docs/vision.md
---

UMMAYA는 대한민국 국가 인프라 AX를 위한 conversational agent harness입니다. 사용자는 하나의 접근하기 쉬운 query surface에서 공공서비스 결과를 요청하고, 시스템은 요구 분해, tool selection, permission boundary, evidence, official handoff를 처리합니다.

이 문서는 네 단계의 독자를 위해 작성되었습니다. UMMAYA가 필요한지 판단하는 사람, packaged CLI를 처음 실행하는 사용자, claim이 근거 있는지 확인하는 evaluator, adapter surface를 확장하는 contributor가 같은 문서에서 서로 다른 질문의 답을 찾을 수 있어야 합니다.

## 여기서 시작하기

처음이라면 Start section을 순서대로 읽는 것이 좋습니다. 이 section은 사용자 문제, 현재 capability, 설치 경로, 첫 successful session, prompt shape, query 뒤에 일어나는 일을 설명합니다.

| Page | Use it when |
|---|---|
| [Why UMMAYA](/ko/start/why-ummaya/) | 제품 목적을 이해해야 할 때 |
| [What UMMAYA Can Do Today](/ko/start/what-ummaya-can-do-today/) | 현재 capability와 limit을 확인하고 싶을 때 |
| [Quickstart](/ko/start/quickstart/) | CLI를 설치하고 실행하고 싶을 때 |
| [First Successful Session](/ko/start/first-successful-session/) | 성공한 첫 실행이 어떤 모습인지 알고 싶을 때 |
| [What You Can Ask](/ko/start/what-you-can-ask/) | 더 좋은 prompt를 만들고 싶을 때 |
| [What Happens After You Ask](/ko/start/what-happens-after-you-ask/) | user-level system loop를 이해하고 싶을 때 |

Start section의 목표는 architecture가 필요해지기 전에 UMMAYA를 이해할 수 있게 만드는 것입니다. UMMAYA는 내부 구조를 먼저 설명하는 도구가 아니라, 흩어진 공공서비스를 사용자의 행정 결과 언어로 묶는 제품입니다.

## 보호된 작업 전에 신뢰 확인하기

identity, payment, certificate, welfare application, tax filing, official record change를 실험하기 전에는 Trust section을 읽어야 합니다. 이런 workflow에서 UMMAYA는 가장 조심스럽게 말하고 행동해야 합니다.

Trust page는 Live, Mock, Handoff, permission, consent, data, credential, local session, official handoff, explicit non-goal을 설명합니다. 독자는 public lookup과 protected action, preparation과 completion을 구분할 수 있어야 합니다.

## 상황별로 UMMAYA 사용하기

Use section은 실제 공공서비스 상황으로 구성되어 있습니다. emergency and safety, moving and housing, welfare, tax and payments, identity and certificates, sessions and receipts, troubleshooting이 그 축입니다.

각 page는 같은 실용 질문에 답해야 합니다. 무엇을 물어볼 수 있는가, 어떤 일이 일어나야 하는가, UMMAYA가 어디까지 행동할 수 있는가, 어디서 멈춰야 하는가, 다음에 사용자가 무엇을 해야 하는가입니다.

## Coverage와 Architecture 평가하기

Coverage page는 current capability, adapter evidence, target-state scenario, roadmap logic을 보여줍니다. Architecture page는 왜 UMMAYA가 Claude Code-style harness를 이식하는지, primitive가 어떻게 동작하는지, query engine이 retrieval, tool call, permission, stop reason을 어떻게 조정하는지 설명합니다.

지원 여부를 확인하려면 coverage를 읽고, national AX goal을 감당할 수 있는 설계인지 확인하려면 architecture를 읽습니다. 두 영역은 분리되어 있지만 같은 사실을 말해야 합니다. coverage가 현재 상태를 말하고, architecture가 그 상태를 확장 가능한 구조로 설명합니다.

## Build와 Reference

Build page는 adapter author와 maintainer를 위한 영역입니다. adapter authoring과 docs, generated metadata, deployment output을 aligned 상태로 유지하는 LLMOps를 설명합니다.

Reference page는 LLM-readable docs를 노출합니다. future agent는 human reader와 같은 boundary를 읽고, 오래된 claim이나 fallback translation을 다시 만들어내지 않아야 합니다.

## 읽는 규칙

페이지가 capability를 주장할 때는 state label과 evidence를 함께 확인합니다. task가 Live이면 무엇이 그것을 뒷받침하는지 문서가 말해야 합니다. Mock 또는 Handoff이면 사용자가 행동하기 전에 그 경계를 볼 수 있어야 합니다.

이 규칙이 UMMAYA 문서의 핵심입니다. UMMAYA는 국가 인프라를 AX하려는 야심을 갖지만, 문서는 현재 증거와 사용자 안전을 넘어 말하지 않습니다.
