---
title: "为什么是 UMMAYA"
description: "为什么 UMMAYA 作为 national-infrastructure AX harness 存在。"
llm_index: true
audience:
  - non_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs/vision.md
  - docs/requirements/ummaya-migration-tree.md
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

UMMAYA 存在，是因为从用户角度看，韩国公共服务工作是碎片化的。一个生活事件可能同时涉及 portals、agencies、identity rails、certificates、payments、local records、welfare rules、healthcare data、safety sources 和 public-data APIs。用户不应在提出结果请求前先理解整张地图。

UMMAYA 的目标是 Korean national-infrastructure AX：在分散的公共服务 domains 之上提供一个易接近的 query surface。系统应分解请求、选择 tools、在需要时请求 permission、返回 evidence，并在 official path 必须接管时诚实停止。

## 用户问题

用户问题不只是公共服务网站很多。更深的问题是，用户必须先把真实生活需求翻译成 agencies、forms、credentials、portals 的语言，工作才开始。

例如，“我搬家了”可能涉及地址解析、地方政府记录、公用事业、车辆或停车规则、住房文件和 official handoff。“我需要支持”可能涉及福利指南、家庭文件、eligibility boundaries 和申请渠道。用户的 intent 是一句话，但 infrastructure path 是多 domain。

UMMAYA 的设计目标是吸收这种翻译负担，同时不假装 official authority 会消失。

## 产品主张

UMMAYA 应让一个人请求公共服务结果，并看到发生了什么。一个有用回答应显示哪一步是 public lookup，哪一步需要 consent，哪一步是 Mock，哪一步变成 Handoff。

这就是 UMMAYA 是 agent harness 而不是普通 chatbot 的原因。chatbot 可以解释服务，同时在没有 evidence 时听起来也很权威。UMMAYA 必须把回答连接到受控 loop：context、retrieval、primitive choice、validation、permission、adapter execution 和 stop reason。

## 机制

UMMAYA 把公共服务 channels 和 policy-shaped workflows 包装成 tools。模型看到的是小的 primitive surface，目前是 `locate`、`find`、`check`、`send`，而 adapter layer 承载 domain detail、schema、status、citation 和 permission metadata。

query engine 决定下一步是 location resolution、public lookup、protected checking、submission preparation 还是 Handoff。这个决定就是 national AX 的核心：用户用 outcome 说话，系统处理 routing 和 evidence。

## 为什么参考 Claude Code

Claude Code 是参考对象，因为它把 tool use、permission prompts、context assembly、session continuity 和 terminal UX 合成一个可工作的 harness。UMMAYA 把这个 harness pattern 从 developer work 迁移到 public-service work。

允许替换的部分很窄。FriendliAI 上的 K-EXAONE 替换 model provider，韩国公共服务 tools 替换 files、shell、git 和 code tools。围绕 bounded tool use、permission、context 和 visible progress 的纪律应保持不变。

## 本站必须证明什么

本站必须在不过度声称的前提下说服读者。它应展示 UMMAYA 今天能做什么，什么是 Mock 或 Handoff，如何安装 packaged CLI，第一次成功会话是什么样子，以及 architecture 如何让公共服务 claim 保持 grounded。

如果文档让 UMMAYA 听起来像官方政府服务，它失败。如果让 UMMAYA 听起来像普通 chatbot，它也失败。正确承诺更窄也更强：one query surface、tool-backed evidence、visible boundaries 和 honest official handoff。
