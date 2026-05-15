---
title: 복지와 가구 지원
description: 복지 안내, 준비, eligibility boundary, official application handoff를 이해합니다.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs-site/src/data/generated/adapters.json
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- citizen_user
- considering_user
- public_sector_evaluator
---

복지와 가구 지원 workflow는 가치가 큽니다. 여러 기관, eligibility rules, household documents, local office를 자주 넘나들기 때문입니다. 동시에 helpful-sounding answer가 official eligibility로 오해될 수 있어서 위험도 큽니다.

UMMAYA는 사용자가 공개 경로를 이해하고 다음 단계를 준비하게 도와야 합니다. 그러나 live, consented, official check가 증명하지 않는 한 승인, 대상자, 선정, 신청 완료를 말하면 안 됩니다.

## 좋은 프롬프트

공개 안내, 준비, boundary 표시를 요청하세요.

```text
기초생활보장이나 긴급복지 지원을 알아보고 싶어. 공개 안내 기준으로 준비할 서류와 공식 확인이 필요한 단계를 나눠서 알려줘.
```

이 프롬프트는 UMMAYA가 false eligibility decision을 만들지 않으면서 도움을 줄 수 있게 합니다. guidance와 preparation을 요청하고 official approval을 요구하지 않습니다.

## 예상 흐름

UMMAYA는 먼저 공개 안내를 조회한 뒤 일반 requirement와 user-specific check를 분리해야 합니다. household income, assets, residency, disability, childcare, crisis condition은 protected data와 official verification이 필요할 수 있습니다.

```text
사용자가 welfare support를 질문
  -> `find`가 공개 program guidance를 조회
  -> `check`가 지원되는 경우 eligibility-like boundary를 확인
  -> live official channel과 consent가 있을 때만 `send`
  -> 아니면 Handoff가 official path를 표시
```

이 순서는 public explanation과 protected eligibility를 분리합니다. 공식 신청 전에 멈춰도 답변은 유용할 수 있습니다.

## 도움이 되지만 정직한 언어

final answer는 live evidence가 더 강한 표현을 뒷받침하지 않는 한 preparation language를 사용해야 합니다. 좋은 표현은 `public guidance suggests`, `documents to prepare`, `official confirmation required`, `UMMAYA cannot determine eligibility in this session`, `continue through the official service`입니다.

| 사용자 필요 | UMMAYA 역할 | 경계 |
|---|---|---|
| program discovery | `find` | 공개 안내 |
| document checklist | retrieved guidance 기반 synthesis | preparation only |
| eligibility-like check | valid classification과 consent가 있는 `check` | Live, Mock, 또는 Handoff |
| application | live channel과 consent가 있는 `send` | 아니면 Handoff |

위험한 표현은 live evidence 없는 `approved`, `eligible`, `benefit granted`, `application submitted`입니다. 이런 단어는 사용자의 결정을 바꾸므로 proof가 필요합니다.

## 좋은 답변의 구성

좋은 복지 답변은 사용자의 다음 decision을 중심으로 구성되어야 합니다. 가능한 program, 공개 criteria 요약, 준비 문서, official service 또는 office, UMMAYA가 수행하지 못한 step을 말해야 합니다.

평가자에게는 state label도 보여야 합니다. Mock eligibility check를 사용했다면 final text는 Mock이라고 말해야 합니다. 다음 단계가 official application이라면 Handoff라고 말해야 합니다.

## 복구

사용자가 진행할 수 없으면 UMMAYA는 가장 작은 safe clarifying detail을 묻거나 official path를 알려야 합니다. 불필요한 sensitive data를 요구하면 안 됩니다. tool path와 consent model이 justify하지 않는 한 household or financial detail을 수집하면 안 됩니다.

제품 가치는 practical honesty입니다. 사용자는 더 명확한 경로를 얻고, UMMAYA는 guidance를 fake authority로 바꾸기 전에 멈춥니다.
