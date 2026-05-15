---
title: Domain Roadmap
description: UMMAYA 如何把 domain 从 target-state scenario 推进到 mock，再到 live capability。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- eval/scenarios/national_ax_citizen_requests_v1.yaml
- docs/api/README.md
audience:
- considering_user
- public_sector_evaluator
- maintainer
---

domain roadmap 说明 UMMAYA 如何在不过度声称的情况下成长。一个 domain 在 live 之前也可能对 national AX 很重要，但文档必须诚实标注 current state。

roadmap 不是 wish list。它是一条 promotion ladder：scenario、mock、live，然后随着 official channels 和 credentials 可用，扩展为更丰富的 live workflows。

## Target Domains

UMMAYA 的 target map 跟随 citizen work，而不是 agency org charts。

| Domain | Target user work |
|---|---|
| Safety and healthcare | find public safety, hospital, emergency, weather, and hazard information |
| Housing and local records | prepare moving, address, housing, and local-service workflows |
| Welfare and household support | find guidance, prepare documents, expose eligibility boundaries |
| Tax, fines, payments, utilities | prepare filings, payment paths, receipt expectations, and official handoff |
| Identity, certificates, MyData | explain official paths, consent points, and protected data flows |
| Labor, education, immigration, legal | map multi-agency guidance and target-state workflows |

这个表定义 demand，不表示每一行今天都是 Live。

## Promotion Logic

当 public shape 清楚到可以负责任地 mirror 时，domain 从 scenario 进入 Mock。只有当项目拥有 official callable channel、必要的 credential path、schema、permission metadata、sanitized request/response artifact 和 test strategy 时，Mock 才能进入 Live。

promotion rule 防止文档把 ambition 写成 false current-state claim。official channel 不可用时，target-state domain 作为 Handoff 仍然有价值。

## 为什么 Planned Domains 仍重要

National AX 要按完整 citizen journey 判断。学生 portfolio 项目今天不可能 live-complete 每个 protected system，但可以展示 caller architecture、evidence ladder，以及每个 domain 的 honest gap。

Planned domains 给 query engine、adapter model、permission UX 和 docs 一个 future-facing test。它们也显示公共基础设施要让 UMMAYA 更完整，需要提供 callable、consented、LLM-safe channels。

## Roadmap Evidence

roadmap claim 至少应追到一种 artifact：target-state scenario、adapter metadata、public API documentation、policy citation、schema、fixture 或 issue/spec。如果没有任何 artifact，该 domain 应描述为 research target，而不是 planned capability。

这个 evidence rule 让 roadmap 对 contributor 有用。它告诉他们下一步是 research、mock adapter、live credential validation、permission design 还是 docs update。

## 下一步

把 roadmap 与 [Current Coverage](/ch/coverage/current-coverage/) 和 [Adapter Matrix](/ch/coverage/adapter-matrix/) 一起使用。它们回答三个不同问题：用户需要什么、UMMAYA 现在能做什么、什么 evidence 可以证明 promotion。
