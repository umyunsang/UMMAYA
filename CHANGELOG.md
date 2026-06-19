# Changelog

All notable changes to UMMAYA are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.2.9] - 2026-06-19

### Fixed

- Re-ran the release after v0.2.8 npm publication exposed that Cask SHA
  validation still depended on local-vs-CI archive byte identity.
- Changed the Homebrew artifact workflow to render the release Cask from the
  CI-built macOS artifacts and upload that generated Cask alongside the release
  assets, keeping the published tap aligned with the actual public tarballs.

## [v0.2.8] - 2026-06-19

### Fixed

- Rebuilt the release after v0.2.7 npm publication exposed a remaining Homebrew
  artifact gate failure.
- Switched Homebrew Cask archive creation from platform `tar`/`gzip` commands to
  `tar@7.5.16` portable archive generation with fixed metadata, so committed
  Cask checks compare against deterministic CI-built artifacts.

## [v0.2.7] - 2026-06-19

### Fixed

- Re-ran the release from the final hardening commit so npm provenance, tag target,
  GitHub Release, and Homebrew artifacts converge on the same source revision.
- Regenerated Homebrew Cask metadata from the final package input after formatting and
  lockfile changes, preventing stale local tarball SHAs from blocking publication.

## [v0.2.6] - 2026-06-19

### Fixed

- Removed remaining public CLI help references to upstream Claude Desktop and internal
  Claude environment/file names from the UMMAYA startup and MCP command surfaces.
- Bundled public-form conformance baselines as wheel resources so installed packages do
  not depend on repository-relative test fixtures at runtime.
- Hardened release launcher tests so Python virtualenv detection proves the exact
  `import ummaya.cli` probe before selecting a packaged backend.

### Security

- Added npm and Bun runtime dependency audit gates to CI, removed stale Python audit
  exceptions, upgraded PyTorch CPU wheels to 2.12.1, and patched the npm/Bun runtime tree
  for current high/critical advisories.

## [v0.2.5] - 2026-06-19

### Added

- Public document harness: a single model-facing `document` tool wraps Korean public-form
  authoring (HWP/HWPX/PDF/OOXML/ODF) through internal operations — inspect, extract,
  form-schema, copy-for-edit, apply-fill, apply-style, render, validate-public-form, and
  save. Authoring is gated on Evidence Fabric coverage plus explicit approval.
- TUI document approval review surface so document authoring stops for an in-session
  approval before the harness writes, fills, or renders a public form.

### Changed

- Modernized adapter route selection: intent extraction → decision service → feasibility
  → retrieval policy → cards/projection now ranks the concrete adapter set surfaced to
  the model.

### Fixed

- Preserved issued document approval tokens across the TUI approval flow so an approved
  authoring session is not re-prompted.

## [v0.2.4] - 2026-05-31

### Fixed

- Synced the Homebrew cask artifact SHA with the published 0.2.4 macOS archive and cleaned
  release artifacts so the npm tarball, Python wheel, TUI bundle, and Cask metadata agree.

## [v0.2.3] - 2026-05-26

### Fixed

- Restored the released v0.2.1 Claude Code-style mid-loop painting behavior after
  v0.2.2's deferred concrete adapter loading hid the root primitive tool surface.
- Emitted same-turn assistant preamble text before tool-call frames so the TUI paints
  the model's intent/tool-use narration before the first adapter row and between tool calls.
- Added regression coverage and captured tmux/VHS evidence for the weather query loop.

## [v0.2.2] - 2026-05-25

### Fixed

- Stabilized live adapter discovery so location-heavy citizen queries keep the relevant
  concrete medical, emergency, traffic, and weather tools visible to the model.
- Added fail-closed coordinate validation and recovery hints for HIRA, NMC, and locate
  follow-up calls while preserving KMA's grid-based weather path.
- Hardened packaged npm and Homebrew launchers against stale backend environment variables
  and verified the 0.2.2 package metadata across npm, Python, TUI, uv, and Cask files.
- Made Homebrew cask artifact archives deterministic and omitted optional native canvas builds
  so committed Cask SHA values match the published macOS artifacts.

## [v0.2.0] - 2026-05-25

### Added

- Added the KMA APIHub structured adapter catalog and generated tool surface for approved
  weather, observation, satellite, radar, aviation, earthquake, and model endpoints.
- Added prebuilt macOS Homebrew cask artifacts for the project tap install path.
- Added TUI/package smoke coverage for the CC-style runtime bundle and FriendliAI login path.

### Changed

- Tightened the UMMAYA TUI and agent loop toward the restored Claude Code harness structure
  while keeping UMMAYA branding, K-EXAONE/FriendliAI provider wiring, and Korean public-service
  tool content.
- Updated release packaging so npm metadata, Python metadata, TUI metadata, and Homebrew cask
  metadata move together for the 0.2 series.
- Retired unavailable live identity-check branches from the active release surface after provider
  access was confirmed unavailable for the current undergraduate account.

### Fixed

- Fixed terminal submit behavior for LF/coalesced enter input paths and paste-followed-by-enter
  scenarios.
- Fixed KMA weather calls to use the APIHub credential path for the approved KMA APIHub
  endpoints instead of mixing it with the data.go.kr credential surface.
- Fixed duplicated final-answer rendering in the live TUI tool loop.

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

## [v0.1.13] - 2026-05-22

### Fixed

- Normalized LF terminal keypresses to Return in the Ink input parser so prompt text submits correctly in terminals that send `\n`.
- Synced the Homebrew cask SHA to the published `ummaya@0.1.13` npm registry tarball.

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
