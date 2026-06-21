# UMMAYA

![npm version](https://img.shields.io/npm/v/ummaya.svg?style=flat-square)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue.svg?style=flat-square)](LICENSE)
[![docs](https://img.shields.io/badge/docs-Cloudflare%20Pages-0f172a.svg?style=flat-square)](https://ummaya-docs.pages.dev/en/)
<!-- npmjs.com package pages challenge non-browser link checkers; verify with `npm view ummaya`. -->
<!-- markdown-link-check-disable-next-line -->
<sub>[npm package](https://www.npmjs.com/package/ummaya)</sub>

**Terminal AI agent for Korean public-service workflows.**

UMMAYA is an open-source civic AI agent that brings a Claude Code-style tool loop to Korean public-service and national administrative workflows. You ask for an outcome in natural language; UMMAYA routes the request, calls registered civic adapters, shows tool progress, and stops at identity, consent, payment, or official-authority boundaries.

If Codex and Claude Code are terminal agents for software work, UMMAYA is the same class of interface for Korean public-service work: a terminal AI agent, public-service tool-calling harness, government-workflow CLI, and national AX reference client powered by `K-EXAONE` on FriendliAI.

> UMMAYA is an independent academic and R&D project. It is not affiliated with, endorsed by, or operated by Anthropic, LG AI Research, FriendliAI, the Korean government, or any public agency.

<a href="https://github.com/umyunsang/UMMAYA/blob/main/assets/ummaya-demo.mp4">
  <img src="https://raw.githubusercontent.com/umyunsang/UMMAYA/main/assets/ummaya-demo.gif" alt="UMMAYA terminal demo showing public-service prompts, tool calls, tool results, and final answers" width="100%">
</a>

<sub>Click the demo to open the MP4. The recording is from a real `ummaya` terminal session; waiting time was trimmed, but prompts, UI, tool calls, and answers were not synthesized.</sub>

## Find This Repo When You Need

| Search intent | Why UMMAYA matches |
|---|---|
| Terminal AI agent for Korean public services | Runs as a local CLI and answers Korean public-service requests through tool calls. |
| Civic AI agent or govtech agent | Wraps public-information, location, identity, submission, and document workflows behind auditable adapters. |
| Claude Code-style tool loop outside coding | Migrates the agent loop, permission UX, context assembly, and terminal interaction model from developer work to public-service work. |
| K-EXAONE or FriendliAI agent example | Uses `LGAI-EXAONE/K-EXAONE-236B-A23B` through FriendliAI Serverless as the fixed model path. |
| LLM tool calling for government workflows | Exposes a small action vocabulary while adapters carry agency-specific details and evidence. |

Canonical discovery terms: `terminal AI agent`, `Korean public-service workflows`, `civic AI agent`, `government workflow CLI`, `public-service tool calling`, `national AX`, `K-EXAONE`, `FriendliAI`, `Claude Code-style harness`, `llms.txt`.

## Install

```bash
npm install -g ummaya
```

Homebrew on macOS:

```bash
brew install --cask umyunsang/ummaya/ummaya
```

The Homebrew cask installs a prebuilt macOS archive. It does not run `npm install` or `bun install` during installation. The unqualified official-cask form will work only after Homebrew accepts UMMAYA into `Homebrew/homebrew-cask`.

## First Run

```bash
ummaya
```

Inside the terminal session:

```text
/login
```

Paste your FriendliAI API key, then ask in everyday language:

```text
동아대 승학캠퍼스에서 친구가 갑자기 아프면 지금 바로 연락할 응급실 어디가 가까워?
```

Public packaged CLI users should not need to prepare Kakao, JUSO, SGIS, data.go.kr, KMA/APIHub, gateway bearer, or other operator-managed public API credentials. Sessions are stored locally; resumable sessions print a command such as `ummaya --resume <session-id>`.

## What You Can Ask

Ask for the public-service outcome, not the agency API name.

| User goal | Example prompt | Expected boundary |
|---|---|---|
| Find nearby public information | `다대1동 근처에서 오늘 전화해볼 수 있는 내과가 있을까? 가까운 곳 위주로 주소랑 전화번호를 알려줘.` | Live public lookup when an adapter is available. |
| Combine weather, safety, and travel context | `비 오는 날 다대포에서 김해공항까지 차로 가야 해. 날씨랑 도로 위험 정보를 같이 보고 조심할 점을 알려줘.` | Live public data plus clear source boundaries. |
| Prepare a protected public-service workflow | `모바일 신분증으로 본인확인하고, 내 자격으로 신청 가능한 복지 지원을 확인해줘.` | `check` starts identity or delegation flow; Mock or Handoff if no live authority exists. |
| Draft a public form | `전입신고서 양식을 열어서 내 정보로 채워줘. 제출 전에 어떤 칸이 비었는지도 확인해줘.` | `document` inspects and prepares; saving requires evidence and approval. |

## How It Works

UMMAYA keeps the model-facing surface small. The LLM sees a few stable actions; adapters handle agency-specific APIs, schemas, credentials, mock fixtures, and evidence.

| Layer | Role |
|---|---|
| Harness | Claude Code-style loop: plan, call tools, inspect results, continue or stop. |
| Model | `K-EXAONE` through FriendliAI Serverless. |
| Tool registry | Korean public-service adapters registered as model-callable tools. |
| Permission UX | Explicit consent and authority gates before protected actions. |
| Evidence | Status labels, receipts, source traces, and local session history. |

## Main Tool Families

| Tool | Public alias | Role |
|---|---|---|
| `locate` | `resolve_location` | Resolve places, addresses, coordinates, and administrative areas before a service lookup. |
| `find` | `lookup` | Retrieve public information such as weather, emergency rooms, hospitals, road safety, welfare information, and other public-service reads. |
| `check` | `verify` | Enter protected work by establishing identity, consent, purpose, scope, and delegation. This is the light permission gate. |
| `send` | `submit` | Execute or prepare submissions, payments, applications, receipts, or official handoffs when a live or mock channel is registered. This is a heavy permission gate. |
| `document` | `document` | Inspect, fill, style, validate, render, and save Korean public forms such as HWP, HWPX, PDF, OOXML, and ODF. This is gated by Evidence Fabric coverage and explicit in-session approval. |

## Capability Status

UMMAYA is useful only if it is honest about authority. Every domain is treated as Live, Mock, or Handoff.

| Status | Meaning |
|---|---|
| Live | An official callable channel, valid credential path, and documented contract are available. |
| Mock | The channel exists or is policy-mandated, but this repo lacks live authority; UMMAYA mirrors the public shape without pretending completion. |
| Handoff | Only an official portal, person, app, or protected rail can complete the work today. |

Live public-information flows are the easiest to verify today, so demos focus on those. Identity, submission, payment, certificate, correction, and some form-writing paths are Live only when an official callable channel, valid credential, and documented contract exist.

## For Users, Researchers, And Agents

| Reader | Start here |
|---|---|
| End users | [Quickstart](https://ummaya-docs.pages.dev/en/start/quickstart/) and [what you can ask](https://ummaya-docs.pages.dev/en/start/what-you-can-ask/) |
| LLM research tools | [llms.txt](https://ummaya-docs.pages.dev/llms.txt) and [LLM-readable docs](https://ummaya-docs.pages.dev/en/reference/llm-readable-docs/) |
| Adapter contributors | [Adapter authoring](https://ummaya-docs.pages.dev/en/build/adapter-authoring/) and [docs/api/](docs/api/) |
| Architecture reviewers | [docs/vision.md](docs/vision.md) and [docs/requirements/ummaya-migration-tree.md](docs/requirements/ummaya-migration-tree.md) |

## Model And License

UMMAYA currently uses `LGAI-EXAONE/K-EXAONE-236B-A23B` through FriendliAI Serverless for LLM responses.

- Model: [K-EXAONE-236B-A23B](https://huggingface.co/LGAI-EXAONE/K-EXAONE-236B-A23B)
- Reasoning mode: `/reasoning` or `UMMAYA_K_EXAONE_REASONING_MODE` selects `fast`, `balanced`, `deep`, `diagnostic`, or `auto`.
- Thinking channel: `UMMAYA_K_EXAONE_THINKING` default `false` remains as a legacy compatibility flag; use `/reasoning deep` or `UMMAYA_K_EXAONE_REASONING_MODE=deep` for reasoning-channel diagnostics or benchmark runs.
- Model license: [K-EXAONE AI Model License Agreement](https://huggingface.co/LGAI-EXAONE/K-EXAONE-236B-A23B/blob/main/LICENSE)
- Project license: [Apache License 2.0](LICENSE)

The model license and UMMAYA source-code license are separate. UMMAYA does not grant rights to LG AI Research, FriendliAI, Hugging Face, Korean government, or public-agency assets.

## Docs

- English docs: [ummaya-docs.pages.dev/en](https://ummaya-docs.pages.dev/en/)
- Korean docs: [ummaya-docs.pages.dev/ko](https://ummaya-docs.pages.dev/ko/)
- Agent-readable discovery: [llms.txt](https://ummaya-docs.pages.dev/llms.txt)
- Architecture source of truth: [docs/vision.md](docs/vision.md)
- Requirements tree: [docs/requirements/ummaya-migration-tree.md](docs/requirements/ummaya-migration-tree.md)
- Adapter docs: [docs/api/](docs/api/)
- Codex continuation: [docs/onboarding/codex-continuation.md](docs/onboarding/codex-continuation.md)
- Release readiness: [docs/release/homebrew-official-readiness.md](docs/release/homebrew-official-readiness.md)
- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)
