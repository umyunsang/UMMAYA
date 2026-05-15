---
title: 세션, 영수증, 기록
description: 긴 workflow가 session, receipt, context compression을 통해 inspect 가능하게 유지되는
  방식을 설명합니다.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- specs/033-permission-v2-spectrum-consent-ledger/spec.md
audience:
- citizen_user
- public_sector_evaluator
- maintainer
---

Sessions, receipts, history는 UMMAYA 답변 이후에도 workflow를 inspect 가능하게 만듭니다. 국가 AX workflow는 여러 turn에 걸칠 수 있습니다. location이 해석되고, 공개 정보가 조회되고, protected boundary가 나타나고, 사용자가 나중에 돌아왔을 때 시스템은 왜 멈췄는지 기억해야 합니다.

목적은 모든 것을 영원히 저장하는 것이 아닙니다. 사용자가 무슨 일이 있었는지, 무엇이 허용되었는지, 무엇이 Mock인지, 무엇이 official path를 요구하는지 이해할 만큼의 structured evidence를 보존하는 것입니다.

## Sessions

session은 public-service flow의 working context를 보존해야 합니다. user request, resolved location, selected adapter, permission state, tool result, stop reason, final answer가 포함될 수 있습니다. 이 continuity가 없으면 multi-step public-service task는 workflow가 아니라 반복 대화가 됩니다.

가능할 때는 다음처럼 resume합니다.

```bash
ummaya resume <session-id>
```

resume된 session은 authority를 조용히 upgrade하면 안 됩니다. 이전 turn이 Handoff에서 멈췄다면 다음 turn도 protected step이 완료되지 않았음을 알아야 합니다.

## Receipts

receipt는 permission과 action state를 보이게 해야 합니다. adapter, mode, purpose, timestamp, policy citation, outcome, Live/Mock 여부를 식별해야 합니다.

mock receipt는 agency receipt가 아닙니다. workflow shape를 simulation했다는 evidence입니다. 사용자가 official completion과 혼동하지 않도록 반드시 label이 있어야 합니다.

| Receipt field | 중요한 이유 |
|---|---|
| Adapter and primitive | 어떤 tool path가 실행됐는지 보여줌 |
| Mode | Live, Mock, Handoff를 구분 |
| Purpose | action이 왜 시도됐는지 설명 |
| Permission or consent state | protected work 허용 여부를 보여줌 |
| Outcome and stop reason | 무엇이 일어났고 무엇이 일어나지 않았는지 설명 |

## History

history는 사용자가 실용적인 질문에 답하게 해야 합니다. 내가 무엇을 물었는지, 어떤 공개 정보가 발견되었는지, 어떤 단계가 consent를 요구했는지, 어떤 official service가 남았는지, 다음에 무엇을 해야 하는지 확인할 수 있어야 합니다.

history는 친절한 transcript 안에 sensitive data를 숨기면 안 됩니다. protected data가 나타나면 runtime flow와 같은 local-session, consent rules를 따라야 합니다. future reasoning이나 inspection에 불필요한 field는 편의만으로 보존하면 안 됩니다.

## Context Compression

Context compression은 long session에서 유용한 state를 유지하면서 model context가 관리 불가능하게 커지는 것을 막습니다. 압축은 reasoning surface를 줄이는 것이지 evidence boundary를 지우는 것이 아닙니다.

compression이 model prompt에서 detail을 제거하더라도 generated outputs와 receipts는 inspection에 충분한 구조를 가져야 합니다. compressed context는 resolved location, adapter result summary, permission decision, Live/Mock/Handoff state, stop reason을 보존해야 합니다.

## 복구

session이 resume되지 않거나 receipt가 없으면 UMMAYA는 어떤 evidence가 unavailable인지 말하고 completion claim을 피해야 합니다. missing receipt는 강한 표현을 cautious wording으로 낮춰야 합니다. filed, paid, issued, approved가 아니라 prepared, found, suggested, handed off라고 말해야 합니다.
