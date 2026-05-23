---
title: Quickstart
description: Install the packaged UMMAYA CLI, start a session, and run one safe public-service prompt.
llm_index: true
audience:
  - new_user
  - considering_user
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - README.md
  - package.json
---

This quickstart is for the packaged UMMAYA CLI. The goal is not to inspect documentation files, clone the repository, or run source tests. The goal is to install the user-facing command, start a session, sign in to FriendliAI, and ask one safe public-service question.

Use a public lookup for the first run. Do not start with payment, certificate issuance, identity verification, tax filing, official record changes, or personal account data. Those flows require explicit authority and often stop at Mock or Handoff.

## Choose An Install Path

Use Homebrew on macOS when possible. Use npm when you want the published package path or are not using Homebrew. Both paths should expose the same user command: `ummaya`.

| Platform path | Best for | Command |
|---|---|---|
| Homebrew cask | macOS users who want a native install/update path | `brew install --cask umyunsang/ummaya/ummaya` |
| npm global package | users who already manage CLI tools with npm | `npm install -g ummaya` |

If you are evaluating UMMAYA as a user, prefer these packaged paths over a source checkout. Source workflows belong to contributor documentation.

## Install On macOS

Install or upgrade through the Homebrew cask:

```bash
brew install --cask umyunsang/ummaya/ummaya
ummaya --version
```

The version command is the first proof that the shell can find the packaged CLI. If it fails, open a new terminal and check whether Homebrew's binary path is available in your shell.

Do not switch to a source checkout to fix a packaging issue unless you are contributing to the project. A user quickstart should validate the published command that ordinary users will run.

## Install With npm

Install the package globally:

```bash
npm install -g ummaya
ummaya --version
```

The npm package exposes the `ummaya` command through `bin/ummaya`. The wrapper starts the terminal UI and backend together, so runtime dependencies such as Bun and `uv` must be available on the machine.

If npm installs successfully but the command fails, keep the error message. It tells you whether the problem is package resolution, runtime dependency, provider setup, or startup logic.

## Start And Sign In

Start UMMAYA:

```bash
ummaya
```

The first session should lead you through provider setup or sign-in when needed. UMMAYA uses FriendliAI/K-EXAONE for model reasoning. If sign-in fails, fix that before testing adapters; a provider failure is not a public-service failure.

A successful sign-in only proves model access. It does not grant authority over government portals, identity systems, payments, or certificates.

## Run A Safe First Prompt

Use a prompt that asks for public information and gives a clear place.

```text
동아대 승학캠퍼스 근처 응급실이나 야간 진료 정보를 공식 정보 기준으로 찾아줘.
```

A good first answer should show a public-service path, such as location resolution followed by public healthcare or emergency information lookup. If a step is not live or becomes protected, UMMAYA should label it as Mock or Handoff instead of pretending to complete it.

## Know What Success Looks Like

The first successful session proves a narrow path:

- the packaged command starts;
- FriendliAI/K-EXAONE can be reached;
- the query engine can process a user request;
- a public lookup or honest stop reason appears;
- the final answer states source, state, boundary, and next action.

It does not prove every national-infrastructure domain is live. It proves the harness can move from user query to tool-backed or boundary-aware answer.

## Common Recovery

If `ummaya` is not found, reinstall through the package path and open a new shell. If the command starts but sign-in fails, fix provider credentials before trying another prompt. If the answer says Mock, treat it as simulation. If it says Handoff, continue through the official service named in the answer.

If a public lookup fails, try a simpler prompt with a location and one public information need. This isolates install/provider problems from adapter coverage problems.

## Update Or Reinstall

Use the same package manager you used for install:

```bash
brew upgrade --cask umyunsang/ummaya/ummaya
```

```bash
npm install -g ummaya@latest
```

After updating, run `ummaya --version` and one safe public prompt again. That gives you a user-level smoke test without touching repository internals.

If the update changes behavior, compare the visible answer state rather than only the version number. The important regression signal is whether public lookup, Mock, and Handoff labels still appear correctly.

## Next Step

After the first successful prompt, read [What You Can Ask](/en/start/what-you-can-ask/) to write better prompts and [Live, Mock, And Handoff](/en/trust/live-mock-handoff/) before trying protected workflows.

This order matters. Better prompts make the first experience useful, and the trust page prevents protected workflows from being mistaken for automatic official completion.
