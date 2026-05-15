---
title: "Official Handoff"
description: "UMMAYA가 official service만 완료할 수 있는 경계에 도달했을 때 일어나야 하는 일입니다."
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs/api/README.md
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

Official Handoff는 UMMAYA가 정부처럼 가장하지 않으면서도 유용하게 남는 방식입니다. workflow가 identity verification, certificate issuance, payment, filing, application submission, official record change에 도달하면 path를 준비하고 멈추는 것이 자주 가장 안전한 결과입니다.

Handoff는 방치처럼 느껴지면 안 됩니다. 좋은 handoff는 무엇이 준비되었는지, 무엇이 official로 남았는지, official service로 무엇을 가져가야 하는지 알려줍니다.

## 좋은 Handoff의 구성

좋은 Handoff answer는 다섯 가지를 포함해야 합니다.

| 요소 | 목적 |
|---|---|
| Official continuation path | 실제 authority가 어디 있는지 알려줌 |
| Prepared context | UMMAYA가 이미 해석하거나 찾은 것을 보존 |
| Missing authority | 왜 멈췄는지 설명 |
| Required evidence or credential | official step에 필요한 것을 알려줌 |
| Next action | stop을 usable plan으로 바꿈 |

답변이 단지 “official site로 가세요”라고만 말하면 너무 얇습니다. live proof 없이 “completed”라고 말하면 unsafe합니다.

## 예시

```text
UMMAYA prepared the certificate issuance path and identified the official authentication step.
It did not verify identity or issue the certificate in this session.
Continue through the official certificate service with your required authentication method.
```

이 wording은 preparation과 completion을 분리하기 때문에 유용합니다. 또한 무엇이 일어나지 않았는지도 알려줍니다.

## Handoff가 product feature인 이유

Handoff는 limitation처럼 보일 수 있지만 safety design의 일부입니다. 국가 인프라 업무는 legal authority, personal data, money, official records를 넘나듭니다. authority를 증명할 수 없는 system은 명확히 멈춰야 합니다.

사용자는 그 stop 전까지 confusion이 줄어드는 것만으로도 이익을 얻습니다. UMMAYA는 route를 설명하고, documents를 준비하고, likely consent point를 식별하고, official step에 context를 넘길 수 있습니다.

## Handoff가 Live가 되는 방식

Handoff path가 Live가 되려면 official callable channel, credential path, schema, permission metadata, sanitized artifacts, behavior를 증명하는 tests가 필요합니다. target state가 바람직하다는 이유만으로 Handoff domain을 Live로 승격하면 안 됩니다.

promotion은 사용자 trust decision을 바꿉니다. 그래서 wording이 바뀌기 전에 evidence가 먼저 바뀌어야 합니다.

## 복구

사용자가 Handoff 이후 계속하려면 UMMAYA는 official service를 우회하는 대신 준비를 도와야 합니다. 무엇을 가져가야 하는지, 어떤 login이나 certificate가 필요할 수 있는지, 이전 context 중 무엇을 재사용해야 하는지 요약할 수 있습니다.

올바른 close는 실용적입니다. `UMMAYA stopped here because official authority is required; here is the next official step.`
