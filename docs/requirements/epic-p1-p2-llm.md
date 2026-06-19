# Epic P1+P2 · Dead code + Anthropic→FriendliAI migration

## Objective

Remove all Anthropic-specific bootstrap, telemetry, auth, and migration cruft. Replace model/auth/endpoint references with FriendliAI/K-EXAONE. Target: `main.tsx` 4683 → ~2000 lines.

## Acceptance criteria

- [ ] 0 references to `@anthropic-ai/sdk` in runtime code
- [ ] All `logEvent` / `profileCheckpoint` / `growthbook` / `statsig` calls removed
- [ ] All CC version migrations deleted (11 files listed below)
- [ ] `FRIENDLI_API_KEY` env var wired via `LLMClient` (rewired `query.ts` / `QueryEngine.ts`)
- [ ] `prompts/system_v1.md` loaded via `PromptLoader` (Spec 026)
- [ ] Model ID = `LGAI-EXAONE/K-EXAONE-236B-A23B`

---

## P1 file-level scope

### Ant-only blocks (delete guarded branches)
- `tui/src/main.tsx` — `=== "ant"` / `ANT_INTERNAL` guards (~58 call sites)
- `tui/src/screens/REPL.tsx`
- `tui/src/tools/AgentTool/AgentTool.tsx`
- `tui/src/tools/AgentTool/UI.tsx`
- `tui/src/components/Spinner.tsx`
- `tui/src/components/DevBar.tsx`
- `tui/src/components/Feedback.tsx`
- `tui/src/components/NativeAutoUpdater.tsx`
- `tui/src/utils/processUserInput/processSlashCommand.tsx`
- `tui/src/buddy/useBuddyNotification.tsx`

### CC Migrations (delete all 11)
- `tui/src/migrations/migrateAutoUpdatesToSettings.ts`
- `tui/src/migrations/migrateBypassPermissionsAcceptedToSettings.ts`
- `tui/src/migrations/migrateEnableAllProjectMcpServersToSettings.ts`
- `tui/src/migrations/migrateFennecToOpus.ts`
- `tui/src/migrations/migrateLegacyOpusToCurrent.ts`
- `tui/src/migrations/migrateOpusToOpus1m.ts`
- `tui/src/migrations/migrateReplBridgeEnabledToRemoteControlAtStartup.ts`
- `tui/src/migrations/migrateSonnet1mToSonnet45.ts`
- `tui/src/migrations/migrateSonnet45ToSonnet46.ts`
- `tui/src/migrations/resetAutoModeOptInForDefaultOffer.ts`
- `tui/src/migrations/resetProToOpusDefault.ts`

### CC Telemetry (strip or noop entire directories/files)
- `tui/src/services/services/analytics/` — all 7 files (`growthbook.ts`, `datadog.ts`, `firstPartyEventLogger.ts`, `sink.ts`, `sinkKillswitch.ts`, `metadata.ts`, `index.ts`)
- `tui/src/utils/telemetry/` — all 5 files (`sessionTracing.ts`, `betaSessionTracing.ts`, `instrumentation.ts`, `pluginTelemetry.ts`, `skillLoadedEvent.ts`)
- `tui/src/types/types/generated/events_mono/` — delete generated event types
- `tui/src/services/services/internalLogging.ts`

### CC Auth (strip)
- `tui/src/utils/auth.ts`
- `tui/src/utils/secureStorage/` — all 6 files (`keychainPrefetch.ts`, `macOsKeychainStorage.ts`, `macOsKeychainHelpers.ts`, `fallbackStorage.ts`, `plainTextStorage.ts`, `index.ts`)
- `tui/src/services/services/oauth/` — all 5 files (`client.ts`, `index.ts`, `auth-code-listener.ts`, `crypto.ts`, `getOauthProfile.ts`)
- `tui/src/commands/login/login.tsx`, `tui/src/commands/logout/logout.tsx`

### CC Teleport / Remote (strip)
- `tui/src/remote/` — all 4 files (`RemoteSessionManager.ts`, `remotePermissionBridge.ts`, `sdkMessageAdapter.ts`, `SessionsWebSocket.ts`)
- `tui/src/services/services/remoteManagedSettings/securityCheck.tsx`
- `tui/src/utils/teleport.tsx`, `tui/src/utils/teleport/gitBundle.ts`
- `tui/src/utils/background/remote/remoteSession.ts`, `preconditions.ts`
- `tui/src/components/TeleportResumeWrapper.tsx`, `tui/src/hooks/useTeleportResume.tsx`

---

## P2 file-level scope

### API endpoints (replace or remove)
- `tui/src/services/api/ummaya.ts` — **replace**: rewire to FriendliAI `/v1/chat/completions`
- `tui/src/services/services/api/client.ts` — **replace**: swap base URL + auth header to `FRIENDLI_API_KEY`
- `tui/src/services/services/api/bootstrap.ts` — **strip**: Anthropic-side bootstrap handshake
- `tui/src/services/services/api/usage.ts` — **strip**: Anthropic usage/billing endpoint
- `tui/src/services/services/api/overageCreditGrant.ts` — **delete**
- `tui/src/services/services/api/referral.ts` — **delete**
- `tui/src/services/services/api/adminRequests.ts` — **delete**
- `tui/src/services/services/api/filesApi.ts` — **evaluate**: keep if FriendliAI Files API compatible
- `tui/src/services/services/api/grove.ts` — **delete** (Grove is Anthropic-internal)
- `tui/src/services/api/overageCreditGrant.ts`, `referral.ts`, `errors.ts` — **delete** (duplicate stubs)

### OAuth / Model config
- `tui/src/constants/constants/oauth.ts` — **replace** Anthropic OAuth constants with FriendliAI API key config
- `tui/src/utils/model/antModels.ts` — **replace** `getDefaultMainLoopModel` return value with `LGAI-EXAONE/K-EXAONE-236B-A23B`
- `tui/src/utils/modelCost.ts` — **strip**: Anthropic token pricing table
- `tui/src/utils/betas.ts` — **strip**: Anthropic beta-header management

### Policy limits (strip entirely)
- `tui/src/services/services/policyLimits/index.ts`
- `tui/src/services/services/policyLimits/types.ts`
- `tui/src/services/services/claudeAiLimits.ts`

### MCP Anthropic integration (strip)
- `tui/src/services/services/mcp/claudeai.ts`

### Entrypoint rewire
- `tui/src/entrypoints/init.ts` — replace `initializeTelemetryAfterTrust` with UMMAYA OTEL init (Spec 021)
- `tui/src/query.ts`, `tui/src/QueryEngine.ts` — rewire `@anthropic-ai/sdk` client instantiation to FriendliAI `LLMClient`

### Keep (but rewire)
- `tui/src/services/services/api/withRetry.ts` — keep retry logic, update error codes
- `tui/src/services/services/api/errors.ts` / `errorUtils.ts` — keep structure, strip Anthropic-specific error codes
- `tui/src/services/services/api/promptCacheBreakDetection.ts` — keep if FriendliAI supports cache tokens

---

## Out of scope

Tool system (P3) · UI components (P4) · Plugin DX (P5) · docs/api (P6)

## Dependencies

Requires Epic P0 complete (repo scaffold, `FRIENDLI_API_KEY` secret wiring).

## Related decisions

`docs/requirements/ummaya-migration-tree.md` § L1-A + § P1/P2
