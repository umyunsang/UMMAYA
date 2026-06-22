# UMMAYA Documentation Full Audit — 2026-06-17

> Phase 1 deliverable for the "full-sweep documentation refresh + capstone
> presentation" initiative. Inventories every prose doc, records drift against
> codebase reality, and produces the Phase 2 update worklist + Phase 3
> presentation plan. Inputs are read-only; this file is the plan-of-record.

## 0. Scope reframing

- `find docs -name "*.md"` returns **231** files.
- **101** of those live under `docs/api/data-go-kr-candidate-docs/**` — raw
  downloaded data.go.kr dataset pages (numbered by dataset id). These are
  **reference source material, not prose to rewrite**. They are kept verbatim
  and indexed, never edited.
- **130 prose docs** are the actual audit surface. Of those, ~20 are the
  *foundation set* that defines project direction and feeds the presentation.

## 1. Codebase reality baseline (the source of truth for updates)

| Fact | Value (verified 2026-06-17) | Where |
|---|---|---|
| Version (source of truth) | **0.2.5** (unreleased; latest tag `v0.2.4`) | `package.json`, `pyproject.toml`, `tui/package.json` |
| LLM | `LGAI-EXAONE/K-EXAONE-236B-A23B` on FriendliAI Serverless | `src/ummaya/llm/` |
| Primitive families (internal) | `find`, `locate`, `send`, `check`, **`document`** (+ `delegation`) | `src/ummaya/primitives/__init__.py` |
| Primitive aliases (public) | `lookup=find`, `resolve_location=locate`, `submit=send`, `verify=check` | same |
| `subscribe` | **deprecated / inactive** (not in `PRIMITIVE_REGISTRY`) | same |
| Gated primitives | `{check, send, document}` (heavy: `send, document`; light: `check`) | same |
| Tool-system upgrade A | **Public document harness** — `document_inspect/extract/form_schema/copy_for_edit/apply_fill/apply_style/render/validate_public_form/save`; HWP·HWPX·PDF·OOXML·ODF; evidence+approval gated | `src/ummaya/tools/documents/`, `src/ummaya/evidence/document_*` |
| Tool-system upgrade B | **Modernized adapter route selection** — intent extractor → decision service → feasibility → retrieval policy → cards/projection | `src/ummaya/tools/routing/` |
| Live adapter families | KOROAD, KMA (×6 incl. APIHub structured), HIRA, NMC, NFA119, MOHW, KFTC OpenGiro/MyData, verified data.go.kr wave | `src/ummaya/tools/{koroad,kma,hira,nmc,nfa119,mohw,...}` |

## 2. Drift findings (concrete, actionable)

**D1 — Primitive set is stale in BOTH foundation docs.**
- `AGENTS.md` L1-C: "Five reserved primitive families (`lookup · resolve_location · submit · verify · subscribe`)" — lists deprecated `subscribe`, omits new `document`.
- `docs/requirements/ummaya-migration-tree.md` §C1: "`find · locate · send · check` (4개 active) · `subscribe` 제거/보류" — omits new `document`.
- Reality: `find/lookup · locate/resolve_location · send/submit · check/verify · document`. The dual internal/public naming is also undocumented.

**D2 — Version drift.** 20 prose files still reference `0.1-alpha`; current is `0.2.5`. README badges/text predate 0.2.x.

**D3 — CHANGELOG stale.** Latest entry is `v0.2.3` (2026-05-26). Missing `v0.2.4` (tagged/released) and `v0.2.5` (in-progress).

**D4 — README tool story incomplete.** README §"Main Tools" describes "four main tools: `find`, `locate`, `check`, `send`". Missing the `document` family and the modernized routing layer — exactly the "도구 시스템 고도화/개편" the user flagged.

**D5 — Tool-system docs predate the upgrade.** `docs/tool-adapters.md`, `docs/adapter-authoring.md` (both 05-08), `docs/api/README.md` (05-25) describe the pre-document-harness, pre-routing-modernization surface.

**D6 — No document-harness documentation.** The largest recent subsystem (`tools/documents/`, evidence document harness) has no prose doc in `docs/` beyond ADR-011/012 (HWP/LibreOffice bridges). Needs a first-class design/usage doc.

## 3. Per-doc classification (130 prose docs)

Legend: **UPDATE** (drift, edit), **KEEP** (current, spot-verify only),
**ARCHIVE** (historical record — preserve, do not rewrite), **CREATE** (new doc needed).

### Foundation set — UPDATE (highest priority; feeds presentation)
| Doc | Action | Reason |
|---|---|---|
| `README.md` | UPDATE | D2, D4 — add `document`, routing, version, capstone-grade narrative |
| `docs/vision.md` | UPDATE | D1, D6 — primitive set + document harness + routing in six-layer design |
| `AGENTS.md` | UPDATE | D1 — primitive family list |
| `CLAUDE.md` | UPDATE | D1 — primitive family list (mirror AGENTS) |
| `docs/requirements/ummaya-migration-tree.md` | UPDATE | D1 — §C1 primitive set |
| `CHANGELOG.md` | UPDATE | D3 — add 0.2.4, 0.2.5 |
| `docs/configuration.md` | KEEP | 06-15 fresh; verify document/routing env vars present |
| `docs/conventions.md` | KEEP | 05-31; verify branch/PR rules still accurate |

### Tool system — UPDATE / CREATE (reflect the upgrade)
| Doc | Action | Reason |
|---|---|---|
| `docs/tool-adapters.md` | UPDATE | D5 — add document family + routing decision layer |
| `docs/adapter-authoring.md` | UPDATE | D5 — current adapter contract |
| `docs/api/README.md` | UPDATE | D5 — catalog the document tools |
| `docs/design/mvp-tools.md` | UPDATE | verify against 5-family reality |
| `docs/tool-systems-overview.md` (or `docs/design/document-harness.md`) | CREATE | D6 — document harness + routing modernization design/usage |
| `docs/onboarding/five-primitive-harness.md` | UPDATE | rename/refresh to current family set |

### API adapter catalog — KEEP (spot-verify)
`docs/api/{koroad,kma,hira,nmc,nfa119,mohw,locate,submit,verify}/**`,
`docs/api/verified-data-go-kr/README.md`, `docs/api/kma/apihub-*` — current
(05-14…05-31). KEEP; verify tool_ids match registry. Consider CREATE
`docs/api/documents/` once the harness doc lands.

### Plugins — KEEP (spot-verify)
`docs/plugins/**` (11 docs, 05-14…05-31) — current 5-tier DX. KEEP.

### Scenarios — KEEP (intentional OPAQUE narratives)
`docs/scenarios/**` (9 docs) — by-design handoff narratives; not drift.

### Mock READMEs — KEEP
`docs/mock/**` (6 docs) — barocert, cbs, data_go_kr, mydata, npki_crypto, omnione.

### ADRs — KEEP (append-only decision record)
`docs/adr/**` (11 ADRs). Historical by nature. ADR-009 has a known duplicate
number (`ADR-009-mcpb-compat-lazy-shim` vs `ADR-009-secureStorage-drop`) — note
only, do not renumber (citations exist).

### Security / DPA — KEEP
`docs/security/**` (4 docs) — threat model, safety rails, tool-template spec,
DPA template. Spot-verify primitive references.

### Archive — preserve + index (do NOT rewrite)
- `docs/spec-1978/**`, `docs/spec-1979/**`, `docs/spec-kexaone-tool-wiring/**`
- `docs/deferred/032-ipc-stdio-hardening.md`
- `docs/visual-fidelity/1635-scoring.md`
- `docs/release-notes/epic-467.md`
- `docs/research/ummaya-docs-*-2026-05-15.md` (docs-architecture research, already executed)
- `docs/api/kftc-openapi-*-debug-report.md`, `*-endpoint-inventory.md`, `*-portfolio.md`

### Research / reference — KEEP
`docs/research/**` (remaining) — infrastructure surveys, policy mapping,
tool-schema deep references, corpus notes. Reference material; KEEP.

### Release / packaging — KEEP (verify version refs)
`docs/release-checklist.md`, `docs/release-packaging-plan.md`, `docs/packaging.md`,
`docs/release/homebrew-official-readiness.md` — verify against 0.2.5.

## 4. Phase 2 worklist (ordered)

1. **Foundation primitive-set fix** (D1): AGENTS.md, CLAUDE.md, migration-tree §C1, vision.md — single consistent statement of `find/lookup · locate/resolve_location · send/submit · check/verify · document` with `subscribe` marked deprecated.
2. **CHANGELOG** (D3): add `v0.2.4` and `v0.2.5` entries from git history.
3. **README** (D2, D4): version refresh + add `document` tool section + routing note + capstone-grade "Why/What/How" framing.
4. **Tool-system docs** (D5, D6): update `tool-adapters.md`, `adapter-authoring.md`, `api/README.md`; CREATE the document-harness + routing design doc.
5. **Version sweep** (D2): the remaining `0.1-alpha` references — update where they are current-state claims; leave where they are historical (release-notes, changelog history).
6. **Spot-verify** KEEP docs touched by the primitive rename (security, onboarding, plugins) for stray `subscribe`/4-tool claims.

## 5. Phase 3 plan (presentation + demo)

- **Audience/tone**: academic capstone — story arc: 문제정의 → 기존 한계 → UMMAYA 테제(CC 하네스 byte-identical + 2 swap) → 6-layer 아키텍처 → 도구 시스템(5 family + document harness + 라우팅) → 구현 현황 → 데모 → 검증(Evidence Fabric v2) → 향후(OmniOne/OpenDID live 승격).
- **Previous presentation materials discarded (2026-06-17, user directive)**: `docs/presentation.md` (KSC 2026 deck notes), `docs/presentation/v0.1-alpha/` (old scenario evidence), and `docs/UMMAYA.pdf` (stale **KOSMOS**-branded 8-page deck from before the UMMAYA rename) were `git rm`-ed. The old `docs/demo/` README recording scripts were later removed during the 2026-06-22 latest-deck/latest-video refresh.
- **Slides (tooling decided 2026-06-17)**: build a content brief first (text outline per slide); user approves; then generate the real `.pptx` with the official **`document-skills:pptx`** skill (local generation, no external egress — replaces the earlier Gamma MCP plan). Apply UMMAYA brand (warm amber `#f59e0b`/`#7c2d12`, Umma mascot) via the `theme-factory` / `brand-guidelines` companion skills. **Style (user directive)**: maximize visual materials / diagrams / charts per slide; body text is **개조식 (key-point bullets), not narrative prose**; logically structured. No deck generation before brief approval.
- **Demo video (tooling decided 2026-06-17)**: real-usage desktop capture of `bun run tui` with ordinary Korean prompts (README emergency-room / weather+road-risk flows, plus a document-authoring flow showcasing the new harness), captured + branded/subtitled with the **`ecc:videodb`** plugin (desktop recording → transcode → overlay/branding). Constraint: a live session needs a FriendliAI key (`/login`) which the user will provide to the session; VideoDB is a cloud service, so demo footage leaves the machine for editing. Prepare the capture script + scenario before the user provides the key.

## 6. Invariants honored

- Raw `data-go-kr-candidate-docs/**` untouched.
- ADRs, spec-archives, release-notes preserved as historical record.
- No adapter behavior change; docs follow code, not the reverse.
- Source text English; Korean only for domain data + Korean-primary user/plugin guides + presentation.
