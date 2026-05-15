---
title: "Live、Mock 与 Handoff"
description: "这些状态标签让 UMMAYA 诚实说明自己实际能做什么。"
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs-site/src/data/generated/adapters.json
  - docs/api/README.md
---

Live、Mock、Handoff 是 UMMAYA 的 trust language。它们告诉用户：系统是真的调用了配置好的 channel，还是模拟了已知 workflow shape，还是因为下一步属于 official service 而停止。

这些标签不是实现细节。它们是 UMMAYA 避免听起来比 evidence 更有 authority 的方式。

## Live

Live 表示 UMMAYA 可以调用配置好的公共服务 channel，并把回答建立在 returned result 上。Live answer 应命名相关 source 或 adapter，总结 result，并停留在 result 能证明的范围内。

Live 不表示 domain 中所有动作都可用。weather lookup 可以是 Live，而 user-specific disaster-support application 仍是 Handoff。hospital public lookup 可以是 Live，而 medical triage 仍在 UMMAYA 边界之外。

## Mock

Mock 表示 UMMAYA 可以展示 workflow 的形状，但不会产生官方机构结果。Mock 对测试 tool calling、schemas、permission prompts、receipts 和 UX 很有价值，尤其是在 live credentials 或 official access 尚不可用时。

当 Mock 听起来像 official 时，它就很危险。mock payment 不是 paid。mock certificate 不是 issued。mock identity check 不是 identity verification。Mock 这个词必须出现在结果附近，而不能只藏在 developer-only metadata 里。

## Handoff

Handoff 表示 UMMAYA 可以准备或解释路径，但用户必须通过 official service 继续。当下一步需要 identity、payment、certificate issuance、tax filing、official record change，或 UMMAYA 不持有的其他 authority 时，Handoff 是正确结果。

好的 Handoff 仍然有用。它应命名 official service 或 category，解释 UMMAYA 准备了什么，指出没有做什么，并告诉用户要 live 路径需要什么 evidence 或 credential。

## 如何读状态标签

行动前先读 label。

| Label | What happened | How to treat the result |
|---|---|---|
| Live | 配置好的 channel 返回了 evidence | 在 stated scope 内使用结果 |
| Mock | 已知 workflow shape 被模拟 | 当作 demonstration，不是 official output |
| Handoff | UMMAYA 停在 official boundary | 通过 official service 继续 |
| Planned | domain 属于 target state | 不要当作 current capability |

如果 consequential workflow 的回答没有暴露 label，先要求 UMMAYA 澄清 state，再行动。

## 用户规则

信任 boundary，而不是流畅度。一句简短的 “Handoff required” 比一段暗示隐藏政府访问权的流畅回答更安全。

产品在可见地停止时也是正常工作的。National-infrastructure AX 不是消除官方 authority，而是在 authority 需要出现之前减少混乱。
