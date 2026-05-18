---
title: UMMAYA 文档
description: 用于使用、评估和扩展 UMMAYA 这个韩国 national-infrastructure AX harness 的文档。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs/research/ummaya-docs-audience-audit-2026-05-15.md
- docs/vision.md
audience:
- non_user
- considering_user
- new_user
- public_sector_evaluator
---

UMMAYA 是面向 Korean national-infrastructure AX 的 conversational agent harness。用户通过一个 approachable query surface 请求公共服务结果，系统处理 decomposition、tool selection、permission boundaries、evidence 和 official handoff。

本文件面向四个读者阶段：判断 UMMAYA 是否有用的人、第一次运行 packaged CLI 的新用户、检查 claim 是否 grounded 的 evaluator，以及扩展 adapter surface 的 contributor。

## 从这里开始

如果你是新读者，请按顺序阅读 Start section。它说明 user problem、current capability、installation path、first successful session、prompt shape，以及 query 之后会发生什么。

| Page | Use it when |
|---|---|
| [Why UMMAYA](/ch/start/why-ummaya/) | 需要理解 product purpose |
| [What UMMAYA Can Do Today](/ch/start/what-ummaya-can-do-today/) | 想看 current capability 和 limits |
| [Quickstart](/ch/start/quickstart/) | 想安装并运行 CLI |
| [First Successful Session](/ch/start/first-successful-session/) | 想知道成功的第一次运行是什么样子 |
| [What You Can Ask](/ch/start/what-you-can-ask/) | 想写更好的 prompts |
| [What Happens After You Ask](/ch/start/what-happens-after-you-ask/) | 想理解 user-level system loop |

Start section 应在 architecture 变得必要之前让 UMMAYA 可理解。

## 受保护工作前先读 Trust

在测试 identity、payments、certificates、welfare applications、tax filing 或 official record changes 前，请阅读 Trust section。这些 workflows 是 UMMAYA 最必须谨慎的地方。

Trust pages 解释 Live、Mock、Handoff、permission、consent、data、credentials、local sessions、official handoff 和 explicit non-goals。它们帮助用户区分 public lookup 与 protected action，以及 preparation 与 completion。

## 按情况使用 UMMAYA

Use section 按真实公共服务情况组织：emergency and safety、moving and housing、welfare、tax and payments、identity and certificates、sessions and receipts、troubleshooting。

每个页面都应回答同样的 practical questions：我能问什么、应该发生什么、UMMAYA 能在哪里行动、必须在哪里停止、我下一步做什么。

## 评估 Coverage 与 Architecture

Coverage pages 显示 current capability、[Live Adapters](/ch/coverage/live-adapters/)、adapter evidence、target-state scenarios 和 roadmap logic。Architecture pages 解释 UMMAYA 为什么迁移 Claude Code-style harness、primitives 如何工作、query engine 如何协调 retrieval、tool calls、permission 和 stop reasons。

使用 coverage 检查支持范围；使用 architecture 检查 system design 是否能支撑 national AX goal。

## Build 与 Reference

Build pages 面向 adapter authors 和 maintainers。它们解释 adapter authoring，以及让 docs、generated metadata、deployment outputs 保持 aligned 的 LLMOps。

Reference pages 暴露 LLM-readable docs，让 future agents 能读取与 human readers 相同的 boundaries。

## 阅读规则

每当页面做 capability claim，请寻找 state label 和 evidence。如果 task 是 Live，文档应说明支撑它的内容。如果是 Mock 或 Handoff，文档应在用户行动前让 boundary 可见。
