---
title: "快速开始"
description: "安装打包后的 UMMAYA CLI，启动会话，并运行一个安全的公共服务 prompt。"
llm_index: true
audience:
  - new_user
  - considering_user
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - README.md
  - package.json
---

本快速开始面向打包后的 UMMAYA CLI。目标不是检查文档文件、clone 仓库或运行源码测试，而是安装用户真正会使用的命令，启动会话，登录 FriendliAI，并提出一个安全的公共服务问题。

第一次运行请使用公共查询。不要一开始就要求支付、证书签发、身份验证、报税、官方记录变更或个人账户数据。这些流程需要明确授权，今天也常常会停在 Mock 或 Handoff。

## 选择安装路径

macOS 用户优先使用 Homebrew。想使用 npm 发布包路径，或没有使用 Homebrew 时，可以用 npm。两条路径都应暴露同一个用户命令：`ummaya`。

| Platform path | Best for | Command |
|---|---|---|
| Homebrew cask | 想要原生安装/更新路径的 macOS 用户 | `brew install --cask umyunsang/ummaya/ummaya` |
| npm global package | 已经用 npm 管理 CLI 工具的用户 | `npm install -g ummaya` |

如果你是在以用户身份评估 UMMAYA，请优先使用这些打包路径，而不是 source checkout。源码工作流属于 contributor 文档。

## 在 macOS 上安装

通过 Homebrew cask 安装或升级：

```bash
brew install --cask umyunsang/ummaya/ummaya
ummaya --version
```

version 命令是 shell 能找到打包 CLI 的第一份证据。如果失败，先打开新终端，并检查 Homebrew binary path 是否在 shell 中可用。

不要为了修 packaging 问题而切换到源码 checkout，除非你是在贡献项目。用户 quickstart 应验证普通用户会运行的 published command。

## 使用 npm 安装

全局安装 package：

```bash
npm install -g ummaya
ummaya --version
```

npm package 通过 `bin/ummaya` 暴露 `ummaya` 命令。这个 wrapper 会一起启动 terminal UI 和 backend，所以机器上需要 Bun、`uv` 等运行时依赖。

如果 npm 安装成功但命令失败，保留错误信息。它能告诉你问题在 package resolution、runtime dependency、provider setup 还是 startup logic。

## 启动并登录

启动 UMMAYA：

```bash
ummaya
```

第一次会话应在需要时引导 provider setup 或 sign-in。UMMAYA 使用 FriendliAI/K-EXAONE 做模型推理。如果 sign-in 失败，先修好它再测试 adapter；provider failure 不是公共服务失败。

成功登录只证明模型访问可用。它并不授予政府门户、身份系统、支付或证书的权限。

## 运行安全的第一个 prompt

使用询问公共信息、且地点清晰的 prompt。

```text
동아대 승학캠퍼스 근처 응급실이나 야간 진료 정보를 공식 정보 기준으로 찾아줘.
```

好的第一次回答应显示公共服务路径，例如先做 location resolution，再做公共医疗或应急信息查询。如果某一步不是 live，或变成受保护步骤，UMMAYA 应标为 Mock 或 Handoff，而不是假装完成。

## 什么算成功

第一次成功会话证明的是窄路径：

- packaged command 可以启动；
- FriendliAI/K-EXAONE 可以访问；
- query engine 可以处理用户请求；
- 出现 public lookup 或诚实的 stop reason；
- final answer 写明 source、state、boundary 和 next action。

它不证明所有国家基础设施域都已 live。它证明 harness 可以从用户 query 走到 tool-backed 或 boundary-aware answer。

## 常见恢复

如果找不到 `ummaya`，通过同一 package path 重新安装并打开新 shell。如果命令启动但 sign-in 失败，先修 provider credential。如果回答写着 Mock，把它当作 simulation。如果写着 Handoff，就在回答指定的 official service 中继续。

如果 public lookup 失败，尝试更简单的 prompt：一个地点加一个公共信息需求。这样可以把 install/provider 问题和 adapter coverage 问题分开。

## 更新或重装

使用安装时同一个 package manager：

```bash
brew upgrade --cask umyunsang/ummaya/ummaya
```

```bash
npm install -g ummaya@latest
```

更新后运行 `ummaya --version`，再运行一个安全 public prompt。这是 user-level smoke test，不需要触碰仓库内部。

如果更新改变行为，不要只看版本号。更重要的 regression signal 是 public lookup、Mock、Handoff 标签是否仍然正确出现。

## 下一步

第一次成功 prompt 后，阅读 [What You Can Ask](/ch/start/what-you-can-ask/) 来写更好的 prompt，并在尝试受保护 workflow 前阅读 [Live, Mock, And Handoff](/ch/trust/live-mock-handoff/)。

这个顺序重要。更好的 prompt 让体验有用，trust page 防止受保护 workflow 被误解为自动官方完成。
