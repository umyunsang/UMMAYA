<img alt="UMMAYA wordmark with the compact open-call companion mark" src="https://raw.githubusercontent.com/umyunsang/UMMAYA/main/assets/ummaya-wordmark.png" width="100%">

<a href="https://github.com/umyunsang/UMMAYA/blob/main/assets/ummaya-demo.mp4">
  <img src="https://raw.githubusercontent.com/umyunsang/UMMAYA/main/assets/ummaya-demo.gif" alt="UMMAYA terminal demo showing public-service prompts, tool calls, tool results, and final answers" width="100%">
</a>

<sub>Click the demo to open the MP4. The recording is from a real `ummaya` terminal session; waiting time was trimmed, but prompts, UI, tool calls, and answers were not synthesized.</sub>

# UMMAYA

![npm version](https://img.shields.io/npm/v/ummaya.svg?style=flat-square)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue.svg?style=flat-square)](LICENSE)
[![docs](https://img.shields.io/badge/docs-Cloudflare%20Pages-0f172a.svg?style=flat-square)](https://ummaya-docs.pages.dev/ko/)
<!-- npmjs.com package pages challenge non-browser link checkers; verify with `npm view ummaya`. -->
<!-- markdown-link-check-disable-next-line -->
<sub>[npm package](https://www.npmjs.com/package/ummaya)</sub>

**Unified Multi-Ministry Agent for Your Administration.** Pronounced `ummaya`.

UMMAYA is a terminal agent for Korean public-service workflows. You describe the outcome in natural language; UMMAYA locates the right public-service context, calls wrapped tools, shows the work, and stops when identity, consent, or official authority is required.

It is a client-side reference implementation for national administrative AX workflows: Claude Code-style tool loop and permission UX, with `FriendliAI Serverless + K-EXAONE` as the model path and Korean public-service adapters as the tool surface.

> UMMAYA is an independent academic and R&D project. It is not affiliated with, endorsed by, or operated by Anthropic, LG AI Research, FriendliAI, the Korean government, or any public agency.

Current status: the 0.2.x release line has shipped. Active work focuses on the public document harness and adapter route-selection modernization; [`docs/vision.md`](docs/vision.md) and [`docs/requirements/ummaya-migration-tree.md`](docs/requirements/ummaya-migration-tree.md) are the design contract.

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

## What It Handles

| Work | Example prompt |
|---|---|
| Public lookup | `다대1동 근처에서 오늘 전화해볼 수 있는 내과가 있을까? 가까운 곳 위주로 주소랑 전화번호를 알려줘.` |
| Weather and local risk | `비 오는 날 다대포에서 김해공항까지 차로 가야 해. 날씨랑 도로 위험 정보를 같이 보고 조심할 점을 알려줘.` |
| Protected workflow | `모바일 신분증으로 본인확인하고, 내 자격으로 신청 가능한 복지 지원을 확인해줘.` |
| Public-form authoring | `전입신고서 양식을 열어서 내 정보로 채워줘. 제출 전에 어떤 칸이 비었는지도 확인해줘.` |

Live public-information flows are easiest to verify today, so demos focus on those. Identity, submission, payment, certificate, correction, and some form-writing paths are Live only when an official callable channel, valid credential, and documented contract exist. Otherwise they are marked Mock or Handoff instead of pretending a protected government action completed.

## Main Tools

UMMAYA keeps the model-facing surface small and lets adapters handle agency-specific details behind it.

| Tool | Public alias | Role |
|---|---|
| `locate` | `resolve_location` | Resolve places, addresses, coordinates, and administrative areas before a service lookup. |
| `find` | `lookup` | Retrieve public information such as weather, emergency rooms, hospitals, road safety, welfare information, and other public-service reads. |
| `check` | `verify` | Enter protected work by establishing identity, consent, purpose, scope, and delegation. This is the light permission gate. |
| `send` | `submit` | Execute or prepare submissions, payments, applications, receipts, or official handoffs when a live or mock channel is registered. This is a heavy permission gate. |
| `document` | `document` | Inspect, fill, style, validate, render, and save Korean public forms such as HWP, HWPX, PDF, OOXML, and ODF. This is gated by Evidence Fabric coverage and explicit in-session approval. |

## Authority Boundary

| Situation | UMMAYA behavior |
|---|---|
| Public lookup | Use live public adapters when available and answer only from found results. |
| Protected action | Start with `check`, the protected-domain entrypoint; continue to `send` only with scoped delegation. |
| Public-form authoring | Use `document`; stop for evidence coverage and user approval before writing. |
| Missing live authority | Return Mock or Handoff with the same boundary shape, not a fake completion. |
| API failure or zero result | Stop clearly instead of inventing a result. |

## Model And License

UMMAYA currently uses `LGAI-EXAONE/K-EXAONE-236B-A23B` through FriendliAI Serverless for LLM responses.

- Model: [K-EXAONE-236B-A23B](https://huggingface.co/LGAI-EXAONE/K-EXAONE-236B-A23B)
- Reasoning mode: `/reasoning` or `UMMAYA_K_EXAONE_REASONING_MODE` selects `fast`, `balanced`, `deep`, `diagnostic`, or `auto`.
- Thinking channel: `UMMAYA_K_EXAONE_THINKING` default `false` remains as a legacy compatibility flag; use `/reasoning deep` or `UMMAYA_K_EXAONE_REASONING_MODE=deep` for reasoning-channel diagnostics or benchmark runs.
- Model license: [K-EXAONE AI Model License Agreement](https://huggingface.co/LGAI-EXAONE/K-EXAONE-236B-A23B/blob/main/LICENSE)
- Project license: [Apache License 2.0](LICENSE)

The model license and UMMAYA source-code license are separate. UMMAYA does not grant rights to LG AI Research, FriendliAI, Hugging Face, Korean government, or public-agency assets.

## Docs

- Korean docs: [ummaya-docs.pages.dev/ko](https://ummaya-docs.pages.dev/ko/)
- Product purpose: [Korean user guide](https://ummaya-docs.pages.dev/ko/start/why-ummaya/)
- Agent-readable discovery: [llms.txt](https://ummaya-docs.pages.dev/llms.txt)
- Architecture source of truth: [docs/vision.md](docs/vision.md)
- Requirements tree: [docs/requirements/ummaya-migration-tree.md](docs/requirements/ummaya-migration-tree.md)
- Adapter docs: [docs/api/](docs/api/)
- Codex continuation: [docs/onboarding/codex-continuation.md](docs/onboarding/codex-continuation.md)
- Release readiness: [docs/release/homebrew-official-readiness.md](docs/release/homebrew-official-readiness.md)
- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)
