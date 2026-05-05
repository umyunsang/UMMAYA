<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/kosmos-banner-dark.svg"/>
  <source media="(prefers-color-scheme: light)" srcset="assets/kosmos-banner-light.svg"/>
  <img alt="KOSMOS" src="assets/kosmos-banner-light.svg" width="600"/>
</picture>

# KOSMOS

**KO**rean public **S**erivce **M**ulti-agent **O**rchestration **S**ystem

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Code of Conduct](https://img.shields.io/badge/Contributor%20Covenant-2.1-purple.svg)](CODE_OF_CONDUCT.md)
[![GitHub Discussions](https://img.shields.io/badge/discussions-join-blueviolet)](https://github.com/umyunsang/KOSMOS/discussions)

A conversational multi-agent harness that orchestrates data.go.kr's 5,000+ public APIs around LG AI Research's K-EXAONE through an agentic tool loop.

> Academic R&D project. Not affiliated with Anthropic, LG AI Research, or the Korean government.

## Vision

Turn the 5,000+ fragmented public APIs on data.go.kr into a single conversational interface where citizens can resolve cross-ministry civil affairs (민원) in natural language — route safety, emergency services, welfare benefits, residence transfer, and more.

## Citizen Scenarios

Five end-to-end flows the platform must handle for the vision to be considered met:

```text
시민:   "내일 부산에서 서울 가는데, 안전한 경로 추천해줘"
KOSMOS: KOROAD accident data + KMA weather alerts + road-risk index
        → "Gyeongbu Expressway Daejeon-Cheonan section: high risk,
           fog advisory. Suggest Jungbu-Naeryuk detour."

시민:   "아이가 열이 나는데 근처 야간 응급실 어디야?"
KOSMOS: 119 emergency API + HIRA hospital info
        → Available ERs ranked by location + current wait time

시민:   "이사 준비 중인데, 전입신고랑 자동차 주소변경이랑
        건강보험 주소변경 다 해야 하는데"
KOSMOS: Coordinator dispatches Civil-affairs / Transport / Welfare workers
        → "전입신고 선행 → 자동차·건강보험 병렬"
```

Citizens never learn which ministry runs which API. **KOSMOS does the routing.**

## Architecture

KOSMOS transfers six architectural layers from Claude Code into the public-service domain:

<img src="docs/diagrams/kosmos_6_layer_architecture.svg" alt="KOSMOS 6-Layer Architecture" width="100%">

The lineage of each layer:

| Layer | Claude Code Origin | KOSMOS Adaptation |
|---|---|---|
| **Query Engine** | `while(true)` tool loop + 5-stage preprocessing | Civil-affairs state machine with ministry routing |
| **Tool System** | `buildTool()` factory + Partition-Sort cache strategy | `buildGovAPI()` adapters for data.go.kr endpoints |
| **Permission Pipeline** | 7-step gauntlet with bypass-immune checks | Citizen authentication + PII protection layers |
| **Agent Swarms** | File-based mailbox IPC + Coordinator synthesis | Ministry-specialist agents over message queue |
| **Context Assembly** | CLAUDE.md 6-tier memory + per-turn attachments | `CITIZEN.md` profile + live API status attachments |
| **Error Recovery** | `withRetry` with 429/529/401 matrix | Public-API outage fallback + cross-ministry verification |

For deep dives into the Query Engine loop, the Permission Pipeline gauntlet, and the Agent Swarm coordination model, see [`docs/presentation.md`](docs/presentation.md) and [`docs/vision.md`](docs/vision.md).

## L1 Pillars (approved 2026-04-24)

Canonical requirements tree: [`docs/requirements/kosmos-migration-tree.md`](docs/requirements/kosmos-migration-tree.md). Every subsequent spec and PR cites this tree as its source of truth.

- **L1-A · LLM Harness Layer** — Single fixed provider: **FriendliAI Serverless + K-EXAONE** (model ID `LGAI-EXAONE/K-EXAONE-236B-A23B` — 236B MoE with 23B active params; native 256K context; `enable_thinking=True` is the model-card default, KOSMOS toggles via `KOSMOS_K_EXAONE_THINKING` env, default `true` — reasoning active by default, set to `false` to disable). CC agentic-loop preserved 1:1. Native K-EXAONE function calling (Hermes-parser compatible). Context from `prompts/system_v1.md` + compaction + prompt cache. Sessions in `~/.kosmos/memdir/user/sessions/` (JSONL). Error recovery: ordinary network retry only. Observability: 4-tier OTEL (GenAI / Tool / Permission / local Langfuse) with zero external egress.
- **L1-B · Public-Service Tool System** — `Tool.ts` interface rewritten, registered on both TS and Python sides. Hybrid coverage (built-in live APIs + built-in mocks + plugin infra). Discovery via BM25 + dense `lookup`. Composite tools removed — LLM chains primitives. Full 5-tier plugin DX (template / guide / examples / submission / registry), Korean-primary, PIPA-trustee responsibility explicit.
- **L1-C · Main-Verb Abstraction** — Four reserved primitives (`lookup` · `submit` · `verify` · `subscribe`) with a shared `PrimitiveInput/Output` envelope. Self-classifying adapters routed by central `build_routing_index()`. System prompt exposes primitive signatures only; BM25 surfaces everything else dynamically. Plugin extensions namespaced as `plugin.<id>.<verb>`.

## Brand

UFO mascot (dome + saucer + landing lights, 4-pose adaptation of CC's Clawd technique) · purple palette (`body #a78bfa` · `background #4c1d95`) · brand glyph `✻` · thread glyphs `⏺ · ⎿` (CC-preserved).

## Architecture layers and L1 pillars

The six-layer architecture above describes **how the harness is structured**. The three L1 pillars describe **what the harness delivers to citizens**. Both are canonical — layers answer the engineering "how", pillars answer the product "what". Every spec PR maps its changes to at least one pillar and one layer.

## Execution phases (canonical)

Migration from the CC port (Epic P0) to a shippable citizen harness is sequenced as seven phases. Each phase is a separate Epic issue citing the tree.

| Phase | Epic | Scope |
|---|---|---|
| **P0** Baseline Runnable | [#1632](https://github.com/umyunsang/KOSMOS/issues/1632) (merged 2026-04-24) | CC 2.1.88 port compile/runtime recovery |
| **P1** Dead code elimination | [#1633](https://github.com/umyunsang/KOSMOS/issues/1633) | ant-only branches · `feature()` flags · CC version migrations · CC telemetry |
| **P2** Anthropic → FriendliAI | [#1633](https://github.com/umyunsang/KOSMOS/issues/1633) (combined with P1) | API · auth · OAuth → FriendliAI constants |
| **P3** Tool-system wiring | #1634 (pending) | `Tool.ts` + Python stdio MCP · 4 primitives |
| **P4** UI L2 implementation | #1635 (pending) | Components for REPL / Permission Gauntlet / Ministry Agent / Onboarding / aux |
| **P5** Plugin DX | #1636 (pending) | template · CLI · docs · examples · registry |
| **P6** Docs + smoke | #1637 (pending) | `docs/api` · `docs/plugins` · `bun run tui` validation |

## Status

Live integration against `data.go.kr` validated end-to-end for Scenario 1 (route safety) with 33/33 tests passing. Epic #1632 (P0) merged on 2026-04-24, restoring compile + runtime for the ported CC 2.1.88 harness. Epic #1633 (P1 + P2) spec in progress.

## Policy Alignment

KOSMOS's mission directly mirrors **Korea AI Action Plan 2026-2028** (국가인공지능전략위원회, 2026.2.25), Strategic Area 7 (공공AX), Task 58, Principle 9:

> "Open API와 OpenMCP를 제공해 민간에서도 공공서비스를 손쉽게 결합해서 국민들에게 제공할 수 있어야 한다."
> *(Open API and OpenMCP must be provided so that the private sector can easily combine public services and deliver them to citizens.)*

Full citation set: [`docs/presentation.md § 1.5 정책 정합성`](docs/presentation.md#15-정책-정합성--대한민국-ai-행동계획-2026-2028).

## Contributing

Contributions are very welcome — issues, design discussions, tool adapters, and documentation. Start with:

- [CONTRIBUTING.md](CONTRIBUTING.md) — workflow, branch and commit conventions, coding standards
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — Contributor Covenant 2.1
- [SECURITY.md](SECURITY.md) — private vulnerability reporting
- [CHANGELOG.md](CHANGELOG.md) — release history

For questions or design proposals, open a [Discussion](https://github.com/umyunsang/KOSMOS/discussions) before writing code on large ideas.

## License

Licensed under the [Apache License 2.0](LICENSE). By contributing, you agree that your contributions will be licensed under the same terms.
