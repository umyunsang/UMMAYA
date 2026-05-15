# Changelog

All notable changes to UMMAYA are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.1-alpha] — 2026-04-26

The UMMAYA migration-completion release. Initiative #1631 closed; the six Phase Epics — P0 #1632 (baseline runnable), P1+P2 #1633 (dead-code + Friendli migration), P3 #1634 (tool-system wiring), P4 #1847 (UI L2 citizen port), P5 #1927 (5-tier plugin DX), and P6 #1637 (docs/API + integration smoke) — all merged.

### Highlights

- UMMAYA now routes a Korean citizen's question through the migrated Claude Code harness end-to-end: EXAONE function call → `lookup` / `submit` / `verify` / `subscribe` primitives → registered adapter → permission gauntlet → response in the migrated TUI.
- 24 registry-bundled adapters documented under [`docs/api/`](./docs/api/) with seven mandatory fields (classification · envelope · bilingual ko/en search hints · endpoint · permission tier · worked example · constraints) and 25 Draft 2020-12 JSON Schema files under [`docs/api/schemas/`](./docs/api/schemas/), produced deterministically by [`scripts/build_schemas.py`](./scripts/build_schemas.py) (stdlib + Pydantic v2 only).
- 5-tier plugin DX onboards external contributors via `ummaya plugin init` (Spec 1636); PIPA §26 trustee acknowledgment SHA-256 enforced in CI.
- Integrated `bun test` reports 928 pass / 4 skip / 3 todo / 0 fail / 0 errors over 935 tests; legacy `docs/tools/` absorbed into `docs/api/`; the removed `road_risk_score` composite leaves zero non-historical references in the documentation tree.
- Zero new runtime dependencies introduced across the migration (AGENTS.md hard rule preserved through every Phase).

### Aligned with

- Korea AI Action Plan (2026-2028) Principles 8 (single conversational surface), 9 (Open API and OpenMCP), and 5 (consent-based access; no paper submission).
- PIPA §26 trustee model — every adapter that processes personal information is wired through the permission gauntlet (Spec 033) and records receipts in the user-tier memdir.

### Out of v0.1-alpha (deferred)

- Full OpenAPI 3.0 specification for `/agent-delegation` (#1972).
- Permanent removal of the `ministries_for_composite()` API extension point (#1973).
- Live-mode regression coverage for the 12 Live-tier adapters (#1974).
- Auto-generated adapter spec stubs from Pydantic docstrings (#1975).
- Shape-mirror migration of the OPAQUE mock stubs (`barocert/`, `npki_crypto/`, `omnione/`) into `docs/scenarios/` (#1976).

## [Unreleased]

### Added

- Added fourteen direct-curl verified data.go.kr-style `find` adapters, generated JSON schemas, and docs for the first credential-backed public-data adapter wave.
- Initial project scaffold with `README.md` and `.gitignore`
- Apache License 2.0
- Contribution guide, Code of Conduct (Contributor Covenant 2.1), security policy
- Issue templates for bug reports, feature requests, and API adapter proposals
- Pull request template

### Fixed

- Corrected prepackage TUI branding so resume instructions, terminal titles, and package/version output use UMMAYA/ummaya and `v0.1.0-alpha` instead of upstream Claude CLI names or issue-number build metadata.
