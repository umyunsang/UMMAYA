# audit-prod § Audit 6 — Plugin DX (Tier 1-5) + /plugin slash commands

> Lead Opus, 2026-05-04 (autonomous, 25 min budget). Scope: Spec 1636 + Spec 1979.
> Captures: `specs/audit-prod/snap-6-plugin/` (full /plugin + /plugins),
> `specs/audit-prod/snap-6-plugin-install/` (install/uninstall paths),
> `specs/audit-prod/snap-6-plugin-real/` (live catalog dry-run).

## TL;DR — Production Y/N

**N**. Backend pipeline is solid (125/125 pytest pass, 8-phase installer with
fail-closed SHA + manifest + PIPA hash + L3-no-skip gates), but **two P0
blockers** stop a citizen from completing the install/list flow today.

| Tier × Axis | Status | Blocker |
|-------------|--------|---------|
| Tier 1 template + `kosmos plugin init` TUI + `uvx` fallback | 🟢 OK | — |
| Tier 2 9 Korean docs (actually 11 .md, exceeds spec) | 🟢 OK | — |
| Tier 3 4 example repos (live catalog has 4 entries verified) | 🟡 partial | provenance URLs 404 (P0) |
| Tier 4 50-item validation matrix + reusable workflow + issue template | 🟢 OK | — |
| Tier 5 store/index catalog + 8-phase installer + SLSA verifier | 🔴 broken | provenance 404 + SLSA binary not vendored (P0) |
| /plugin install/uninstall/list/pipa-text slash command | 🟡 partial | summary lands in notification strip, not chat log (P1) |
| /plugins browser surface | 🔴 broken | Esc dismiss does not fire — overlay swallows all subsequent input (P0) |
| PIPA §26 trustee SHA-256 hash gate | 🟢 OK | — |
| `plugin.<id>.<verb>` namespace (ADR-007) | 🟢 OK | — |
| BM25 search_hint integration | 🟢 OK | — |
| plugin_op IPC arm wiring | 🟢 OK | — |
| 30-min quickstart UX (SC-001) | 🟢 OK (per spec evidence) | — |

## P0 issues (production blocker)

### P0-1 · `/plugins` browser does NOT dismiss on Esc; overlay swallows all subsequent input
- **Symptom**: After `/plugins` opens, every keystroke (slash command, text, Esc) is consumed by the dead overlay; the citizen is stuck until SIGINT.
- **Evidence**: `snap-6-plugin/snap-005-4-plugins-browser.txt` (browser open) → `snap-006-4b-plugins-after-esc.txt` (identical, Esc ignored) → `snap-007/008/009/010/011` all identical (subsequent /plugin install/uninstall/install seoul_subway --dry-run typed but never reaches PromptInput).
- **Root cause**: `tui/src/screens/REPL.tsx:3559` mounts `PluginBrowser` with `setToolJSX({ ..., isLocalJSXCommand: true })`. Per AGENTS.md Infrastructure Insight #3, this sets `isModalOverlayActive = true` in `PromptInput.tsx:244` and **deactivates EVERY useInput hook in the parent prompt subtree** — including PluginBrowser's own `useInput((_,key) => key.escape && onDismiss())` at `tui/src/components/plugins/PluginBrowser.tsx:141`.
- **Fix**: change `isLocalJSXCommand: true` → `false` on line 3559 (and lines 3568 / 3576). One-line per call-site. Same fix that unblocked `/help` overlay during integration-verification (cited in AGENTS.md insight 3).
- **Severity**: P0 — citizen cannot escape the overlay; effectively a session-lock UX bug.

### P0-2 · Tier 5 provenance attestations 404 → SLSA gate forces `KOSMOS_PLUGIN_SLSA_SKIP=true` in production
- **Symptom**: `https://github.com/kosmos-plugin-store/kosmos-plugin-seoul-subway/releases/download/v0.1.0/seoul_subway.intoto.jsonl` returns 404 (verified 2026-05-04 11:28 KST). All four catalog entries (seoul-subway / post-office / nts-homtax / nhis-check) point at provenance URLs that do not exist.
- **Effect**: Without `KOSMOS_PLUGIN_SLSA_SKIP=true`, Phase 3 fails at `provenance_fetch_failed` (exit_code=6, IO error) — citizen cannot install any plugin.
- **With `KOSMOS_PLUGIN_SLSA_SKIP=true`**, Phase 3 emits the warning "bypassing SLSA verification" and the install proceeds — but `installer.py:537` REFUSES to skip in `KOSMOS_ENV in {production, prod, release}`. So production deploys must publish real provenance attestations or remove the entries from the catalog.
- **Compounding bug**: `~/.kosmos/vendor/slsa-verifier/` does not exist on this machine. First-time install would auto-bootstrap via `scripts/bootstrap_slsa_verifier.sh`, but the CI gate requires the binary pre-vendored (or the bootstrap step in install docs).
- **Fix**: (a) generate + publish real `.intoto.jsonl` attestations for all 4 example repos using `slsa-framework/slsa-github-generator@v2.x`, or (b) revert the 4 example entries to "draft" / remove them from `kosmos-plugin-store/index/main` until provenance is published; (c) document the `bootstrap_slsa_verifier.sh` step in `docs/plugins/installation.md`.
- **Severity**: P0 — production install is blocked.

## P1 issues (UX-blocking)

### P1-3 · `/plugin list` payload (entries[]) never rendered to citizen
- **Symptom**: `/plugin list` round-trips successfully (📋 플러그인 목록 조회 완료 message lands), but the actual `entries` payload from `payload_start/payload_delta/payload_end` is silently discarded by `PluginInstallFlow.tsx:209` (the "list" branch shows a generic 완료 message and does NOT consume the `payload_*` frames).
- **Evidence**: `snap-6-plugin/snap-003-3-list.txt` (sent state) → `snap-004-3b-list-after.txt` (only "📋 플러그인 목록 조회 완료" displayed; no plugin enumeration).
- **Fix**: extend `PluginInstallFlow.tsx` to consume the `payload_start/payload_delta/payload_end` triplet for `sub === 'list'`, parse the `{entries: PluginListEntry[]}` JSON, and render an in-flow table (or hand off to `PluginBrowser` directly).
- **Severity**: P1 — `/plugin list` is functionally a no-op for the citizen; only `/plugins` browser surface shows the list (and that one is broken by P0-1).

### P1-4 · Slash command summaries land in ephemeral notification strip, not chat log
- **Symptom**: `/plugin pipa-text`, `/plugin` (usage), `/plugin install` outcomes all surface via `addNotification(...priority: 'immediate')` at `REPL.tsx:3384`. They render in the right-aligned hint zone (single-line, ephemeral) and disappear at next keystroke. Citizens lose the PIPA SHA-256 hash, install receipt, and exit-code reason within ~2s.
- **Evidence**: every `snap-001-1-pipa-text.txt` shows the hash anchored to the right margin in the notification zone; the message stream stays empty.
- **Fix**: route command outcomes via `addMessage({role: 'system', content: result})` instead of `addNotification(...)`, OR add a dedicated `system-block` cell renderer to PluginInstallFlow's terminal state (already supported by CC's `display: 'system'` contract — REPL just doesn't consume it).
- **Severity**: P1 — citizen can't audit install outcomes.

### P1-5 · `/plugin uninstall <not-installed>` reports "🗑️ 제거 완료" instead of "미설치"
- **Symptom**: `uninstall_plugin` is documented as idempotent (returns exit_code=0 on no-op), but the TUI surfaces success ("🗑️ ... 플러그인 제거 완료") for a plugin that was never installed — misleading to citizens.
- **Evidence**: `snap-6-plugin-install/snap-003-3-uninstall-miss.txt`.
- **Root cause**: `kosmos/plugins/uninstall.py:114` returns `_EXIT_OK` with no signal that the no-op path was taken. The dispatcher then emits `result="success"`. PluginInstallFlow can't distinguish "really uninstalled" from "was never installed".
- **Fix**: extend `UninstallResult` with `was_idempotent_noop: bool`, pipe it through `plugin_op_complete.idempotent_noop` field, render distinct citizen text ("이미 설치되어 있지 않습니다" / "Plugin was not installed").
- **Severity**: P1 — wrong feedback enables accidental confusion ("did I really uninstall the right plugin?").

### P1-6 · Bare exit codes leaked to citizen instead of human-readable error reason
- **Symptom**: `/plugin install seoul-subway --dry-run` ends with "✗ seoul-subway 플러그인 설치 실패 (exit_code=2)". Citizen has no way to know `exit_code=2` = "bundle SHA-256 mismatch".
- **Evidence**: `snap-6-plugin-real/snap-002-2-install-dryrun-after.txt`.
- **Fix**: PluginInstallFlow.tsx should map the 8 documented exit codes (installer.py:76-83) to canonical Korean messages — backend already returns `error_kind` + `error_message` via `InstallResult`, but `plugin_op_complete` frame schema does not propagate them. Either (a) widen `PluginOpFrame` with `error_kind` / `error_message_ko` / `error_message_en` (recommended), or (b) hard-code the 8-row map in PluginInstallFlow.tsx.
- **Severity**: P1 — opaque failure reason blocks citizen self-recovery.

## P2 issues (polish)

### P2-7 · Catalog `name` (hyphen) vs `plugin_id` (underscore) mismatch is undocumented for citizens
- The catalog uses `name: "seoul-subway"` but `plugin_id: "seoul_subway"`. Citizens who type `/plugin install seoul_subway` (the more natural form, matching the directory layout) get exit_code=1 catalog miss. Either reject install on `name=seoul_subway` with a hint ("did you mean: seoul-subway?") or alias both forms in the catalog resolver.

### P2-8 · `~/.kosmos/vendor/slsa-verifier/` not pre-vendored on dev machines
- First-time install auto-runs `scripts/bootstrap_slsa_verifier.sh`, but the bootstrap step is silent and undocumented in `docs/plugins/quickstart.ko.md`. A failed bootstrap surfaces as `binary_not_found` (exit_code=7), not a clear "first-run setup required" message.

### P2-9 · `tui/src/commands/plugin/` CC marketplace residue remains in repo
- `tui/src/commands/plugin/index.tsx` (description: "Manage Claude Code plugins") + sibling `.tsx` files (`AddMarketplace.tsx`, `BrowseMarketplace.tsx`, `DiscoverPlugins.tsx`, `ManageMarketplaces.tsx`, `ManagePlugins.tsx`, etc — 18 files total) are CC marketplace surface dead code. KOSMOS routes `/plugin` via the singular `plugin.tsx` (verified at `commands.ts:146`). Confirmed dead in commit message of Spec 1979 T021 ("CC marketplace residue ... is now unreachable from citizen surface; cleanup tracked"). Recommend explicit cleanup (rm -r `tui/src/commands/plugin/`) before v0.1 production.

## Pass/fail axis matrix (P0/P1 surfaced above)

| Surface | Boot | Wire | Fail-closed | UX | Verdict |
|---------|------|------|-------------|----|---------|
| `/plugin pipa-text` | ✓ | ✓ | ✓ | 🔴 P1-4 | 🟡 |
| `/plugin` (usage) | ✓ | ✓ | ✓ | 🔴 P1-4 | 🟡 |
| `/plugin list` | ✓ | ✓ (IPC ok) | ✓ | 🔴 P1-3 + P1-4 | 🔴 |
| `/plugin install <bad>` | ✓ | ✓ | ✓ | 🔴 P1-4 + P1-6 | 🟡 |
| `/plugin install <real>` | ✓ | ✓ to Phase 2 | 🔴 P0-2 SLSA | 🔴 P1-6 | 🔴 |
| `/plugin uninstall <miss>` | ✓ | ✓ | 🔴 P1-5 | 🔴 P1-4 | 🔴 |
| `/plugins` browser | ✓ | ✓ (IPC list ok) | ✓ | 🔴 P0-1 stuck-overlay | 🔴 |
| Tier 1 init | ✓ | n/a | ✓ | n/a | 🟢 |
| Tier 2 docs | ✓ | n/a | n/a | n/a | 🟢 |
| Tier 3 example repos | 🟡 (4 catalog entries exist) | n/a | n/a | n/a | 🟡 (P0-2) |
| Tier 4 validation workflow | ✓ | ✓ | ✓ | n/a | 🟢 |
| Tier 5 catalog + installer + SLSA | ✓ catalog | ✓ installer | 🔴 P0-2 | n/a | 🔴 |

## Production verdict: **N**

Backend (Python plugin module + IPC dispatcher + 8-phase installer + 6 cross-field validators + L3-no-skip gate + PIPA hash + safe_extract path-traversal defense) is **production-grade**. 125/125 pytest pass.

TUI surface ships **two P0 blockers**:
1. `/plugins` browser swallows input forever (one-line `isLocalJSXCommand: false` fix).
2. Tier 5 catalog publishes provenance URLs that 404 (publish real `.intoto.jsonl` attestations).

Plus **four P1 UX bugs** (list payload not rendered, summaries lost in notification strip, idempotent uninstall ambiguous, bare exit codes leaked).

Estimated work to v0.1 production: 1 day (P0-1 fix + P1 fixes) + 0.5 day (P0-2 publish provenance) = **1.5 day Lead+Sonnet pair**.
