---
title: Sessions、Receipts 与 History
description: 理解 UMMAYA 如何通过 session、receipt 和 context compression 让长 workflow 可检查。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- specs/033-permission-v2-spectrum-consent-ledger/spec.md
audience:
- citizen_user
- public_sector_evaluator
- maintainer
---

Sessions、receipts 和 history 让 UMMAYA 在第一次回答之后仍然可检查。National AX workflows 可以跨多轮：location 被解析，public information 被取回，protected boundary 出现，用户稍后返回，系统必须记得它为什么停下。

目的不是永久保存一切。目的是保留足够的 structured evidence，让用户、evaluator 或 maintainer 理解发生了什么、允许了什么、什么是 Mock、什么仍需要 official path。

## Sessions

session 应保留公共服务 flow 的 working context：用户请求、resolved location、selected adapter、permission state、tool result、stop reason 和 final answer。没有这种 continuity，多步骤公共服务任务会退化为重复聊天。

可用时，用类似命令恢复：

```bash
ummaya resume <session-id>
```

恢复的 session 不应静默升级 authority。如果上一轮停在 Handoff，下一轮仍应知道 protected step 没有完成。

## Receipts

receipt 应让 permission 和 action state 可见。它应识别 adapter、mode、purpose、timestamp、policy citation、outcome，以及 result 是 Live 还是 Mock。

mock receipt 不是 agency receipt。它是 UMMAYA 模拟 workflow shape 的 evidence。receipt 必须标出 state，避免用户把 mock 和 official completion 混淆。

| Receipt field | Why it matters |
|---|---|
| Adapter and primitive | Shows what tool path ran |
| Mode | Distinguishes Live, Mock, and Handoff |
| Purpose | Explains why the action was attempted |
| Permission or consent state | Shows whether protected work was allowed |
| Outcome and stop reason | Explains what happened and what did not |

## History

history 应帮助用户回答实际问题：我问了什么，找到了什么 public information，哪一步需要 consent，哪个 official service 还剩下，我下一步做什么。

history 不应把 sensitive data 藏在友好的 transcript 里。如果 protected data 出现，它必须遵守与 runtime flow 相同的 local-session 和 consent rules。如果某字段对未来 reasoning 或 inspection 不必要，就不应仅为方便而保留。

## Context Compression

context compression 支持长 session：它保留有用 state，同时防止 model context 变得不可管理。它应压缩 reasoning surface，而不是抹掉 evidence boundary。

如果 compression 从 model prompt 中移除细节，generated outputs 和 receipts 仍需要足够结构用于 inspection。compressed context 应保留 resolved location、adapter result summary、permission decision、Live/Mock/Handoff state 和 stop reason。

## Recovery

如果 session 无法恢复或 receipt 缺失，UMMAYA 应说明什么 evidence 不可用，并避免 completion claims。缺失 receipt 应把强措辞改成谨慎措辞：prepared、found、suggested、handed off，而不是 filed、paid、issued 或 approved。
