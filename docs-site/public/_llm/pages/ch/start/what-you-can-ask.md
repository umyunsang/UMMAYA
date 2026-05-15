---
title: 你可以问什么
description: 按公共服务结果来 prompt UMMAYA，而不是按 agency API 或内部 adapter 名称。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs-site/src/data/generated/adapters.json
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- new_user
- active_user
- public_sector_evaluator
---

向 UMMAYA 请求公共服务结果，而不是请求一个内部 adapter。系统应自行判断请求需要 `locate`、`find`、`check`、`send`，还是需要 Handoff。

好的 prompt 会给出用户处境、地点或 domain、想要的结果，以及 evidence expectation。除非 agency 本身就是用户要求，否则不需要先说机构名。

## 最好的 prompt 形状

不确定时使用这个形状：

```text
I am trying to <public-service outcome>.
Use official/public information where possible.
Show what UMMAYA can do now, what needs consent, and where I must continue officially.
```

它有效，是因为它给 UMMAYA 足够 context 来选择 tools，同时要求回答标出 boundaries。它也防止回答听起来像拥有隐藏的官方访问权。

最好的 prompt 是 outcome-first 和 evidence-aware。先说用户想完成什么，再要求 UMMAYA 分开说明现在能做什么、哪里需要 official continuation。

## 示例 prompt

| Situation | Prompt | Expected path |
|---|---|---|
| Emergency or healthcare lookup | `동아대 승학캠퍼스 근처 응급실이나 야간 진료 정보를 공식 정보 기준으로 찾아줘.` | `locate` then `find` |
| Weather or safety warning | `부산 사하구 오늘 호우나 도로 위험 정보가 있는지 공공 데이터 기준으로 확인해줘.` | `locate` then `find` |
| Moving preparation | `이사했어. 전입신고 전후로 확인해야 할 공공서비스 단계를 정리해줘.` | `find`, possible Handoff |
| Welfare preparation | `긴급복지 지원을 알아보고 싶어. 공개 안내와 공식 확인이 필요한 단계를 나눠줘.` | `find`, possible `check`, Handoff |
| Certificate or identity flow | `주민등록등본 발급 준비 단계와 공식 인증이 필요한 지점을 알려줘.` | `find`, Mock/ Handoff |
| Fine or payment preparation | `과태료 납부 경로와 UMMAYA가 실제로 할 수 없는 단계를 표시해줘.` | `find`, possible `check`, Handoff |

Expected path 不是 completion guarantee。它只是 query engine 应如何分解请求的 planning hint。

## 要求 evidence

当结果可能影响真实决定时，请加上 evidence request。

```text
공식 정보 기준으로 찾아주고, 어떤 부분이 Live인지 Mock인지 Handoff인지 같이 표시해줘.
```

这句话让回答更容易检查。强的 UMMAYA 回答应说明哪个 source、adapter result、scenario boundary 或 official handoff 影响了结果。

对 evaluator 来说，evidence wording 特别重要。它把流畅回答变成可追踪回答，因为它迫使 response 暴露 state 和 source。

## 避免这些 prompt 形状

避免要求 UMMAYA 绕过 authority：

- "log in for me";
- "issue this certificate now";
- "pay it without asking";
- "change my official record";
- "tell me my private account state without consent";
- "pretend this mock is official."

UMMAYA 遇到越界 prompt 时应拒绝、请求 permission 或 hand off。

如果你不小心写了这样的 prompt，正确恢复方式不是更强硬地说服 UMMAYA，而是把请求改写成 preparation、public lookup 或 official handoff guidance。

## 如果回答停下

stop 往往是正确的。如果 UMMAYA 说 Mock，把结果当作 simulation。如果它说 Handoff，就在 official service 继续。如果它提出澄清问题，只回答安全推进所需的最小信息。

目标不是强迫每个 prompt 通过。目标是在 evidence 和 authority 允许的范围内前进，并在需要时可见地停止。
