---
title: Harness Migration
description: 为什么 UMMAYA 要把 Claude Code 的 harness 迁移到国家基础设施 AX。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs/vision.md
- docs/requirements/ummaya-migration-tree.md
- docs/api/README.md
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- citizen_user
- considering_user
- public_sector_evaluator
---

UMMAYA 的架构从一个产品判断开始：韩国国家基础设施需要一个面向用户的 agent harness。用户不应该先判断问题属于政府24、Hometax、Wetax、地方政府、身份认证、证书、公共缴费、天气源还是 data.go.kr API。用户只需要说出结果，harness 负责拆解、取证、调用工具、询问权限，并在没有官方权限时停止。

Claude Code 是参考对象，因为它已经证明了这种 harness 形态：用户说出目标，系统组装 context，模型调用有边界的工具，权限 UI 暴露风险，session 保留上下文，终端显示可检查的过程。UMMAYA 把这个结构迁移到公共服务领域。

下面的 architecture diagram 每张只回答一个问题。Context view 回答“UMMAYA 位于哪里？”Loop view 回答“用户提问后第一轮发生什么？”Primitive、retrieval、permission、stop reason 在更深入的页面中分别放大。

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-01-national-ax-context.svg" alt="最小 C4 context diagram：Citizen asks UMMAYA; UMMAYA reasons with K-EXAONE and uses Public APIs or Official Channels." />
  <figcaption>Context view：一个 query surface、一个 model、两个公共服务 boundary。</figcaption>
</figure>

## 两个被允许的替换

| Harness 部分 | Claude Code | UMMAYA |
|---|---|---|
| Model provider | Claude 系列 | FriendliAI Serverless 上的 K-EXAONE |
| Tool surface | 文件、shell、git、代码工具 | 韩国公共服务 adapter 与 official handoff path |

其余纪律保持稳定：query loop、tool-call protocol、permission request path、context assembly、terminal UI、session persistence、evidence-oriented debugging。

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-02-query-loop.svg" alt="最小 C4 dynamic diagram：Citizen, UI, Query Engine, Sessions, Registry, K-EXAONE Client, K-EXAONE, Answer." />
  <figcaption>Query loop view：ask、route、context、select、reason、answer。</figcaption>
</figure>

这些 diagram 从 `docs/architecture/c4/workspace.dsl` 生成。修改 architecture model 后，请运行 `npm run docs:c4` 重新生成。每张 diagram 只保留足以解释一个读者任务的内容。

## 保持稳定的部分

稳定的是操作循环：收集 context，选择有边界的 action，执行 action，把结果投回 conversation，并重复直到任务完成或安全停止。这一循环让 UMMAYA 不只是聊天记录，而是一个可检查的公共服务 client。

UI 的可见性同样重要。用户应该看到系统先解析位置，再查询公开信息，再到达受保护边界。如果顺序不可见，最终答案就无法被信任。

## 发生变化的部分

UMMAYA 改变的是风险模型。开发者 harness 关心危险 shell command、文件覆盖、项目状态。国家基础设施 harness 关心 PIPA、身份验证、证书、税务、缴费、官方记录和机构政策。

| Claude Code concern | UMMAYA concern | Discipline |
|---|---|---|
| Dangerous shell command | Protected public-service action | 权限必须明确并有政策 citation |
| File overwrite | Official record change | 没有 live authority 就不能声称完成 |
| Project memory | Citizen session context | 本地 session 必须可检查 |
| Tool result | Public-service evidence or receipt | Final answer 必须基于返回结果 |
| Context window | Long administrative workflow | Context assembly 和 compression 要保留决策理由 |

## 一次请求中的迁移路径

```text
用户提出 outcome
  -> query engine 保留 intent 和 session context
  -> retrieval 缩小 public-service adapter 候选
  -> K-EXAONE 选择 locate、find、check 或 send
  -> permission pipeline 分类 action
  -> adapter 返回 Live evidence、Mock evidence 或 Handoff material
  -> UI 显示顺序，final answer 说明 boundary
```

这个路径故意很窄。涉及身份、缴费、证书、官方提交时，UMMAYA 不会把边界藏在自信的段落里。它会询问、停止或 handoff。

## Boundary

Live 表示可以调用已配置的官方或公共服务渠道并以结果为依据。Mock 表示可以展示形状忠实的流程，但不是官方结果。Handoff 表示 UMMAYA 可以准备路径，但用户必须在官方服务继续。Harness migration 只有在同时降低门户负担和保留可检查性时才成立。
