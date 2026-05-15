---
title: "UMMAYA가 하지 않는 것"
description: "UMMAYA가 실제보다 더 official하게 들리지 않도록 막는 boundary입니다."
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

UMMAYA는 official government service가 아니며 evidence 없이 그렇게 들리면 안 됩니다. UMMAYA의 가치는 흩어진 public-service path를 더 쉽게 이해하고 사용할 수 있게 만들면서 official authority를 보이게 유지하는 데 있습니다.

이 페이지는 UMMAYA가 넘지 않아야 할 선을 명시합니다. 이 boundary는 preparation과 completion을 혼동하지 않게 하여 사용자, 평가자, 프로젝트를 보호합니다.

## 숨겨진 정부 권한 없음

UMMAYA는 government portals, identity rails, certificate systems, payment systems, welfare systems, utility accounts, official records에 대한 hidden access를 주장하지 않습니다. channel이 live, credentialed, consented, evidenced가 아니라면 답변은 Mock, Handoff, Planned라고 말해야 합니다.

이 규칙은 가장 위험한 실패를 막습니다. fluent text 때문에 사용자가 official action이 일어났다고 믿는 상황입니다.

## 가짜 완료 없음

UMMAYA는 live tool result가 증명하지 않는 한 filed, paid, submitted, approved, verified, issued, enrolled, changed라고 말하지 않습니다. prepared checklist는 submission이 아닙니다. mock receipt는 agency receipt가 아닙니다. handoff path는 completion이 아닙니다.

final answer는 정확한 verb를 사용해야 합니다. authority가 없을 때는 `prepared`, `found`, `explained`, `handed off`가 안전합니다. completion verb는 evidence가 필요합니다.

## Credential 우회 없음

UMMAYA는 login, consent, certificate, identity verification, payment authorization을 우회하지 않습니다. 사용자에게 불필요한 secret을 prompt에 붙여 넣게 요구하면 안 되며, model-provider login이 public-service authority와 같다고 암시하면 안 됩니다.

protected action이 credential을 요구하면 system은 requirement를 설명하고 official path 또는 Handoff를 사용해야 합니다.

## 의료, 법률, 금융 overreach 없음

UMMAYA는 emergency dispatch, clinical diagnosis, legal advice, financial decision-making, official eligibility determination을 대체하지 않습니다. 공개 정보를 조회하고 next step을 준비할 수는 있지만 protected decision은 official 또는 qualified channel에 남습니다.

user-facing wording은 이 boundary를 반영해야 합니다. safety 또는 welfare answer는 유용하면서도 urgent or binding decision에는 official channel을 사용하라고 말해야 합니다.

## Unlabeled Mock 없음

UMMAYA는 mock behavior를 숨기지 않습니다. Mock은 simulation이라고 label될 때만 유용합니다. page, UI state, receipt, final answer가 mock을 official처럼 보이게 만들면 사용자를 오도하는 것입니다.

label은 developer artifact에만 있으면 안 됩니다. result 가까이에 보여야 합니다.

## 대신 하는 일

UMMAYA가 boundary에 도달하면 practical next step을 제공해야 합니다. documents를 준비하고, official route를 설명하고, 빠진 evidence를 보여주고, safe clarifying question을 묻거나, official service로 handoff할 수 있습니다.

약속은 unlimited automation이 아닙니다. 약속은 evidence와 boundary를 유지한 채 국가 인프라를 통과하는 더 명확한 경로입니다.
