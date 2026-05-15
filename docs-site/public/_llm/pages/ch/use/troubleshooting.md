---
title: 故障排查
description: 先解决用户可见问题，再进入 maintainer debugging。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs/testing.md
- docs/onboarding/codex-continuation.md
audience:
- citizen_user
- maintainer
---

Troubleshooting 应从用户看到的 symptom 开始，而不是从 repository internals 开始。正在试用 UMMAYA 的人需要知道 command 是否安装、sign-in 是否成功、public lookup 是否能运行，或 protected step 是否正确停止。

maintainer debugging 仍然重要，但它在用户路径清楚之后。如果第一句话是 “run tests” 或 “inspect git status”，文档已经跳过了读者问题。

## Symptom Map

用可见 symptom 选择第一项检查。在排除简单用户路径前，不要直接跳到深度 debugging。

| Symptom | First check | Likely next step |
|---|---|---|
| `ummaya` command not found | install path | rerun installer, Homebrew cask, or npm global install |
| command starts but cannot sign in | FriendliAI login or token state | sign in again and confirm provider configuration |
| first prompt returns no useful result | prompt shape and public adapter availability | try a public lookup prompt with a clear place |
| answer says Mock | domain has shape but no live authority | read Live/Mock/Handoff and treat it as simulation |
| answer says Handoff | next step needs official authority | continue through the official service |
| session resume fails | session ID and local session availability | check the printed resume command and local storage |

这个表是 triage map，不是 proof。如果 symptom 在第一次修复后重复，记录 exact command、visible message 和出问题的 page/workflow。

## Install Checks

如果 command 不存在，先确认你用了哪种安装方式。packaged CLI 是用户路径；source checkout commands 属于 contributors。

```bash
ummaya --version
```

如果 shell 找不到 `ummaya`，通过选择的 package path 重新安装并打开新 shell。如果 command 存在但启动失败，在尝试另一个 installer 前记录 visible error。

## Login Checks

UMMAYA 使用 FriendliAI/K-EXAONE 作为 model provider。sign-in 失败时，第一问题是 provider credential 是否存在，CLI 是否能访问它。login failure 不是 adapter failure，不应描述成 public-service problem。

修复 login 后，先用安全 public prompt，再尝试 protected workflow。好的 smoke prompt 应带有明确 location，并询问 public weather、road、hospital 或 safety information。

## Mock 或 Handoff 混淆

Mock 和 Handoff 本身不是错误。Mock 表示 UMMAYA 演示 workflow shape，没有 official completion。Handoff 表示下一步必须通过 official service，因为 UMMAYA 没有安全 callable path。

恢复方式是读 state label 并决定下一步。如果你想要 demo，Mock 可能足够。如果你想要 real filing、payment、certificate、identity verification 或 record change，除非 live authority 已配置，否则 Handoff 是诚实结果。

## Maintainer Debugging

maintainer 可以在保留 user symptom 后检查 generated docs、tests、IPC frames、adapter schemas 和 TUI captures。debugging note 应保留原 symptom：command、prompt、expected state、actual state，以及 failure 发生在 install、provider、retrieval、permission、adapter execution 还是 rendering。

不要用内部 shorthand 取代用户-facing failure。"Adapter error" 不够。要说哪个 adapter、哪个 mode、哪个 primitive、哪个 stop reason。

## Recovery

如果所有用户检查都无效，收集最小有用报告：operating system、install method、`ummaya --version`、prompt used、visible state label 和 exact stop message。这份报告给 maintainer 足够 context，而不用要求用户理解整个 repository。
