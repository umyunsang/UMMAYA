<img alt="UMMAYA banner with the Umma mascot and Unified Multi-Ministry Agent for Your Administration wordmark" src="https://raw.githubusercontent.com/umyunsang/UMMAYA/main/assets/ummaya-readme-banner.png" width="100%">

<a href="https://github.com/umyunsang/UMMAYA/blob/main/assets/ummaya-demo.mp4">
  <img src="https://raw.githubusercontent.com/umyunsang/UMMAYA/main/assets/ummaya-demo.gif" alt="UMMAYA terminal demo showing public-service prompts, separated tool calls, compact tool results, and final assistant answers" width="100%">
</a>

<sub>Click the demo to open the MP4. The recording comes from a real `ummaya` terminal session captured with `t-rec`; waiting time was trimmed, but prompts, UI, tool calls, and answers were not synthesized.</sub>

# UMMAYA

[![npm version](https://img.shields.io/npm/v/ummaya.svg?style=flat-square)](https://www.npmjs.com/package/ummaya)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue.svg?style=flat-square)](LICENSE)
[![docs](https://img.shields.io/badge/docs-Cloudflare%20Pages-0f172a.svg?style=flat-square)](https://ummaya-docs.pages.dev/ko/)

**Unified Multi-Ministry Agent for Your Administration.**
읽으면, **엄마야**.

UMMAYA is a terminal agent for Korean public-service workflows. You describe the outcome in natural language, and UMMAYA routes the request through four main tools: `find`, `locate`, `check`, and `send`.

Read the full documentation at [ummaya-docs.pages.dev/ko](https://ummaya-docs.pages.dev/ko/). Start with the [Korean user guide](https://ummaya-docs.pages.dev/ko/start/why-ummaya/) if you want the product purpose first, or use [llms.txt](https://ummaya-docs.pages.dev/llms.txt) when an agent needs machine-readable project context.

```bash
npm install -g ummaya
```

Homebrew on macOS:

```bash
brew install --cask umyunsang/ummaya/ummaya
```

The Homebrew cask installs a prebuilt macOS archive and does not run `npm install`
or `bun install` during installation. The unqualified official-cask form will
work only after Homebrew accepts UMMAYA into `Homebrew/homebrew-cask`.

Run `ummaya`, type `/login`, and paste your FriendliAI API key. Public CLI users should not need to prepare Kakao, JUSO, SGIS, data.go.kr, or other public API keys.

> UMMAYA is an academic and R&D project. It is not an official service of Anthropic, LG AI Research, FriendliAI, the Korean government, or any public agency.

## First Run

```bash
ummaya
```

Inside the terminal session:

```text
/login
```

Then ask in everyday language:

```text
동아대 승학캠퍼스에서 친구가 갑자기 아프면 지금 바로 연락할 응급실 어디가 가까워?
```

UMMAYA stores sessions locally. When a session can be resumed, the terminal prints a command such as `ummaya --resume <session-id>`.

## Why UMMAYA

Korean public services already exist across government portals, public datasets, address systems, emergency channels, weather services, hospital registries, and identity rails. The hard part for a citizen is not whether those systems exist. The hard part is knowing which one to use, in what order, and what to do next.

People do not usually think like this:

```text
Call the emergency medical institution API after resolving my administrative district code.
```

They think like this:

```text
다대1동 근처에서 지금 전화해볼 수 있는 병원 어디야?
```

UMMAYA treats that sentence as the interface. The terminal should show the work as it happens: location resolution, public-service lookup, protected-work checks when needed, compact tool results, and a final answer that a person can act on.

## What You Can Ask

These are prompts you can type directly into UMMAYA. They are written as user tasks, not as API names.

| Situation | Prompt |
|---|---|
| Nearby emergency care | `동아대 승학캠퍼스에서 친구가 갑자기 아프면 지금 바로 연락할 응급실 어디가 가까워? 찾아진 곳만 이름, 주소, 전화번호로 정리해줘.` |
| Local clinic lookup | `다대1동 근처에서 오늘 전화해볼 수 있는 내과가 있을까? 가까운 곳 위주로 주소랑 전화번호를 알려줘.` |
| Weather for a walk | `퇴근하고 다대포해수욕장 걸어가도 괜찮을까? 지금 비 오는지랑 체감상 추운지만 알려줘.` |
| Weather plus road risk | `비 오는 날 다대포에서 김해공항까지 차로 가야 해. 날씨랑 도로 위험 정보를 같이 보고 조심할 점을 알려줘.` |
| Moving workflow | `이사했어. 전입신고하고 자동차, 건강보험, 학교 관련 주소 변경까지 가능한 단계는 진행하고, 공식 권한이 필요한 단계는 어디서 멈추는지 알려줘.` |
| Permissioned workflow | `모바일 신분증으로 본인확인하고, 내 자격으로 가능한 복지 지원을 찾아서 신청 가능한 단계까지 진행해줘.` |

Live public-information flows are shown most often in the demo because they can be verified through public APIs. Identity, submission, payment, and correction flows are permissioned; UMMAYA routes them through `check` first, receives a scoped delegation context when the identity channel allows it, and only then lets `send` call the wrapped public-service channel. Today the public identity-check tools are mock or shape-mirrored unless an official credentialed channel is available; the OpenDID hackathon work targets the conversion of that `check` path into a live OmniOne CX / Open DID / Chain-backed tool. When official live authority is not available, the same flow is marked Mock or Handoff instead of pretending that a protected government action was completed.

## Main Tools

UMMAYA keeps the model-facing surface small. Instead of exposing dozens of agency-specific APIs directly to the LLM, it gives the agent four durable primitives and lets adapters handle ministry-specific details behind them.

### `locate`

`locate` turns places, addresses, coordinates, and administrative areas into usable location context. A prompt like "동아대 승학캠퍼스 근처" may need coordinates, district names, and region codes before any public-service lookup can make sense.

Typical use:

```text
동아대학교 승학캠퍼스 근처에서 지금 갈 수 있는 응급실을 알려줘.
```

The terminal should show location work as its own step, not hide it inside the final answer.

### `find`

`find` retrieves public information. This is the live-heavy path: weather, emergency rooms, hospitals, road safety, welfare information, and other public-service reads.

Typical use:

```text
다대포에서 김해공항까지 가야 하는데 비랑 도로 위험 정보를 같이 보고 판단해줘.
```

UMMAYA should only answer from results it actually found. If a live lookup returns one local hospital, the answer should not invent two more from another city.

### `check`

`check` handles identity and scoped delegation. This is where Mobile ID, MyData consent, certificates, or OmniOne-style QR/app verification belongs: the user should scan or approve through the identity channel instead of typing raw personal data into the chat. In the current public package these identity tools are mock-backed or shape-mirrored unless a real provider credential exists. The hackathon path is to replace the mock identity ceremony with a live OmniOne CX / Open DID / Chain-backed `check` tool while preserving the same downstream delegation contract. A successful protected `check` returns a delegation context that downstream tools can consume.

Typical use:

```text
모바일 신분증으로 본인확인하고, 내 자격으로 신청 가능한 복지 지원을 확인해줘.
```

The role of `check` is not generic advice. It is the protected-action boundary: identity proof, purpose, scope, consent, and delegation are established before UMMAYA moves toward a protected public-service action.

### `send`

`send` executes or prepares submission, payment, application, receipt, or official handoff flows through wrapped public-service channels. It consumes the delegation context from `check` when the target domain requires identity or consent.

Typical use:

```text
정부24 주민등록등본 발급 민원을 본인확인 후 신청 가능한 단계까지 진행해줘.
```

`send` is where UMMAYA moves beyond answer generation: if a live or permitted channel exists it calls that channel; if only a mock or official handoff is available it preserves the same receipt-shaped boundary and says so clearly.

## Permissioned Work

UMMAYA separates public information from protected action.

| Work type | UMMAYA behavior |
|---|---|
| Public lookup | Use live public adapters when available. |
| Location resolution | Use live geocoding/address/region adapters when available. |
| Identity and delegation | Use `check` to call the wrapped identity/consent channel, such as Mobile ID, MyData, certificates, or OmniOne-style QR/app verification. |
| Certificates, payment, submission, correction | Use `send` with the delegation context when a live or mock channel is registered; otherwise hand off to the official path. |
| API failure, zero result, missing authority | Stop clearly instead of inventing a result. |

This is not a separate safety pitch. It is part of how `check` and `send` work: the model plans the task, calls the right wrapped public-service tools, and stops at the authority boundary instead of acting like a reference-only RAG answerer.

## Model And License

UMMAYA currently uses `LGAI-EXAONE/K-EXAONE-236B-A23B` through FriendliAI Serverless for LLM responses.

- Model: [K-EXAONE-236B-A23B](https://huggingface.co/LGAI-EXAONE/K-EXAONE-236B-A23B)
- Reasoning mode: `/reasoning` or `UMMAYA_K_EXAONE_REASONING_MODE` selects `fast`, `balanced`, `deep`, `diagnostic`, or `auto`.
- Thinking channel: `UMMAYA_K_EXAONE_THINKING` default `false` remains as a legacy compatibility flag; set `/reasoning deep` or `UMMAYA_K_EXAONE_REASONING_MODE=deep` for reasoning-channel diagnostics or benchmark runs.
- Model license: [K-EXAONE AI Model License Agreement](https://huggingface.co/LGAI-EXAONE/K-EXAONE-236B-A23B/blob/main/LICENSE)
- Project license: [Apache License 2.0](LICENSE)

The model license and the UMMAYA source-code license are separate. UMMAYA does not grant rights to LG AI Research, FriendliAI, Hugging Face, Korean government, or public-agency assets.
