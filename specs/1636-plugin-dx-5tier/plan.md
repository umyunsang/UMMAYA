# Implementation Plan: Plugin DX 5-tier (Template · Guide · Examples · Submission · Registry)

**Branch**: `feat/1636-plugin-dx-5tier` | **Date**: 2026-04-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/Users/um-yunsang/KOSMOS/specs/1636-plugin-dx-5tier/spec.md`

## Summary

P5 ships the 5-tier external Plugin DX so ministries, agencies, and citizen developers can land KOSMOS tool adapters without forking the platform. Tier 1 (template + `kosmos plugin init` CLI) gives a contributor a passing test in ≤ 30 min; Tier 2 (9 Korean-primary guides under `docs/plugins/`) explains the conventions; Tier 3 (4 example plugins — 2 Live, 2 Mock) demonstrates the patterns; Tier 4 (PR template + `plugin-validation.yml` workflow + 50-item review checklist + `security-review.md` with PIPA §26 trustee acknowledgment) machine-enforces every reviewable invariant; Tier 5 (`kosmos-plugin-store` GitHub org + `kosmos plugin install` with SLSA-provenance verification + `src/kosmos/plugins/registry.py` + `src/kosmos/plugins/manifest_schema.py`) installs and discovers plugins at runtime through the existing Spec 022 BM25 index.

The technical approach reuses every existing harness primitive — Pydantic v2 manifests inherit the Spec 022/031 `AdapterRegistration` shape, OTEL spans extend Spec 021 with `kosmos.plugin.id`, permission decisions flow through the Spec 033 spectrum, audit records carry the Spec 024 `auth_level`/`pipa_class`/`is_irreversible`/`dpa_reference` quadruple, and consent receipts append to the Spec 035 memdir ledger. Zero new runtime dependencies on the Python side; on the TUI side we add only `slsa-verifier` as a vendored CLI we shell out to (decision: vendored binary, not a JS wrapper — see research § R-3).

## Technical Context

**Language/Version**: Python 3.12+ (existing backend baseline — `src/kosmos/plugins/`); TypeScript 5.6+ on Bun v1.2.x (existing Spec 287 TUI stack — `tui/src/commands/plugin-init.ts` + `tui/src/commands/plugin-install.ts`); YAML for `.github/workflows/plugin-validation.yml`; Markdown for `docs/plugins/` Korean-primary guides.

**Primary Dependencies**: `pydantic >= 2.13` (existing — manifest schema); `pydantic-settings >= 2.0` (existing — `KOSMOS_PLUGIN_*` env catalog); `httpx >= 0.27` (existing — example Live plugins); `opentelemetry-sdk` + `opentelemetry-semantic-conventions` (existing — `kosmos.plugin.id` span attribute, Spec 021 extension); `pytest` + `pytest-asyncio` (existing — example plugin test fixtures); stdlib `hashlib` (acknowledgment SHA-256), `subprocess` (shell out to `slsa-verifier`), `pathlib` (registry filesystem walk), `importlib` (auto-discovery loader). **Ink + React** (existing Spec 287 — `kosmos plugin init`/`install` UI). External tools shelled out to: `slsa-verifier` (vendored Go binary, ~10 MB, see research § R-3), `gh` (existing CLI for org/repo operations, used in workflow only). **Zero new Python runtime deps; zero new TS runtime deps** — AGENTS.md hard rule preserved.

**Storage**: User-tier memdir under `~/.kosmos/memdir/user/plugins/` (new path; siblings of `consent/` from Spec 035). Directory layout: `~/.kosmos/memdir/user/plugins/<plugin_id>/` containing the installed bundle (manifest.yaml, adapter.py, schema.py, fixtures, signature artifacts). `~/.kosmos/memdir/user/plugins/index.json` cached catalog snapshot for offline `kosmos plugin list`. Append-only consent receipts continue to live in `~/.kosmos/memdir/user/consent/` (Spec 035 ledger).

**Testing**: `uv run pytest` for backend (manifest validator, registry loader, BM25 index rebuild). `bun test` for TUI commands. `pytest` inside the `kosmos-plugin-template` repo for the scaffold itself (every scaffold MUST report green out of the box per FR-003). GitHub Actions matrix for `plugin-validation.yml` (negative-test PRs to verify rejection paths per SC-003). No live `data.go.kr` calls in CI per Constitution §IV.

**Target Platform**: Citizen laptop (macOS 12+, Linux Ubuntu 22.04+, Windows 11 with WSL2). Backend Python 3.12+ runtime; TUI bun 1.2.x runtime. No mobile path. Plugin-template repo and example-plugin repos run on the same target as KOSMOS itself (developer laptop).

**Project Type**: Multi-stack single-project (backend Python + TUI TypeScript + GitHub-side templates/workflows). The 5-tier scope is naturally distributed across all three stacks; we keep them under the same repository tree per AGENTS.md (the `kosmos-plugin-store` org is a *runtime* artifact; its catalog is hosted there but the catalog *generator* + `kosmos plugin install` resolver live in this repo).

**Performance Goals**:
- Plugin auto-discovery boot cost: < 200 ms per installed plugin (SC-010), measured by microbenchmark gated in CI.
- `kosmos plugin install <name>` cold install: < 30 s (SC-005) including network fetch, SLSA verification, manifest validation, registry registration, BM25 reindex.
- BM25 reindex after install: < 5 s for the new adapter to surface in `lookup(mode="search")` (SC-004).
- `plugin-validation.yml` end-to-end runtime: < 5 minutes per PR (so contributor feedback is fast).

**Constraints**:
- Zero new Python runtime dependencies (AGENTS.md hard rule + Constitution by precedent of every prior Spec).
- Zero outbound network calls in `plugin-validation.yml` test runner sandbox (Constitution §IV).
- Manifest schema MUST be backward-compatible with Spec 022/031 `AdapterRegistration` — plugins are GovAPITool instances, not a parallel hierarchy. Reuse the existing `_AUTH_TYPE_LEVEL_MAPPING` and the Spec 025 V6 backstop.
- Korean-primary documentation (memory `feedback_output_language`); English source code identifiers.
- All source text in English except Korean domain data (AGENTS.md hard rule); Korean text confined to `description_ko`, `search_hint_ko`, and `docs/plugins/*.ko.md`.

**Scale/Scope**:
- 4 example plugins ship with this Epic (Tier 3 deliverable).
- 9 Korean-primary guides (Tier 2 deliverable).
- 50-item review checklist (Tier 4 deliverable; derivation in research § R-1).
- Catalog scale assumption: hundreds of plugins (not millions) for the foreseeable future — incremental indexing is a deferred optimization.
- Repo layout for the 4 examples: standalone repos under the new `kosmos-plugin-store` org (decision: research § R-2).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version 1.1.1 (Ratified 2026-04-12, Last Amended 2026-04-19). Reviewed all six principles against this plan.

| Principle | Status | Evidence |
|---|---|---|
| **§I Reference-Driven Development** | PASS | Phase 0 Research § R-0 maps every design decision to one of: `docs/vision.md § Reference materials` (Pydantic AI for manifest schema, Claude Code reconstructed `builtinPlugins.ts` for the TS-side registry, Anthropic Cookbook orchestrator-workers for the example-plugin synthesis flow), AGENTS.md `docs/tool-adapters.md` checklist (50-item derivation foundation), or a prior KOSMOS Spec (022/024/025/031/033/035). Every guide under `docs/plugins/` MUST cite its reference (FR-007); this is enforced by checklist item Q4-CITE in research § R-1. |
| **§II Fail-Closed Security (NON-NEGOTIABLE)** | PASS | FR-023 mandates manifest defaults `requires_auth=True`, `is_personal_data=True`, `is_concurrency_safe=False`, `cache_ttl_seconds=0` — identical to the existing GovAPITool defaults. The scaffold CLI emits the strict defaults; relaxation requires explicit edit + CI documentation. The 50-item checklist (research § R-1) has dedicated items for each of the 4 fields. |
| **§III Pydantic v2 Strict Typing (NON-NEGOTIABLE)** | PASS | FR-019 mandates the manifest schema be a Pydantic v2 model with no `Any` types; `pipa_trustee_acknowledgment` is a discriminated nested model; verbs are a `frozenset[Literal[...]]` over the active plugin primitives + `plugin.<id>.<verb>` namespace pattern (regex-validated). The scaffold's emitted `schema.py` boilerplate is Pydantic v2 BaseModel with explicit `Field(...)` declarations including `description=` (per Spec 019 input-discipline). |
| **§IV Government API Compliance** | PASS | FR-016 mandates the validation-workflow test runner sandbox blocks all outbound sockets so example-plugin tests cannot accidentally hit live `data.go.kr` from CI. FR-008 example plugins ship recorded fixtures only. The `kosmos plugin init --mock` branch enforces `mock_source_spec` (URL or attribution) and a CI lint that no `httpx`/`aiohttp` outbound socket calls exist in the mock test path. |
| **§V Policy Alignment** | PASS | FR-014 + User Story 3 mandate machine-enforced PIPA §26 trustee acknowledgment for every plugin with `processes_pii: true`. The canonical text + SHA-256 lives in `docs/plugins/security-review.md`; CI rejects manifests with missing or hash-mismatched acknowledgment blocks. Aligns with AI Action Plan Principle 8/9 (single conversational window, Open API ecosystem) by lowering the contribution barrier for ministries' Open APIs. |
| **§VI Deferred Work Accountability** | PASS | spec.md "Scope Boundaries & Deferred Items" section present with 4 Permanent OOS items + 7 Deferred-table entries (2 referencing existing issues #1820 / #1812; 5 marked NEEDS TRACKING for `/speckit-taskstoissues`). Phase 0 Research § R-VALIDATION verifies each existing issue is OPEN and lists every NEEDS TRACKING entry for downstream resolution. Spec text scanned for unregistered "separate epic" / "future phase" / "v2" patterns — all matches are inside the Deferred table. |

**Gate verdict**: PASS — proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/1636-plugin-dx-5tier/
├── plan.md              # This file
├── research.md          # Phase 0 — 6 special-order research items + 50-item derivation + Deferred-items validation
├── data-model.md        # Phase 1 — PluginManifest / PIPATrusteeAck / ReviewChecklistItem / CatalogEntry / ConsentReceipt
├── quickstart.md        # Phase 1 — 30-min contributor walkthrough (verifies SC-001)
├── contracts/           # Phase 1
│   ├── manifest.schema.json          # JSON Schema export of PluginManifest (versioned contract)
│   ├── plugin-init.cli.md            # `kosmos plugin init <name>` argument + flag contract
│   ├── plugin-install.cli.md         # `kosmos plugin install <name>` argument + flag contract
│   ├── plugin-validation-workflow.md # `.github/workflows/plugin-validation.yml` job + step contract
│   ├── catalog-index.schema.json     # `kosmos-plugin-store/index.json` schema
│   └── pipa-acknowledgment.md        # Canonical PIPA §26 trustee text + SHA-256 + how to acknowledge
├── checklists/
│   └── requirements.md  # Already exists from /speckit-specify (16/16 pass)
└── tasks.md             # NOT created here; produced by /speckit-tasks
```

### Source Code (repository root)

```text
# Backend Python
src/kosmos/plugins/                        # NEW module
├── __init__.py
├── manifest_schema.py                     # FR-019 Pydantic v2 manifest model + nested PIPA block
├── registry.py                            # FR-020 auto-discovery loader + BM25 reindex hook
├── installer.py                           # `kosmos plugin install` Python-side resolver (TUI shells out)
├── slsa.py                                # SLSA verification helper (subprocess wrapper around vendored slsa-verifier)
├── canonical_acknowledgment.py            # SHA-256 of canonical PIPA text loaded from docs/plugins/security-review.md
├── exceptions.py                          # PluginRegistrationError, ManifestValidationError, AcknowledgmentMismatchError
└── tests/                                 # pytest suite (negative + positive)
    ├── test_manifest_schema.py
    ├── test_registry_autodiscovery.py
    ├── test_installer_slsa.py
    ├── test_acknowledgment_hash.py
    └── test_namespace_invariant.py

src/kosmos/tools/registry.py               # MODIFY: hook plugins.registry into BM25Index rebuild
src/kosmos/tools/models.py                 # MODIFY (additive): expose AdapterRegistration as the parent contract for plugin manifests

# TUI TypeScript
tui/src/commands/plugin-init.ts            # NEW — interactive `/plugin init <name>` scaffold (Ink prompts → file emit)
tui/src/commands/plugin-install.ts         # NEW — `/plugin install <name>` (catalog fetch → SLSA verify subprocess → backend IPC notify reload)
tui/src/commands/plugin-list.ts            # NEW — `/plugin list` (read ~/.kosmos/memdir/user/plugins/index.json)
tui/src/commands/index.ts                  # MODIFY: register the 3 new commands
tui/test/commands/plugin-init.test.ts      # bun test — verify scaffold emits passing template
tui/test/commands/plugin-install.test.ts   # bun test — mock SLSA pass + fail paths

# GitHub-side artifacts (live at repo root)
.github/ISSUE_TEMPLATE/plugin-submission.yml      # FR-011
.github/workflows/plugin-validation.yml           # FR-012/015/016
.github/workflows/plugin-acknowledgment-audit.yml # Out-of-scope drift workflow (Deferred)

# Documentation
docs/plugins/README.md                     # MODIFY (extend existing index)
docs/plugins/quickstart.ko.md              # NEW — 30-min path
docs/plugins/architecture.md               # NEW — Tool.ts + 4-primitive mapping
docs/plugins/pydantic-schema.md            # NEW — schema authoring rules
docs/plugins/search-hint.md                # NEW — Ko/En bilingual hints
docs/plugins/permission-tier.md            # NEW — Layer 1/2/3 decision tree
docs/plugins/data-go-kr.md                 # NEW — portal key handling
docs/plugins/live-vs-mock.md               # NEW — when to use which tier
docs/plugins/testing.md                    # NEW — pytest fixture conventions
docs/plugins/review-checklist.md           # NEW — the 50 items (canonical source-of-truth for plugin-validation.yml)
docs/plugins/security-review.md            # NEW — L3 gate + PIPA §26 trustee text + canonical SHA-256

# External repositories (created during implementation, not committed here)
# - kosmos-plugin-template (GitHub template repo)
# - kosmos-plugin-store (GitHub org)
# - kosmos-plugin-store/kosmos-plugin-seoul-subway
# - kosmos-plugin-store/kosmos-plugin-post-office
# - kosmos-plugin-store/kosmos-plugin-nts-homtax (Mock)
# - kosmos-plugin-store/kosmos-plugin-nhis-check (Mock)
```

**Structure Decision**: Multi-stack single-project, with the 5-tier scope distributed across `src/kosmos/plugins/` (backend), `tui/src/commands/` (TUI), `.github/` (workflow + template), and `docs/plugins/` (Korean-primary docs). External GitHub-side artifacts (template repo + 4 example repos + plugin-store org) are *runtime* deliverables produced by the implementation tasks, not in-repo source. The standalone-repo layout for the 4 examples (vs. sub-directories under a single examples repo) is decided in research § R-2 and committed in this plan.

## Complexity Tracking

> No Constitution-Check violations. The plan uses zero new Python or TS runtime dependencies, reuses every existing harness primitive, and keeps the GitHub-side template/workflow surface conventional. The only "new external thing" is the vendored `slsa-verifier` binary (research § R-3), which is the industry-standard SLSA L3 verification tool — chosen over re-implementing verification in Python (Constitution §I: prefer adopting validated patterns over inventing).

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none) | (none) | (none) |

## Post-Phase 1 Constitution Re-Check

After producing `research.md`, `data-model.md`, `contracts/`, and `quickstart.md`, the gate is re-evaluated. Result: **still PASS** — no design artifact introduced a new dependency, none altered the fail-closed default set, and the 50-item checklist derivation in `research.md § R-1` directly traces every item back to a Constitution principle, an AGENTS.md rule, or a prior Spec invariant. The standalone-repo layout decision (research § R-2) does not change Constitution standing — it is an organizational choice with `docs/plugins/quickstart.ko.md` documenting the convention.

## Phase Output Pointer

- Phase 0: [`research.md`](./research.md)
- Phase 1: [`data-model.md`](./data-model.md), [`contracts/`](./contracts/), [`quickstart.md`](./quickstart.md)
- Phase 2 (NEXT): `tasks.md` via `/speckit-tasks`

## Notes for downstream commands

- `setup-plan.sh` rejects `feat/`-prefixed branches (KOSMOS uses Conventional Commits per AGENTS.md, spec-kit defaults to bare `NNN-name` branches). The `.specify/feature.json` pointer (`specs/1636-plugin-dx-5tier`) is authoritative for downstream commands; bypass the script.
- `update-agent-context.sh` likely fails the same branch check; `CLAUDE.md`'s Active Technologies section is updated manually to add the P5 stack rows after `/speckit-tasks` completes (the script will be retried then; if still failing, manual edit).
