import { Command as CommanderCommand, InvalidArgumentError, Option } from '@commander-js/extra-typings';
import chalk from 'chalk';
import { readFileSync } from 'fs';
import mapValues from 'lodash-es/mapValues.js';
import pickBy from 'lodash-es/pickBy.js';
import uniqBy from 'lodash-es/uniqBy.js';
import React from 'react';
import { init } from './entrypoints/init.js';
import { addToHistory } from './history.js';
import type { Root } from './ink.js';
import { launchRepl } from './replLauncher.js';
// UMMAYA: services/api/filesApi deleted (Anthropic session API). File download via --file flag is unsupported.
import { prefetchOfficialMcpUrls } from './services/mcp/officialRegistry.js';
import type { McpSdkServerConfig, McpServerConfig, ScopedMcpServerConfig } from './services/mcp/types.js';
import type { ToolInputJSONSchema } from './Tool.js';
import { createSyntheticOutputTool, isSyntheticOutputToolEnabled } from './tools/SyntheticOutputTool/SyntheticOutputTool.js';
import { getAllBaseTools, getTools } from './tools.js';
import { verifyBootRegistry } from './services/toolRegistry/bootGuard.js';
import { canUserConfigureAdvisor, getInitialAdvisorSetting, isAdvisorEnabled, isValidAdvisorModel, modelSupportsAdvisor } from './utils/advisor.js';
import { isAgentSwarmsEnabled } from './utils/agentSwarmsEnabled.js';
import { count, uniq } from './utils/array.js';
import { checkHasTrustDialogAccepted, getGlobalConfig, getRemoteControlAtStartup, isAutoUpdaterDisabled, saveGlobalConfig } from './utils/config.js';
import { seedEarlyInput, stopCapturingEarlyInput } from './utils/earlyInput.js';
import { getInitialEffortSetting, parseEffortValue } from './utils/effort.js';
import { getInitialFastModeSetting, isFastModeEnabled, prefetchFastModeStatus, resolveFastModeStatusFromCache } from './utils/fastMode.js';
import { getInitialReasoningModeSetting } from './utils/kExaoneReasoning.js';
import { applyConfigEnvironmentVariables } from './utils/managedEnv.js';
import { createSystemMessage } from './utils/systemMessageFactories.js';
import { createUserMessage } from './utils/userMessageFactories.js';
import { getPlatform } from './utils/platform.js';
import { getBaseRenderOptions } from './utils/renderOptions.js';
// UMMAYA: services/api/sessionIngress deleted. sessionIngressAuth stub kept for build compatibility.
import { settingsChangeDetector } from './utils/settings/changeDetector.js';
import { skillChangeDetector } from './utils/skills/skillChangeDetector.js';
import { jsonParse, writeFileSync_DEPRECATED } from './utils/slowOperations.js';
import { computeInitialTeamContext } from './utils/swarm/reconnection.js';
import { initializeWarningHandler } from './utils/warningHandler.js';
import { isWorktreeModeEnabled } from './utils/worktreeModeEnabled.js';

// Lazy require to avoid circular dependency: teammate.ts -> AppState.tsx -> ... -> main.tsx
/* eslint-disable @typescript-eslint/no-require-imports */
const getTeammateUtils = () => require('./utils/teammate.js') as typeof import('./utils/teammate.js');
const getTeammatePromptAddendum = () => require('./utils/swarm/teammatePromptAddendum.js') as typeof import('./utils/swarm/teammatePromptAddendum.js');
const getTeammateModeSnapshot = () => require('./utils/swarm/backends/teammateModeSnapshot.js') as typeof import('./utils/swarm/backends/teammateModeSnapshot.js');
/* eslint-enable @typescript-eslint/no-require-imports */
import { relative, resolve } from 'path';
import { getOriginalCwd, setAdditionalDirectoriesForClaudeMd, setMainLoopModelOverride, setMainThreadAgentType } from './bootstrap/state.js';
import { getCommands } from './commands.js';
import type { StatsStore } from './context/stats.js';
import { launchInvalidSettingsDialog, launchResumeChooser } from './dialogLaunchers.js';
import { SHOW_CURSOR } from './ink/termio/dec.js';
import { exitWithError, exitWithMessage, getRenderContext, renderAndRun, showSetupScreens, showDialog } from './interactiveHelpers.js';
import { initBuiltinPlugins } from './plugins/bundled/index.js';
/* eslint-enable @typescript-eslint/no-require-imports */
import { getMcpToolsCommandsAndResources, prefetchAllMcpResources } from './services/mcp/client.js';
import { VALID_INSTALLABLE_SCOPES, VALID_UPDATE_SCOPES } from './services/plugins/pluginCliCommands.js';
import { initBundledSkills } from './skills/bundled/index.js';
import type { AgentColorName } from './tools/AgentTool/agentColorManager.js';
import { getActiveAgentsFromList, getAgentDefinitionsWithOverrides, isBuiltInAgent, isCustomAgent, parseAgentsFromJson } from './tools/AgentTool/loadAgentsDir.js';
import type { LogOption } from './types/logs.js';
import type { Message as MessageType } from './types/message.js';
import { assertMinVersion } from './utils/autoUpdater.js';
import { CLAUDE_IN_CHROME_SKILL_HINT } from './utils/claudeInChrome/prompt.js';
import { setupClaudeInChrome, shouldAutoEnableClaudeInChrome, shouldEnableClaudeInChrome } from './utils/claudeInChrome/setup.js';
import { getContextWindowForModel } from './utils/context.js';
import { loadConversationForResume } from './utils/conversationRecovery.js';
import { hasNodeOption, isBareMode, isEnvTruthy, isInProtectedNamespace } from './utils/envUtils.js';
import { refreshExampleCommands } from './utils/exampleCommands.js';
import type { FpsMetrics } from './utils/fpsTracker.js';
import { getWorktreePaths } from './utils/getWorktreePaths.js';
import { findGitRoot, getIsGit, getWorktreeCount } from './utils/git.js';
import { getGhAuthStatus } from './utils/github/ghAuthStatus.js';
import { safeParseJSON } from './utils/json.js';
import { logError } from './utils/log.js';
import { getModelDeprecationWarning } from './utils/model/deprecation.js';
import { getDefaultMainLoopModel, getUserSpecifiedModelSetting, normalizeModelStringForAPI, parseUserSpecifiedModel } from './utils/model/model.js';
import { ensureModelStringsInitialized } from './utils/model/modelStrings.js';
import { PERMISSION_MODES } from './utils/permissions/PermissionMode.js';
import { checkAndDisableBypassPermissions, initializeToolPermissionContext, initialPermissionModeFromCLI, parseToolListFromCLI } from './utils/permissions/permissionSetup.js';
import { cleanupOrphanedPluginVersionsInBackground } from './utils/plugins/cacheUtils.js';
import { initializeVersionedPlugins } from './utils/plugins/installedPluginsManager.js';
import { getGlobExclusionsForPluginCache } from './utils/plugins/orphanedPluginFilter.js';
import { countFilesRoundedRg } from './utils/ripgrep.js';
import { processSessionStartHooks, processSetupHooks } from './utils/sessionStart.js';
import { cacheSessionTitle, getSessionIdFromLog, loadTranscriptFromFile, saveAgentSetting, saveMode, searchSessionsByCustomTitle, sessionIdExists } from './utils/sessionStorage.js';
import { getInitialSettings, getSettingsForSource, getSettingsWithErrors } from './utils/settings/settings.js';
import { resetSettingsCache } from './utils/settings/settingsCache.js';
import type { ValidationError } from './utils/settings/validation.js';
import { generateTempFilePath } from './utils/tempfile.js';
import { validateUuid } from './utils/uuid.js';
// Plugin startup checks are now handled non-blockingly in REPL.tsx

import { registerMcpAddCommand } from 'src/commands/mcp/addCommand.js';
import { registerMcpXaaIdpCommand } from 'src/commands/mcp/xaaIdpCommand.js';
// Managed MCP proxy removed in P1+P2 (Spec 1633); UMMAYA does not consume
// upstream enterprise MCP configs. The eligibility check is now a no-op.
const fetchClaudeAIMcpConfigsIfEligible = async (): Promise<Record<string, never>> => ({});
import { clearServerCache } from 'src/services/mcp/client.js';
import { areMcpConfigsAllowedWithEnterpriseMcpConfig, dedupClaudeAiMcpServers, doesEnterpriseMcpConfigExist, filterMcpServersByPolicy, getClaudeCodeMcpConfigs, getMcpServerSignature, parseMcpConfig, parseMcpConfigFromFilePath } from 'src/services/mcp/config.js';
import { excludeCommandsByServer, excludeResourcesByServer } from 'src/services/mcp/utils.js';
import { isXaaEnabled } from 'src/services/mcp/xaaIdpLogin.js';
import { getRelevantTips } from 'src/services/tips/tipRegistry.js';
import { CLAUDE_IN_CHROME_MCP_SERVER_NAME, isClaudeInChromeMCPServer } from 'src/utils/claudeInChrome/common.js';
import { registerCleanup } from 'src/utils/cleanupRegistry.js';
import { eagerParseCliFlag } from 'src/utils/cliArgs.js';
import { createEmptyAttributionState } from 'src/utils/commitAttribution.js';
import { countConcurrentSessions, registerSession, updateSessionName } from 'src/utils/concurrentSessions.js';
import { getCwd } from 'src/utils/cwd.js';
import { logForDebugging, setHasFormattedOutput } from 'src/utils/debug.js';
import { errorMessage, getErrnoCode, isENOENT, toError } from 'src/utils/errors.js';
import { getFsImplementation, safeResolvePath } from 'src/utils/fsOperations.js';
import { gracefulShutdown, gracefulShutdownSync } from 'src/utils/gracefulShutdown.js';
import { setAllHookEventsEnabled } from 'src/utils/hooks/hookEvents.js';
import { assertFriendliApiKeyForUse } from 'src/utils/auth.js';
import { refreshModelCapabilities } from 'src/utils/model/modelCapabilities.js';
import { peekForStdinData, writeToStderr } from 'src/utils/process.js';
import { setCwd } from 'src/utils/Shell.js';
import { type ProcessedResume, processResumedConversation } from 'src/utils/sessionRestore.js';
import { parseSettingSourcesFlag } from 'src/utils/settings/constants.js';
import { plural } from 'src/utils/stringUtils.js';
import { getInitialMainLoopModel, getIsNonInteractiveSession, getSdkBetas, getSessionId, getUserMsgOptIn, setAllowedSettingSources, setChromeFlagOverride, setClientType, setCwdState, setFlagSettingsPath, setInitialMainLoopModel, setInlinePlugins, setIsInteractive, setOriginalCwd, setQuestionPreviewFormat, setSdkBetas, setSessionBypassPermissionsMode, setSessionPersistenceDisabled, setSessionSource, setUserMsgOptIn } from './bootstrap/state.js';

// TeleportRepoMismatchDialog dynamically imported at call sites
/* eslint-enable @typescript-eslint/no-require-imports */
// teleportWithProgress dynamically imported at call site
import { initializeLspServerManager } from './services/lsp/manager.js';
import { shouldEnablePromptSuggestion } from './services/PromptSuggestion/promptSuggestion.js';
import { type AppState, getDefaultAppState, IDLE_SPECULATION_STATE } from './state/AppStateStore.js';
import { onChangeAppState } from './state/onChangeAppState.js';
import { createStore } from './state/store.js';
import { isInBundledMode, isRunningWithBun } from './utils/bundledMode.js';
import { logForDiagnosticsNoPII } from './utils/diagLogs.js';
import { clearPluginCache } from './utils/plugins/pluginLoader.js';
import { shouldEnableThinkingByDefault, type ThinkingConfig } from './utils/thinking.js';
import { initUser } from './utils/user.js';
import { getTmuxInstallInstructions, isTmuxAvailable, parsePRReference } from './utils/worktree.js';



type ModuleRequire = (specifier: string) => unknown
type InspectorModule = {
  url: () => string | undefined
}

function isModuleRequire(value: unknown): value is ModuleRequire {
  return typeof value === 'function'
}

function isInspectorModule(value: unknown): value is InspectorModule {
  return typeof value === 'object' && value !== null && 'url' in value && typeof value.url === 'function'
}

function getInspectorFromGlobal(): InspectorModule | undefined {
  const globalRequire: unknown = Reflect.get(globalThis, 'require')
  if (!isModuleRequire(globalRequire)) return undefined

  const inspector = globalRequire('inspector')
  return isInspectorModule(inspector) ? inspector : undefined
}

// Check if running in debug/inspection mode
function isBeingDebugged() {
  const isBun = isRunningWithBun();

  // Check for inspect flags in process arguments (including all variants)
  const hasInspectArg = process.execArgv.some(arg => {
    if (isBun) {
      // Note: Bun has an issue with single-file executables where application arguments
      // from process.argv leak into process.execArgv (similar to https://github.com/oven-sh/bun/issues/11673)
      // This breaks use of --debug mode if we omit this branch
      // We're fine to skip that check, because Bun doesn't support Node.js legacy --debug or --debug-brk flags
      return /--inspect(-brk)?/.test(arg);
    } else {
      // In Node.js, check for both --inspect and legacy --debug flags
      return /--inspect(-brk)?|--debug(-brk)?/.test(arg);
    }
  });

  // Check if NODE_OPTIONS contains inspect flags
  const hasInspectEnv = process.env.NODE_OPTIONS && /--inspect(-brk)?|--debug(-brk)?/.test(process.env.NODE_OPTIONS);

  // Check if inspector is available and active (indicates debugging)
  try {
    // Dynamic import would be better but is async - use global object instead
    const inspector = getInspectorFromGlobal();
    const hasInspectorUrl = !!inspector?.url();
    return hasInspectorUrl || hasInspectArg || hasInspectEnv;
  } catch {
    // Ignore error and fall back to argument detection
    return hasInspectArg || hasInspectEnv;
  }
}

// Exit if we detect node debugging or inspection
if ("external" !== 'ant' && isBeingDebugged()) {
  // Use process.exit directly here since we're in the top-level code before imports
  // and gracefulShutdown is not yet available
  // eslint-disable-next-line custom-rules/no-top-level-side-effects
  process.exit(1);
}

// TODO(1633): migrations removed — migration files deleted in Wave A-C.
// If model-alias migrations are needed for UMMAYA, add them here.
const CURRENT_MIGRATION_VERSION = 11;
function runMigrations(): void {
  // No-op: all Anthropic-internal migration modules deleted in Epic #1633 Wave A-C.
  // Update CURRENT_MIGRATION_VERSION and add UMMAYA-specific migrations here when needed.
}

/**
 * Prefetch system context (including git status) only when it's safe to do so.
 * Git commands can execute arbitrary code via hooks and config (e.g., core.fsmonitor,
 * diff.external), so we must only run them after trust is established or in
 * non-interactive mode where trust is implicit.
 */
function prefetchSystemContextIfSafe(): void {
  const isNonInteractiveSession = getIsNonInteractiveSession();

  // In non-interactive mode (--print), trust dialog is skipped and
  // execution is considered trusted (as documented in help text)
  // Epic #2152 R5 — citizen chat-request path no longer reads getSystemContext
  // (cwd / gitStatus / claudeMd are developer-domain). Prefetch warm-ups are
  // dead under the citizen harness; the AgentTool path that legitimately
  // consumes the developer context still calls getSystemContext on demand
  // inside its own module (tools/AgentTool/runAgent.ts).
  if (isNonInteractiveSession) {
    logForDiagnosticsNoPII('info', 'prefetch_system_context_non_interactive_skipped');
    return;
  }
  logForDiagnosticsNoPII('info', 'prefetch_system_context_skipped_citizen_path');
}

/**
 * Start background prefetches and housekeeping that are NOT needed before first render.
 * These are deferred from setup() to reduce event loop contention and child process
 * spawning during the critical startup path.
 * Call this after the REPL has been rendered.
 */
export function startDeferredPrefetches(): void {
  // This function runs after first render, so it doesn't block the initial paint.
  // However, the spawned processes and async work still contend for CPU and event
  // loop time, which skews startup benchmarks (CPU profiles, time-to-first-render
  // measurements). Skip all of it when we're only measuring startup performance.
  if (isEnvTruthy(process.env.CLAUDE_CODE_EXIT_AFTER_FIRST_RENDER) ||
  // --bare: skip ALL prefetches. These are cache-warms for the REPL's
  // first-turn responsiveness (initUser, getUserContext, tips, countFiles,
  // modelCapabilities, change detectors). Scripted -p calls don't have a
  // "user is typing" window to hide this work in — it's pure overhead on
  // the critical path.
  isBareMode()) {
    return;
  }

  // Process-spawning prefetches (consumed at first API call, user is still typing).
  // Epic #2152 R5 — getUserContext / getSystemContext warm-ups removed: the
  // citizen chat-request path does not read CLAUDE.md / cwd / gitStatus.
  void initUser();
  void getRelevantTips();
  void countFilesRoundedRg(getCwd(), AbortSignal.timeout(3000), []);

  // Analytics and feature flag initialization
  void prefetchOfficialMcpUrls();
  void refreshModelCapabilities();

  // File change detectors deferred from init() to unblock first render
  void settingsChangeDetector.initialize();
  if (!isBareMode()) {
    void skillChangeDetector.initialize();
  }

}
function loadSettingsFromFlag(settingsFile: string): void {
  try {
    const trimmedSettings = settingsFile.trim();
    const looksLikeJson = trimmedSettings.startsWith('{') && trimmedSettings.endsWith('}');
    let settingsPath: string;
    if (looksLikeJson) {
      // It's a JSON string - validate and create temp file
      const parsedJson = safeParseJSON(trimmedSettings);
      if (!parsedJson) {
        process.stderr.write(chalk.red('Error: Invalid JSON provided to --settings\n'));
        process.exit(1);
      }

      // Create a temporary file and write the JSON to it.
      // Use a content-hash-based path instead of random UUID to avoid
      // busting the FriendliAI API prompt cache. The settings path ends up
      // in the Bash tool's sandbox denyWithinAllow list, which is part of
      // the tool description sent to the API. A random UUID per subprocess
      // changes the tool description on every query() call, invalidating
      // the cache prefix and causing a 12x input token cost penalty.
      // The content hash ensures identical settings produce the same path
      // across process boundaries (each SDK query() spawns a new process).
      settingsPath = generateTempFilePath('claude-settings', '.json', {
        contentHash: trimmedSettings
      });
      writeFileSync_DEPRECATED(settingsPath, trimmedSettings, 'utf8');
    } else {
      // It's a file path - resolve and validate by attempting to read
      const {
        resolvedPath: resolvedSettingsPath
      } = safeResolvePath(getFsImplementation(), settingsFile);
      try {
        readFileSync(resolvedSettingsPath, 'utf8');
      } catch (e) {
        if (isENOENT(e)) {
          process.stderr.write(chalk.red(`Error: Settings file not found: ${resolvedSettingsPath}\n`));
          process.exit(1);
        }
        throw e;
      }
      settingsPath = resolvedSettingsPath;
    }
    setFlagSettingsPath(settingsPath);
    resetSettingsCache();
  } catch (error) {
    if (error instanceof Error) {
      logError(error);
    }
    process.stderr.write(chalk.red(`Error processing settings: ${errorMessage(error)}\n`));
    process.exit(1);
  }
}
function loadSettingSourcesFromFlag(settingSourcesArg: string): void {
  try {
    const sources = parseSettingSourcesFlag(settingSourcesArg);
    setAllowedSettingSources(sources);
    resetSettingsCache();
  } catch (error) {
    if (error instanceof Error) {
      logError(error);
    }
    process.stderr.write(chalk.red(`Error processing --setting-sources: ${errorMessage(error)}\n`));
    process.exit(1);
  }
}

/**
 * Parse and load settings flags early, before init()
 * This ensures settings are filtered from the start of initialization
 */
function eagerLoadSettings(): void {
  // Parse --settings flag early to ensure settings are loaded before init()
  const settingsFile = eagerParseCliFlag('--settings');
  if (settingsFile) {
    loadSettingsFromFlag(settingsFile);
  }

  // Parse --setting-sources flag early to control which sources are loaded
  const settingSourcesArg = eagerParseCliFlag('--setting-sources');
  if (settingSourcesArg !== undefined) {
    loadSettingSourcesFromFlag(settingSourcesArg);
  }
}
function initializeEntrypoint(isNonInteractive: boolean): void {
  // Skip if already set (e.g., by SDK or other entrypoints)
  if (process.env.CLAUDE_CODE_ENTRYPOINT) {
    return;
  }
  const cliArgs = process.argv.slice(2);

  // Check for MCP serve command (handle flags before mcp serve, e.g., --debug mcp serve)
  const mcpIndex = cliArgs.indexOf('mcp');
  if (mcpIndex !== -1 && cliArgs[mcpIndex + 1] === 'serve') {
    process.env.CLAUDE_CODE_ENTRYPOINT = 'mcp';
    return;
  }
  if (isEnvTruthy(process.env.CLAUDE_CODE_ACTION)) {
    process.env.CLAUDE_CODE_ENTRYPOINT = 'claude-code-github-action';
    return;
  }

  // Note: 'local-agent' entrypoint is set by the local agent mode launcher
  // via CLAUDE_CODE_ENTRYPOINT env var (handled by early return above)

  // Set based on interactive status
  process.env.CLAUDE_CODE_ENTRYPOINT = isNonInteractive ? 'sdk-cli' : 'cli';
}

export async function main() {

  // SECURITY: Prevent Windows from executing commands from current directory
  // This must be set before ANY command execution to prevent PATH hijacking attacks
  // See: https://docs.microsoft.com/en-us/windows/win32/api/processenv/nf-processenv-searchpathw
  process.env.NoDefaultCurrentDirectoryInExePath = '1';

  // Initialize warning handler early to catch warnings
  initializeWarningHandler();
  process.on('exit', () => {
    resetCursor();
  });
  process.on('SIGINT', () => {
    // In print mode, print.ts registers its own SIGINT handler that aborts
    // the in-flight query and calls gracefulShutdown; skip here to avoid
    // preempting it with a synchronous process.exit().
    if (process.argv.includes('-p') || process.argv.includes('--print')) {
      return;
    }
    process.exit(0);
  });

  // Check for -p/--print and --init-only flags early to set isInteractiveSession before init()
  // This is needed because telemetry initialization calls auth functions that need this flag
  const cliArgs = process.argv.slice(2);
  const hasPrintFlag = cliArgs.includes('-p') || cliArgs.includes('--print');
  const hasInitOnlyFlag = cliArgs.includes('--init-only');
  const hasSdkUrl = cliArgs.some(arg => arg.startsWith('--sdk-url'));
  // UMMAYA-1978 T003b: Bun's `process.stdout.isTTY` is `undefined` (not `true`)
  // when invoked through wrappers like `bun run ...` or under PTY harnesses
  // where the parent shell already wrapped fd1. The CC original assumed Node's
  // strict-boolean isTTY (true under TTY, false under pipes). To preserve the
  // PTY-driven verification path required by memory `feedback_runtime_verification`,
  // UMMAYA adds an explicit `UMMAYA_FORCE_INTERACTIVE` env override that the
  // PTY scenario harness sets when it knows fd1 is a real TTY slave. The
  // override must NEVER be set in a citizen's environment — it is a test-harness
  // signal, not a runtime configuration.
  const ummayaForceInteractive = process.env.UMMAYA_FORCE_INTERACTIVE === '1';
  const isNonInteractive = hasPrintFlag || hasInitOnlyFlag || hasSdkUrl || (!ummayaForceInteractive && !process.stdout.isTTY);

  // Stop capturing early input for non-interactive modes
  if (isNonInteractive) {
    stopCapturingEarlyInput();
  }

  // Set simplified tracking fields
  const isInteractive = !isNonInteractive;
  setIsInteractive(isInteractive);

  // Initialize entrypoint based on mode - needs to be set before any event is logged
  initializeEntrypoint(isNonInteractive);

  // Determine client type
  const clientType = (() => {
    if (isEnvTruthy(process.env.GITHUB_ACTIONS)) return 'github-action';
    if (process.env.CLAUDE_CODE_ENTRYPOINT === 'sdk-ts') return 'sdk-typescript';
    if (process.env.CLAUDE_CODE_ENTRYPOINT === 'sdk-py') return 'sdk-python';
    if (process.env.CLAUDE_CODE_ENTRYPOINT === 'sdk-cli') return 'sdk-cli';
    if (process.env.CLAUDE_CODE_ENTRYPOINT === 'claude-vscode') return 'claude-vscode';
    if (process.env.CLAUDE_CODE_ENTRYPOINT === 'local-agent') return 'local-agent';
    if (process.env.CLAUDE_CODE_ENTRYPOINT === 'claude-desktop') return 'claude-desktop';

    // Check if session-ingress token is provided (indicates remote session)
    const hasSessionIngressToken = process.env.CLAUDE_CODE_SESSION_ACCESS_TOKEN || process.env.CLAUDE_CODE_WEBSOCKET_AUTH_FILE_DESCRIPTOR;
    if (process.env.CLAUDE_CODE_ENTRYPOINT === 'remote' || hasSessionIngressToken) {
      return 'remote';
    }
    return 'cli';
  })();
  setClientType(clientType);
  const previewFormat = process.env.CLAUDE_CODE_QUESTION_PREVIEW_FORMAT;
  if (previewFormat === 'markdown' || previewFormat === 'html') {
    setQuestionPreviewFormat(previewFormat);
  } else if (!clientType.startsWith('sdk-') &&
  // Desktop and CCR pass previewFormat via toolConfig; when the feature is
  // gated off they pass undefined — don't override that with markdown.
  clientType !== 'claude-desktop' && clientType !== 'local-agent' && clientType !== 'remote') {
    setQuestionPreviewFormat('markdown');
  }

  // Tag sessions created via `ummaya remote-control` so the backend can identify them
  if (process.env.CLAUDE_CODE_ENVIRONMENT_KIND === 'bridge') {
    setSessionSource('remote-control');
  }

  // Parse and load settings flags early, before init()
  eagerLoadSettings();
  await run();
}
async function getInputPrompt(prompt: string, inputFormat: 'text' | 'stream-json'): Promise<string | AsyncIterable<string>> {
  if (!process.stdin.isTTY &&
  // Input hijacking breaks MCP.
  !process.argv.includes('mcp')) {
    if (inputFormat === 'stream-json') {
      return process.stdin;
    }
    process.stdin.setEncoding('utf8');
    let data = '';
    const onData = (chunk: string) => {
      data += chunk;
    };
    process.stdin.on('data', onData);
    // If no data arrives in 3s, stop waiting and warn. Stdin is likely an
    // inherited pipe from a parent that isn't writing (subprocess spawned
    // without explicit stdin handling). 3s covers slow producers like curl,
    // jq on large files, python with import overhead. The warning makes
    // silent data loss visible for the rare producer that's slower still.
    const timedOut = await peekForStdinData(process.stdin, 3000);
    process.stdin.off('data', onData);
    if (timedOut) {
      process.stderr.write('Warning: no stdin data received in 3s, proceeding without it. ' + 'If piping from a slow command, redirect stdin explicitly: < /dev/null to skip, or wait longer.\n');
    }
    return [prompt, data].filter(Boolean).join('\n');
  }
  return prompt;
}
async function run(): Promise<CommanderCommand> {

  // Create help config that sorts options by long option name.
  // Commander supports compareOptions at runtime but @commander-js/extra-typings
  // doesn't include it in the type definitions, so we use Object.assign to add it.
  function createSortedHelpConfig(): {
    sortSubcommands: true;
    sortOptions: true;
  } {
    const getOptionSortKey = (opt: Option): string => opt.long?.replace(/^--/, '') ?? opt.short?.replace(/^-/, '') ?? '';
    return Object.assign({
      sortSubcommands: true,
      sortOptions: true
    } as const, {
      compareOptions: (a: Option, b: Option) => getOptionSortKey(a).localeCompare(getOptionSortKey(b))
    });
  }
  const program = new CommanderCommand().configureHelp(createSortedHelpConfig()).enablePositionalOptions();

  // Use preAction hook to run initialization only when executing a command,
  // not when displaying help. This avoids the need for env variable signaling.
  program.hook('preAction', async thisCommand => {
        await init();
  
    // process.title on Windows sets the console title directly; on POSIX,
    // terminal shell integration may mirror the process name to the tab.
    // After init() so settings.json env can also gate this (gh-4765).
    if (!isEnvTruthy(process.env.CLAUDE_CODE_DISABLE_TERMINAL_TITLE)) {
      process.title = 'ummaya';
    }

    // Attach logging sinks so subcommand handlers can use logEvent/logError.
    // Before PR #11106 logEvent dispatched directly; after, events queue until
    // a sink attaches. setup() attaches sinks for the default command, but
    // subcommands (doctor, mcp, plugin, auth) never call setup() and would
    // silently drop events on process.exit(). Both inits are idempotent.
    const {
      initSinks
    } = await import('./utils/sinks.js');
    initSinks();
  
    // gh-33508: --plugin-dir is a top-level program option. The default
    // action reads it from its own options destructure, but subcommands
    // (plugin list, plugin install, mcp *) have their own actions and
    // never see it. Wire it up here so getInlinePlugins() works everywhere.
    // thisCommand.opts() is typed {} here because this hook is attached
    // before .option('--plugin-dir', ...) in the chain — extra-typings
    // builds the type as options are added. Narrow with a runtime guard;
    // the collect accumulator + [] default guarantee string[] in practice.
    const pluginDir = thisCommand.getOptionValue('pluginDir');
    if (Array.isArray(pluginDir) && pluginDir.length > 0 && pluginDir.every(p => typeof p === 'string')) {
      setInlinePlugins(pluginDir);
      clearPluginCache('preAction: --plugin-dir inline plugins');
    }
    runMigrations();
  
  
    });
  program.name('ummaya').description(`UMMAYA - starts an interactive session by default, use -p/--print for non-interactive output`).argument('[prompt]', 'Your prompt', String)
  // Subcommands inherit helpOption via commander's copyInheritedSettings —
  // setting it once here covers mcp, plugin, auth, and all other subcommands.
  .helpOption('-h, --help', 'Display help for command').option('-d, --debug [filter]', 'Enable debug mode with optional category filtering (e.g., "api,hooks" or "!1p,!file")', (_value: string | true) => {
    // If value is provided, it will be the filter string
    // If not provided but flag is present, value will be true
    // The actual filtering is handled in debug.ts by parsing process.argv
    return true;
  }).addOption(new Option('--debug-to-stderr', 'Enable debug mode (to stderr)').hideHelp()).option('--debug-file <path>', 'Write debug logs to a specific file path (implicitly enables debug mode)', () => true).option('--verbose', 'Override verbose mode setting from config', () => true).option('-p, --print', 'Print response and exit (useful for pipes). Note: The workspace trust dialog is skipped when UMMAYA is run with the -p mode. Only use this flag in directories you trust.', () => true).option('--bare', 'Minimal mode: skip hooks, LSP, plugin sync, attribution, auto-memory, background prefetches, keychain reads, and project-memory auto-discovery. Enables minimal compatibility mode. FriendliAI auth still requires an active /login session. Skills still resolve via /skill-name. Explicitly provide context via: --system-prompt[-file], --append-system-prompt[-file], --add-dir, --mcp-config, --settings, --agents, --plugin-dir.', () => true).addOption(new Option('--init', 'Run Setup hooks with init trigger, then continue').hideHelp()).addOption(new Option('--init-only', 'Run Setup and SessionStart:startup hooks, then exit').hideHelp()).addOption(new Option('--maintenance', 'Run Setup hooks with maintenance trigger, then continue').hideHelp()).addOption(new Option('--output-format <format>', 'Output format (only works with --print): "text" (default), "json" (single result), or "stream-json" (realtime streaming)').choices(['text', 'json', 'stream-json'])).addOption(new Option('--json-schema <schema>', 'JSON Schema for structured output validation. ' + 'Example: {"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}').argParser(String)).option('--include-hook-events', 'Include all hook lifecycle events in the output stream (only works with --output-format=stream-json)', () => true).option('--include-partial-messages', 'Include partial message chunks as they arrive (only works with --print and --output-format=stream-json)', () => true).addOption(new Option('--input-format <format>', 'Input format (only works with --print): "text" (default), or "stream-json" (realtime streaming input)').choices(['text', 'stream-json'])).option('--mcp-debug', '[DEPRECATED. Use --debug instead] Enable MCP debug mode (shows MCP server errors)', () => true).option('--dangerously-skip-permissions', 'Bypass all permission checks. Recommended only for sandboxes with no internet access.', () => true).option('--allow-dangerously-skip-permissions', 'Enable bypassing all permission checks as an option, without it being enabled by default. Recommended only for sandboxes with no internet access.', () => true).addOption(new Option('--thinking <mode>', 'Thinking mode: enabled (equivalent to adaptive), disabled').choices(['enabled', 'adaptive', 'disabled']).hideHelp()).addOption(new Option('--max-thinking-tokens <tokens>', '[DEPRECATED. Use --thinking instead for newer models] Maximum number of thinking tokens (only works with --print)').argParser(Number).hideHelp()).addOption(new Option('--max-turns <turns>', 'Maximum number of agentic turns in non-interactive mode. This will early exit the conversation after the specified number of turns. (only works with --print)').argParser(Number).hideHelp()).addOption(new Option('--max-budget-usd <amount>', 'Maximum dollar amount to spend on API calls (only works with --print)').argParser(value => {
    const amount = Number(value);
    if (isNaN(amount) || amount <= 0) {
      throw new Error('--max-budget-usd must be a positive number greater than 0');
    }
    return amount;
  })).addOption(new Option('--task-budget <tokens>', 'API-side task budget in tokens (output_config.task_budget)').argParser(value => {
    const tokens = Number(value);
    if (isNaN(tokens) || tokens <= 0 || !Number.isInteger(tokens)) {
      throw new Error('--task-budget must be a positive integer');
    }
    return tokens;
  }).hideHelp()).option('--replay-user-messages', 'Re-emit user messages from stdin back on stdout for acknowledgment (only works with --input-format=stream-json and --output-format=stream-json)', () => true).addOption(new Option('--enable-auth-status', 'Enable auth status messages in SDK mode').default(false).hideHelp()).option('--allowedTools, --allowed-tools <tools...>', 'Comma or space-separated list of tool names to allow (e.g. "Bash(git:*) Edit")').option('--tools <tools...>', 'Specify the list of available tools from the built-in set. Use "" to disable all tools, "default" to use all tools, or specify tool names (e.g. "Bash,Edit,Read").').option('--disallowedTools, --disallowed-tools <tools...>', 'Comma or space-separated list of tool names to deny (e.g. "Bash(git:*) Edit")').option('--mcp-config <configs...>', 'Load MCP servers from JSON files or strings (space-separated)').addOption(new Option('--permission-prompt-tool <tool>', 'MCP tool to use for permission prompts (only works with --print)').argParser(String).hideHelp()).addOption(new Option('--system-prompt <prompt>', 'System prompt to use for the session').argParser(String)).addOption(new Option('--system-prompt-file <file>', 'Read system prompt from a file').argParser(String).hideHelp()).addOption(new Option('--append-system-prompt <prompt>', 'Append a system prompt to the default system prompt').argParser(String)).addOption(new Option('--append-system-prompt-file <file>', 'Read system prompt from a file and append to the default system prompt').argParser(String).hideHelp()).addOption(new Option('--permission-mode <mode>', 'Permission mode to use for the session').argParser(String).choices(PERMISSION_MODES)).option('-c, --continue', 'Continue the most recent conversation in the current directory', () => true).option('-r, --resume [value]', 'Resume a conversation by session ID, or open interactive picker with optional search term', value => value || true).option('--fork-session', 'When resuming, create a new session ID instead of reusing the original (use with --resume or --continue)', () => true).addOption(new Option('--prefill <text>', 'Pre-fill the prompt input with text without submitting it').hideHelp()).addOption(new Option('--deep-link-origin', 'Signal that this session was launched from a deep link').hideHelp()).addOption(new Option('--deep-link-repo <slug>', 'Repo slug the deep link ?repo= parameter resolved to the current cwd').hideHelp()).addOption(new Option('--deep-link-last-fetch <ms>', 'FETCH_HEAD mtime in epoch ms, precomputed by the deep link trampoline').argParser(v => {
    const n = Number(v);
    return Number.isFinite(n) ? n : undefined;
  }).hideHelp()).option('--from-pr [value]', 'Resume a session linked to a PR by PR number/URL, or open interactive picker with optional search term', value => value || true).option('--no-session-persistence', 'Disable session persistence - sessions will not be saved to disk and cannot be resumed (only works with --print)').addOption(new Option('--resume-session-at <message id>', 'When resuming, only messages up to and including the assistant message with <message.id> (use with --resume in print mode)').argParser(String).hideHelp()).addOption(new Option('--rewind-files <user-message-id>', 'Restore files to state at the specified user message and exit (requires --resume)').hideHelp())
  // @[MODEL LAUNCH]: Update the example model ID in the --model help text.
  .option('--model <model>', `Model for the current session. Defaults to UMMAYA's configured FriendliAI K-EXAONE model.`).addOption(new Option('--effort <level>', `Effort level for the current session (low, medium, high, max)`).argParser((rawValue: string) => {
    const value = rawValue.toLowerCase();
    const allowed = ['low', 'medium', 'high', 'max'];
    if (!allowed.includes(value)) {
      throw new InvalidArgumentError(`It must be one of: ${allowed.join(', ')}`);
    }
    return value;
  })).option('--agent <agent>', `Agent for the current session. Overrides the 'agent' setting.`).option('--betas <betas...>', 'Beta headers to include in API requests (API key users only)').option('--fallback-model <model>', 'Enable automatic fallback to specified model when default model is overloaded (only works with --print)').addOption(new Option('--workload <tag>', 'Workload tag for billing-header attribution (cc_workload). Process-scoped; set by SDK daemon callers that spawn subprocesses for cron work. (only works with --print)').hideHelp()).option('--settings <file-or-json>', 'Path to a settings JSON file or a JSON string to load additional settings from').option('--add-dir <directories...>', 'Additional directories to allow tool access to').option('--ide', 'Automatically connect to IDE on startup if exactly one valid IDE is available', () => true).option('--strict-mcp-config', 'Only use MCP servers from --mcp-config, ignoring all other MCP configurations', () => true).option('--session-id <uuid>', 'Use a specific session ID for the conversation (must be a valid UUID)').option('-n, --name <name>', 'Set a display name for this session (shown in /resume and terminal title)').option('--agents <json>', 'JSON object defining custom agents (e.g. \'{"reviewer": {"description": "Reviews code", "prompt": "You are a code reviewer"}}\')').option('--setting-sources <sources>', 'Comma-separated list of setting sources to load (user, project, local).')
  // gh-33508: <paths...> (variadic) consumed everything until the next
  // --flag. `claude --plugin-dir /path mcp add --transport http` swallowed
  // `mcp` and `add` as paths, then choked on --transport as an unknown
  // top-level option. Single-value + collect accumulator means each
  // --plugin-dir takes exactly one arg; repeat the flag for multiple dirs.
  .option('--plugin-dir <path>', 'Load plugins from a directory for this session only (repeatable: --plugin-dir A --plugin-dir B)', (val: string, prev: string[]) => [...prev, val], [] as string[]).option('--disable-slash-commands', 'Disable all skills', () => true).option('--chrome', 'Enable browser integration').option('--no-chrome', 'Disable browser integration').option('--file <specs...>', 'File resources to download at startup. Format: file_id:relative_path (e.g., --file file_abc:doc.txt file_def:img.png)').action(async (prompt, options) => {
  
    // --bare = one-switch minimal mode. Sets SIMPLE so all the existing
    // gates fire (CLAUDE.md, skills, hooks inside executeHooks, agent
    // dir-walk). Must be set before setup() / any of the gated work runs.
    if ((options as {
      bare?: boolean;
    }).bare) {
      process.env.CLAUDE_CODE_SIMPLE = '1';
    }

    // Ignore "code" as a prompt - treat it the same as no prompt
    if (prompt === 'code') {
      // biome-ignore lint/suspicious/noConsole:: intentional console output
      console.warn(chalk.yellow('Tip: You can launch UMMAYA with just `ummaya`'));
      prompt = undefined;
    }


    // Assistant mode: when .claude/settings.json has assistant: true AND
    // the tengu_kairos GrowthBook gate is on, force brief on. Permission
    // mode is left to the user — settings defaultMode or --permission-mode
    // apply as normal. REPL-typed messages already default to 'next'
    // priority (messageQueueManager.enqueue) so they drain mid-turn between
    // tool calls. SendUserMessage (BriefTool) is enabled via the brief env
    // var. SleepTool stays disabled (its isEnabled() gates on proactive).
    // kairosEnabled is computed once here and reused at the
    // getAssistantSystemPromptAddendum() call site further down.
    //
    // Trust gate: .claude/settings.json is attacker-controllable in an
    // untrusted clone. We run ~1000 lines before showSetupScreens() shows
    // the trust dialog, and by then we've already appended
    // .claude/agents/assistant.md to the system prompt. Refuse to activate
    // until the directory has been explicitly trusted.
    const kairosEnabled = false;
    const {
      debug = false,
      debugToStderr = false,
      dangerouslySkipPermissions,
      allowDangerouslySkipPermissions = false,
      tools: baseTools = [],
      allowedTools = [],
      disallowedTools = [],
      mcpConfig = [],
      permissionMode: permissionModeCli,
      addDir = [],
      fallbackModel,
      betas = [],
      ide = false,
      sessionId,
      includeHookEvents,
      includePartialMessages
    } = options;
    if (options.prefill) {
      seedEarlyInput(options.prefill);
    }

    // UMMAYA: filesApi deleted — file download via --file flag is unsupported.
    const agentsJson = options.agents;
    const agentCli = options.agent;

    // NOTE: LSP manager initialization is intentionally deferred until after
    // the trust dialog is accepted. This prevents plugin LSP servers from
    // executing code in untrusted directories before user consent.

    // Extract these separately so they can be modified if needed
    let outputFormat = options.outputFormat;
    let inputFormat = options.inputFormat;
    let verbose = options.verbose ?? getGlobalConfig().verbose;
    let print = options.print;
    const init = options.init ?? false;
    const initOnly = options.initOnly ?? false;
    const maintenance = options.maintenance ?? false;

    // Extract disable slash commands flag
    const disableSlashCommands = options.disableSlashCommands || false;


    // Extract worktree option
    // worktree can be true (flag without value) or a string (custom name or PR reference)
    const worktreeOption = isWorktreeModeEnabled() ? (options as {
      worktree?: boolean | string;
    }).worktree : undefined;
    let worktreeName = typeof worktreeOption === 'string' ? worktreeOption : undefined;
    const worktreeEnabled = worktreeOption !== undefined;

    // Check if worktree name is a PR reference (#N or GitHub PR URL)
    let worktreePRNumber: number | undefined;
    if (worktreeName) {
      const prNum = parsePRReference(worktreeName);
      if (prNum !== null) {
        worktreePRNumber = prNum;
        worktreeName = undefined; // slug will be generated in setup()
      }
    }

    // Extract tmux option (requires --worktree)
    const tmuxEnabled = isWorktreeModeEnabled() && (options as {
      tmux?: boolean;
    }).tmux === true;

    // Validate tmux option
    if (tmuxEnabled) {
      if (!worktreeEnabled) {
        process.stderr.write(chalk.red('Error: --tmux requires --worktree\n'));
        process.exit(1);
      }
      if (getPlatform() === 'windows') {
        process.stderr.write(chalk.red('Error: --tmux is not supported on Windows\n'));
        process.exit(1);
      }
      if (!(await isTmuxAvailable())) {
        process.stderr.write(chalk.red(`Error: tmux is not installed.\n${getTmuxInstallInstructions()}\n`));
        process.exit(1);
      }
    }

    // Extract teammate options (for tmux-spawned agents)
    // Declared outside the if block so it's accessible later for system prompt addendum
    let storedTeammateOpts: TeammateOptions | undefined;
    if (isAgentSwarmsEnabled()) {
      // Extract agent identity options (for tmux-spawned agents)
      // These replace the CLAUDE_CODE_* environment variables
      const teammateOpts = extractTeammateOptions(options);
      storedTeammateOpts = teammateOpts;

      // If any teammate identity option is provided, all three required ones must be present
      const hasAnyTeammateOpt = teammateOpts.agentId || teammateOpts.agentName || teammateOpts.teamName;
      const hasAllRequiredTeammateOpts = teammateOpts.agentId && teammateOpts.agentName && teammateOpts.teamName;
      if (hasAnyTeammateOpt && !hasAllRequiredTeammateOpts) {
        process.stderr.write(chalk.red('Error: --agent-id, --agent-name, and --team-name must all be provided together\n'));
        process.exit(1);
      }

      // If teammate identity is provided via CLI, set up dynamicTeamContext
      if (teammateOpts.agentId && teammateOpts.agentName && teammateOpts.teamName) {
        getTeammateUtils().setDynamicTeamContext?.({
          agentId: teammateOpts.agentId,
          agentName: teammateOpts.agentName,
          teamName: teammateOpts.teamName,
          color: teammateOpts.agentColor,
          planModeRequired: teammateOpts.planModeRequired ?? false,
          parentSessionId: teammateOpts.parentSessionId
        });
      }

      // Set teammate mode CLI override if provided
      // This must be done before setup() captures the snapshot
      if (teammateOpts.teammateMode) {
        getTeammateModeSnapshot().setCliTeammateModeOverride?.(teammateOpts.teammateMode);
      }
    }

    // Extract remote sdk options
    const sdkUrl = (options as {
      sdkUrl?: string;
    }).sdkUrl ?? undefined;

    // Allow env var to enable partial messages (used by sandbox gateway for baku)
    const effectiveIncludePartialMessages = includePartialMessages || isEnvTruthy(process.env.CLAUDE_CODE_INCLUDE_PARTIAL_MESSAGES);

    // Enable all hook event types when explicitly requested via SDK option
    // or when running in CLAUDE_CODE_REMOTE mode (CCR needs them).
    // Without this, only SessionStart and Setup events are emitted.
    if (includeHookEvents || isEnvTruthy(process.env.CLAUDE_CODE_REMOTE)) {
      setAllHookEventsEnabled(true);
    }

    // Auto-set input/output formats, verbose mode, and print mode when SDK URL is provided
    if (sdkUrl) {
      // If SDK URL is provided, automatically use stream-json formats unless explicitly set
      if (!inputFormat) {
        inputFormat = 'stream-json';
      }
      if (!outputFormat) {
        outputFormat = 'stream-json';
      }
      // Auto-enable verbose mode unless explicitly disabled or already set
      if (options.verbose === undefined) {
        verbose = true;
      }
      // Auto-enable print mode unless explicitly disabled
      if (!options.print) {
        print = true;
      }
    }

    // Extract teleport option
    const teleport = (options as {
      teleport?: string | true;
    }).teleport ?? null;

    // Extract remote option (can be true if no description provided, or a string)
    const remoteOption = (options as {
      remote?: string | true;
    }).remote;
    const remote = remoteOption === true ? '' : remoteOption ?? null;

    // Extract --remote-control / --rc flag (enable bridge in interactive session)
    const remoteControlOption = (options as {
      remoteControl?: string | true;
    }).remoteControl ?? (options as {
      rc?: string | true;
    }).rc;
    // Actual bridge check is deferred to after showSetupScreens() so that
    // trust is established and GrowthBook has auth headers.
    let remoteControl = false;
    const remoteControlName = typeof remoteControlOption === 'string' && remoteControlOption.length > 0 ? remoteControlOption : undefined;

    // Validate session ID if provided
    if (sessionId) {
      // Check for conflicting flags
      // --session-id can be used with --continue or --resume when --fork-session is also provided
      // (to specify a custom ID for the forked session)
      if ((options.continue || options.resume) && !options.forkSession) {
        process.stderr.write(chalk.red('Error: --session-id can only be used with --continue or --resume if --fork-session is also specified.\n'));
        process.exit(1);
      }

      // When --sdk-url is provided (bridge/remote mode), the session ID is a
      // server-assigned tagged ID (e.g. "session_local_01...") rather than a
      // UUID. Skip UUID validation and local existence checks in that case.
      if (!sdkUrl) {
        const validatedSessionId = validateUuid(sessionId);
        if (!validatedSessionId) {
          process.stderr.write(chalk.red('Error: Invalid session ID. Must be a valid UUID.\n'));
          process.exit(1);
        }

        // Check if session ID already exists
        if (sessionIdExists(validatedSessionId)) {
          process.stderr.write(chalk.red(`Error: Session ID ${validatedSessionId} is already in use.\n`));
          process.exit(1);
        }
      }
    }

    // UMMAYA: --file flag / session file download removed (Anthropic Files API dead code).

    // Get isNonInteractiveSession from state (was set before init())
    const isNonInteractiveSession = getIsNonInteractiveSession();

    // Validate that fallback model is different from main model
    if (fallbackModel && options.model && fallbackModel === options.model) {
      process.stderr.write(chalk.red('Error: Fallback model cannot be the same as the main model. Please specify a different model for --fallback-model.\n'));
      process.exit(1);
    }

    // Handle system prompt options
    let systemPrompt = options.systemPrompt;
    if (options.systemPromptFile) {
      if (options.systemPrompt) {
        process.stderr.write(chalk.red('Error: Cannot use both --system-prompt and --system-prompt-file. Please use only one.\n'));
        process.exit(1);
      }
      try {
        const filePath = resolve(options.systemPromptFile);
        systemPrompt = readFileSync(filePath, 'utf8');
      } catch (error) {
        const code = getErrnoCode(error);
        if (code === 'ENOENT') {
          process.stderr.write(chalk.red(`Error: System prompt file not found: ${resolve(options.systemPromptFile)}\n`));
          process.exit(1);
        }
        process.stderr.write(chalk.red(`Error reading system prompt file: ${errorMessage(error)}\n`));
        process.exit(1);
      }
    }

    // Handle append system prompt options
    let appendSystemPrompt = options.appendSystemPrompt;
    if (options.appendSystemPromptFile) {
      if (options.appendSystemPrompt) {
        process.stderr.write(chalk.red('Error: Cannot use both --append-system-prompt and --append-system-prompt-file. Please use only one.\n'));
        process.exit(1);
      }
      try {
        const filePath = resolve(options.appendSystemPromptFile);
        appendSystemPrompt = readFileSync(filePath, 'utf8');
      } catch (error) {
        const code = getErrnoCode(error);
        if (code === 'ENOENT') {
          process.stderr.write(chalk.red(`Error: Append system prompt file not found: ${resolve(options.appendSystemPromptFile)}\n`));
          process.exit(1);
        }
        process.stderr.write(chalk.red(`Error reading append system prompt file: ${errorMessage(error)}\n`));
        process.exit(1);
      }
    }

    // Add teammate-specific system prompt addendum for tmux teammates
    if (isAgentSwarmsEnabled() && storedTeammateOpts?.agentId && storedTeammateOpts?.agentName && storedTeammateOpts?.teamName) {
      const addendum = getTeammatePromptAddendum().TEAMMATE_SYSTEM_PROMPT_ADDENDUM;
      appendSystemPrompt = appendSystemPrompt ? `${appendSystemPrompt}\n\n${addendum}` : addendum;
    }
    const {
      mode: permissionMode,
      notification: permissionModeNotification
    } = initialPermissionModeFromCLI({
      permissionModeCli,
      dangerouslySkipPermissions
    });
    process.env.UMMAYA_PERMISSION_MODE = permissionMode;

    // Store session bypass permissions mode for trust dialog check
    setSessionBypassPermissionsMode(permissionMode === 'bypassPermissions');

    // Parse the MCP config files/strings if provided
    let dynamicMcpConfig: Record<string, ScopedMcpServerConfig> = {};
    if (mcpConfig && mcpConfig.length > 0) {
      // Process mcpConfig array
      const processedConfigs = mcpConfig.map(config => config.trim()).filter(config => config.length > 0);
      let allConfigs: Record<string, McpServerConfig> = {};
      const allErrors: ValidationError[] = [];
      for (const configItem of processedConfigs) {
        let configs: Record<string, McpServerConfig> | null = null;
        let errors: ValidationError[] = [];

        // First try to parse as JSON string
        const parsedJson = safeParseJSON(configItem);
        if (parsedJson) {
          const result = parseMcpConfig({
            configObject: parsedJson,
            filePath: 'command line',
            expandVars: true,
            scope: 'dynamic'
          });
          if (result.config) {
            configs = result.config.mcpServers;
          } else {
            errors = result.errors;
          }
        } else {
          // Try as file path
          const configPath = resolve(configItem);
          const result = parseMcpConfigFromFilePath({
            filePath: configPath,
            expandVars: true,
            scope: 'dynamic'
          });
          if (result.config) {
            configs = result.config.mcpServers;
          } else {
            errors = result.errors;
          }
        }
        if (errors.length > 0) {
          allErrors.push(...errors);
        } else if (configs) {
          // Merge configs, later ones override earlier ones
          allConfigs = {
            ...allConfigs,
            ...configs
          };
        }
      }
      if (allErrors.length > 0) {
        const formattedErrors = allErrors.map(err => `${err.path ? err.path + ': ' : ''}${err.message}`).join('\n');
        logForDebugging(`--mcp-config validation failed (${allErrors.length} errors): ${formattedErrors}`, {
          level: 'error'
        });
        process.stderr.write(`Error: Invalid MCP configuration:\n${formattedErrors}\n`);
        process.exit(1);
      }
      if (Object.keys(allConfigs).length > 0) {
        // SDK hosts (Nest/Desktop) own their server naming and may reuse
        // built-in names — skip reserved-name checks for type:'sdk'.
        const nonSdkConfigNames = Object.entries(allConfigs).filter(([, config]) => config.type !== 'sdk').map(([name]) => name);
        let reservedNameError: string | null = null;
        if (nonSdkConfigNames.some(isClaudeInChromeMCPServer)) {
          reservedNameError = `Invalid MCP configuration: "${CLAUDE_IN_CHROME_MCP_SERVER_NAME}" is a reserved MCP name.`;
        }
        if (reservedNameError) {
          // stderr+exit(1) — a throw here becomes a silent unhandled
          // rejection in stream-json mode (void main() in cli.tsx).
          process.stderr.write(`Error: ${reservedNameError}\n`);
          process.exit(1);
        }

        // Add dynamic scope to all configs. type:'sdk' entries pass through
        // unchanged — they're extracted into sdkMcpConfigs downstream and
        // passed to print.ts. The Python SDK relies on this path (it doesn't
        // send sdkMcpServers in the initialize message). Dropping them here
        // broke Coworker (inc-5122). The policy filter below already exempts
        // type:'sdk', and the entries are inert without an SDK transport on
        // stdin, so there's no bypass risk from letting them through.
        const scopedConfigs = mapValues(allConfigs, config => ({
          ...config,
          scope: 'dynamic' as const
        }));

        // Enforce managed policy (allowedMcpServers / deniedMcpServers) on
        // --mcp-config servers. Without this, the CLI flag bypasses the
        // enterprise allowlist that user/project/local configs go through in
        // getClaudeCodeMcpConfigs — callers spread dynamicMcpConfig back on
        // top of filtered results. Filter here at the source so all
        // downstream consumers see the policy-filtered set.
        const {
          allowed,
          blocked
        } = filterMcpServersByPolicy(scopedConfigs);
        if (blocked.length > 0) {
          process.stderr.write(`Warning: MCP ${plural(blocked.length, 'server')} blocked by enterprise policy: ${blocked.join(', ')}\n`);
        }
        dynamicMcpConfig = {
          ...dynamicMcpConfig,
          ...allowed
        };
      }
    }

    // Extract UMMAYA in Chrome option and enforce browser session access (unless user is ant)
    const chromeOpts = options as {
      chrome?: boolean;
    };
    // Store the explicit CLI flag so teammates can inherit it
    setChromeFlagOverride(chromeOpts.chrome);
    const enableClaudeInChrome = shouldEnableClaudeInChrome(chromeOpts.chrome);
    const autoEnableClaudeInChrome = !enableClaudeInChrome && shouldAutoEnableClaudeInChrome();
    if (enableClaudeInChrome) {
      const platform = getPlatform();
      try {
        const {
          mcpConfig: chromeMcpConfig,
          allowedTools: chromeMcpTools,
          systemPrompt: chromeSystemPrompt
        } = setupClaudeInChrome();
        dynamicMcpConfig = {
          ...dynamicMcpConfig,
          ...chromeMcpConfig
        };
        allowedTools.push(...chromeMcpTools);
        if (chromeSystemPrompt) {
          appendSystemPrompt = appendSystemPrompt ? `${chromeSystemPrompt}\n\n${appendSystemPrompt}` : chromeSystemPrompt;
        }
      } catch (error) {
        logForDebugging(`[UMMAYA in Chrome] Error: ${error}`);
        logError(error);
        // biome-ignore lint/suspicious/noConsole:: intentional console output
        console.error(`Error: Failed to run with UMMAYA in Chrome.`);
        process.exit(1);
      }
    } else if (autoEnableClaudeInChrome) {
      try {
        const {
          mcpConfig: chromeMcpConfig
        } = setupClaudeInChrome();
        dynamicMcpConfig = {
          ...dynamicMcpConfig,
          ...chromeMcpConfig
        };
        const hint = CLAUDE_IN_CHROME_SKILL_HINT;
        appendSystemPrompt = appendSystemPrompt ? `${appendSystemPrompt}\n\n${hint}` : hint;
      } catch (error) {
        // Silently skip any errors for the auto-enable
        logForDebugging(`[UMMAYA in Chrome] Error (auto-enable): ${error}`);
      }
    }

    // Extract strict MCP config flag
    const strictMcpConfig = options.strictMcpConfig || false;

    // Check if enterprise MCP configuration exists. When it does, only allow dynamic MCP
    // configs that contain special server types (sdk)
    if (doesEnterpriseMcpConfigExist()) {
      if (strictMcpConfig) {
        process.stderr.write(chalk.red('You cannot use --strict-mcp-config when an enterprise MCP config is present'));
        process.exit(1);
      }

      // For --mcp-config, allow if all servers are internal types (sdk)
      if (dynamicMcpConfig && !areMcpConfigsAllowedWithEnterpriseMcpConfig(dynamicMcpConfig)) {
        process.stderr.write(chalk.red('You cannot dynamically configure MCP servers when an enterprise MCP config is present'));
        process.exit(1);
      }
    }

    // chicago MCP: guarded Computer Use (app allowlist + frontmost gate +
    // SCContentFilter screenshots). Ant-only, GrowthBook-gated — failures
    // are silent (this is dogfooding). Platform + interactive checks inline
    // so non-macOS / print-mode ants skip the heavy @ant/computer-use-mcp
    // import entirely. gates.js is light (type-only package import).
    //
    // Placed AFTER the enterprise-MCP-config check: that check rejects any
    // dynamicMcpConfig entry with `type !== 'sdk'`, and our config is
    // `type: 'stdio'`. An enterprise-config ant with the GB gate on would
    // otherwise process.exit(1). Chrome has the same latent issue but has
    // shipped without incident; chicago places itself correctly.

    // Store additional directories for CLAUDE.md loading (controlled by env var)
    setAdditionalDirectoriesForClaudeMd(addDir);


    // SDK opt-in for SendUserMessage via --tools. All sessions require
    // explicit opt-in; listing it in --tools signals intent. Runs BEFORE
    // initializeToolPermissionContext so getToolsForDefaultPreset() sees
    // the tool as enabled when computing the base-tools disallow filter.
    // Conditional require avoids leaking the tool-name string into
    // external builds.

    // This await replaces blocking existsSync/statSync calls that were already in
    // the startup path. Wall-clock time is unchanged; we just yield to the event
    // loop during the fs I/O instead of blocking it. See #19661.
    const initResult = await initializeToolPermissionContext({
      allowedToolsCli: allowedTools,
      disallowedToolsCli: disallowedTools,
      baseToolsCli: baseTools,
      permissionMode,
      allowDangerouslySkipPermissions,
      addDirs: addDir
    });
    let toolPermissionContext = initResult.toolPermissionContext;
    const {
      warnings,
      dangerousPermissions,
      overlyBroadBashPermissions
    } = initResult;


    // Print any warnings from initialization
    warnings.forEach(warning => {
      // biome-ignore lint/suspicious/noConsole:: intentional console output
      console.error(warning);
    });
    void assertMinVersion();

    // UMMAYA connector config fetch: -p mode only (interactive uses useManageMCPConnections
    // two-phase loading). Kicked off here to overlap with setup(); awaited
    // before runHeadless so single-turn -p sees connectors. Skipped under
    // enterprise/strict MCP to preserve policy boundaries.
    const claudeaiConfigPromise: Promise<Record<string, ScopedMcpServerConfig>> = isNonInteractiveSession && !strictMcpConfig && !doesEnterpriseMcpConfigExist() &&
    // --bare / SIMPLE: skip managed connector proxy servers (datadog, Gmail,
    // Slack, BigQuery, PubMed — 6-14s each to connect). Scripted calls
    // that need MCP pass --mcp-config explicitly.
    !isBareMode() ? fetchClaudeAIMcpConfigsIfEligible().then(configs => {
      const {
        allowed,
        blocked
      } = filterMcpServersByPolicy(configs);
      if (blocked.length > 0) {
        process.stderr.write(`Warning: UMMAYA MCP ${plural(blocked.length, 'server')} blocked by enterprise policy: ${blocked.join(', ')}\n`);
      }
      return allowed;
    }) : Promise.resolve({});

    // Kick off MCP config loading early (safe - just reads files, no execution).
    // Both interactive and -p use getClaudeCodeMcpConfigs (local file reads only).
    // The local promise is awaited later (before prefetchAllMcpResources) to
    // overlap config I/O with setup(), commands loading, and trust dialog.
    logForDebugging('[STARTUP] Loading MCP configs...');
    const mcpConfigStart = Date.now();
    let mcpConfigResolvedMs: number | undefined;
    // --bare skips auto-discovered MCP (.mcp.json, user settings, plugins) —
    // only explicit --mcp-config works. dynamicMcpConfig is spread onto
    // allMcpConfigs downstream so it survives this skip.
    const mcpConfigPromise = (strictMcpConfig || isBareMode() ? Promise.resolve({
      servers: {} as Record<string, ScopedMcpServerConfig>
    }) : getClaudeCodeMcpConfigs(dynamicMcpConfig)).then(result => {
      mcpConfigResolvedMs = Date.now() - mcpConfigStart;
      return result;
    });

    // NOTE: We do NOT call prefetchAllMcpResources here - that's deferred until after trust dialog

    if (inputFormat && inputFormat !== 'text' && inputFormat !== 'stream-json') {
      // biome-ignore lint/suspicious/noConsole:: intentional console output
      console.error(`Error: Invalid input format "${inputFormat}".`);
      process.exit(1);
    }
    if (inputFormat === 'stream-json' && outputFormat !== 'stream-json') {
      // biome-ignore lint/suspicious/noConsole:: intentional console output
      console.error(`Error: --input-format=stream-json requires output-format=stream-json.`);
      process.exit(1);
    }

    // Validate sdkUrl is only used with appropriate formats (formats are auto-set above)
    if (sdkUrl) {
      if (inputFormat !== 'stream-json' || outputFormat !== 'stream-json') {
        // biome-ignore lint/suspicious/noConsole:: intentional console output
        console.error(`Error: --sdk-url requires both --input-format=stream-json and --output-format=stream-json.`);
        process.exit(1);
      }
    }

    // Validate replayUserMessages is only used with stream-json formats
    if (options.replayUserMessages) {
      if (inputFormat !== 'stream-json' || outputFormat !== 'stream-json') {
        // biome-ignore lint/suspicious/noConsole:: intentional console output
        console.error(`Error: --replay-user-messages requires both --input-format=stream-json and --output-format=stream-json.`);
        process.exit(1);
      }
    }

    // Validate includePartialMessages is only used with print mode and stream-json output
    if (effectiveIncludePartialMessages) {
      if (!isNonInteractiveSession || outputFormat !== 'stream-json') {
        writeToStderr(`Error: --include-partial-messages requires --print and --output-format=stream-json.`);
        process.exit(1);
      }
    }

    // Validate --no-session-persistence is only used with print mode
    if (options.sessionPersistence === false && !isNonInteractiveSession) {
      writeToStderr(`Error: --no-session-persistence can only be used with --print mode.`);
      process.exit(1);
    }
    const effectivePrompt = prompt || '';
    let inputPrompt = await getInputPrompt(effectivePrompt, (inputFormat ?? 'text') as 'text' | 'stream-json');
  
    // Activate proactive mode BEFORE getTools() so SleepTool.isEnabled()
    // (which returns isProactiveActive()) passes and Sleep is included.
    // The later REPL-path maybeActivateProactive() calls are idempotent.
    maybeActivateProactive(options);
    let tools = getTools(toolPermissionContext);

    // Epic γ #2294 · T019 — boot guard: verify 9-member contract on all primitives.
    // Runs once per process, synchronous, ≤200ms wall-clock (SC-002).
    {
      const guardResult = verifyBootRegistry(getAllBaseTools())
      if (!guardResult.ok) {
        console.error(guardResult.diagnostic)
        process.exit(1)
      }
    }

      let jsonSchema: ToolInputJSONSchema | undefined;
    if (isSyntheticOutputToolEnabled({
      isNonInteractiveSession
    }) && options.jsonSchema) {
      jsonSchema = jsonParse(options.jsonSchema) as ToolInputJSONSchema;
    }
    if (jsonSchema) {
      const syntheticOutputResult = createSyntheticOutputTool(jsonSchema);
      if ('tool' in syntheticOutputResult) {
        // Add SyntheticOutputTool to the tools array AFTER getTools() filtering.
        // This tool is excluded from normal filtering (see tools.ts) because it's
        // an implementation detail for structured output, not a user-controlled tool.
        tools = [...tools, syntheticOutputResult.tool];
      } else {
      }
    }

    // IMPORTANT: setup() must be called before any other code that depends on the cwd or worktree setup
      logForDebugging('[STARTUP] Running setup()...');
    const setupStart = Date.now();
    const {
      setup
    } = await import('./setup.js');
    // Parallelize setup() with commands+agents loading. setup()'s ~28ms is
    // mostly startUdsMessaging (socket bind, ~20ms) — not disk-bound, so it
    // doesn't contend with getCommands' file reads. Gated on !worktreeEnabled
    // since --worktree makes setup() process.chdir() (setup.ts:203), and
    // commands/agents need the post-chdir cwd.
    const preSetupCwd = getCwd();
    // Register bundled skills/plugins before kicking getCommands() — they're
    // pure in-memory array pushes (<1ms, zero I/O) that getBundledSkills()
    // reads synchronously. Previously ran inside setup() after ~20ms of
    // await points, so the parallel getCommands() memoized an empty list.
    if (process.env.CLAUDE_CODE_ENTRYPOINT !== 'local-agent') {
      initBuiltinPlugins();
      initBundledSkills();
    }
    // UDS_INBOX feature removed in Epic #1633 — CC wired this through the
    // Unix-domain inbox path, which UMMAYA does not use. Preserve the
    // `setup()` signature by passing `undefined`.
    const messagingSocketPath: string | undefined = undefined;
    const setupPromise = setup(preSetupCwd, permissionMode, allowDangerouslySkipPermissions, worktreeEnabled, worktreeName, tmuxEnabled, sessionId ? validateUuid(sessionId) : undefined, worktreePRNumber, messagingSocketPath);
    const commandsPromise = worktreeEnabled ? null : getCommands(preSetupCwd);
    const agentDefsPromise = worktreeEnabled ? null : getAgentDefinitionsWithOverrides(preSetupCwd);
    // Suppress transient unhandledRejection if these reject during the
    // ~28ms setupPromise await before Promise.all joins them below.
    commandsPromise?.catch(() => {});
    agentDefsPromise?.catch(() => {});
    await setupPromise;
    logForDebugging(`[STARTUP] setup() completed in ${Date.now() - setupStart}ms`);
  
    // Replay user messages into stream-json only when the socket was
    // explicitly requested. The auto-generated socket is passive — it
    // lets tools inject if they want to, but turning it on by default
    // shouldn't reshape stream-json for SDK consumers who never touch it.
    // Callers who inject and also want those injections visible in the
    // stream pass --messaging-socket-path explicitly (or --replay-user-messages).
    let effectiveReplayUserMessages = !!options.replayUserMessages;
    if (getIsNonInteractiveSession()) {
      // Apply full merged settings env now (including project-scoped
      // .claude/settings.json PATH/GIT_DIR/GIT_WORK_TREE) so gitExe() and
      // the git spawn below see it. Trust is implicit in -p mode; the
      // docstring at managedEnv.ts:96-97 says this applies "potentially
      // dangerous environment variables such as LD_PRELOAD, PATH" from all
      // sources. The later call in the isNonInteractiveSession block below
      // is idempotent (Object.assign, configureGlobalAgents ejects prior
      // interceptor) and picks up any plugin-contributed env after plugin
      // init. Project settings are already loaded here:
      // applySafeConfigEnvironmentVariables in init() called
      // getSettings_DEPRECATED at managedEnv.ts:86 which merges all enabled
      // sources including projectSettings/localSettings.
      applyConfigEnvironmentVariables();

      // Epic #2152 R5 — citizen chat-request path no longer reads
      // getSystemContext / getUserContext (cwd / gitStatus / CLAUDE.md are
      // developer-domain). The original CC warm-ups here pre-spawned git
      // subprocess + CLAUDE.md fs.readFile during the ~280ms config-init
      // window; both are dead under UMMAYA.
      // Kick ensureModelStringsInitialized now — for Bedrock this triggers
      // a 100-200ms profile fetch that was awaited serially at
      // print.ts:739. updateBedrockModelStrings is sequential()-wrapped so
      // the await joins the in-flight fetch. Non-Bedrock is a sync
      // early-return (zero-cost).
      void ensureModelStringsInitialized();
    }

    // Apply --name: cache-only so no orphan file is created before the
    // session ID is finalized by --continue/--resume. materializeSessionFile
    // persists it on the first user message; REPL's useTerminalTitle reads it
    // via getCurrentSessionTitle.
    const sessionNameArg = options.name?.trim();
    if (sessionNameArg) {
      cacheSessionTitle(sessionNameArg);
    }


    // Special case the default model with the null keyword
    // NOTE: Model resolution happens after setup() to ensure trust is established before AWS auth
    const userSpecifiedModel = options.model === 'default' ? getDefaultMainLoopModel() : options.model;
    const userSpecifiedFallbackModel = fallbackModel === 'default' ? getDefaultMainLoopModel() : fallbackModel;

    // Reuse preSetupCwd unless setup() chdir'd (worktreeEnabled). Saves a
    // getCwd() syscall in the common path.
    const currentCwd = worktreeEnabled ? getCwd() : preSetupCwd;
    logForDebugging('[STARTUP] Loading commands and agents...');
    const commandsStart = Date.now();
    // Join the promises kicked before setup() (or start fresh if
    // worktreeEnabled gated the early kick). Both memoized by cwd.
    const [commands, agentDefinitionsResult] = await Promise.all([commandsPromise ?? getCommands(currentCwd), agentDefsPromise ?? getAgentDefinitionsWithOverrides(currentCwd)]);
    logForDebugging(`[STARTUP] Commands and agents loaded in ${Date.now() - commandsStart}ms`);
  
    // Parse CLI agents if provided via --agents flag
    let cliAgents: typeof agentDefinitionsResult.activeAgents = [];
    if (agentsJson) {
      try {
        const parsedAgents = safeParseJSON(agentsJson);
        if (parsedAgents) {
          cliAgents = parseAgentsFromJson(parsedAgents, 'flagSettings');
        }
      } catch (error) {
        logError(error);
      }
    }

    // Merge CLI agents with existing ones
    const allAgents = [...agentDefinitionsResult.allAgents, ...cliAgents];
    const agentDefinitions = {
      ...agentDefinitionsResult,
      allAgents,
      activeAgents: getActiveAgentsFromList(allAgents)
    };

    // Look up main thread agent from CLI flag or settings
    const agentSetting = agentCli ?? getInitialSettings().agent;
    let mainThreadAgentDefinition: (typeof agentDefinitions.activeAgents)[number] | undefined;
    if (agentSetting) {
      mainThreadAgentDefinition = agentDefinitions.activeAgents.find(agent => agent.agentType === agentSetting);
      if (!mainThreadAgentDefinition) {
        logForDebugging(`Warning: agent "${agentSetting}" not found. ` + `Available agents: ${agentDefinitions.activeAgents.map(a => a.agentType).join(', ')}. ` + `Using default behavior.`);
      }
    }

    // Store the main thread agent type in bootstrap state so hooks can access it
    setMainThreadAgentType(mainThreadAgentDefinition?.agentType);


    // Persist agent setting to session transcript for resume view display and restoration
    if (mainThreadAgentDefinition?.agentType) {
      saveAgentSetting(mainThreadAgentDefinition.agentType);
    }

    // Apply the agent's system prompt for non-interactive sessions
    // (interactive mode uses buildEffectiveSystemPrompt instead)
    if (isNonInteractiveSession && mainThreadAgentDefinition && !systemPrompt && !isBuiltInAgent(mainThreadAgentDefinition)) {
      const agentSystemPrompt = mainThreadAgentDefinition.getSystemPrompt();
      if (agentSystemPrompt) {
        systemPrompt = agentSystemPrompt;
      }
    }

    // initialPrompt goes first so its slash command (if any) is processed;
    // user-provided text becomes trailing context.
    // Only concatenate when inputPrompt is a string. When it's an
    // AsyncIterable (SDK stream-json mode), template interpolation would
    // call .toString() producing "[object Object]". The AsyncIterable case
    // is handled in print.ts via structuredIO.prependUserMessage().
    if (mainThreadAgentDefinition?.initialPrompt) {
      if (typeof inputPrompt === 'string') {
        inputPrompt = inputPrompt ? `${mainThreadAgentDefinition.initialPrompt}\n\n${inputPrompt}` : mainThreadAgentDefinition.initialPrompt;
      } else if (!inputPrompt) {
        inputPrompt = mainThreadAgentDefinition.initialPrompt;
      }
    }

    // Compute effective model early so hooks can run in parallel with MCP
    // If user didn't specify a model but agent has one, use the agent's model
    let effectiveModel = userSpecifiedModel;
    if (!effectiveModel && mainThreadAgentDefinition?.model && mainThreadAgentDefinition.model !== 'inherit') {
      effectiveModel = parseUserSpecifiedModel(mainThreadAgentDefinition.model);
    }
    setMainLoopModelOverride(effectiveModel);

    // Compute resolved model for hooks (use user-specified model at launch)
    setInitialMainLoopModel(getUserSpecifiedModelSetting() || null);
    const initialMainLoopModel = getInitialMainLoopModel();
    const resolvedInitialModel = parseUserSpecifiedModel(initialMainLoopModel ?? getDefaultMainLoopModel());
    let advisorModel: string | undefined;
    if (isAdvisorEnabled()) {
      const advisorOption = canUserConfigureAdvisor() ? (options as {
        advisor?: string;
      }).advisor : undefined;
      if (advisorOption) {
        logForDebugging(`[AdvisorTool] --advisor ${advisorOption}`);
        if (!modelSupportsAdvisor(resolvedInitialModel)) {
          process.stderr.write(chalk.red(`Error: The model "${resolvedInitialModel}" does not support the advisor tool.\n`));
          process.exit(1);
        }
        const normalizedAdvisorModel = normalizeModelStringForAPI(parseUserSpecifiedModel(advisorOption));
        if (!isValidAdvisorModel(normalizedAdvisorModel)) {
          process.stderr.write(chalk.red(`Error: The model "${advisorOption}" cannot be used as an advisor.\n`));
          process.exit(1);
        }
      }
      advisorModel = canUserConfigureAdvisor() ? advisorOption ?? getInitialAdvisorSetting() : advisorOption;
      if (advisorModel) {
        logForDebugging(`[AdvisorTool] Advisor model: ${advisorModel}`);
      }
    }

    // For tmux teammates with --agent-type, append the custom agent's prompt
    if (isAgentSwarmsEnabled() && storedTeammateOpts?.agentId && storedTeammateOpts?.agentName && storedTeammateOpts?.teamName && storedTeammateOpts?.agentType) {
      // Look up the custom agent definition
      const customAgent = agentDefinitions.activeAgents.find(a => a.agentType === storedTeammateOpts.agentType);
      if (customAgent) {
        // Get the prompt - need to handle both built-in and custom agents
        let customPrompt: string | undefined;
        if (customAgent.source === 'built-in') {
          // Built-in agents have getSystemPrompt that takes toolUseContext
          // We can't access full toolUseContext here, so skip for now
          logForDebugging(`[teammate] Built-in agent ${storedTeammateOpts.agentType} - skipping custom prompt (not supported)`);
        } else {
          // Custom agents have getSystemPrompt that takes no args
          customPrompt = customAgent.getSystemPrompt();
        }

        // Log agent memory loaded event for tmux teammates
        if (customPrompt) {
          const customInstructions = `\n# Custom Agent Instructions\n${customPrompt}`;
          appendSystemPrompt = appendSystemPrompt ? `${appendSystemPrompt}\n\n${customInstructions}` : customInstructions;
        }
      } else {
        logForDebugging(`[teammate] Custom agent ${storedTeammateOpts.agentType} not found in available agents`);
      }
    }
    maybeActivateBrief(options);
    // defaultView: 'chat' is a persisted opt-in — check entitlement and set
    // userMsgOptIn so the tool + prompt section activate. Interactive-only:
    // defaultView is a display preference; SDK sessions have no display, and
    // the assistant installer writes defaultView:'chat' to settings.local.json
    // which would otherwise leak into --print sessions in the same directory.
    // Runs right after maybeActivateBrief() so all startup opt-in paths fire
    // BEFORE any isBriefEnabled() read below (proactive prompt's
    // briefVisibility). A persisted 'chat' after a GB kill-switch falls
    // through (entitlement fails).
    // Coordinator mode has its own system prompt and filters out Sleep, so
    // the generic proactive prompt would tell it to call a tool it can't
    // access and conflict with delegation instructions.

    // Ink root is only needed for interactive sessions — patchConsole in the
    // Ink constructor would swallow console output in headless mode.
    let root!: Root;
    let getFpsMetrics!: () => FpsMetrics | undefined;
    let stats!: StatsStore;

    // Show setup screens after commands are loaded
    if (!isNonInteractiveSession) {
      const ctx = getRenderContext(false);
      getFpsMetrics = ctx.getFpsMetrics;
      stats = ctx.stats;
      const {
        createRoot
      } = await import('./ink.js');
      root = await createRoot(ctx.renderOptions);

      logForDebugging('[STARTUP] Running showSetupScreens()...');
      const setupScreensStart = Date.now();
      // UMMAYA — `devChannels` was lost during CC sourcemap reconstruction
      // (Spec 1632 baseline drop). Upstream Claude Code uses it for the
      // ``--dangerously-load-development-channels`` private-plugin path,
      // which UMMAYA does not ship (Spec 1633 P1 dead-code clause). Pass
      // ``undefined`` so showSetupScreens routes to the citizen flow.
      const devChannels = undefined;
      const onboardingShown = await showSetupScreens(root, permissionMode, allowDangerouslySkipPermissions, commands, enableClaudeInChrome, devChannels);
      logForDebugging(`[STARTUP] showSetupScreens() completed in ${Date.now() - setupScreensStart}ms`);

      // Now that trust is established and GrowthBook has auth headers,
      // resolve the --remote-control / --rc entitlement gate.


      // Skip executing /login if we just completed onboarding for it
      if (onboardingShown && prompt?.trim().toLowerCase() === '/login') {
        prompt = '';
      }
      if (onboardingShown) {
        // Refresh auth-dependent services now that the user has logged in during onboarding.
        // Keep in sync with the post-login logic in src/commands/login.tsx
        // Clear any stale trusted device token then enroll for Remote Control.
        // Both self-gate on tengu_sessions_elevated_auth_enforcement internally
        // — enrollTrustedDevice() via checkGate_CACHED_OR_BLOCKING (awaits
        // the GrowthBook reinit above), clearTrustedDeviceToken() via the
        // sync cached check (acceptable since clear is idempotent).
      }

    }

    // If gracefulShutdown was initiated (e.g., user rejected trust dialog),
    // process.exitCode will be set. Skip all subsequent operations that could
    // trigger code execution before the process exits (e.g. we don't want apiKeyHelper
    // to run if trust was not established).
    if (process.exitCode !== undefined) {
      logForDebugging('Graceful shutdown initiated, skipping further initialization');
      return;
    }

    // Initialize LSP manager AFTER trust is established (or in non-interactive mode
    // where trust is implicit). This prevents plugin LSP servers from executing
    // code in untrusted directories before user consent.
    // Must be after inline plugins are set (if any) so --plugin-dir LSP servers are included.
    initializeLspServerManager();

    // Show settings validation errors after trust is established
    // MCP config errors don't block settings from loading, so exclude them
    if (!isNonInteractiveSession) {
      const {
        errors
      } = getSettingsWithErrors();
      const nonMcpErrors = errors.filter(e => !e.mcpErrorMetadata);
      if (nonMcpErrors.length > 0) {
        await launchInvalidSettingsDialog(root, {
          settingsErrors: nonMcpErrors,
          onExit: () => gracefulShutdownSync(1)
        });
      }
    }

    // Check quota status, fast mode, passes eligibility, and bootstrap data
    // after trust is established. These make API calls which could trigger
    // apiKeyHelper execution.
    // --bare / SIMPLE: skip — these are cache-warms for the REPL's
    // first-turn responsiveness (quota, passes, fastMode, bootstrap data). Fast
    // mode doesn't apply to the Agent SDK anyway (see getFastModeUnavailableReason).
    const bgRefreshThrottleMs = 0;
    const lastPrefetched = getGlobalConfig().startupPrefetchedAt ?? 0;
    const skipStartupPrefetches = isBareMode() || bgRefreshThrottleMs > 0 && Date.now() - lastPrefetched < bgRefreshThrottleMs;
    if (!skipStartupPrefetches) {
      const lastPrefetchedInfo = lastPrefetched > 0 ? ` last ran ${Math.round((Date.now() - lastPrefetched) / 1000)}s ago` : '';
      logForDebugging(`Starting background startup prefetches${lastPrefetchedInfo}`);


      if (true) {
        void prefetchFastModeStatus();
      } else {
        // Kill switch skips the network call, not org-policy enforcement.
        // Resolve from cache so orgStatus doesn't stay 'pending' (which
        // getFastModeUnavailableReason treats as permissive).
        resolveFastModeStatusFromCache();
      }
      if (bgRefreshThrottleMs > 0) {
        saveGlobalConfig(current => ({
          ...current,
          startupPrefetchedAt: Date.now()
        }));
      }
    } else {
      logForDebugging(`Skipping startup prefetches, last ran ${Math.round((Date.now() - lastPrefetched) / 1000)}s ago`);
      // Resolve fast mode org status from cache (no network)
      resolveFastModeStatusFromCache();
    }
    if (!isNonInteractiveSession) {
      void refreshExampleCommands(); // Pre-fetch example commands (runs git log, no API call)
    }

    // Resolve MCP configs (started early, overlaps with setup/trust dialog work)
    const {
      servers: existingMcpConfigs
    } = await mcpConfigPromise;
    logForDebugging(`[STARTUP] MCP configs resolved in ${mcpConfigResolvedMs}ms (awaited at +${Date.now() - mcpConfigStart}ms)`);
    // CLI flag (--mcp-config) should override file-based configs, matching settings precedence
    const allMcpConfigs = {
      ...existingMcpConfigs,
      ...dynamicMcpConfig
    };

    // Separate SDK configs from regular MCP configs
    const sdkMcpConfigs: Record<string, McpSdkServerConfig> = {};
    const regularMcpConfigs: Record<string, ScopedMcpServerConfig> = {};
    for (const [name, config] of Object.entries(allMcpConfigs)) {
      const typedConfig = config as ScopedMcpServerConfig | McpSdkServerConfig;
      if (typedConfig.type === 'sdk') {
        sdkMcpConfigs[name] = typedConfig as McpSdkServerConfig;
      } else {
        regularMcpConfigs[name] = typedConfig as ScopedMcpServerConfig;
      }
    }
  
    // Prefetch MCP resources after trust dialog (this is where execution happens).
    // Interactive mode only: print mode defers connects until headlessStore exists
    // and pushes per-server (below), so ToolSearch's pending-client handling works
    // and one slow server doesn't block the batch.
    const localMcpPromise = isNonInteractiveSession ? Promise.resolve({
      clients: [],
      tools: [],
      commands: []
    }) : prefetchAllMcpResources(regularMcpConfigs);
    const claudeaiMcpPromise = isNonInteractiveSession ? Promise.resolve({
      clients: [],
      tools: [],
      commands: []
    }) : claudeaiConfigPromise.then(configs => Object.keys(configs).length > 0 ? prefetchAllMcpResources(configs) : {
      clients: [],
      tools: [],
      commands: []
    });
    // Merge with dedup by name: each prefetchAllMcpResources call independently
    // adds helper tools (ListMcpResourcesTool, ReadMcpResourceTool) via
    // local dedup flags, so merging two calls can yield duplicates. print.ts
    // already uniqBy's the final tool pool, but dedup here keeps appState clean.
    const mcpPromise = Promise.all([localMcpPromise, claudeaiMcpPromise]).then(([local, claudeai]) => ({
      clients: [...local.clients, ...claudeai.clients],
      tools: uniqBy([...local.tools, ...claudeai.tools], 'name'),
      commands: uniqBy([...local.commands, ...claudeai.commands], 'name')
    }));

    // Start hooks early so they run in parallel with MCP connections.
    // Skip for initOnly/init/maintenance (handled separately), non-interactive
    // (handled via setupTrigger), and resume/continue (conversationRecovery.ts
    // fires 'resume' instead — without this guard, hooks fire TWICE on /resume
    // and the second systemMessage clobbers the first. gh-30825)
    const hooksPromise = initOnly || init || maintenance || isNonInteractiveSession || options.continue || options.resume ? null : processSessionStartHooks('startup', {
      agentType: mainThreadAgentDefinition?.agentType,
      model: resolvedInitialModel
    });

    // MCP never blocks REPL render OR turn 1 TTFT. useManageMCPConnections
    // populates appState.mcp async as servers connect (connectToServer is
    // memoized — the prefetch calls above and the hook converge on the same
    // connections). getToolUseContext reads store.getState() fresh via
    // computeTools(), so turn 1 sees whatever's connected by query time.
    // Slow servers populate for turn 2+. Matches interactive-no-prompt
    // behavior. Print mode: per-server push into headlessStore (below).
    const hookMessages: Awaited<NonNullable<typeof hooksPromise>> = [];
    // Suppress transient unhandledRejection — the prefetch warms the
    // memoized connectToServer cache but nobody awaits it in interactive.
    mcpPromise.catch(() => {});
    const mcpClients: Awaited<typeof mcpPromise>['clients'] = [];
    const mcpTools: Awaited<typeof mcpPromise>['tools'] = [];
    const mcpCommands: Awaited<typeof mcpPromise>['commands'] = [];
    let thinkingEnabled = shouldEnableThinkingByDefault();
    let thinkingConfig: ThinkingConfig = thinkingEnabled !== false ? {
      type: 'adaptive'
    } : {
      type: 'disabled'
    };
    if (options.thinking === 'adaptive' || options.thinking === 'enabled') {
      thinkingEnabled = true;
      thinkingConfig = {
        type: 'adaptive'
      };
    } else if (options.thinking === 'disabled') {
      thinkingEnabled = false;
      thinkingConfig = {
        type: 'disabled'
      };
    } else {
      const maxThinkingTokens = process.env.MAX_THINKING_TOKENS ? parseInt(process.env.MAX_THINKING_TOKENS, 10) : options.maxThinkingTokens;
      if (maxThinkingTokens !== undefined) {
        if (maxThinkingTokens > 0) {
          thinkingEnabled = true;
          thinkingConfig = {
            type: 'enabled',
            budgetTokens: maxThinkingTokens
          };
        } else if (maxThinkingTokens === 0) {
          thinkingEnabled = false;
          thinkingConfig = {
            type: 'disabled'
          };
        }
      }
    }
    logForDiagnosticsNoPII('info', 'started', {
      version: MACRO.VERSION,
      is_native_binary: isInBundledMode()
    });
    registerCleanup(async () => {
      logForDiagnosticsNoPII('info', 'exited');
    });


    // Register PID file for concurrent-session detection (~/.claude/sessions/)
    // and fire multi-clauding telemetry. Lives here (not init.ts) so only the
    // REPL path registers — not subcommands like `claude doctor`. Chained:
    // count must run after register's write completes or it misses our own file.
    void registerSession().then(registered => {
      if (!registered) return;
      if (sessionNameArg) {
        void updateSessionName(sessionNameArg);
      }
      void countConcurrentSessions().then(count => {
        if (count >= 2) {
        }
      });
    });

    // Initialize versioned plugins system (triggers V1→V2 migration if
    // needed). Then run orphan GC, THEN warm the Grep/Glob exclusion cache.
    // Sequencing matters: the warmup scans disk for .orphaned_at markers,
    // so it must see the GC's Pass 1 (remove markers from reinstalled
    // versions) and Pass 2 (stamp unmarked orphans) already applied. The
    // warm also lands before autoupdate (fires on first submit in REPL)
    // can orphan this session's active version underneath us.
    // --bare / SIMPLE: skip plugin version sync + orphan cleanup. These
    // are install/upgrade bookkeeping that scripted calls don't need —
    // the next interactive session will reconcile. The await here was
    // blocking -p on a marketplace round-trip.
    if (isBareMode()) {
      // skip — no-op
    } else if (isNonInteractiveSession) {
      // In headless mode, await to ensure plugin sync completes before CLI exits
      await initializeVersionedPlugins();
          void cleanupOrphanedPluginVersionsInBackground().then(() => getGlobExclusionsForPluginCache());
    } else {
      // In interactive mode, fire-and-forget — this is purely bookkeeping
      // that doesn't affect runtime behavior of the current session
      void initializeVersionedPlugins().then(async () => {
              await cleanupOrphanedPluginVersionsInBackground();
        void getGlobExclusionsForPluginCache();
      });
    }
    const setupTrigger = initOnly || init ? 'init' : maintenance ? 'maintenance' : null;
    if (initOnly) {
      applyConfigEnvironmentVariables();
      await processSetupHooks('init', {
        forceSyncExecution: true
      });
      await processSessionStartHooks('startup', {
        forceSyncExecution: true
      });
      gracefulShutdownSync(0);
      return;
    }

    // --print mode
    if (isNonInteractiveSession) {
      if (outputFormat === 'stream-json' || outputFormat === 'json') {
        setHasFormattedOutput(true);
      }

      // Apply full environment variables in print mode since trust dialog is bypassed
      // This includes potentially dangerous environment variables from untrusted sources
      // but print mode is considered trusted (as documented in help text)
      applyConfigEnvironmentVariables();
      try {
        assertFriendliApiKeyForUse();
      } catch (error) {
        writeToStderr(`${errorMessage(error)}\n`);
        gracefulShutdownSync(1);
        return;
      }

      // TODO(1633-T012): invoke Spec 021 UMMAYA OTEL init here
      // once initUmmayaOtel() exists (separate commit).

      // Kick SessionStart hooks now so the subprocess spawn overlaps with
      // MCP connect + plugin init + print.ts import below. loadInitialMessages
      // joins this at print.ts:4397. Guarded same as loadInitialMessages —
      // continue/resume/teleport paths don't fire startup hooks (or fire them
      // conditionally inside the resume branch, where this promise is
      // undefined and the ?? fallback runs). Also skip when setupTrigger is
      // set — those paths run setup hooks first (print.ts:544), and session
      // start hooks must wait until setup completes.
      const sessionStartHooksPromise = options.continue || options.resume || teleport || setupTrigger ? undefined : processSessionStartHooks('startup');
      // Suppress transient unhandledRejection if this rejects before
      // loadInitialMessages awaits it. Downstream await still observes the
      // rejection — this just prevents the spurious global handler fire.
      sessionStartHooksPromise?.catch(() => {});
    
      // Headless mode supports all prompt commands and some local commands
      // If disableSlashCommands is true, return empty array
      const commandsHeadless = disableSlashCommands ? [] : commands.filter(command => command.type === 'prompt' && !command.disableNonInteractive || command.type === 'local' && command.supportsNonInteractive);
      const defaultState = getDefaultAppState();
      const headlessInitialState: AppState = {
        ...defaultState,
        mcp: {
          ...defaultState.mcp,
          clients: mcpClients,
          commands: mcpCommands,
          tools: mcpTools
        },
        toolPermissionContext,
        effortValue: parseEffortValue(options.effort) ?? getInitialEffortSetting(),
        reasoningMode: getInitialReasoningModeSetting(),
        ...(isFastModeEnabled() && {
          fastMode: getInitialFastModeSetting(effectiveModel ?? null)
        }),
        ...(isAdvisorEnabled() && advisorModel && {
          advisorModel
        }),
        kairosEnabled: false
      };

      // Init app state
      const headlessStore = createStore(headlessInitialState, onChangeAppState);

      // Check if bypassPermissions should be disabled based on Statsig gate
      // This runs in parallel to the code below, to avoid blocking the main loop.
      if (toolPermissionContext.mode === 'bypassPermissions' || allowDangerouslySkipPermissions) {
        void checkAndDisableBypassPermissions(toolPermissionContext);
      }


      // Set global state for session persistence
      if (options.sessionPersistence === false) {
        setSessionPersistenceDisabled(true);
      }

      // Store SDK betas in global state for context window calculation
      setSdkBetas(betas);

      // Print-mode MCP: per-server incremental push into headlessStore.
      // Mirrors useManageMCPConnections — push pending first (so ToolSearch's
      // pending-check at ToolSearchTool.ts:334 sees them), then replace with
      // connected/failed as each server settles.
      const connectMcpBatch = (configs: Record<string, ScopedMcpServerConfig>, label: string): Promise<void> => {
        if (Object.keys(configs).length === 0) return Promise.resolve();
        headlessStore.setState(prev => ({
          ...prev,
          mcp: {
            ...prev.mcp,
            clients: [...prev.mcp.clients, ...Object.entries(configs).map(([name, config]) => ({
              name,
              type: 'pending' as const,
              config
            }))]
          }
        }));
        return getMcpToolsCommandsAndResources(({
          client,
          tools,
          commands
        }) => {
          headlessStore.setState(prev => ({
            ...prev,
            mcp: {
              ...prev.mcp,
              clients: prev.mcp.clients.some(c => c.name === client.name) ? prev.mcp.clients.map(c => c.name === client.name ? client : c) : [...prev.mcp.clients, client],
              tools: uniqBy([...prev.mcp.tools, ...tools], 'name'),
              commands: uniqBy([...prev.mcp.commands, ...commands], 'name')
            }
          }));
        }, configs).catch(err => logForDebugging(`[MCP] ${label} connect error: ${err}`));
      };
      // Await all MCP configs — print mode is often single-turn, so
      // "late-connecting servers visible next turn" doesn't help. SDK init
      // message and turn-1 tool list both need configured MCP tools present.
      // Zero-server case is free via the early return in connectMcpBatch.
      // Connectors parallelize inside getMcpToolsCommandsAndResources
      // (processBatched with Promise.all). claude.ai is awaited too — its
      // fetch was kicked off early (line ~2558) so only residual time blocks
      // here. --bare skips claude.ai entirely for perf-sensitive scripts.
          await connectMcpBatch(regularMcpConfigs, 'regular');
          // Dedup: suppress plugin MCP servers that duplicate a claude.ai
      // connector (connector wins), then connect claude.ai servers.
      // Bounded wait — #23725 made this blocking so single-turn -p sees
      // connectors, but with 40+ slow connectors tengu_startup_perf p99
      // climbed to 76s. If fetch+connect doesn't finish in time, proceed;
      // the promise keeps running and updates headlessStore in the
      // background so turn 2+ still sees connectors.
      const CLAUDE_AI_MCP_TIMEOUT_MS = 5_000;
      const claudeaiConnect = claudeaiConfigPromise.then(claudeaiConfigs => {
        if (Object.keys(claudeaiConfigs).length > 0) {
          const claudeaiSigs = new Set<string>();
          for (const config of Object.values(claudeaiConfigs)) {
            const sig = getMcpServerSignature(config);
            if (sig) claudeaiSigs.add(sig);
          }
          const suppressed = new Set<string>();
          for (const [name, config] of Object.entries(regularMcpConfigs)) {
            if (!name.startsWith('plugin:')) continue;
            const sig = getMcpServerSignature(config);
            if (sig && claudeaiSigs.has(sig)) suppressed.add(name);
          }
          if (suppressed.size > 0) {
            logForDebugging(`[MCP] Lazy dedup: suppressing ${suppressed.size} plugin server(s) that duplicate claude.ai connectors: ${[...suppressed].join(', ')}`);
            // Disconnect before filtering from state. Only connected
            // servers need cleanup — clearServerCache on a never-connected
            // server triggers a real connect just to kill it (memoize
            // cache-miss path, see useManageMCPConnections.ts:870).
            for (const c of headlessStore.getState().mcp.clients) {
              if (!suppressed.has(c.name) || c.type !== 'connected') continue;
              c.client.onclose = undefined;
              void clearServerCache(c.name, c.config).catch(() => {});
            }
            headlessStore.setState(prev => {
              let {
                clients,
                tools,
                commands,
                resources
              } = prev.mcp;
              clients = clients.filter(c => !suppressed.has(c.name));
              tools = tools.filter(t => !t.mcpInfo || !suppressed.has(t.mcpInfo.serverName));
              for (const name of suppressed) {
                commands = excludeCommandsByServer(commands, name);
                resources = excludeResourcesByServer(resources, name);
              }
              return {
                ...prev,
                mcp: {
                  ...prev.mcp,
                  clients,
                  tools,
                  commands,
                  resources
                }
              };
            });
          }
        }
        // Suppress claude.ai connectors that duplicate an enabled
        // manual server (URL-signature match). Plugin dedup above only
        // handles `plugin:*` keys; this catches manual `.mcp.json` entries.
        // plugin:* must be excluded here — step 1 already suppressed
        // those (claude.ai wins); leaving them in suppresses the
        // connector too, and neither survives (gh-39974).
        const nonPluginConfigs = pickBy(regularMcpConfigs, (_, n) => !n.startsWith('plugin:'));
        const {
          servers: dedupedClaudeAi
        } = dedupClaudeAiMcpServers(claudeaiConfigs, nonPluginConfigs);
        return connectMcpBatch(dedupedClaudeAi, 'claudeai');
      });
      let claudeaiTimer: ReturnType<typeof setTimeout> | undefined;
      const claudeaiTimedOut = await Promise.race([claudeaiConnect.then(() => false), new Promise<boolean>(resolve => {
        claudeaiTimer = setTimeout(r => r(true), CLAUDE_AI_MCP_TIMEOUT_MS, resolve);
      })]);
      if (claudeaiTimer) clearTimeout(claudeaiTimer);
      if (claudeaiTimedOut) {
        logForDebugging(`[MCP] claude.ai connectors not ready after ${CLAUDE_AI_MCP_TIMEOUT_MS}ms — proceeding; background connection continues`);
      }
    
      // In headless mode, start deferred prefetches immediately (no user typing delay)
      // --bare / SIMPLE: startDeferredPrefetches early-returns internally.
      // backgroundHousekeeping (initExtractMemories, pruneShellSnapshots,
      // cleanupOldMessageFiles) and sdkHeapDumpMonitor are all bookkeeping
      // that scripted calls don't need — the next interactive session reconciles.
      if (!isBareMode()) {
        startDeferredPrefetches();
        void import('./utils/backgroundHousekeeping.js').then(m => m.startBackgroundHousekeeping());
      }
      // UMMAYA Epic #2637 — cli/print.ts PORT (FR-003, FR-016).
      // CC-original: dynamic import of print.ts + runHeadless invocation.
      // Replaces the Spec 1633/2293 "not supported" block.
      const {
        runHeadless
      } = await import('src/cli/print.js');
      await runHeadless(inputPrompt, () => headlessStore.getState(), headlessStore.setState, commandsHeadless, tools, sdkMcpConfigs, agentDefinitions.activeAgents, {
        continue: options.continue,
        resume: options.resume,
        verbose: verbose,
        outputFormat: outputFormat,
        jsonSchema,
        permissionPromptToolName: options.permissionPromptTool,
        allowedTools,
        thinkingConfig,
        maxTurns: options.maxTurns,
        maxBudgetUsd: options.maxBudgetUsd,
        taskBudget: options.taskBudget ? {
          total: options.taskBudget
        } : undefined,
        systemPrompt,
        appendSystemPrompt,
        userSpecifiedModel: effectiveModel,
        fallbackModel: userSpecifiedFallbackModel,
        teleport,
        sdkUrl,
        replayUserMessages: effectiveReplayUserMessages,
        includePartialMessages: effectiveIncludePartialMessages,
        forkSession: options.forkSession || false,
        resumeSessionAt: options.resumeSessionAt || undefined,
        rewindFiles: options.rewindFiles,
        enableAuthStatus: options.enableAuthStatus,
        agent: agentCli,
        workload: options.workload,
        setupTrigger: setupTrigger ?? undefined,
        sessionStartHooksPromise
      });
      return;
    }


    // Get deprecation warning for the initial model (resolvedInitialModel computed earlier for hooks parallelization)
    const deprecationWarning = getModelDeprecationWarning(resolvedInitialModel);

    // Build initial notification queue
    const initialNotifications: Array<{
      key: string;
      text: string;
      color?: 'warning';
      priority: 'high';
    }> = [];
    if (permissionModeNotification) {
      initialNotifications.push({
        key: 'permission-mode-notification',
        text: permissionModeNotification,
        priority: 'high'
      });
    }
    if (deprecationWarning) {
      initialNotifications.push({
        key: 'model-deprecation-warning',
        text: deprecationWarning,
        color: 'warning',
        priority: 'high'
      });
    }
    const effectiveToolPermissionContext = {
      ...toolPermissionContext,
      mode: isAgentSwarmsEnabled() && getTeammateUtils().isPlanModeRequired() ? 'plan' as const : toolPermissionContext.mode
    };
    // All startup opt-in paths (--tools, --brief, defaultView) have fired
    // above; initialIsBriefOnly just reads the resulting state.
    const initialIsBriefOnly = false;
    const fullRemoteControl = remoteControl || getRemoteControlAtStartup() || kairosEnabled;
    let ccrMirrorEnabled = false;
    const initialState: AppState = {
      settings: getInitialSettings(),
      tasks: {},
      agentNameRegistry: new Map(),
      verbose: verbose ?? getGlobalConfig().verbose ?? false,
      mainLoopModel: initialMainLoopModel,
      mainLoopModelForSession: null,
      isBriefOnly: initialIsBriefOnly,
      expandedView: getGlobalConfig().showSpinnerTree ? 'teammates' : getGlobalConfig().showExpandedTodos ? 'tasks' : 'none',
      showTeammateMessagePreview: isAgentSwarmsEnabled() ? false : undefined,
      selectedIPAgentIndex: -1,
      coordinatorTaskIndex: -1,
      viewSelectionMode: 'none',
      footerSelection: null,
      toolPermissionContext: effectiveToolPermissionContext,
      agent: mainThreadAgentDefinition?.agentType,
      agentDefinitions,
      mcp: {
        clients: [],
        tools: [],
        commands: [],
        resources: {},
        pluginReconnectKey: 0
      },
      plugins: {
        enabled: [],
        disabled: [],
        commands: [],
        errors: [],
        installationStatus: {
          marketplaces: [],
          plugins: []
        },
        needsRefresh: false
      },
      statusLineText: undefined,
      kairosEnabled,
      remoteSessionUrl: undefined,
      remoteConnectionStatus: 'connecting',
      remoteBackgroundTaskCount: 0,
      replBridgeEnabled: fullRemoteControl || ccrMirrorEnabled,
      replBridgeExplicit: remoteControl,
      replBridgeOutboundOnly: ccrMirrorEnabled,
      replBridgeConnected: false,
      replBridgeSessionActive: false,
      replBridgeReconnecting: false,
      replBridgeConnectUrl: undefined,
      replBridgeSessionUrl: undefined,
      replBridgeEnvironmentId: undefined,
      replBridgeSessionId: undefined,
      replBridgeError: undefined,
      replBridgeInitialName: remoteControlName,
      showRemoteCallout: false,
      notifications: {
        current: null,
        queue: initialNotifications
      },
      elicitation: {
        queue: []
      },
      todos: {},
      remoteAgentTaskSuggestions: [],
      fileHistory: {
        snapshots: [],
        trackedFiles: new Set(),
        snapshotSequence: 0
      },
      attribution: createEmptyAttributionState(),
      thinkingEnabled,
      promptSuggestionEnabled: shouldEnablePromptSuggestion(),
      sessionHooks: new Map(),
      inbox: {
        messages: []
      },
      promptSuggestion: {
        text: null,
        promptId: null,
        shownAt: 0,
        acceptedAt: 0,
        generationRequestId: null
      },
      speculation: IDLE_SPECULATION_STATE,
      speculationSessionTimeSavedMs: 0,
      skillImprovement: {
        suggestion: null
      },
      workerSandboxPermissions: {
        queue: [],
        selectedIndex: 0
      },
      pendingWorkerRequest: null,
      pendingSandboxRequest: null,
      authVersion: 0,
      initialMessage: inputPrompt ? {
        message: createUserMessage({
          content: String(inputPrompt)
        })
      } : null,
      effortValue: parseEffortValue(options.effort) ?? getInitialEffortSetting(),
      reasoningMode: getInitialReasoningModeSetting(),
      activeOverlays: new Set<string>(),
      fastMode: getInitialFastModeSetting(resolvedInitialModel),
      ...(isAdvisorEnabled() && advisorModel && {
        advisorModel
      }),
      // Compute teamContext synchronously to avoid useEffect setState during render.
      // KAIROS: assistantTeamContext takes precedence — set earlier in the
      // KAIROS block so Agent(name: "foo") can spawn in-process teammates
      // without TeamCreate. computeInitialTeamContext() is for tmux-spawned
      // teammates reading their own identity, not the assistant-mode leader.
      teamContext: computeInitialTeamContext?.()
    };

    // Add CLI initial prompt to history
    if (inputPrompt) {
      addToHistory(String(inputPrompt));
    }
    const initialTools = mcpTools;

    // Increment numStartups synchronously — first-render readers like
    // shouldShowEffortCallout (via useState initializer) need the updated
    // value before setImmediate fires. Defer only telemetry.
    saveGlobalConfig(current => ({
      ...current,
      numStartups: (current.numStartups ?? 0) + 1
    }));


    // Defer session uploader resolution to the onTurnComplete callback to avoid
    // adding a new top-level await in main.tsx (performance-critical path).
    // The per-turn auth logic in sessionDataUploader.ts handles unauthenticated
    // state gracefully (re-checks each turn, so auth recovery mid-session works).
    // UMMAYA — sessionDataUploader is upstream-only (Anthropic claude.ai
    // session sync); UMMAYA does not exfiltrate sessions. Set the promise to
    // null so the lazy-resolve path becomes a no-op (Spec 1633 dead-code
    // policy + ReferenceError fix from Spec 1632 sourcemap reconstruction).
    const sessionUploaderPromise: Promise<{ createSessionTurnUploader: () => unknown }> | null = null;
    const uploaderReady = sessionUploaderPromise ? sessionUploaderPromise.then(mod => mod.createSessionTurnUploader()).catch(() => null) : null;
    const sessionConfig = {
      debug: debug || debugToStderr,
      commands: [...commands, ...mcpCommands],
      initialTools,
      mcpClients,
      autoConnectIdeFlag: ide,
      mainThreadAgentDefinition,
      disableSlashCommands,
      dynamicMcpConfig,
      strictMcpConfig,
      systemPrompt,
      appendSystemPrompt,
      thinkingConfig,
      ...(uploaderReady && {
        onTurnComplete: (messages: MessageType[]) => {
          void uploaderReady.then(uploader => uploader?.(messages));
        }
      })
    };

    // Shared context for processResumedConversation calls
    const resumeContext = {
      modeApi: null,
      mainThreadAgentDefinition,
      agentDefinitions,
      currentCwd,
      cliAgents,
      initialState
    };
    if (options.continue) {
      // Continue the most recent conversation directly
      let resumeSucceeded = false;
      try {
        const resumeStart = performance.now();

        // Clear stale caches before resuming to ensure fresh file/skill discovery
        const {
          clearSessionCaches
        } = await import('./commands/clear/caches.js');
        clearSessionCaches();
        const result = await loadConversationForResume(undefined /* sessionId */, undefined /* sourceFile */);
        if (!result) {
          return await exitWithError(root, 'No conversation found to continue');
        }
        const loaded = await processResumedConversation(result, {
          forkSession: !!options.forkSession,
          includeAttribution: true,
          transcriptPath: result.fullPath
        }, resumeContext);
        if (loaded.restoredAgentDef) {
          mainThreadAgentDefinition = loaded.restoredAgentDef;
        }
        maybeActivateProactive(options);
        maybeActivateBrief(options);
        resumeSucceeded = true;
        await launchRepl(root, {
          getFpsMetrics,
          stats,
          initialState: loaded.initialState
        }, {
          ...sessionConfig,
          mainThreadAgentDefinition: loaded.restoredAgentDef ?? mainThreadAgentDefinition,
          initialMessages: loaded.messages,
          initialFileHistorySnapshots: loaded.fileHistorySnapshots,
          initialContentReplacements: loaded.contentReplacements,
          initialAgentName: loaded.agentName,
          initialAgentColor: loaded.agentColor
        }, renderAndRun);
      } catch (error) {
        if (!resumeSucceeded) {
        }
        logError(error);
        process.exit(1);
      }

    } else if (options.resume || options.fromPr || teleport || remote !== null) {
      // Handle resume flow - from file (ant-only), session ID, or interactive selector

      // Clear stale caches before resuming to ensure fresh file/skill discovery
      const {
        clearSessionCaches
      } = await import('./commands/clear/caches.js');
      clearSessionCaches();
      let messages: MessageType[] | null = null;
      let processedResume: ProcessedResume | undefined = undefined;
      let maybeSessionId = validateUuid(options.resume);
      let searchTerm: string | undefined = undefined;
      // Store full LogOption when found by custom title (for cross-worktree resume)
      let matchedLog: LogOption | null = null;
      // PR filter for --from-pr flag
      let filterByPr: boolean | number | string | undefined = undefined;

      // Handle --from-pr flag
      if (options.fromPr) {
        if (options.fromPr === true) {
          // Show all sessions with linked PRs
          filterByPr = true;
        } else if (typeof options.fromPr === 'string') {
          // Could be a PR number or URL
          filterByPr = options.fromPr;
        }
      }

      // If resume value is not a UUID, try exact match by custom title first
      if (options.resume && typeof options.resume === 'string' && !maybeSessionId) {
        const trimmedValue = options.resume.trim();
        if (trimmedValue) {
          const matches = await searchSessionsByCustomTitle(trimmedValue, {
            exact: true
          });
          if (matches.length === 1) {
            // Exact match found - store full LogOption for cross-worktree resume
            matchedLog = matches[0]!;
            maybeSessionId = getSessionIdFromLog(matchedLog) ?? null;
          } else {
            // No match or multiple matches - use as search term for picker
            searchTerm = trimmedValue;
          }
        }
      }


      // If not loaded as a file, try as session ID
      if (maybeSessionId) {
        // Resume specific session by ID
        const sessionId = maybeSessionId;
        try {
          const resumeStart = performance.now();
          // Use matchedLog if available (for cross-worktree resume by custom title)
          // Otherwise fall back to sessionId string (for direct UUID resume)
          const result = await loadConversationForResume(matchedLog ?? sessionId, undefined);
          if (!result) {
            return await exitWithError(root, `No conversation found with session ID: ${sessionId}`);
          }
          const fullPath = matchedLog?.fullPath ?? result.fullPath;
          processedResume = await processResumedConversation(result, {
            forkSession: !!options.forkSession,
            sessionIdOverride: sessionId,
            transcriptPath: fullPath
          }, resumeContext);
          if (processedResume.restoredAgentDef) {
            mainThreadAgentDefinition = processedResume.restoredAgentDef;
          }
        } catch (error) {
          logError(error);
          await exitWithError(root, `Failed to resume session ${sessionId}`);
        }
      }

      // UMMAYA: fileDownloadPromise block removed (filesApi dead code).

      // If we have a processed resume or teleport messages, render the REPL
      const resumeData = processedResume ?? (Array.isArray(messages) ? {
        messages,
        fileHistorySnapshots: undefined,
        agentName: undefined,
        agentColor: undefined as AgentColorName | undefined,
        restoredAgentDef: mainThreadAgentDefinition,
        initialState,
        contentReplacements: undefined
      } : undefined);
      if (resumeData) {
        maybeActivateProactive(options);
        maybeActivateBrief(options);
        await launchRepl(root, {
          getFpsMetrics,
          stats,
          initialState: resumeData.initialState
        }, {
          ...sessionConfig,
          mainThreadAgentDefinition: resumeData.restoredAgentDef ?? mainThreadAgentDefinition,
          initialMessages: resumeData.messages,
          initialFileHistorySnapshots: resumeData.fileHistorySnapshots,
          initialContentReplacements: resumeData.contentReplacements,
          initialAgentName: resumeData.agentName,
          initialAgentColor: resumeData.agentColor
        }, renderAndRun);
      } else {
        // Show interactive selector (includes same-repo worktrees)
        // Note: ResumeConversation loads logs internally to ensure proper GC after selection
        await launchResumeChooser(root, {
          getFpsMetrics,
          stats,
          initialState
        }, getWorktreePaths(getOriginalCwd()), {
          ...sessionConfig,
          initialSearchQuery: searchTerm,
          forkSession: options.forkSession,
          filterByPr
        });
      }
    } else {
      // Pass unresolved hooks promise to REPL so it can render immediately
      // instead of blocking ~500ms waiting for SessionStart hooks to finish.
      // REPL will inject hook messages when they resolve and await them before
      // the first API call so the model always sees hook context.
      const pendingHookMessages = hooksPromise && hookMessages.length === 0 ? hooksPromise : undefined;
          maybeActivateProactive(options);
      maybeActivateBrief(options);
      // Persist the current mode for fresh sessions so future resumes know what mode was used

      // If launched via a deep link, show a provenance banner so the user
      // knows the session originated externally. Linux xdg-open and
      // browsers with "always allow" set dispatch the link with no OS-level
      // confirmation, so this is the only signal the user gets that the
      // prompt — and the working directory / CLAUDE.md it implies — came
      // from an external source rather than something they typed.
      const deepLinkBanner: ReturnType<typeof createSystemMessage> | null = null;
      const initialMessages = deepLinkBanner ? [deepLinkBanner, ...hookMessages] : hookMessages.length > 0 ? hookMessages : undefined;
      await launchRepl(root, {
        getFpsMetrics,
        stats,
        initialState
      }, {
        ...sessionConfig,
        initialMessages,
        pendingHookMessages
      }, renderAndRun);
    }
  }).version(`${MACRO.VERSION} (UMMAYA)`, '-v, --version', 'Output the version number');

  // Worktree flags
  program.option('-w, --worktree [name]', 'Create a new git worktree for this session (optionally specify a name)');
  program.option('--tmux', 'Create a tmux session for the worktree (requires --worktree). Uses iTerm2 native panes when available; use --tmux=classic for traditional tmux.');
  if (canUserConfigureAdvisor()) {
    program.addOption(new Option('--advisor <model>', 'Enable the server-side advisor tool with the specified model (alias or full ID).').hideHelp());
  }

  // Teammate identity options (set by leader when spawning tmux teammates)
  // These replace the CLAUDE_CODE_* environment variables
  program.addOption(new Option('--agent-id <id>', 'Teammate agent ID').hideHelp());
  program.addOption(new Option('--agent-name <name>', 'Teammate display name').hideHelp());
  program.addOption(new Option('--team-name <name>', 'Team name for swarm coordination').hideHelp());
  program.addOption(new Option('--agent-color <color>', 'Teammate UI color').hideHelp());
  program.addOption(new Option('--plan-mode-required', 'Require plan mode before implementation').hideHelp());
  program.addOption(new Option('--parent-session-id <id>', 'Parent session ID for analytics correlation').hideHelp());
  program.addOption(new Option('--teammate-mode <mode>', 'How to spawn teammates: "tmux", "in-process", or "auto"').choices(['auto', 'tmux', 'in-process']).hideHelp());
  program.addOption(new Option('--agent-type <type>', 'Custom agent type for this teammate').hideHelp());

  // Enable SDK URL for all builds but hide from help
  program.addOption(new Option('--sdk-url <url>', 'Use remote WebSocket endpoint for SDK I/O streaming (only with -p and stream-json format)').hideHelp());

  // Enable teleport/remote flags for all builds but keep them undocumented until GA
  program.addOption(new Option('--teleport [session]', 'Resume a teleport session, optionally specify session ID').hideHelp());
  program.addOption(new Option('--remote [description]', 'Create a remote session with the given description').hideHelp());

  // -p/--print mode: skip subcommand registration. The 52 subcommands
  // (mcp, auth, plugin, skill, task, config, doctor, update, etc.) are
  // never dispatched in print mode — commander routes the prompt to the
  // default action. The subcommand registration path was measured at ~65ms
  // on baseline — mostly the isBridgeEnabled() call (25ms settings Zod parse
  // + 40ms sync keychain subprocess), both hidden by the try/catch that
  // always returns false before enableConfigs(). cc:// URLs are rewritten to
  // `open` at main() line ~851 BEFORE this runs, so argv check is safe here.
  const isPrintMode = process.argv.includes('-p') || process.argv.includes('--print');
  const isCcUrl = process.argv.some(a => a.startsWith('cc://') || a.startsWith('cc+unix://'));
  if (isPrintMode && !isCcUrl) {
      await program.parseAsync(process.argv);
      return program;
  }

  // claude mcp

  const mcp = program.command('mcp').description('Configure and manage MCP servers').configureHelp(createSortedHelpConfig()).enablePositionalOptions();
  mcp.command('serve').description(`Start the UMMAYA MCP server`).option('-d, --debug', 'Enable debug mode', () => true).option('--verbose', 'Override verbose mode setting from config', () => true).action(async ({
    debug,
    verbose
  }: {
    debug?: boolean;
    verbose?: boolean;
  }) => {
    const {
      mcpServeHandler
    } = await import('./cli/handlers/mcp.js');
    await mcpServeHandler({
      debug,
      verbose
    });
  });

  // Register the mcp add subcommand (extracted for testability)
  registerMcpAddCommand(mcp);
  if (isXaaEnabled()) {
    registerMcpXaaIdpCommand(mcp);
  }
  mcp.command('remove <name>').description('Remove an MCP server').option('-s, --scope <scope>', 'Configuration scope (local, user, or project) - if not specified, removes from whichever scope it exists in').action(async (name: string, options: {
    scope?: string;
  }) => {
    const {
      mcpRemoveHandler
    } = await import('./cli/handlers/mcp.js');
    await mcpRemoveHandler(name, options);
  });
  mcp.command('list').description('List configured MCP servers. Note: The workspace trust dialog is skipped and stdio servers from .mcp.json are spawned for health checks. Only use this command in directories you trust.').action(async () => {
    const {
      mcpListHandler
    } = await import('./cli/handlers/mcp.js');
    await mcpListHandler();
  });
  mcp.command('get <name>').description('Get details about an MCP server. Note: The workspace trust dialog is skipped and stdio servers from .mcp.json are spawned for health checks. Only use this command in directories you trust.').action(async (name: string) => {
    const {
      mcpGetHandler
    } = await import('./cli/handlers/mcp.js');
    await mcpGetHandler(name);
  });
  mcp.command('add-json <name> <json>').description('Add an MCP server (stdio or SSE) with a JSON string').option('-s, --scope <scope>', 'Configuration scope (local, user, or project)', 'local').option('--client-secret', 'Prompt for OAuth client secret (or set MCP_CLIENT_SECRET env var)').action(async (name: string, json: string, options: {
    scope?: string;
    clientSecret?: true;
  }) => {
    const {
      mcpAddJsonHandler
    } = await import('./cli/handlers/mcp.js');
    await mcpAddJsonHandler(name, json, options);
  });
  mcp.command('add-from-desktop').description('Import MCP servers from a desktop MCP config (Mac and WSL only)').option('-s, --scope <scope>', 'Configuration scope (local, user, or project)', 'local').action(async (options: {
    scope?: string;
  }) => {
    const {
      mcpAddFromDesktopHandler
    } = await import('./cli/handlers/mcp.js');
    await mcpAddFromDesktopHandler(options);
  });
  mcp.command('reset-project-choices').description('Reset all approved and rejected project-scoped (.mcp.json) servers within this project').action(async () => {
    const {
      mcpResetChoicesHandler
    } = await import('./cli/handlers/mcp.js');
    await mcpResetChoicesHandler();
  });


  const auth = program.command('auth').description('Show UMMAYA FriendliAI session-auth status').configureHelp(createSortedHelpConfig());
  auth.command('login').description('Show how to log in with /login inside the TUI').option('--email <email>', 'Ignored in UMMAYA').option('--sso', 'Ignored in UMMAYA').option('--console', 'Ignored in UMMAYA').action(async ({
    email,
    sso,
    console: useConsole,
  }: {
    email?: string;
    sso?: boolean;
    console?: boolean;
  }) => {
    const {
      authLogin
    } = await import('./cli/handlers/auth.js');
    await authLogin({
      email,
      sso,
      console: useConsole
    });
  });
  auth.command('status').description('Show authentication status').option('--json', 'Output as JSON (default)').option('--text', 'Output as human-readable text').action(async (opts: {
    json?: boolean;
    text?: boolean;
  }) => {
    const {
      authStatus
    } = await import('./cli/handlers/auth.js');
    await authStatus(opts);
  });
  auth.command('logout').description('Clear FriendliAI credentials from this CLI process').action(async () => {
    const {
      authLogout
    } = await import('./cli/handlers/auth.js');
    await authLogout();
  });

  /**
   * Helper function to handle marketplace command errors consistently.
   * Logs the error and exits the process with status 1.
   * @param error The error that occurred
   * @param action Description of the action that failed
   */
  // Hidden flag on all plugin/marketplace subcommands to target cowork_plugins.
  const coworkOption = () => new Option('--cowork', 'Use cowork_plugins directory').hideHelp();

  // Plugin validate command
  const pluginCmd = program.command('plugin').alias('plugins').description('Manage UMMAYA plugins').configureHelp(createSortedHelpConfig());
  pluginCmd.command('validate <path>').description('Validate a plugin or marketplace manifest').addOption(coworkOption()).action(async (manifestPath: string, options: {
    cowork?: boolean;
  }) => {
    const {
      pluginValidateHandler
    } = await import('./cli/handlers/plugins.js');
    await pluginValidateHandler(manifestPath, options);
  });

  // Plugin list command
  pluginCmd.command('list').description('List installed plugins').option('--json', 'Output as JSON').option('--available', 'Include available plugins from marketplaces (requires --json)').addOption(coworkOption()).action(async (options: {
    json?: boolean;
    available?: boolean;
    cowork?: boolean;
  }) => {
    const {
      pluginListHandler
    } = await import('./cli/handlers/plugins.js');
    await pluginListHandler(options);
  });

  // Marketplace subcommands
  const marketplaceCmd = pluginCmd.command('marketplace').description('Manage UMMAYA plugin marketplaces').configureHelp(createSortedHelpConfig());
  marketplaceCmd.command('add <source>').description('Add a marketplace from a URL, path, or GitHub repo').addOption(coworkOption()).option('--sparse <paths...>', 'Limit checkout to specific directories via git sparse-checkout (for monorepos). Example: --sparse .claude-plugin plugins').option('--scope <scope>', 'Where to declare the marketplace: user (default), project, or local').action(async (source: string, options: {
    cowork?: boolean;
    sparse?: string[];
    scope?: string;
  }) => {
    const {
      marketplaceAddHandler
    } = await import('./cli/handlers/plugins.js');
    await marketplaceAddHandler(source, options);
  });
  marketplaceCmd.command('list').description('List all configured marketplaces').option('--json', 'Output as JSON').addOption(coworkOption()).action(async (options: {
    json?: boolean;
    cowork?: boolean;
  }) => {
    const {
      marketplaceListHandler
    } = await import('./cli/handlers/plugins.js');
    await marketplaceListHandler(options);
  });
  marketplaceCmd.command('remove <name>').alias('rm').description('Remove a configured marketplace').addOption(coworkOption()).action(async (name: string, options: {
    cowork?: boolean;
  }) => {
    const {
      marketplaceRemoveHandler
    } = await import('./cli/handlers/plugins.js');
    await marketplaceRemoveHandler(name, options);
  });
  marketplaceCmd.command('update [name]').description('Update marketplace(s) from their source - updates all if no name specified').addOption(coworkOption()).action(async (name: string | undefined, options: {
    cowork?: boolean;
  }) => {
    const {
      marketplaceUpdateHandler
    } = await import('./cli/handlers/plugins.js');
    await marketplaceUpdateHandler(name, options);
  });

  // Plugin install command
  pluginCmd.command('install <plugin>').alias('i').description('Install a plugin from available marketplaces (use plugin@marketplace for specific marketplace)').option('-s, --scope <scope>', 'Installation scope: user, project, or local', 'user').addOption(coworkOption()).action(async (plugin: string, options: {
    scope?: string;
    cowork?: boolean;
  }) => {
    const {
      pluginInstallHandler
    } = await import('./cli/handlers/plugins.js');
    await pluginInstallHandler(plugin, options);
  });

  // Plugin uninstall command
  pluginCmd.command('uninstall <plugin>').alias('remove').alias('rm').description('Uninstall an installed plugin').option('-s, --scope <scope>', 'Uninstall from scope: user, project, or local', 'user').option('--keep-data', "Preserve the plugin's persistent data directory (~/.claude/plugins/data/{id}/)").addOption(coworkOption()).action(async (plugin: string, options: {
    scope?: string;
    cowork?: boolean;
    keepData?: boolean;
  }) => {
    const {
      pluginUninstallHandler
    } = await import('./cli/handlers/plugins.js');
    await pluginUninstallHandler(plugin, options);
  });

  // Plugin enable command
  pluginCmd.command('enable <plugin>').description('Enable a disabled plugin').option('-s, --scope <scope>', `Installation scope: ${VALID_INSTALLABLE_SCOPES.join(', ')} (default: auto-detect)`).addOption(coworkOption()).action(async (plugin: string, options: {
    scope?: string;
    cowork?: boolean;
  }) => {
    const {
      pluginEnableHandler
    } = await import('./cli/handlers/plugins.js');
    await pluginEnableHandler(plugin, options);
  });

  // Plugin disable command
  pluginCmd.command('disable [plugin]').description('Disable an enabled plugin').option('-a, --all', 'Disable all enabled plugins').option('-s, --scope <scope>', `Installation scope: ${VALID_INSTALLABLE_SCOPES.join(', ')} (default: auto-detect)`).addOption(coworkOption()).action(async (plugin: string | undefined, options: {
    scope?: string;
    cowork?: boolean;
    all?: boolean;
  }) => {
    const {
      pluginDisableHandler
    } = await import('./cli/handlers/plugins.js');
    await pluginDisableHandler(plugin, options);
  });

  // Plugin update command
  pluginCmd.command('update <plugin>').description('Update a plugin to the latest version (restart required to apply)').option('-s, --scope <scope>', `Installation scope: ${VALID_UPDATE_SCOPES.join(', ')} (default: user)`).addOption(coworkOption()).action(async (plugin: string, options: {
    scope?: string;
    cowork?: boolean;
  }) => {
    const {
      pluginUpdateHandler
    } = await import('./cli/handlers/plugins.js');
    await pluginUpdateHandler(plugin, options);
  });
  // END ANT-ONLY

  // Setup token command
  program.command('setup-token').description('Set up a long-lived authentication token').action(async () => {
    const [{
      setupTokenHandler
    }, {
      createRoot
    }] = await Promise.all([import('./cli/handlers/util.js'), import('./ink.js')]);
    const root = await createRoot(getBaseRenderOptions(false));
    await setupTokenHandler(root);
  });

  // Agents command - list configured agents
  program.command('agents').description('List configured agents').option('--setting-sources <sources>', 'Comma-separated list of setting sources to load (user, project, local).').action(async () => {
    const {
      agentsHandler
    } = await import('./cli/handlers/agents.js');
    await agentsHandler();
    process.exit(0);
  });

  // Remote Control command — connect local environment to UMMAYA on the web.
  // The actual command is intercepted by the fast-path in cli.tsx before
  // Commander.js runs, so this registration exists only for help output.
  // Always hidden: isBridgeEnabled() at this point (before enableConfigs)
  // would throw inside isClaudeAISubscriber → getGlobalConfig and return
  // false via the try/catch — but not before paying ~65ms of side effects
  // (25ms settings Zod parse + 40ms sync `security` keychain subprocess).
  // The dynamic visibility never worked; the command was always hidden.

  // Doctor command - check installation health
  program.command('doctor').description('Check the health of your UMMAYA installation. Note: The workspace trust dialog is skipped and stdio servers from .mcp.json are spawned for health checks. Only use this command in directories you trust.').action(async () => {
    const [{
      doctorHandler
    }, {
      createRoot
    }] = await Promise.all([import('./cli/handlers/util.js'), import('./ink.js')]);
    const root = await createRoot(getBaseRenderOptions(false));
    await doctorHandler(root);
  });

  // claude update
  //
  // For SemVer-compliant versioning with build metadata (X.X.X+SHA):
  // - We perform exact string comparison (including SHA) to detect any change
  // - This ensures users always get the latest build, even when only the SHA changes
  // - UI shows both versions including build metadata for clarity
  program.command('update').alias('upgrade').description('Check for updates and install if available').action(async () => {
    const {
      update
    } = await import('src/cli/update.js');
    await update();
  });



  // claude install
  program.command('install [target]').description('Install UMMAYA native build. Use [target] to specify version (stable, latest, or specific version)').option('--force', 'Force installation even if already installed').action(async (target: string | undefined, options: {
    force?: boolean;
  }) => {
    const {
      installHandler
    } = await import('./cli/handlers/util.js');
    await installHandler(target, options);
  });

  await program.parseAsync(process.argv);

  // Record final checkpoint for total_time calculation

  return program;
}
function maybeActivateProactive(_options: unknown): void {
  // PROACTIVE/KAIROS features removed in Epic #1633
}
function maybeActivateBrief(_options: unknown): void {
  // KAIROS/KAIROS_BRIEF features removed in Epic #1633
}function resetCursor() {
  const terminal = process.stderr.isTTY ? process.stderr : process.stdout.isTTY ? process.stdout : undefined;
  terminal?.write(SHOW_CURSOR);
}
type TeammateOptions = {
  agentId?: string;
  agentName?: string;
  teamName?: string;
  agentColor?: string;
  planModeRequired?: boolean;
  parentSessionId?: string;
  teammateMode?: 'auto' | 'tmux' | 'in-process';
  agentType?: string;
};
function extractTeammateOptions(options: unknown): TeammateOptions {
  if (typeof options !== 'object' || options === null) {
    return {};
  }
  const opts = options as Record<string, unknown>;
  const teammateMode = opts.teammateMode;
  return {
    agentId: typeof opts.agentId === 'string' ? opts.agentId : undefined,
    agentName: typeof opts.agentName === 'string' ? opts.agentName : undefined,
    teamName: typeof opts.teamName === 'string' ? opts.teamName : undefined,
    agentColor: typeof opts.agentColor === 'string' ? opts.agentColor : undefined,
    planModeRequired: typeof opts.planModeRequired === 'boolean' ? opts.planModeRequired : undefined,
    parentSessionId: typeof opts.parentSessionId === 'string' ? opts.parentSessionId : undefined,
    teammateMode: teammateMode === 'auto' || teammateMode === 'tmux' || teammateMode === 'in-process' ? teammateMode : undefined,
    agentType: typeof opts.agentType === 'string' ? opts.agentType : undefined
  };
}
// [P0 reconstructed] Bottom-of-file main() invocation.
// CC 2.1.88 sourcemap reconstruction dropped the entry call that normally
// appeared at file end: `main().catch(err => { process.stderr.write(err); process.exit(1); })`.
// Without this, `bun run src/main.tsx` loads the module and exits immediately
// without reaching the splash render path.
// Epic ζ #2297 — REMOVED top-level `main().catch(...)` invocation that caused
// `main()` to execute TWICE: once at module-import side-effect time (this
// block) and once via the explicit `await cliMain()` at
// `src/entrypoints/cli.tsx:338`. The double-execution surfaced as duplicate
// duplicate `tool_registry: ... entries verified` log lines + duplicated welcome banner
// rendering visible in the user's interactive PTY session (2026-04-30 user
// report). cli.tsx is the canonical CLI entry per `package.json#scripts.tui`
// and ALWAYS imports main.js + awaits it; the bottom-of-file invocation has
// been redundant since that import-then-await pattern was finalised. The
// rich debug-on-rejection wrapper that lived here has been moved to cli.tsx
// where the single canonical await happens, preserving the
// "[UMMAYA/CC] fatal: ..." failure-mode telemetry.
