---
title: Domain Roadmap
description: UMMAYA가 domain을 target-state scenario에서 mock, live capability로 이동시키는
  방식입니다.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- eval/scenarios/national_ax_citizen_requests_v1.yaml
- docs/api/README.md
audience:
- considering_user
- public_sector_evaluator
- maintainer
---

domain roadmap은 UMMAYA가 과장 없이 성장하는 방식을 설명합니다. 어떤 domain은 live가 되기 전에도 national AX에 중요할 수 있지만 문서는 현재 state를 정직하게 label해야 합니다.

roadmap은 wishlist가 아닙니다. scenario, mock, live, 그리고 official channel과 credentials가 생긴 뒤 더 풍부한 live workflow로 이어지는 promotion ladder입니다.

## Target Domains

UMMAYA의 target map은 agency org chart가 아니라 citizen work를 따릅니다.

| Domain | Target user work |
|---|---|
| Safety and healthcare | public safety, hospital, emergency, weather, hazard information 찾기 |
| Housing and local records | moving, address, housing, local-service workflow 준비 |
| Welfare and household support | guidance 찾기, documents 준비, eligibility boundary 노출 |
| Tax, fines, payments, utilities | filing, payment path, receipt expectation, official handoff 준비 |
| Identity, certificates, MyData | official path, consent point, protected data flow 설명 |
| Labor, education, immigration, legal | multi-agency guidance와 target-state workflow mapping |

이 표는 demand를 정의합니다. 모든 row가 오늘 Live라는 뜻은 아닙니다.

## Promotion Logic

domain은 public shape가 책임 있게 mirror될 만큼 명확할 때 scenario에서 Mock으로 이동합니다. Mock에서 Live로 이동하려면 official callable channel, 필요한 경우 credential path, schema, permission metadata, sanitized request/response artifact, test strategy가 필요합니다.

promotion rule은 문서가 ambition을 false current-state claim으로 바꾸는 것을 막습니다. official channel이 없을 때도 target-state domain은 Handoff로 가치 있을 수 있습니다.

## Planned Domain이 중요한 이유

National AX는 전체 citizen journey로 평가됩니다. student portfolio project가 오늘 모든 protected system을 live-complete할 수는 없지만, 각 domain에 대해 caller architecture, evidence ladder, honest gap을 보여줄 수 있습니다.

Planned domain은 query engine, adapter model, permission UX, docs를 future-facing test로 만듭니다. 또한 UMMAYA가 더 완성되려면 public infrastructure에 callable, consented, LLM-safe channel이 필요하다는 점을 보여줍니다.

## Roadmap Evidence

Roadmap claim은 최소 하나의 artifact로 trace되어야 합니다. target-state scenario, adapter metadata, public API documentation, policy citation, schema, fixture, issue/spec 중 하나가 필요합니다. 아무것도 없으면 planned capability가 아니라 research target으로 설명해야 합니다.

이 evidence rule은 contributor에게 다음 action을 알려줍니다. research, mock adapter, live credential validation, permission design, docs update 중 무엇이 필요한지 알 수 있습니다.

## 다음 단계

roadmap은 [Current Coverage](/ko/coverage/current-coverage/)와 [Adapter Matrix](/ko/coverage/adapter-matrix/)와 함께 읽으세요. 세 문서는 서로 다른 질문에 답합니다. 사용자가 무엇을 필요로 하는지, UMMAYA가 지금 무엇을 할 수 있는지, promotion을 정당화할 evidence가 무엇인지입니다.
