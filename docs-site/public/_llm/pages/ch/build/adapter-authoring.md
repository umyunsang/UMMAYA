---
title: Adapter Authoring
description: 贡献者如何把一个公共服务 channel 包装成带 evidence 的 UMMAYA adapter。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs/api/README.md
- docs/plugins/security-review.md
audience:
- adapter_author
- maintainer
- public_sector_evaluator
---

adapter 是 UMMAYA 扩展的单位。一个 adapter 应把一个公共服务 channel、mockable policy shape 或 official handoff path 包装成一个 tool entry，并带有 schema、citation、state label 和 permission metadata。

adapter authoring 不只是 backend work。adapter 决定文档可以诚实声称什么、model 可以调用什么、用户会看到什么 permission、final answer 可以引用什么 evidence。

## 先选择正确状态

写代码前先分类 channel。

| State | Use when | Documentation consequence |
|---|---|---|
| Live | official callable channel and credential path exist | docs may describe evidence-backed execution within scope |
| Mock | channel shape is known or policy-mandated, but live access is unavailable | docs must label simulation |
| Handoff | next step belongs to an opaque official service | docs should prepare the path and stop |
| Planned | target-state demand exists but shape/evidence is not ready | docs may describe roadmap, not current capability |

这个判断必须最先发生，因为它改变 schema、tests、permission wording 和 user-facing claims。

## Required Contents

有用 adapter 需要足够结构，让 query engine 和 docs 对同一事实达成一致。

| Requirement | Why it matters |
|---|---|
| primitive | ties the adapter to `locate`, `find`, `check`, or `send` |
| input/output schema | prevents plausible but invalid tool calls |
| Live/Mock/Handoff state | controls user-facing authority language |
| permission tier | separates public lookup from protected action |
| public or policy citation | prevents UMMAYA-invented authority |
| fixture or artifact | makes Mock or Live behavior inspectable |
| search hints | lets retrieval find the adapter from citizen language |

如果 adapter 缺这些 fields，文档不应把它作为用户 workflow 的 evidence 来推广。

## 用户文档要求

每个影响 user-facing coverage 的 adapter 都需要 prose。prose 应说明 adapter 支持什么、不支持什么、适用什么 status label，以及什么 answer language 是安全的。

例如，public weather adapter 可以支持 Live weather lookup。它不能支持 personal disaster benefit eligibility，除非存在另一个 protected path。文档应把这些 claim 分开。

## Promotion Requirement

从 Mock promoted to Live 需要 evidence，而不是 optimism。项目需要 official endpoint 或 channel validation、credential handling、schema validation、permission metadata、sanitized request/response artifacts，以及不会在 CI 中调用 live citizen infrastructure 的 tests。

promotion 后，重新生成 docs surfaces 并 review 受影响页面：

```bash
npm run docs:generate
npm run docs:check
```

如果 generated adapter metadata 改变，user docs 和 LLM-readable docs 必须一起改变。

## Failure Mode

常见失败是先加 tool，再写宽泛 marketing copy。UMMAYA 应反过来：先证明 channel shape，定义 boundary，然后只让文档声称 evidence 支持的内容。
