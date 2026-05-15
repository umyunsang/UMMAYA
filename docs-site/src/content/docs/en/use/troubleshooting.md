---
title: Troubleshooting
description: Fix common user-facing problems before moving into maintainer debugging.
llm_index: true
audience:
  - citizen_user
  - maintainer
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs/testing.md
  - docs/onboarding/codex-continuation.md
---

Troubleshooting should start from the symptom the user sees, not from repository internals. A person trying UMMAYA needs to know whether the command is installed, sign-in worked, a public lookup can run, or a protected step correctly stopped.

Maintainer debugging still matters, but it comes after the user path is clear. If the first answer is "run tests" or "inspect git status", the docs have skipped the reader's problem.

## Symptom Map

Use the visible symptom to choose the first check. Do not jump to deep debugging until the simple user path is ruled out.

| Symptom | First check | Likely next step |
|---|---|---|
| `ummaya` command not found | install path | rerun installer, Homebrew cask, or npm global install |
| command starts but cannot sign in | FriendliAI login or token state | sign in again and confirm provider configuration |
| first prompt returns no useful result | prompt shape and public adapter availability | try a public lookup prompt with a clear place |
| answer says Mock | domain has shape but no live authority | read Live/Mock/Handoff and treat it as simulation |
| answer says Handoff | next step needs official authority | continue through the official service |
| session resume fails | session ID and local session availability | check the printed resume command and local storage |

The table is a triage map, not a proof. If a symptom repeats after the first fix, capture the exact command, visible message, and page or workflow where the failure happened.

## Install Checks

If the command is missing, first confirm which installation method you used. The packaged CLI is the user path; source checkout commands are for contributors.

```bash
ummaya --version
```

If the shell cannot find `ummaya`, reinstall through the chosen package path and open a new shell. If the command exists but fails at startup, record the visible error before trying another installer.

## Login Checks

UMMAYA uses FriendliAI/K-EXAONE as the model provider. If sign-in fails, the first question is whether the provider credential exists and the CLI can reach it. A login failure is not an adapter failure and should not be described as a public-service problem.

After fixing login, use a safe public prompt before trying a protected workflow. A good smoke prompt asks for public weather, road, hospital, or safety information with a clear location.

## Mock Or Handoff Confusion

Mock and Handoff are not errors by themselves. Mock means UMMAYA demonstrated a workflow shape without official completion. Handoff means the next step must happen through an official service because UMMAYA lacks a safe callable path.

The recovery is to read the state label and decide what you need next. If you wanted a demo, Mock may be enough. If you wanted a real filing, payment, certificate, identity verification, or record change, Handoff is the honest result unless live authority is configured.

## Maintainer Debugging

Maintainers can inspect generated docs, tests, IPC frames, adapter schemas, and TUI captures after the user symptom is preserved. The debugging note should keep the original symptom visible: command, prompt, expected state, actual state, and whether the failure happened in install, provider, retrieval, permission, adapter execution, or rendering.

Do not replace a user-facing failure with internal shorthand. "Adapter error" is not enough. Say which adapter, which mode, which primitive, and which stop reason were involved.

## Recovery

If none of the user checks works, collect the minimum useful report: operating system, install method, `ummaya --version`, prompt used, visible state label, and exact stop message. That report gives maintainers enough context without asking the user to understand the whole repository.
