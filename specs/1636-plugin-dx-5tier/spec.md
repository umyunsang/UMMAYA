# Feature Specification: Plugin DX 5-tier (Template · Guide · Examples · Submission · Registry)

**Feature Branch**: `feat/1636-plugin-dx-5tier`
**Created**: 2026-04-25
**Status**: Draft
**Input**: User description: P5 · Plugin DX (Full 5-tier) — ministry, agency, and citizen developers can contribute KOSMOS tool adapters via a 5-tier Developer Experience infrastructure (template · guide · examples · submission · registry). Korean primary, PIPA §26 trustee responsibility explicit. Canonical sources: Epic #1636, `docs/requirements/kosmos-migration-tree.md § L1-B B8`, `docs/vision.md § Reference materials`, execution-phase order § P5.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ministry developer contributes a Live tool adapter via the 5-tier DX (Priority: P1)

A backend developer at a Korean ministry (e.g., 우정사업본부) needs to expose a public-data API (parcel tracking) so KOSMOS citizens can ask "내 택배 어디?" and have the LLM call the right adapter. Today there is no path for them to do this without forking KOSMOS itself.

**Why this priority**: This is the entire reason P5 exists. Without an external contribution path, KOSMOS cannot scale beyond the 4 seed adapters from Spec 022 + the bundled Phase-2 adapters. The migration tree § L1-B B8 explicitly mandates "Full 5-tier · 한국어 primary" so external developers — not just the core team — can land adapters. Without P1 working end-to-end, every other tier (guide, examples, submission, registry) is decoration.

**Independent Test**: A developer with no prior KOSMOS knowledge clones `kosmos-plugin-template`, runs `kosmos plugin init seoul-subway` from the TUI, edits the generated `adapter.py` to wrap the Seoul Open Data Plaza subway-arrival API, runs `uv run pytest` against the generated fixture replay, and submits a PR using the plugin-submission issue template. The PR validation workflow gates the merge. After merge, `kosmos plugin install seoul-subway` from a citizen's TUI registers the adapter into the live `lookup` BM25 index. Success: the LLM, when asked about subway arrivals, surfaces the new adapter via dynamic discovery and invokes it through the `lookup(mode="fetch")` envelope without any system-prompt edit.

**Acceptance Scenarios**:

1. **Given** a developer who has never touched KOSMOS, **When** they read `docs/plugins/quickstart.ko.md` and follow the steps, **Then** they reach a passing `pytest` green for the boilerplate adapter within 30 minutes.
2. **Given** a generated plugin that violates manifest invariants (e.g., overrides reserved root primitive `lookup` instead of `plugin.<id>.<verb>`), **When** the developer opens a PR, **Then** the `plugin-validation.yml` workflow fails with a Korean error message citing which invariant was violated and which `docs/plugins/` page explains the fix.
3. **Given** a merged plugin published to `kosmos-plugin-store`, **When** a citizen runs `kosmos plugin install seoul-subway`, **Then** the install verifies the SLSA signature, registers the adapter into the in-process registry + BM25 index, and the next `lookup(search="지하철")` LLM call returns the new adapter as a candidate without restarting the TUI.

---

### User Story 2 - Citizen developer contributes a Mock tool adapter for a permission-restricted system (Priority: P2)

A graduate student studying public-service AX wants to contribute a mock adapter for a system the core team cannot legally call (e.g., 홈택스 — requires NTS partnership). They author a Mock-tier adapter that mirrors the public OpenAPI spec without ever calling the live system, so KOSMOS users can still demo and prototype the citizen experience.

**Why this priority**: Mock adapters are the only way KOSMOS can demonstrate breadth across systems where the project lead has no API key (memory `feedback_mock_evidence_based`: shape-mirroring is allowed only when public spec exists). P2 because the Live-tier path (P1) must work first; Mock-tier is a thinner variant of the same DX flow.

**Independent Test**: The contributor uses the same `kosmos plugin init` CLI but selects the `--mock` flag in the scaffold prompt. The template generates an adapter where every `httpx` call is replaced with fixture-replay logic and the manifest declares `tier: "mock"`. The validation workflow enforces that mock adapters reference a public spec source (URL or filed-document attribution) and never make outbound network calls (CI lint check). Success: the mock adapter appears in `lookup(search="세금")` results with a visible `[Mock]` tag in the TUI Plugin browser (P4-wired surface).

**Acceptance Scenarios**:

1. **Given** a contributor follows the Mock-tier branch of the quickstart guide, **When** they generate a `nts-homtax` adapter and run the test suite, **Then** every fixture is replayed without any outbound network attempt and the test runner reports a recorded `network egress = 0`.
2. **Given** a Mock adapter manifest, **When** the validation workflow inspects it, **Then** the workflow rejects manifests that lack a `mock_source_spec` field pointing to a public document (URL, PDF, or attribution).
3. **Given** an installed Mock adapter, **When** the TUI Plugin browser renders, **Then** the entry shows the Mock glyph distinct from Live entries so the citizen knows the response is illustrative, not authoritative.

---

### User Story 3 - Plugin author handles personal-data flow with PIPA §26 trustee acknowledgment (Priority: P2)

A plugin author writes an adapter that processes a citizen's resident-registration number (주민등록번호) — for example, a 건강검진 (health-checkup) lookup. PIPA §26 requires the trustee (the plugin) to formally acknowledge their role and obligations. The DX must enforce this acknowledgment in the manifest itself, not as an honor-system docstring.

**Why this priority**: KOSMOS's PIPA stance (memory `project_pipa_role`) is "trustee by default — controller carve-out only at the LLM synthesis step." Every plugin that processes PII inherits trustee status. Without machine-enforced acknowledgment, KOSMOS as the platform inherits unbounded liability. P2 because it is a precondition for P1 graduating to general public release, but P1 can ship to internal contributors without it being fully enforced.

**Independent Test**: A contributor opens a plugin with `processes_pii: true` in the manifest. The `plugin-validation.yml` workflow rejects the PR unless the manifest also contains a `pipa_trustee_acknowledgment` block listing: trustee org name, contact, the PII fields handled, the legal basis for handling, and a SHA-256 hash of the acknowledgment text the contributor agrees to. The acknowledgment text is canonical (lives in `docs/plugins/security-review.md`) and cannot be modified per-plugin — only acknowledged. Success: a manifest missing the block fails CI; a manifest with a tampered hash fails CI; a complete and well-formed block passes CI and is recorded as the PR-merge audit trail.

**Acceptance Scenarios**:

1. **Given** an adapter manifest with `processes_pii: true` and no `pipa_trustee_acknowledgment` block, **When** the validation workflow runs, **Then** CI fails with a Korean error referencing PIPA §26 and pointing to `docs/plugins/security-review.md`.
2. **Given** an acknowledgment block whose `acknowledgment_sha256` does not match the canonical text, **When** validation runs, **Then** CI fails and reports the expected hash so the contributor can re-sync.
3. **Given** a PR merged with a valid acknowledgment, **When** the registry catalogs the plugin, **Then** the catalog entry surfaces the trustee org name + contact so installing citizens can see who handles their PII before activating the plugin.

---

### User Story 4 - PR validation workflow enforces 50-item review checklist before merge (Priority: P2)

A core maintainer reviews a contributed plugin PR. Today, manual review is the only quality gate, which does not scale and is inconsistent. The 50-item review checklist (covering Pydantic schema strictness, search_hint Ko/En completeness, permission-tier correctness, fail-closed defaults, fixture coverage, no hardcoded keys, OTEL span emission, and 43 more items) MUST be machine-enforced before a human even reviews.

**Why this priority**: Constitution §II (Fail-Closed Security) and §III (Pydantic v2 Strict Typing) are non-negotiable. The 50-item checklist is the operationalization of those principles for plugin contributions. P2 because P1 can land internally with manual review while the workflow is being built, but external contributions cannot scale without it.

**Independent Test**: A contributor opens a PR that violates checklist item #14 (fail-closed default `requires_auth = False`). The `plugin-validation.yml` workflow fails the PR with a comment listing the failing checklist item, the constitution principle it violates, and the line in `adapter.py` to fix. Success: every one of the 50 items is mapped to either a static lint, a unit-test assertion, or a workflow check; no item is left as "manual reviewer judgment."

**Acceptance Scenarios**:

1. **Given** a plugin PR, **When** `plugin-validation.yml` runs, **Then** all 50 checklist items execute and the PR receives a Korean summary comment stating "✓ N/50 통과 · ✗ M/50 실패 — 실패 항목: [#3 search_hint Korean missing, #14 requires_auth=False, ...]".
2. **Given** a PR that passes 50/50, **When** human reviewers look at it, **Then** the Copilot Gate + Codex Gate proceed without the platform team having to re-verify mechanical items.
3. **Given** an evolution of the checklist (e.g., new item added), **When** the canonical `docs/plugins/review-checklist.md` is updated, **Then** the workflow's executable checks are derived from the same source-of-truth (a manifest mapping item-id → check-implementation), preventing drift.

---

### User Story 5 - Citizen browses, installs, and revokes plugins from within the TUI (Priority: P3)

A citizen using KOSMOS opens the Plugin browser (already wired in P4 via `tui/src/components/plugins/PluginBrowser.tsx`), sees community-contributed plugins from `kosmos-plugin-store`, installs one with `kosmos plugin install <name>`, and later revokes a previously granted permission via the existing `/consent` flow.

**Why this priority**: P3 because the citizen-facing install/revoke surface is the *consumption* side of P5. Until P1–P4 ship, there is nothing for citizens to consume. The actual marketplace browser UI (the `a` keystroke destination in P4 PluginBrowser) is explicitly out of scope (#1820 — separate Epic) — P5 only ships the install CLI + registry catalog the marketplace would later consume.

**Independent Test**: A citizen runs `kosmos plugin install seoul-subway` from the TUI. The install command resolves the plugin name against the `kosmos-plugin-store` GitHub org catalog, downloads a signed bundle, verifies the SLSA signature, registers the adapter into the running session's tool registry without restart, surfaces a Layer-1/2/3 permission summary, and waits for citizen consent. Success: the citizen can ask the LLM a subway question and the new adapter is invoked, with all permission decisions recorded in the existing `~/.kosmos/memdir/user/consent/` ledger from Spec 035.

**Acceptance Scenarios**:

1. **Given** a fresh citizen TUI session, **When** the citizen runs `kosmos plugin install seoul-subway`, **Then** the install completes within 30 seconds, the adapter appears in `lookup(search="지하철")`, and a consent receipt is appended to the consent ledger.
2. **Given** an installed plugin, **When** the citizen runs `/consent revoke rcpt-<id>` for a permission previously granted to that plugin, **Then** the next plugin invocation is blocked at the existing Spec 033 Permission Gauntlet without the plugin needing any special integration.
3. **Given** a plugin whose SLSA signature does not verify, **When** install runs, **Then** the install aborts with a Korean error message and no partial state is left in the registry.

---

### Edge Cases

- **Reserved-name override**: Contributor authors a plugin that declares its own `lookup` verb (overriding root-primitive). Manifest validator rejects on parse, before any registry write.
- **Manifest schema-drift**: An older manifest schema version is used. Loader rejects with a clear "schema version X.Y not supported, please regenerate from `kosmos plugin init`" message.
- **Bilingual search_hint missing**: Plugin declares only Korean `search_hint`, no English. Validation fails per memory `feedback_check_references_first` requirement that hints stay bilingual.
- **Live adapter that secretly mocks**: Contributor labels adapter `tier: "live"` but every code path is fixture-replay. CI lint detects no `httpx`/`aiohttp` outbound socket calls in the live tier and rejects the labeling.
- **Mock adapter that secretly calls live**: Inverse of above — contributor labels `tier: "mock"` but actually issues a live HTTP call during tests. CI sandbox blocks all outbound sockets in the mock test runner; any attempt fails the test.
- **Plugin name collision**: Two plugins claim the same `<plugin_id>`. Registry rejects the second registration with a clear collision error and points the contributor at the existing plugin's manifest.
- **Plugin contains binary assets exceeding repo budget**: Per AGENTS.md hard-rule (no >1 MB files without permission), CI rejects and instructs the author to host binaries externally.
- **Trustee acknowledgment text drift**: The canonical PIPA acknowledgment text in `docs/plugins/security-review.md` is updated. All previously merged plugins now have a stale `acknowledgment_sha256`. CI surfaces a separate "stale-acknowledgment-audit" workflow that lists affected plugins so they can re-acknowledge in a follow-up PR — never silently invalidate.
- **Citizen installs plugin offline**: Install command requires network for SLSA verification. Offline path returns a clear "install requires network for signature verification" error rather than silently degrading to unsigned install.

## Requirements *(mandatory)*

### Functional Requirements

#### Tier 1 — Template (시작하기)

- **FR-001**: System MUST provide a public `kosmos-plugin-template` GitHub template repository containing a complete buildable starter (`pyproject.toml`, adapter boilerplate, Pydantic schema stub, pytest fixture, `README.ko.md`) that a developer can use as the basis for a new plugin via the GitHub "Use this template" flow.
- **FR-002**: System MUST provide a `kosmos plugin init <name>` CLI command (in the TUI commands layer) that scaffolds a new plugin in the current working directory with the same structure as the template repo, prompting for: plugin id, plugin tier (`live` / `mock`), default permission Layer (1/2/3), Korean and English search hints, and whether the plugin processes PII.
- **FR-003**: The scaffold MUST emit a working passing test out of the box — running `uv run pytest` against the freshly scaffolded plugin MUST report green without any user code changes.
- **FR-004**: The scaffolded `adapter.py` MUST register the new tool under the `plugin.<plugin_id>.<verb>` namespace, where `<verb>` is one of the active plugin primitive verbs (`lookup` / `submit` / `verify`) that the plugin self-classifies into. Root primitives MUST NOT be overridable.

#### Tier 2 — Guide (`docs/plugins/`)

- **FR-005**: System MUST publish 9 Korean-primary guides under `docs/plugins/`: `README.md` (index, extending the existing index), `quickstart.ko.md` (30-minute path from clone-to-passing-tests), `architecture.md` (Tool.ts + 4-primitive mapping), `pydantic-schema.md` (input/output schema authoring rules per Constitution §III), `search-hint.md` (Ko/En bilingual hint authoring), `permission-tier.md` (Layer 1/2/3 decision tree per Spec 033), `data-go-kr.md` (public-data portal key handling), `live-vs-mock.md` (when to use which tier and the lint/CI consequences), `testing.md` (pytest fixture conventions, `@pytest.mark.live` discipline).
- **FR-006**: Each guide MUST include both a Korean-primary body and a fixed bilingual glossary section so an English-only reader can identify the Korean term and look up the relevant section.
- **FR-007**: Each guide MUST cite at least one canonical reference (Constitution §I — Reference-Driven Development): the relevant Spec number, `docs/vision.md § Reference materials` entry, AGENTS.md section, or `.references/claude-code-sourcemap` path the convention derives from.

#### Tier 3 — Examples

- **FR-008**: System MUST publish 4 reference example plugins as separate repositories (or sub-directories under a single examples repo, decided in `/speckit-plan` Phase 0):
  - `kosmos-plugin-seoul-subway` — Live, Seoul Open Data Plaza subway arrival API.
  - `kosmos-plugin-post-office` — Live, 우정사업본부 parcel tracking.
  - `kosmos-plugin-nts-homtax` — Mock, NTS 홈택스 (project lead lacks API access).
  - `kosmos-plugin-nhis-check` — Mock, 국민건강보험공단 health-checkup.
- **FR-009**: Each example plugin MUST be installable via `kosmos plugin install <name>` and MUST be referenced in `docs/plugins/quickstart.ko.md` as the model the contributor reads while writing their own adapter.
- **FR-010**: Each example plugin MUST include a `README.ko.md` explaining: (1) the public-spec source, (2) the permission Layer rationale, (3) the test fixture provenance, and (4) for Mock examples, the explicit reason live access is unavailable to the project.

#### Tier 4 — Submission

- **FR-011**: System MUST publish `.github/ISSUE_TEMPLATE/plugin-submission.yml` so external contributors can file a structured submission issue (capturing: plugin id, tier, ministry/agency, public-spec URL, contact, PII handling, target permission Layer).
- **FR-012**: System MUST publish a `.github/workflows/plugin-validation.yml` workflow that runs on every PR touching a plugin manifest, performing static + dynamic checks for all 50 review-checklist items.
- **FR-013**: System MUST publish `docs/plugins/review-checklist.md` containing exactly 50 review items, each with: item id, Korean description, English description, the constitution principle or AGENTS.md rule it enforces, and the file/workflow that mechanically enforces it. No item may be marked "manual reviewer judgment only" — every item MUST trace to a runnable check.
- **FR-014**: System MUST publish `docs/plugins/security-review.md` containing the canonical PIPA §26 trustee acknowledgment text + the L3-gated approval procedure. The page MUST display the SHA-256 of the canonical acknowledgment text so contributors can verify their manifest's `acknowledgment_sha256` value.
- **FR-015**: The validation workflow MUST emit a single Korean summary comment on the PR ("N/50 통과 · M/50 실패 — 실패 항목: …") and MUST block merge until N == 50.
- **FR-016**: The validation workflow MUST sandbox plugin tests so no outbound network call escapes during CI (Constitution §IV — never call live `data.go.kr` from CI).

#### Tier 5 — Registry

- **FR-017**: System MUST establish a public GitHub organization `kosmos-plugin-store` that hosts the canonical catalog of accepted plugins (one repo per plugin, plus a top-level `index.json` listing with name, version, tier, permission summary, trustee org, last-published timestamp).
- **FR-018**: System MUST provide a `kosmos plugin install <name>` CLI command (in the TUI commands layer) that resolves `<name>` against the catalog, downloads the latest published bundle, verifies the SLSA provenance signature, performs manifest validation locally (mirroring the CI checks), registers the adapter into the running registry without TUI restart, and writes a consent receipt for the install action to the existing `~/.kosmos/memdir/user/consent/` ledger.
- **FR-019**: System MUST provide a Pydantic v2 manifest schema (`src/kosmos/plugins/manifest_schema.py`) covering all required and optional fields: `plugin_id`, `version`, `tier` (`live`|`mock`), `adapter.tool_id` (must match `plugin.<plugin_id>.<verb>` regex; `<verb>` is one of the active plugin primitives `lookup`/`submit`/`verify`), `permission_layer` (1|2|3), `processes_pii` (bool), `pipa_trustee_acknowledgment` (block; required if `processes_pii`), `search_hint_ko`, `search_hint_en`, `mock_source_spec` (required if `tier == "mock"`), `otel_attributes` (must include `kosmos.plugin.id`), and `slsa_provenance_url`.
- **FR-020**: System MUST provide an auto-discovery loader (`src/kosmos/plugins/registry.py`) that, at backend boot and on every `install`/`uninstall`, scans installed plugins, validates each manifest, registers tools into the in-process registry, and rebuilds the BM25 index (Spec 022) so the LLM's `lookup(mode="search")` immediately surfaces newly installed plugins without any system-prompt edit.
- **FR-021**: All plugin tool invocations MUST emit OTEL spans carrying the `kosmos.plugin.id` attribute (per Spec 021 GenAI semantics extension). The auto-discovery loader MUST refuse to register a plugin whose manifest does not declare this attribute.

#### Cross-cutting (governance)

- **FR-022**: System MUST refuse to register any plugin whose primitive verbs include a root primitive name unprefixed by `plugin.<plugin_id>.` — active plugin primitives `lookup` / `submit` / `verify` are reserved.
- **FR-023**: System MUST default plugin manifests to fail-closed values per Constitution §II: `requires_auth = True`, `is_personal_data = True`, `is_concurrency_safe = False`, `cache_ttl_seconds = 0`. The scaffold CLI MUST NOT emit a starter manifest with relaxed values; relaxation requires explicit edit + CI documentation.
- **FR-024**: System MUST publish a Korean-primary "L2+ plugin sandboxing guidelines" section in `docs/plugins/security-review.md` recommending `sandbox-exec` (macOS) or `firejail` (Linux) for plugins running at Permission Layer 2 or 3, and explaining what the platform DOES enforce vs. what is contributor responsibility.
- **FR-025**: All Korean-primary documentation MUST conform to memory `feedback_output_language` — chat in Korean, but code identifiers and source comments in English. Generated `adapter.py` MUST use English identifiers; only `description_ko` and `search_hint_ko` carry Korean text.

### Key Entities

- **Plugin Manifest**: The Pydantic v2 contract describing one plugin to the registry. Required fields cover identity (`plugin_id`, `version`), classification (`tier`, `adapter.tool_id` namespaced as `plugin.<id>.<verb>`, `permission_layer`), discovery (`search_hint_ko`, `search_hint_en`), security (`processes_pii`, `pipa_trustee_acknowledgment`), evidence (`mock_source_spec` for Mock tier, `slsa_provenance_url`), and observability (`otel_attributes`).
- **PIPA Trustee Acknowledgment Block**: A nested manifest field containing trustee org name, contact, the canonical acknowledgment text's SHA-256, and the contributor's signature line. Validated server-side against the canonical text in `docs/plugins/security-review.md`.
- **Review Checklist Item**: One of 50 items with id, Korean description, English description, constitution-principle or AGENTS.md reference, and a pointer to the file or workflow step that mechanically enforces it.
- **Catalog Entry**: One row in `kosmos-plugin-store/index.json` summarizing a published plugin (name, version, tier, permission summary, trustee org, last-published timestamp, SLSA-provenance URL). Source of truth for `kosmos plugin install` resolution.
- **Consent Receipt for Plugin Install**: An append-only record in `~/.kosmos/memdir/user/consent/` (Spec 035 ledger) noting that the citizen consented to install plugin X at time T; revocation later writes a complementary record.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new contributor with no prior KOSMOS exposure goes from cloning `kosmos-plugin-template` to a passing local `pytest` green in **under 30 minutes** (measured via timed onboarding session with at least 3 different external testers).
- **SC-002**: 100% of the 50 review-checklist items are mechanically enforced by `plugin-validation.yml` (i.e., zero items rely solely on human reviewer judgment, audited by reading the checklist source-of-truth manifest).
- **SC-003**: For every plugin that declares `processes_pii: true`, the validation workflow rejects PRs with a missing or hash-mismatched PIPA trustee acknowledgment block in **100%** of cases (verified with at least 5 negative-test PRs).
- **SC-004**: After `kosmos plugin install <name>` succeeds, the new adapter is discoverable via `lookup(mode="search", query="<korean keyword>")` within **5 seconds** without restarting the TUI.
- **SC-005**: SLSA signature verification rejects every tampered or unsigned bundle in install (verified by at least 3 negative-test bundles); a verified bundle installs without warnings in under **30 seconds** (cold install, fresh session).
- **SC-006**: Every published example plugin (4 plugins) passes its own `plugin-validation.yml` workflow when its repository is run as a PR against itself, demonstrating the workflow is self-consistent.
- **SC-007**: Zero plugin invocations succeed without emitting an OTEL span carrying `kosmos.plugin.id` (audited by injecting a no-op fake-OTLP collector and asserting attribute presence on every invocation).
- **SC-008**: After **3 months** of P5 being live, at least **5 external contributions** (plugins or PRs to plugin docs) land from contributors outside the project lead's direct collaborators — measured via `git log --author` on the plugin-store org.
- **SC-009**: Korean-primary `docs/plugins/` guides are readable by a Korean-only reader without context loss, validated by a native-Korean-speaking reviewer who can complete the quickstart with English source files closed.
- **SC-010**: Plugin auto-discovery boot cost adds **less than 200 ms** to backend start-up time per installed plugin, measured by a microbenchmark gated in CI.

## Assumptions

- **Assumption A1**: The `kosmos-plugin-store` GitHub organization can be created by the project lead under the personal account and transferred to a more permanent home later. (KOSMOS is a student portfolio project per AGENTS.md mission line; org creation does not require institutional approval.)
- **Assumption A2**: SLSA provenance generation for plugin bundles uses the existing GitHub Actions `slsa-github-generator` chain (industry standard, no new infrastructure). The template repo's release workflow is the reference implementation.
- **Assumption A3**: External contributors are expected to be at minimum intermediate Python developers (Pydantic v2, pytest, async/await), not absolute beginners. The 30-minute onboarding target reflects this baseline; an absolute-beginner path is out of scope.
- **Assumption A4**: The active plugin primitives (`lookup` / `submit` / `verify`) and their envelope shape remain stable through P5. `subscribe` is deferred until KOSMOS has a real app/push delivery runtime; any change to the primitive set or envelope is a separate Epic and triggers a coordinated re-version of the manifest schema.
- **Assumption A5**: The Plugin browser surface from P4 (`tui/src/components/plugins/PluginBrowser.tsx`) presents what the registry already knows; P5 does not need to extend that component. The marketplace browser destination of the `a` keystroke (#1820) remains a separate Epic.
- **Assumption A6**: The `data.go.kr` portal API key handling pattern from Spec 022 (KOSMOS_-prefixed env var owned by the citizen, never embedded in the plugin) extends unchanged to plugin contributors. The `docs/plugins/data-go-kr.md` guide simply documents the existing pattern.
- **Assumption A7**: PIPA §26 trustee acknowledgment is a static text plus a SHA-256 hash; legal review of the canonical text happens once during P5 implementation and the text is treated as versioned. Renegotiation of the text per individual plugin is out of scope.
- **Assumption A8**: The 50-item review checklist will be derived in `/speckit-plan` Phase 0 from the union of: AGENTS.md plugin-adapter checklist (`docs/tool-adapters.md`), Constitution principles I–VI, Spec 024 `ToolCallAuditRecord` invariants, Spec 025 V6 auth-level allow-list, Spec 033 permission-decision schema, and the existing review patterns from Specs 022 / 031. Item-count "50" is an aspiration; if Phase 0 materializes 47 or 53, that is acceptable and documented in `plan.md`.
- **Assumption A9**: Auto-discovery rebuild of the BM25 index on every `install`/`uninstall` is fast enough at expected catalog scale (hundreds of plugins, not millions). If scale changes, an incremental indexing path becomes a follow-up Epic.

## Scope Boundaries & Deferred Items *(mandatory)*

### Out of Scope (Permanent)

- **Hot-reload dynamic loading of plugin code without TUI restart**: Auto-discovery scans at backend boot and on `install`/`uninstall` events, but live editing of an installed plugin's source code while the TUI is running is permanently out of scope — restart is the contract. (Architectural simplicity; aligns with Python module-loading semantics.)
- **Mobile-native plugin browser app**: KOSMOS is a terminal-based platform per AGENTS.md; there is no mobile path.
- **Plugins authored in non-Python languages**: The 4-primitive envelope and Pydantic v2 manifest are Python-canonical. Cross-language plugin authoring would require an entirely separate IPC contract beyond the scope of any reasonable Epic.
- **Reserved-root-primitive override mechanism**: Even with a justification flag, active plugin primitives (`lookup` / `submit` / `verify`) cannot be overridden by plugins. This is constitutional (migration tree § L1-C C1) and not subject to per-spec carve-out.

### Deferred to Future Work

| Item | Reason for Deferral | Target Epic/Phase | Tracking Issue |
|------|---------------------|-------------------|----------------|
| Citizen-facing plugin marketplace browser UI (the `a`-keybinding destination from P4 PluginBrowser) | P5 builds the registry and install CLI; the in-TUI browser surface for the catalog is a distinct UX problem worth its own Epic | Post-P5 marketplace Epic | #1820 |
| `docs/api` / `docs/plugins` integrated documentation site (e.g., Astro Starlight, MkDocs) | Documentation site rebuild belongs to the docs phase; P5 ships Markdown source-of-truth that the future site will consume unchanged | Phase P6 — Docs + Smoke (#1637) | #1812 |
| Paid plugin model (revenue share, pricing, payment integration) | KOSMOS is a student portfolio project; commercial monetization is not a near-term concern | Post-portfolio commercialization Epic | #1923 |
| Plugin-to-plugin dependency graph (one plugin requires another to be installed first) | At expected catalog scale, dependencies are rare enough that documenting them in `README.ko.md` is sufficient; formal graph resolution is over-engineering until proven needed | Post-P5 if real-world need materializes | #1924 |
| Hot-reload dynamic loading of an installed plugin's edited source without TUI restart | Adds significant complexity to auto-discovery loader; restart is acceptable for the citizen contract; explicitly deferred as worth its own Epic if developer tooling demand materializes | Post-P5 if developer tooling demand materializes | #1925 |
| Acceptance-text drift audit workflow that re-checks all installed plugins' `acknowledgment_sha256` against the latest canonical text | The trustee acknowledgment text is expected to be stable; building the drift-audit workflow before any drift event has happened is premature | Post-P5 first acknowledgment-text update | #1926 |
