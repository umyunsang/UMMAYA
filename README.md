<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/ummaya-banner-dark.svg"/>
  <source media="(prefers-color-scheme: light)" srcset="assets/ummaya-banner-light.svg"/>
  <img alt="UMMAYA" src="assets/ummaya-banner-light.svg" width="600"/>
</picture>

# UMMAYA

**U**nified **M**ulti-**M**inistry **A**gent for **Y**our **A**dministration

`npm install -g ummaya`
or `brew install --cask ummaya`

UMMAYA is a local conversational multi-agent CLI for Korea's national AX public-service infrastructure. It keeps the Claude Code-style harness shape, swaps the model layer to FriendliAI Serverless + K-EXAONE, and swaps the tool surface to Korean public-service adapters.

> Academic R&D project. Not affiliated with Anthropic, LG AI Research, FriendliAI, or the Korean government.

![UMMAYA demo](assets/ummaya-demo.gif)

The demo is recorded from the real Ink TUI against an offline IPC backend. It is generated from [`docs/demo/ummaya-readme.tape`](docs/demo/ummaya-readme.tape) with [VHS](https://github.com/charmbracelet/vhs).

## Quickstart

Install with npm:

```bash
npm install -g ummaya
ummaya
```

Install with Homebrew:

```bash
brew install --cask ummaya
ummaya
```

Use from a source checkout:

```bash
uv sync --frozen --all-extras --dev
cd tui
bun install --frozen-lockfile
bun run tui
```

UMMAYA requires a **FriendliAI API key** before it can send model requests. Start the TUI and run:

```text
/login
```

The FriendliAI key is session-scoped and is not saved to disk. Public-service provider credentials such as data.go.kr, Kakao, Juso, SGIS, identity, payment, utility, or certificate keys are operator-managed; released CLI users are not asked to provide those keys.

## What It Does

UMMAYA turns fragmented public-service channels into one LLM-mediated administrative interface. Citizens should not need to know which ministry, portal, certificate, payment rail, or public-infrastructure operator owns a task.

The runtime is organized around reserved primitives:

| Primitive | Purpose |
|---|---|
| `lookup` | Search or retrieve public-service data and policy evidence |
| `resolve_location` | Normalize addresses, regions, and route context |
| `verify` | Gate identity, delegation, and consent-sensitive access |
| `submit` | File an application, payment, correction, or official request after confirmation |
| `subscribe` | Track deadlines, alerts, status changes, and follow-up events |

Each agency capability is wrapped as one tool adapter. Live adapters call official callable channels when credentials and policy allow it. Mock adapters mirror policy-mandated or documented channels when a live public surface is unavailable. Opaque domains remain documented handoff scenarios.

## Citizen Scenarios

The README demo sweeps the canonical user scenarios that define UMMAYA's target state:

| Scenario | Citizen request |
|---|---|
| Tax execution | "작년 종합소득세 신고하고 환급받을 수 있으면 환급 계좌까지 등록해줘." |
| Residence transfer | "이사했어. 전입신고하고 자동차, 건강보험, 학교 관련 주소도 한 번에 바꿔줘." |
| Payment consolidation | "이번 달 재산세랑 자동차세, 과태료 밀린 거 확인하고 납부 가능한 건 처리해줘." |
| Birth and welfare | "아기가 태어났어. 출생신고, 아동수당, 첫만남이용권, 건강보험 피부양자 등록까지 도와줘." |
| Housing transaction | "전세 계약했어. 확정일자, 임대차 신고, 전세보증 관련 절차를 위험한 부분까지 체크해서 처리해줘." |
| Business start | "카페 창업하려고 해. 사업자등록, 영업신고, 위생교육, 카드가맹, 세금 준비까지 순서대로 처리해줘." |
| Emergency care | "아이가 밤에 열이 높아. 지금 갈 수 있는 응급실이나 야간진료 병원 찾고 보험 적용되는지도 알려줘." |
| Route safety | "내일 부산에서 서울 가는데 날씨, 도로 위험, 대중교통 지연까지 보고 가장 안전한 이동 방법 추천해줘." |
| Disaster response | "집이 침수됐어. 피해 신고, 재난지원금, 임시주거, 전기·가스 안전 점검까지 바로 도와줘." |
| Personal-data rights | "정부기관들이 내 정보를 어디에 쓰고 있는지 확인하고 잘못된 주소나 연락처는 고쳐줘." |

The full target-state demand set lives in [`eval/scenarios/national_ax_citizen_requests_v1.yaml`](eval/scenarios/national_ax_citizen_requests_v1.yaml).

## Architecture

UMMAYA preserves the useful local-agent shape of Claude Code while changing the domain:

| Layer | UMMAYA adaptation |
|---|---|
| Query engine | Tool loop for citizen administrative requests |
| Tool system | `GovAPITool` adapters over Korean public-service channels |
| Permission pipeline | Citizen authentication, consent, PII, and irreversible-action gates |
| Agent swarms | Ministry-specialist workers coordinated through the harness |
| Context assembly | System prompt, session compaction, citizen context, and attachments |
| Error recovery | Network retry, public-channel outage handling, and cited handoff |

The canonical design references are [`docs/vision.md`](docs/vision.md), [`docs/requirements/ummaya-migration-tree.md`](docs/requirements/ummaya-migration-tree.md), and the research-only Claude Code source map under `.references/`.

## Status

Current public release surface:

- npm package: `ummaya`
- Homebrew cask: `ummaya`
- PyPI/backend package: intentionally excluded from this release surface

UMMAYA is still a student portfolio and research project. Some public-service flows are live where official APIs and credentials exist; transactional civil-affairs, identity, certificate, payment, utility, and welfare flows may be mock or handoff until official callable channels are available.

## Documentation

- [`docs/vision.md`](docs/vision.md) - thesis, six-layer design, and reference catalog
- [`docs/packaging.md`](docs/packaging.md) - packaging policy and release workflow
- [`docs/plugins/README.md`](docs/plugins/README.md) - plugin and adapter contributor entry point
- [`CHANGELOG.md`](CHANGELOG.md) - release history
- [`SECURITY.md`](SECURITY.md) - vulnerability reporting

## Contributing

Contributions are welcome through issues, discussions, documentation, and tool adapters. Start with [`CONTRIBUTING.md`](CONTRIBUTING.md) and open a [Discussion](https://github.com/umyunsang/UMMAYA/discussions) before large design changes.

## License

Licensed under the [Apache License 2.0](LICENSE).
