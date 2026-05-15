---
title: "신원, 증명서, MyData"
description: "대부분 Mock 또는 official Handoff가 필요한 신원 기반 workflow를 이해합니다."
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs-site/src/data/generated/adapters.json
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

신원, 증명서, MyData는 대한민국 국가 인프라 AX의 핵심 표면이지만 UMMAYA가 가장 보수적으로 행동해야 하는 영역입니다. 유용한 assistant는 경로를 설명하고, 사용자가 준비할 것을 정리하고, permission shape를 보여줄 수 있습니다. 그러나 live official channel, credential, consent, evidence 없이 신원 확인, 증명서 발급, 문서 서명, 개인 데이터 조회를 완료한 것처럼 말하면 안 됩니다.

이 페이지는 신원 기반 작업에서 UMMAYA가 오늘 안전하게 할 수 있는 일을 이해하려는 사용자를 위한 문서입니다. 요약하면 공개 설명은 유용하고, mock flow는 형태를 보여주며, official Handoff는 자주 올바른 정지점입니다.

## 좋은 프롬프트

보호된 action을 조용히 완료해 달라고 하지 말고 준비, 공식 경로 설명, permission boundary를 요청하세요.

```text
주민등록등본 발급을 준비하려고 해. 필요한 인증 단계와 공식 서비스에서 이어서 해야 할 일을 정리해줘.
```

```text
MyData로 필요한 서류를 확인하는 흐름을 보여줘. 실제 개인 데이터 접근 없이 Mock 기준으로 어디서 consent가 필요한지 알려줘.
```

이 프롬프트는 UMMAYA가 숨은 권한을 주장하지 않고 설명과 준비를 하게 합니다. 사용자가 “지금 발급해줘” 또는 “대신 로그인해줘”라고 묻는다면 시스템은 access를 발명하지 말고 permission 또는 Handoff로 이동해야 합니다.

## 예상 흐름

신원 기반 작업은 보통 `find`에서 시작하고, `check`로 이동할 수 있으며, `send` 전에 멈추는 경우가 많습니다. 공개 안내는 공식 서비스가 요구하는 것을 설명할 수 있습니다. Mock은 consent와 schema shape를 보여줄 수 있습니다. Handoff는 live authority가 없을 때 사용자를 공식 서비스로 보냅니다.

| 단계 | UMMAYA 동작 | 경계 |
|---|---|---|
| 공개 설명 | `find`가 공식 안내 또는 공개 자료를 조회 | 설명 전용 |
| 신원 경계 | `check`가 consent와 credential 요구를 드러냄 | live authority 없으면 Mock |
| 증명서 또는 MyData action | 공식 channel, credential, consent, evidence가 있을 때만 `send` | 아니면 Handoff |

중요한 것은 순서입니다. UMMAYA는 공개 설명에서 바로 “증명서 발급 완료”로 뛰면 안 됩니다. 어느 단계가 보호되었고 왜 공식 경로가 이어받아야 하는지 보여줘야 합니다.

## 보여야 하는 것

신원 답변은 어떤 데이터가 관련되는지, 어떤 consent가 필요한지, 어떤 시스템이 공식인지, UMMAYA가 무엇을 하지 않았는지 말해야 합니다. Live, Mock, Handoff label은 보호된 단계 가까이에 보여야 하며 footnote에 숨으면 안 됩니다.

평가자에게도 이 페이지는 contract입니다. 올바른 flow는 adapter mode, permission decision, stop reason이 final wording과 일치해야 합니다. final answer가 “issued”라고 말했는데 flow가 Mock까지만 갔다면 문서와 제품 언어가 잘못된 것입니다.

## Mock이 여전히 중요한 이유

Mock은 명확히 표시될 때 가치가 있습니다. live credential이나 official channel이 준비되기 전에 consent prompt, schema validation, tool calling, receipt, handoff copy를 검증하게 해줍니다.

하지만 mock이 official처럼 보이면 가치는 사라집니다. Mock identity verification은 identity verification이 아닙니다. Mock certificate result는 certificate가 아닙니다. 답변은 이 차이를 놓칠 수 없게 만들어야 합니다.

## 복구

UMMAYA가 Handoff하면 사용자는 무엇을 이어가야 하는지 알아야 합니다. 공식 서비스 이름, 필요한 인증 방식, 준비할 문서나 데이터, UMMAYA가 수행하지 못한 정확한 단계를 알려야 합니다. 그래야 Handoff가 회피가 아니라 유용한 안내가 됩니다.

제품 약속은 “UMMAYA가 신원 rail을 우회한다”가 아닙니다. 약속은 “공식 신원 rail이 이어받아야 하는 지점까지 혼란을 줄인다”입니다.
