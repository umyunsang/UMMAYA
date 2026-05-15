---
title: "현재 커버리지"
description: "현재 UMMAYA capability를 user task, status label, evidence source로 설명합니다."
llm_index: true
audience:
  - considering_user
  - public_sector_evaluator
  - maintainer
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs-site/src/data/generated/adapters.json
  - docs/api/README.md
---

Coverage는 UMMAYA가 evidence로 표현할 수 있는 public-service path를 뜻합니다. 어떤 domain의 모든 task가 오늘 완료 가능하다는 뜻은 아닙니다.

Coverage는 user outcome과 state label로 읽어야 합니다. Live, Mock, Handoff, Planned는 서로 다른 약속이며 문서는 이를 흐리면 안 됩니다.

## Coverage Summary

| User outcome | Current state | Evidence source |
|---|---|---|
| weather, forecast, warning, public safety lookup | Live | configured KMA 및 관련 public-data adapter |
| road accident와 hazard lookup | Live | configured KOROAD public-data adapter |
| hospital과 emergency information lookup | Live | configured HIRA, NMC, NFA119-style public adapter |
| location과 administrative area resolution | Live | configured JUSO, Kakao, SGIS-style location adapter |
| welfare public guidance | public guidance는 Live | configured MOHW public guidance/search surface |
| traffic fine payment와 welfare application submission | Mock | shape-faithful `send` adapter |
| Digital OnePass, simple auth, mobile ID, certificates, MyData | Mock 또는 Handoff | `check` mock adapter와 scenario docs |
| Government24/Hometax final submissions | Handoff 또는 target-state | official callable channel, credential, consent, artifacts 필요 |

이 표는 current-state map이지 모든 subtask에 대한 product promise가 아닙니다. 어떤 domain은 target-state scenario에 포함되면서 오늘은 Handoff일 수 있습니다.

## Coverage Claim 읽는 법

강한 coverage claim은 user task, state label, evidence 세 부분을 갖습니다. `Healthcare is supported`는 너무 넓습니다. `configured public adapter가 evidence를 반환하는 경우 nearby public hospital lookup은 Live`가 더 나은 claim입니다.

이 wording은 사용자가 public lookup, personal medical records, triage, emergency dispatch를 같은 capability로 오해하지 않게 합니다. 평가자에게도 inspect할 artifact를 제공합니다.

## Evaluator가 확인할 것

Evaluator는 false promotion을 찾아야 합니다. Mock을 official completion처럼 설명하거나, consent evidence 없는 protected workflow, source 없는 public-data answer, target-state channel을 current Live capability처럼 말하면 잘못된 페이지입니다.

adapter matrix, generated metadata, scenario matrix, architecture pages는 서로 일치해야 합니다. 한 surface가 Live라고 하고 다른 surface가 Handoff라고 하면 underlying evidence가 reconcile될 때까지 docs drift로 취급하세요.

## 사용자의 다음 행동

Live public lookup task부터 시작하세요. 그 다음 trust page를 읽은 뒤 Mock 또는 Handoff flow를 시도하세요. binding official action이 필요하면 UMMAYA가 live authority와 receipt evidence를 보여주지 않는 한 official service에서 계속해야 합니다.
