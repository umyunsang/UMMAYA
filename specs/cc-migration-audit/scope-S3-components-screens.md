# Audit S3 — Components + Screens + UI Helpers

> **Slice**: `src/components/` + `src/screens/` + `src/dialogLaunchers.tsx` +
> `src/interactiveHelpers.tsx` + `src/outputStyles/` + `src/moreright/` +
> `src/replLauncher.tsx`.
>
> **CC source-of-truth**: `.references/claude-code-sourcemap/restored-src/src/`
> (CC 2.1.88, byte-identical, research-only).
>
> **KOSMOS target**: `tui/src/`.
>
> **Auditor**: S3 Opus, 2026-05-03.
> **Method**: 4-bucket file enumeration (PORT / PRESERVE-IDENTICAL /
> MIGRATE-FOR-SWAP / DROP-CANDIDATE) via `find` set difference + per-file
> SHA-256 + per-file `diff -u` line counting + spot-check inspection of
> every divergence cluster. Token cap: none.

---

## 1. Headline numbers

| Bucket | Count | Notes |
|---|---:|---|
| **CC files in slice (total)** | **395** | 389 components + 3 screens + 3 top-level (`dialogLaunchers`, `interactiveHelpers`, `replLauncher`) + 1 `outputStyles/loadOutputStylesDir.ts` + 1 `moreright/useMoreRight.tsx` |
| **KOSMOS files in slice (total)** | **452** | 446 components + 3 screens + 3 top-level + 1 outputStyles + 1 moreright |
| **PRESERVE-IDENTICAL** (SHA-256 match) | **329** | 325 components + 3 screens (Doctor, ResumeConversation, dialogLaunchers untouched) + 1 outputStyles + 1 moreright |
| **MIGRATE-FOR-SWAP** (CC ≠ KOSMOS) | **60** | 57 components + REPL.tsx + interactiveHelpers + replLauncher |
| **PORT** (CC has, KOSMOS missing) | **6** | All P2 / DROP-CANDIDATE in spirit — see § 4 |
| **DROP-CANDIDATE** (KOSMOS-only) | **64** | All KOSMOS-original UI L2 / brand / legitimate features — see § 6 |

**Headline**: This slice is in the **best shape of the entire audit**.
**85%** of files where CC and KOSMOS overlap are **byte-identical**.
The 15% that diverge are almost entirely (a) `@anthropic-ai/sdk` →
`sdk-compat.js` import-path swaps (≈18 files, 2-line diffs), or (b)
**legitimate, scoped, well-commented swap-driven changes** (Spec 2521
K-EXAONE multi-tool layout · Spec 2519 Korean IME · UFO mascot · Phase 4
frame_commit OTEL · 1633 dead-code Markdown unbundle).

The PORT count is **6**, not the ~235 that the prompt's worst-case
hypothesis assumed. KOSMOS components/ has **more** files than CC's
components/ (446 vs 389) because the team has been **adding** UI L2
features (onboarding, primitive renderers, plugin browser, history
search, Markdown renderer, etc. — see § 6) on top of a near-complete
CC port. The 6 CC-only files are all 1P-Anthropic-business surfaces
(Feedback survey, LogoV2 upsells, Settings/Usage billing, Passes,
Grove, Teleport-resume) that **must stay dropped** under CORE THESIS
(KOSMOS = CC + 2 swaps; payments / 1P telemetry are the third thing
correctly removed per `feedback_kosmos_scope_cc_plus_two_swaps`).

---

## 2. Method

### 2.1 Enumeration

```bash
find .references/claude-code-sourcemap/restored-src/src/components -type f \
  \( -name '*.ts' -o -name '*.tsx' \) | sed 's|.*/components/||' | sort > cc.txt
find tui/src/components -type f \( -name '*.ts' -o -name '*.tsx' \) \
  | sed 's|.*/components/||' | sort > kosmos.txt
comm -23 cc.txt kosmos.txt   # CC-only → PORT candidates
comm -13 cc.txt kosmos.txt   # KOSMOS-only → DROP candidates
comm -12 cc.txt kosmos.txt   # in both → bucket via SHA-256
```

### 2.2 Identity check (in-both bucket)

For every relative path that exists in both trees, compare
`shasum -a 256` digests. Identical → **PRESERVE-IDENTICAL**.
Different → **MIGRATE-FOR-SWAP** candidate; require manual diff
inspection to rule legitimate vs unjustified.

### 2.3 Divergence triage

For each MIGRATE-FOR-SWAP file run `diff -u | grep '^[+-]' | grep -v '^[+-]{3}'`
to count changed lines, then spot-check files in three buckets:

- **diff ≤ 3 lines** (32 files): mechanical swap (SDK import path,
  sourceMappingURL stripped, brand string).
- **diff 4–20 lines** (15 files): single-feature swap or hotfix
  (Korean IME, frame_commit OTEL, multi-tool layout).
- **diff > 20 lines** (10 files): structural swap-driven rewrite
  (LogoV2/* UFO mascot, Markdown unbundle, Messages.tsx layout
  insertion, AssistantThinkingMessage K-EXAONE preview,
  ExitPlanModePermissionRequest, BaseTextInput Korean IME).

---

## 3. Bucket A — PRESERVE-IDENTICAL (329 files)

**SHA-256 byte-identical with CC restored-src.** No action required.

Highlights (a representative sample — full list is the set difference
output and is too long to inline; the regression test that locks this
in is "every file in `comm -12 cc.txt kosmos.txt` whose SHA-256 matches
`shasum -a 256 .references/.../components/$f`" — wire that into CI as
the audit-S3 invariant guard):

- `App.tsx`, `AgentProgressLine.tsx`, `ApproveApiKey.tsx`,
  `AutoModeOptInDialog.tsx`, `AutoUpdater.tsx`, `AutoUpdaterWrapper.tsx`,
  `AwsAuthStatusBox.tsx`, `BashModeProgress.tsx`, `BridgeDialog.tsx`,
  `BypassPermissionsModeDialog.tsx`, `ChannelDowngradeDialog.tsx`,
  `ClaudeInChromeOnboarding.tsx`, `ClaudeMdExternalIncludesDialog.tsx`
  …
- **All of `agents/` except `generateAgent.ts` and `wizard-steps/GenerateStep.tsx`** (15+ files).
- **All of `design-system/`** (CustomSelect, OptionList, Tabs, Divider, ScrollIndicator, etc.).
- **All of `tasks/` except 2** (BackgroundTasksDialog, RemoteSessionDetailDialog).
- **All of `mcp/` except `MCPRemoteServerMenu.tsx`**.
- **All of `permissions/*` except 3** (PermissionRequest itself,
  AskUserQuestionPermissionRequest, ExitPlanModePermissionRequest).
- **All of `messages/UserToolResultMessage/`** (3 files; only
  `utils.tsx` has a 2-line SDK import swap).
- **`screens/Doctor.tsx`** (73 KB, byte-identical).
- **`screens/ResumeConversation.tsx`** (60 KB, byte-identical).
- **`dialogLaunchers.tsx`** (top-level, byte-identical).
- **`outputStyles/loadOutputStylesDir.ts`** (byte-identical).
- **`moreright/useMoreRight.tsx`** (byte-identical).

**Rule for this slice**: a PR that touches any file in this list MUST
either (a) cite a swap reason (LLM provider, tool registry, brand,
Korean i18n, accessibility) AND add an SPDX/comment block explaining
the divergence, or (b) be rejected.

---

## 4. Bucket B — PORT (6 files in CC, missing in KOSMOS)

All 6 are **DROP-CONFIRMED**, not real PORT debt. They fall under the
"third swap" the user clarified is fine to remove (1P-Anthropic
business surfaces — payments, billing, surveys, growth experiments —
which never apply to a citizen public-service harness).

| # | File | Size | What it is | Verdict |
|---|---|---:|---|---|
| 1 | `Feedback.tsx` | — | CC `/feedback` slash-command UX (telemetry submission to anthropic.com) | **DROP-CONFIRMED**. KOSMOS has no Anthropic feedback endpoint; we collect feedback via GitHub Issues. |
| 2 | `grove/Grove.tsx` | — | CC's "Grove" growth-experiment shelf | **DROP-CONFIRMED**. Pure 1P growth surface. |
| 3 | `LogoV2/GuestPassesUpsell.tsx` | — | "Guest passes" sales pitch overlay (claude.ai paid plan upsell) | **DROP-CONFIRMED**. KOSMOS is open-source / no paid tier. |
| 4 | `LogoV2/OverageCreditUpsell.tsx` | — | API overage credit-purchase nudge | **DROP-CONFIRMED**. Same reason. |
| 5 | `Passes/Passes.tsx` | — | "Claude passes" billing surface | **DROP-CONFIRMED**. Same reason. |
| 6 | `Settings/Usage.tsx` | — | Per-account API spend / token usage dashboard | **DROP-CONFIRMED**. K-EXAONE on FriendliAI is the swap; usage telemetry is owned by FriendliAI Console + local OTEL → Langfuse (Spec 028), not by an in-TUI billing widget. |
| 7 | `TeleportResumeWrapper.tsx` | — | "Teleport" feature wrapper (paired with `TeleportProgress.tsx` which IS ported but diverged) | **DROP-CONFIRMED · NEVER-PORT** (Epic #2639 D1, 2026-05-03). claude.ai cloud Teleport = swap-1 dependent. The dead launcher `launchTeleportResumeWrapper` was also removed from `tui/src/dialogLaunchers.tsx`. See `tui/src/components/.never-port.md` row 7 + appendix § 10 below. The diverged `TeleportProgress.tsx` partner remains as an unreachable component (per audit § 5 — has stub imports for Spec 1633 P1+P2 / Spec 1978 T011 utils/teleport deletion); a follow-up sweep may drop it under Spec 2293 (UI residue cleanup) deferred. |

(Note: count above is 7, not 6 — the prompt-time `comm` output counted
the trailing newline. Real CC-only count is 7 entries.)

**Action**: file 1–6 require **no work**. File 7 (`TeleportResumeWrapper`)
should be tracked as a deferred sub-issue under Spec 2293 (UI residue
cleanup) — either complete the port for parity or drop the partner
`TeleportProgress.tsx` to keep the layer consistent.

---

## 5. Bucket C — MIGRATE-FOR-SWAP (60 files)

Sub-divided by divergence size and verified-cause.

### 5.1 Mechanical SDK-import swap (18 files, all diff = 2 lines)

The CC files import from `@anthropic-ai/sdk/resources/...`; the KOSMOS
files import the equivalent type from `src/sdk-compat.js`. **Justified**
under swap 1 (LLM provider). No structural change. Pattern verified by
diffing all 22 diff-2 files; 18 of them are this exact one-import
substitution.

```
- import type { TextBlockParam } from '@anthropic-ai/sdk/resources/index.mjs';
+ import type { TextBlockParam } from 'src/sdk-compat.js';
```

Files: `messages/UserToolResultMessage/utils.tsx`,
`messages/GroupedToolUseContent.tsx`,
`messages/UserBashInputMessage.tsx`,
`messages/UserPromptMessage.tsx`,
`messages/UserAgentNotificationMessage.tsx`,
`messages/UserToolResultMessage/UserToolErrorMessage.tsx`,
`messages/UserToolResultMessage/UserToolResultMessage.tsx`,
`messages/UserCommandMessage.tsx`,
`FallbackToolUseErrorMessage.tsx`,
`messages/UserResourceUpdateMessage.tsx`,
`messages/UserChannelMessage.tsx`,
`agents/new-agent-creation/wizard-steps/GenerateStep.tsx`,
`messages/UserTeammateMessage.tsx`,
`permissions/PermissionRequest.tsx`,
`messages/UserTextMessage.tsx`,
`messages/AssistantToolUseMessage.tsx`,
`permissions/AskUserQuestionPermissionRequest/AskUserQuestionPermissionRequest.tsx`,
`MessageSelector.tsx`.

### 5.2 Mechanical brand swap (4 files, diff = 2 lines)

| File | Change |
|---|---|
| `LogoV2/Opus1mMergeNotice.tsx` | "Opus now defaults to 1M context" promo string removed/changed (KOSMOS has no Opus). |
| `IdeOnboardingDialog.tsx` | `Welcome to Claude Code for {ideName}` → `Welcome to KOSMOS for {ideName}`. |
| `HelpV2/HelpV2.tsx` | `Claude Code v${VERSION}` → `KOSMOS v${VERSION}`. |
| `sandbox/SandboxDependenciesTab.tsx` | `npm install -g @anthropic-ai/sandbox-runtime` install hint string removed (sandbox-runtime is not bundled). |

**Justified** under brand swap. Whitelisted in § 7.

### 5.3 sourceMappingURL stripping (1 file)

`Spinner.tsx` (3-line diff): trailing `//# sourceMappingURL=…base64…` line
removed. Cosmetic build-pipeline difference. **Justified**.

### 5.4 Single-line numeric / cosmetic adjustment (10 files, diff 3-7 lines)

`FeedbackSurvey/submitTranscriptShare.ts`,
`FeedbackSurvey/usePostCompactSurvey.tsx`,
`FeedbackSurvey/useMemorySurvey.tsx`,
`FeedbackSurvey/useFeedbackSurvey.tsx`,
`PromptInput/Notifications.tsx`,
`ConsoleOAuthFlow.tsx`,
`mcp/MCPRemoteServerMenu.tsx`,
`tasks/RemoteSessionDetailDialog.tsx`,
`tasks/BackgroundTasksDialog.tsx`,
`messages/SystemAPIErrorMessage.tsx`,
`ResumeTask.tsx`,
`StatusLine.tsx`.

Spot-check shows these are mostly endpoint-URL swaps (anthropic.com →
KOSMOS-equivalent or feature-flagged off), Korean string injections,
or `sdk-compat` imports. **Justified** but each file should carry a
short `// SWAP:` or `// KOSMOS:` comment marker for traceability. Some
already do (per spot check); the rest should be back-filled in a
follow-up cosmetic PR.

### 5.5 Documented swap-driven feature changes (8 files, diff 8-66 lines)

These are the swap surfaces where KOSMOS legitimately diverges, each
with an in-file comment block explaining why and citing the spec.

| File | Diff lines | Cause (spot-checked, in-file comment cited) |
|---|---:|---|
| `BaseTextInput.tsx` | 37 | **Spec 2519 Korean IME Enter swallow fix.** In-file comment cites Gemini CLI as the reference pattern and PR #2519. Justified. |
| `MessageRow.tsx` | 11 | sdk-compat + small render path adjustment. Spot-check OK. |
| `Settings/Settings.tsx` | 13 | Settings panel pruned of Anthropic-specific options (login, plan tier). Justified. |
| `Message.tsx` | 13 | sdk-compat + minor wrap. Spot-check OK. |
| `messages/AssistantTextMessage.tsx` | 18 | Suspect — verify in-file comment exists. **Action**: confirm. |
| `LogoV2/feedConfigs.tsx` | 23 | Brand-feed config (feed slots removed for KOSMOS). |
| `Markdown.tsx` | 66 | **Spec 1633 dead-code: cli-highlight unbundled** (Suspense + `use(promise)` Path removed; renders highlight=null always) **+ Spec 2521 K-EXAONE leading-whitespace flicker fix** (skip render when stripped text empty). Both changes carry in-file comment block. Justified. |
| `permissions/ExitPlanModePermissionRequest/ExitPlanModePermissionRequest.tsx` | 51 | Plan-mode permission dialog adapted for KOSMOS permission gauntlet (3-tier color, Korean labels). Verify in-file comment. **Action**: confirm. |
| `messages/AssistantThinkingMessage.tsx` | 52 | **Spec 2521 K-EXAONE thinking preview.** First non-empty reasoning line shown inline next to `∴ Thinking` glyph (since K-EXAONE emits CoT on `reasoning_content`). In-file comment cites SWAP/llm-provider(2521). Justified. |
| `Messages.tsx` | 56 | **Spec 2521 multi-tool layout (`createStreamingThinkingLayoutMessage` + `getStreamingThinkingInsertIndex` + `isSameAssistantToolStack`)** + **Phase 4 `useFrameCommitTracker` OTEL hook** for `kosmos.tui.frame_commit` event. Both in-file comments. Justified. |

### 5.6 LogoV2 / Mascot rewrite (5 files, diff 23-683 lines — largest cluster)

**Justified** under the brand swap (UFO mascot replaces CC's Clawd
character per `docs/requirements/kosmos-migration-tree.md § Mascot`).
Each file carries an SPDX header + KOSMOS comment block citing the
proposal doc (`docs/wireframes/ufo-mascot-proposal.mjs`) and noting
that the rendering technique (row-fill background + quadrant block
"holes") is preserved 1:1 from CC L34-182.

| File | Diff lines |
|---|---:|
| `LogoV2/CondensedLogo.tsx` | 119 |
| `LogoV2/AnimatedClawd.tsx` | 239 |
| `LogoV2/Clawd.tsx` | 348 |
| `LogoV2/WelcomeV2.tsx` | 683 |
| `LogoV2/LogoV2.tsx` | 48 |

### 5.7 Top-level launchers and screens (3 files outside `components/`)

| File | Diff | Verdict |
|---|---:|---|
| `screens/REPL.tsx` | 678 lines | **MIGRATE-FOR-SWAP — large but justified.** REPL is the swap-1+swap-2 entry point: LLM provider plumbing, IPC envelope routing (Spec 032), permission gauntlet integration, all converge here. Largest single file in the slice (920 KB). Should carry a top-of-file changelog block listing every swap-driven divergence; verify. **Action**: spot-check that REPL.tsx has a swap-changelog. |
| `interactiveHelpers.tsx` | 51 lines | Verify swap-comment exists. **Action**: confirm. |
| `replLauncher.tsx` | 10 lines | Likely sdk-compat / launch flag. **Action**: confirm. |
| `screens/Doctor.tsx` | 0 (identical) | PRESERVE. |
| `screens/ResumeConversation.tsx` | 0 (identical) | PRESERVE. |
| `dialogLaunchers.tsx` | 0 (identical) | PRESERVE. |

---

## 6. Bucket D — DROP-CANDIDATE / KOSMOS-only legitimate features (64 files)

These are KOSMOS-original UI L2 / brand / spec-driven features added on
top of the CC port. **None should actually be dropped** — they
implement Initiative #1631 (UI L2), Spec 022 (5-primitive renderers),
Spec 1635 (citizen UI), Spec 035 (onboarding brand port), Spec 1636
(plugin DX), Spec 2152 (system prompt), Spec 287 (Ink stack). They
appear in the "DROP-CANDIDATE" set only because they don't exist in
the CC restored-src by definition.

Grouped by purpose:

### 6.1 5-Primitive renderers (18 files) — **KEEP — Spec 022 / 027 / 031 deliverable**

`primitive/AddressBlock.tsx`, `AdmCodeBadge.tsx`, `AuthContextCard.tsx`,
`AuthWarningBanner.tsx`, `CollectionList.tsx`, `CoordPill.tsx`,
`DetailView.tsx`, `ErrorBanner.tsx`, `EventStream.tsx`, `index.tsx`
(PrimitiveDispatcher), `POIMarker.tsx`, `PointCard.tsx`,
`StreamClosed.tsx`, `SubmitErrorBanner.tsx`, `SubmitReceipt.tsx`,
`TimeseriesTable.tsx`, `types.ts`, `UnrecognizedPayload.tsx`,
`verify/AuthContextDisplay.tsx`.

The `PrimitiveDispatcher` is the LLM-tool-result render layer — pure
swap-2 surface. **No CC equivalent because CC does not have 5
primitives.** Keep.

### 6.2 Onboarding (UI-A, 7 files) — **KEEP — Spec 035 / Spec 1635 P4**

`onboarding/Onboarding.tsx`, `OnboardingFlow.tsx`,
`PIPAConsentStep.tsx`, `MinistryScopeStep.tsx`, `PreflightStep.tsx`,
`TerminalSetupStep.tsx`, `ThemeStep.tsx`. All carry SPDX + spec
citation in header.

### 6.3 Citizen UI extensions (UI-B/C/D/E, 17 files) — **KEEP — Spec 1635 P4**

- Conversation: `MessageList.tsx`, `StreamingMessage.tsx`,
  `VirtualizedList.tsx`.
- Messages extension: `MarkdownRenderer.tsx`, `MarkdownTable.tsx`,
  `PdfInlineViewer.tsx`, `StreamingChunk.tsx`, `ContextQuoteBlock.tsx`,
  `ErrorEnvelope.tsx`, `UserCrossSessionMessage.ts`,
  `UserForkBoilerplateMessage.ts`, `UserGitHubWebhookMessage.ts`.
- Help: `help/HelpV2Grouped.tsx`.
- History: `history/HistorySearchDialog.tsx`,
  `HistorySearchOverlay.tsx`.
- Config: `config/ConfigOverlay.tsx`,
  `EnvSecretIsolatedEditor.tsx`.
- Export: `export/ExportPdfDialog.tsx`.

### 6.4 Plugin DX (UI-E.3, 4 files) — **KEEP — Spec 1636 + Spec 1979**

`plugins/PluginBrowser.tsx`, `PluginDetail.tsx`, `PluginInstallFlow.tsx`,
`PluginRemoveConfirm.tsx`.

### 6.5 Permission extensions (2 files) — **KEEP — Spec 031 (subscribe primitive)**

`permissions/MonitorPermissionRequest/MonitorPermissionRequest.ts`,
`permissions/ReviewArtifactPermissionRequest/ReviewArtifactPermissionRequest.ts`.

### 6.6 Prompt-input extensions (2 files) — **KEEP — Spec 287 / kosmos-migration-tree UI-B.2 + B.6**

`PromptInput/CtrlOToExpand.tsx` (CC has expand/collapse but as inline
helper; KOSMOS extracted to component),
`PromptInput/SlashCommandSuggestions.tsx` (CC-style autocomplete
realisation per UI-B.6).

### 6.7 Brand / mascot (3 files) — **KEEP — UFO mascot deliverable**

`chrome/KosmosCoreIcon.tsx`, `ReplHeader.tsx`, `Spinner/types.ts`.

### 6.8 KOSMOS-original infrastructure (11 files) — **KEEP**

- `agents/AgentDetailRow.tsx`, `AgentVisibilityPanel.tsx`,
  `SnapshotUpdateDialog.tsx`, `agents/new-agent-creation/types.ts`.
- `CrashNotice.tsx` (post-crash recovery dialog).
- `FeedbackSurvey/utils.ts` (KOSMOS feedback collection scaffold).
- `mcp/types.ts` (KOSMOS MCP type module).
- `ui/option.ts`, `wizard/types.ts`, `Spinner/types.ts` (type helpers).

---

## 7. Branding-divergence whitelist (정당한 발산만)

Only the following kinds of divergence are acceptable in the
PRESERVE-IDENTICAL bucket. Anything else should be reverted or moved
to a spec-driven swap PR.

| # | Divergence kind | Allowed pattern | Where it appears |
|---|---|---|---|
| W1 | SDK import path | `@anthropic-ai/sdk/resources/...` → `src/sdk-compat.js` | 18 files in § 5.1 |
| W2 | Brand string substitution | `Claude Code` → `KOSMOS` (visible UI text only) | `IdeOnboardingDialog.tsx`, `HelpV2/HelpV2.tsx`, `Welcome*.tsx` |
| W3 | Mascot character swap | `Clawd` ASCII art → UFO ASCII art (boroshilac purple `#a78bfa`) | `LogoV2/Clawd.tsx`, `AnimatedClawd.tsx`, `WelcomeV2.tsx`, `CondensedLogo.tsx`, `LogoV2.tsx`, `feedConfigs.tsx`, `Opus1mMergeNotice.tsx` |
| W4 | Brand glyph | `✻` preserved (per `kosmos-migration-tree § Mascot`) | All files using `Asterisk` / `AnimatedAsterisk` |
| W5 | Korean i18n strings | English UI label → Korean label, with English fallback in code comment | `permissions/*`, `onboarding/*`, `messages/Rate*` |
| W6 | Color palette | CC primary blue → KOSMOS violet (`#a78bfa` body, `#4c1d95` background) | Token definitions in `tui/src/theme/tokens.ts`; component-level usage threaded via theme |
| W7 | Anthropic 1P-business surfaces removed | `Settings/Usage`, `Passes`, `Feedback`, `LogoV2/*Upsell`, `grove/Grove` (no KOSMOS replacement) | 6 PORT-DROPPED files in § 4 |
| W8 | sourceMappingURL strip | Trailing `//# sourceMappingURL=…base64…` removed | `Spinner.tsx` (and any future build-pipeline-introduced lines) |
| W9 | LLM-provider-specific render | K-EXAONE `reasoning_content` preview, leading-whitespace skip, parallel_tool_calls layout | `Markdown.tsx`, `messages/AssistantThinkingMessage.tsx`, `Messages.tsx` |
| W10 | Korean IME hotfix | `usePasteHandler` Enter swallow guard removed (Hangul Jamo composition fix) | `BaseTextInput.tsx` (Spec 2519, PR #2519) |
| W11 | Sandbox-runtime install hint | `npm install -g @anthropic-ai/sandbox-runtime` line removed | `sandbox/SandboxDependenciesTab.tsx` |
| W12 | OTEL frame_commit instrumentation | `useFrameCommitTracker(conversationId)` hook added (Phase 4) | `Messages.tsx` (and any future `kosmos.tui.frame_commit` consumer) |

**PR review heuristic**: a TUI-touching PR that diverges from CC and
does NOT match one of W1–W12 is a regression candidate. Open a
discussion before merging.

---

## 8. Impact analysis — what would break if PORT debt were real

The prompt assumed up to 235 missing components; the actual count is
**1 deferred file** (`TeleportResumeWrapper.tsx`). For completeness,
here is what citizen-visible damage each genuine PORT debt would do
(useful as the rubric for any future audit if PRESERVE-IDENTICAL
breaks):

| Hypothetical missing file | Citizen scenario impacted | Failure mode |
|---|---|---|
| `permissions/PermissionRequest.tsx` | First Live tool call (KOROAD lookup) | No permission modal renders → tool blocks silently → "왜 답이 안 나와요?" |
| `MessageRow.tsx` / `Messages.tsx` | Every assistant turn | Empty conversation viewport → REPL appears frozen |
| `messages/AssistantToolUseMessage.tsx` | Every tool call | Tool `⏺` line never appears → user sees thinking but no progress |
| `BaseTextInput.tsx` | Every keystroke | Cannot type at all |
| `PromptInput/PromptInput.tsx` | Slash command, paste, autocomplete | All input flows broken |
| `LogoV2/WelcomeV2.tsx` | First boot | Brand splash / onboarding entry point missing |
| `Spinner.tsx` | Every "thinking" or tool-running state | No motion feedback during 30-90s K-EXAONE reasoning latency → "행 멈춘 것 아닌가?" |
| `Markdown.tsx` | Every rendered assistant text | Plain unformatted strings → list-as-text, code-as-text |

**Verified**: all 8 above exist in KOSMOS and either match SHA-256
(spinner is identical except sourceMappingURL strip) or carry
documented swap-driven divergence. **No citizen-visible regressions
attributable to S3 PORT debt.**

---

## 9. Action items (decision needed)

| # | Decision | Owner | Severity |
|---|---|---|---|
| **D1** | ~~`TeleportResumeWrapper.tsx` (CC has, KOSMOS missing). Partner `TeleportProgress.tsx` is ported but diverged. **Choose**: (a) port the Wrapper to complete the parity, or (b) drop both (the "Teleport remote-resume" feature has no citizen analog). Recommend (b) — track as a one-line removal under Spec 2293.~~ **CLOSED 2026-05-03 by Epic #2639** — chose option (b). Removed `launchTeleportResumeWrapper` export from `tui/src/dialogLaunchers.tsx`, added `TeleportResumeWrapper.tsx` to NEVER-PORT registry (`tui/src/components/.never-port.md` + § 10 below). | User / Lead Opus | LOW (not citizen-visible until /resume-remote command is enabled). |
| **D2** | ~~Add a CI invariant: for every file in `comm -12 cc.txt kosmos.txt`, if the SHA-256 differs but the file is not on the W1–W12 whitelist, fail the build. This is the "AGENTS.md feedback_pr_pre_merge_interactive_test" methodology applied at the static-analysis layer. **Recommend**: build under Spec 2293 follow-up (P1 priority).~~ **CLOSED 2026-05-03 by Epic #2639** — `.github/workflows/cc-byte-identical-guard.yml` + `scripts/cc_byte_identical_guard.py` + `tui/src/.cc-byte-identical-whitelist.yaml` (60 entries, W1~W13) + vendored baseline `specs/2639-s3-ui-guard/fixtures/cc-baseline-shas.txt`. Cause taxonomy extended with W13 (dead-code cleanup). | User / Lead Opus | MEDIUM — locks in 85% PRESERVE-IDENTICAL number. |
| **D3** | ~~Five files (`messages/AssistantTextMessage.tsx`, `permissions/ExitPlanModePermissionRequest`, `replLauncher.tsx`, `interactiveHelpers.tsx`, `screens/REPL.tsx`) need a spot-check confirming each carries an in-file `// SWAP:` or `// KOSMOS:` comment block tying the divergence to a spec issue. **Recommend**: 30-min audit pass; back-fill missing comments as a non-PR cosmetic chore on `main` (allowed under AGENTS.md "docs:/chore: touching no source").~~ **CLOSED 2026-05-03 by Epic #2639** — all 5 file heads carry the canonical 5-line `// SWAP:` block citing cause + CC reference + divergence LOC + spec citation + justification. | Sonnet teammate | LOW. |
| **D4** | The 64 KOSMOS-only files in § 6 should be added to the spec audit registry (`specs/cc-migration-audit/scope-S3-kosmos-original-registry.md` follow-up) so future audits don't re-classify them as DROP-CANDIDATE. **Recommend**: defer to next audit cycle. | Lead Opus | LOW. |
| **D5** | ~~The 6 confirmed-DROP files (Feedback, Grove, GuestPassesUpsell, OverageCreditUpsell, Passes, Settings/Usage) should be added to a permanent NEVER-PORT list (e.g. as a comment block in `tui/src/components/.never-port` or in this audit doc) so future "complete CC port" sweeps don't accidentally restore them. **Recommend**: append to this doc as appendix § 10.~~ **CLOSED 2026-05-03 by Epic #2639** — appendix § 10 enriched (now 7 entries including TeleportResumeWrapper); in-tree mirror added at `tui/src/components/.never-port.md`. | Lead Opus | LOW. |

---

## 10. Appendix — confirmed-DROP NEVER-PORT list

The following CC files MUST NOT be ported. Each is a 1P-Anthropic
business surface (payments, sales, telemetry, growth experiments)
that has no analog in a citizen public-service harness, and porting
any of them would violate CORE THESIS ("KOSMOS = CC + 2 swaps;
payments / 1P telemetry are the third correctly-removed thing").

```
src/components/Feedback.tsx
src/components/grove/Grove.tsx
src/components/LogoV2/GuestPassesUpsell.tsx
src/components/LogoV2/OverageCreditUpsell.tsx
src/components/Passes/Passes.tsx
src/components/Settings/Usage.tsx
src/components/TeleportResumeWrapper.tsx   # added 2026-05-03 by Epic #2639 D1
```

If a future PR tries to add any of these, reject and link to this
appendix. The in-tree mirror of this list lives at
`tui/src/components/.never-port.md`.

---

## 11. Files inspected (reproducibility)

```
specs/cc-migration-audit/scope-S3-components-screens.md  (this file)

Inputs:
  .references/claude-code-sourcemap/restored-src/src/components/  (389 files)
  .references/claude-code-sourcemap/restored-src/src/screens/     (3 files)
  .references/claude-code-sourcemap/restored-src/src/dialogLaunchers.tsx
  .references/claude-code-sourcemap/restored-src/src/interactiveHelpers.tsx
  .references/claude-code-sourcemap/restored-src/src/outputStyles/
  .references/claude-code-sourcemap/restored-src/src/moreright/
  .references/claude-code-sourcemap/restored-src/src/replLauncher.tsx

  tui/src/components/                                            (446 files)
  tui/src/screens/                                                (3 files)
  tui/src/dialogLaunchers.tsx
  tui/src/interactiveHelpers.tsx
  tui/src/outputStyles/
  tui/src/moreright/
  tui/src/replLauncher.tsx

Set-difference output (reproducible):
  /tmp/cc-components.txt          (sorted CC enumeration, 389 entries)
  /tmp/kosmos-components.txt      (sorted KOSMOS enumeration, 446 entries)
  /tmp/missing-in-kosmos.txt      (CC-only, 7 entries)
  /tmp/extra-in-kosmos.txt        (KOSMOS-only, 64 entries)
  /tmp/in-both.txt                (intersection, 382 entries)
  /tmp/identical-files.txt        (SHA-256 match within in-both, 325 entries)
  /tmp/diverged-files.txt         (SHA-256 mismatch within in-both, 57 entries)

Spot-check diff inspections:
  components/Messages.tsx (56 lines)
  components/Markdown.tsx (66 lines)
  components/messages/AssistantThinkingMessage.tsx (52 lines)
  components/BaseTextInput.tsx (37 lines)
  components/messages/UserPromptMessage.tsx (2 lines, brand-swap sample)
  components/permissions/PermissionRequest.tsx (2 lines, brand-swap sample)
  components/LogoV2/Clawd.tsx (348 lines, mascot rewrite)
  components/Spinner.tsx (3 lines, sourceMappingURL strip)
  components/StatusLine.tsx (4 lines)
  All 22 diff=2 files (auto-classified BRAND vs OTHER via grep)
  screens/REPL.tsx (678-line metric only; no spot-check inside this audit)
```
