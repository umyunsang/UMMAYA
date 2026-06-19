// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from 'bun:test'
import { readdirSync, readFileSync } from 'fs'
import { join } from 'path'
import { sanitizeTopOfFeedTipForUmmaya } from '../../src/components/LogoV2/EmergencyTip.js'

const ROOT = join(import.meta.dir, '../..')

function sourceFilesUnder(relativeDir: string): string[] {
  const absoluteDir = join(ROOT, relativeDir)
  return readdirSync(absoluteDir, { withFileTypes: true })
    .flatMap(entry => {
      const relativePath = join(relativeDir, entry.name)
      if (entry.isDirectory()) return sourceFilesUnder(relativePath)
      if (!entry.isFile()) return []
      return /\.(tsx?|jsx?)$/.test(entry.name) ? [relativePath] : []
    })
    .sort()
}

const paintSurfaceFiles = [
  'src/services/tips/tipRegistry.ts',
  'src/components/Spinner.tsx',
  'src/components/messages/AssistantTextMessage.tsx',
  'src/components/skills/SkillsMenu.tsx',
  'src/components/design-system/LoadingState.tsx',
  'src/projectOnboardingState.ts',
  'src/components/permissions/PermissionRequest.tsx',
  'src/components/permissions/PermissionPrompt.tsx',
  'src/components/permissions/ComputerUseApproval/ComputerUseApproval.tsx',
  'src/components/permissions/EnterPlanModePermissionRequest/EnterPlanModePermissionRequest.tsx',
  'src/components/permissions/ExitPlanModePermissionRequest/ExitPlanModePermissionRequest.tsx',
  'src/components/HelpV2/General.tsx',
  'src/components/HelpV2/HelpV2.tsx',
  'src/components/InterruptedByUser.tsx',
  'src/components/ThinkingToggle.tsx',
  'src/components/OutputStylePicker.tsx',
  'src/components/FeedbackSurvey/FeedbackSurveyView.tsx',
  'src/components/FeedbackSurvey/TranscriptSharePrompt.tsx',
  'src/components/Feedback.tsx',
  'src/components/LogoV2/feedConfigs.tsx',
  'src/components/LogoV2/GuestPassesUpsell.tsx',
  'src/components/LogoV2/LogoV2.tsx',
  'src/components/ResumeTask.tsx',
  'src/components/IdeOnboardingDialog.tsx',
  'src/components/RemoteCallout.tsx',
  'src/components/RemoteEnvironmentDialog.tsx',
  'src/components/ModelPicker.tsx',
  'src/components/Stats.tsx',
  'src/components/grove/Grove.tsx',
  'src/components/hooks/SelectHookMode.tsx',
  'src/components/hooks/SelectMatcherMode.tsx',
  'src/components/hooks/SelectEventMode.tsx',
  'src/components/hooks/ViewHookMode.tsx',
  'src/components/hooks/HooksConfigMenu.tsx',
  'src/components/mcp/ElicitationDialog.tsx',
  'src/components/mcp/MCPListPanel.tsx',
  'src/components/mcp/MCPRemoteServerMenu.tsx',
  'src/components/mcp/MCPSettings.tsx',
  'src/components/mcp/McpParsingWarnings.tsx',
  'src/components/MCPServerDialogCopy.tsx',
  'src/components/MCPServerDesktopImportDialog.tsx',
  'src/components/sandbox/SandboxSettings.tsx',
  'src/components/sandbox/SandboxOverridesTab.tsx',
  'src/components/PackageManagerAutoUpdater.tsx',
  'src/components/ThemePicker.tsx',
  'src/components/BypassPermissionsModeDialog.tsx',
  'src/components/ClaudeInChromeOnboarding.tsx',
  'src/components/ClaudeMdExternalIncludesDialog.tsx',
  'src/components/CostThresholdDialog.tsx',
  'src/components/DesktopUpsell/DesktopUpsellStartup.tsx',
  'src/components/LogSelector.tsx',
  'src/components/Settings/Config.tsx',
  'src/components/PromptInput/PromptInput.tsx',
  'src/components/TeleportError.tsx',
  'src/components/TeleportRepoMismatchDialog.tsx',
  'src/components/WorkflowMultiselectDialog.tsx',
  'src/components/agents/AgentDetail.tsx',
  'src/components/agents/AgentsList.tsx',
  'src/components/agents/new-agent-creation/wizard-steps/ConfirmStep.tsx',
  'src/components/agents/new-agent-creation/wizard-steps/MethodStep.tsx',
  'src/components/messages/UserToolResultMessage/RejectedPlanMessage.tsx',
  'src/components/tasks/RemoteSessionDetailDialog.tsx',
  'src/screens/REPL.tsx',
  'src/bridge/bridgeMain.ts',
  'src/bridge/bridgeApi.ts',
  'src/bridge/bridgePointer.ts',
  'src/bridge/createSession.ts',
  'src/bridge/replBridge.ts',
  'src/bridge/types.ts',
  'src/constants/github-app.ts',
  'src/constants/product.ts',
  'src/constants/prompts.ts',
  'src/constants/system.ts',
  'src/coordinator/coordinatorMode.ts',
  'src/commands.ts',
  'src/commands/extra-usage/extra-usage-core.ts',
  'src/commands/chrome/chrome.tsx',
  'src/commands/copy/index.ts',
  'src/commands/cost/cost.ts',
  'src/commands/fast/fast.tsx',
  'src/commands/feedback/index.ts',
  'src/commands/ide/ide.tsx',
  'src/commands/init.ts',
  'src/commands/init-verifiers.ts',
  'src/commands/install.tsx',
  'src/commands/install-github-app/install-github-app.tsx',
  'src/commands/install-github-app/ApiKeyStep.tsx',
  'src/commands/install-github-app/CheckExistingSecretStep.tsx',
  'src/commands/install-github-app/CreatingStep.tsx',
  'src/commands/install-github-app/ErrorStep.tsx',
  'src/commands/install-github-app/ExistingWorkflowStep.tsx',
  'src/commands/install-github-app/InstallAppStep.tsx',
  'src/commands/install-github-app/SuccessStep.tsx',
  'src/commands/install-github-app/setupGitHubActions.ts',
  'src/commands/install-github-app/WarningsStep.tsx',
  'src/commands/install-github-app/index.ts',
  'src/commands/install-slack-app/index.ts',
  'src/commands/logout/index.ts',
  'src/commands/memory/memory.tsx',
  'src/commands/mcp/addCommand.ts',
  'src/commands/mcp/xaaIdpCommand.ts',
  'src/commands/model/model.tsx',
  'src/commands/plugin/DiscoverPlugins.tsx',
  'src/commands/plugin/ManageMarketplaces.tsx',
  'src/commands/plugin/PluginTrustWarning.tsx',
  'src/commands/privacy-settings/privacy-settings.tsx',
  'src/commands/remote-setup/remote-setup.tsx',
  'src/commands/remote-setup/index.ts',
  'src/commands/review.ts',
  'src/commands/review/ultrareviewCommand.tsx',
  'src/commands/session/session.tsx',
  'src/commands/stats/index.ts',
  'src/commands/status/index.ts',
  'src/commands/statusline.tsx',
  'src/commands/stickers/index.ts',
  'src/commands/thinkback/index.ts',
  'src/commands/thinkback/thinkback.tsx',
  'src/commands/ultraplan.tsx',
  'src/commands/upgrade/upgrade.tsx',
  'src/commands/voice/voice.ts',
  'src/commands/passes/index.ts',
  'src/commands/insights.ts',
  'src/cli/update.ts',
  'src/cli/handlers/auth.ts',
  'src/services/api/errorUtils.ts',
  'src/cli/handlers/mcp.tsx',
  'src/hooks/useChromeExtensionNotification.tsx',
  'src/hooks/notifs/useCanSwitchToExistingSubscription.tsx',
  'src/hooks/useDiffInIDE.ts',
  'src/hooks/useVoice.ts',
  'src/main.tsx',
  'src/utils/claudeDesktop.ts',
  'src/utils/desktopDeepLink.ts',
  'src/utils/fastMode.ts',
  'src/services/mcp/auth.ts',
  'src/services/notifier.ts',
  'src/services/rateLimitMessages.ts',
  'src/skills/bundled/keybindings.ts',
  'src/skills/bundled/scheduleRemoteAgents.ts',
  'src/tools/AskUserQuestionTool/AskUserQuestionTool.tsx',
  'src/tools/BashTool/BashToolResultMessage.tsx',
  'src/tools/BashTool/pathValidation.ts',
  'src/tools/BashTool/readOnlyValidation.ts',
  'src/tools/BriefTool/UI.tsx',
  'src/tools/ConfigTool/ConfigTool.ts',
  'src/tools/ConfigTool/prompt.ts',
  'src/tools/ConfigTool/supportedSettings.ts',
  'src/tools/EnterPlanModeTool/UI.tsx',
  'src/tools/ExitPlanModeTool/UI.tsx',
  'src/tools/PowerShellTool/UI.tsx',
  'src/tools/WebFetchTool/WebFetchTool.ts',
  'src/tools/WebFetchTool/utils.ts',
  'src/tools/WebSearchTool/WebSearchTool.ts',
  'src/tools/WebSearchTool/prompt.ts',
  'src/tools/AgentTool/built-in/claudeCodeGuideAgent.ts',
  'src/tools/AgentTool/built-in/generalPurposeAgent.ts',
  'src/tools/AgentTool/built-in/statuslineSetup.ts',
  'src/utils/permissionMessages.ts',
  'src/utils/permissions/filesystem.ts',
  'src/utils/permissions/permissions.ts',
  'src/utils/preflightChecks.tsx',
  'src/utils/statusNoticeDefinitions.tsx',
  'src/utils/attribution.ts',
  'src/utils/claudeInChrome/common.ts',
  'src/utils/claudeInChrome/mcpServer.ts',
  'src/utils/claudeInChrome/prompt.ts',
  'src/utils/claudeInChrome/setup.ts',
  'src/utils/claudeInChrome/setupPortable.ts',
  'src/utils/claudeInChrome/toolRendering.tsx',
  'src/utils/teleport/api.ts',
  'src/utils/teleport/environments.ts',
  'src/utils/teleport.tsx',
  'src/utils/attachments.ts',
  'src/utils/stats.ts',
  'src/utils/settings/types.ts',
  'src/utils/http.ts',
  'src/utils/windowsPaths.ts',
  'src/skills/bundled/stuck.ts',
]

const githubAppPublicSurfaceFiles = [
  'src/constants/github-app.ts',
  'src/components/WorkflowMultiselectDialog.tsx',
  ...sourceFilesUnder('src/commands/install-github-app'),
]

const shippedSourceFiles = sourceFilesUnder('src')

const bannedProviderSurfaceTokens = [
  'loginWithClaudeAi',
  'getAnthropicApiKey',
  'isAnthropicAuthEnabled',
  'Claude AI',
] as const

const bannedGitHubAppProviderCopy = [
  'ANTHROPIC_API_KEY',
  'CLAUDE_API_KEY',
  'CLAUDE_CODE_OAUTH_TOKEN',
  'FRIENDLI_TOKEN: \\${{ secrets.FRIENDLI_TOKEN }}',
  'secrets.FRIENDLI_TOKEN',
  'anthropic_api_key',
  'claude_code_oauth_token',
  '.github/workflows/claude.yml',
  '.github/workflows/claude-code-review.yml',
  'add-claude-github-actions',
  'selected_claude_workflow',
  'selected_claude_review_workflow',
  'anthropics/claude-cli',
  'github.com/anthropics/claude-code-action',
  'anthropics/claude-code-action',
  'claude-code-action',
  'Claude GitHub App',
  'Claude PR assistance',
  'Claude workflow',
  'Claude Code Review',
  'Claude PR Assistant',
  'A Claude workflow file',
]

function inlineSourceMapContent(source: string): string {
  const marker = 'sourceMappingURL=data:application/json;charset=utf-8;base64,'
  const line = source.split('\n').find(item => item.includes(marker))
  if (!line) return ''

  const encoded = line.slice(line.indexOf(marker) + marker.length).trim()
  const decoded = JSON.parse(Buffer.from(encoded, 'base64').toString('utf8')) as {
    sourcesContent?: string[]
  }
  return decoded.sourcesContent?.join('\n') ?? ''
}

const bannedVisibleCopy = [
  'Create skills by adding .md files to .claude/skills/',
  'Create skills in .claude/skills/',
  'Claude Code needs your input',
  'Claude Code v${MACRO.VERSION}',
  'Claude understands your codebase',
  'What should Claude do instead?',
  'tell Claude what to do differently',
  'while Claude works',
  "interrupting Claude's current work",
  "Claude's current work",
  'Claude is waiting for your input',
  'How well did Claude use its memory',
  "Copy Claude's last response",
  'can only be invoked by Claude',
  'Ask Claude to use',
  'Claude wants to fetch content',
  'Claude requested permissions',
  'Claude wants to search the web',
  'Loading your Claude Code stats',
  'Start using Claude Code',
  'Help improve Claude',
  'How is Claude doing this session',
  'Sign out from your Anthropic account',
  'Successfully logged out from your Anthropic account',
  'Claude is managed by',
  'Claude is up to date',
  'Another Claude process',
  'Claude Code is up to date',
  'next time you start Claude Code',
  'Add an MCP server to Claude Code',
  'Claude Code will automatically update this',
  'power your Claude Code usage',
  'A Claude workflow file',
  'Claude PR Assistant workflow',
  'Claude Code Review workflow',
  'Claude Code installation completed successfully',
  'Claude Code installation failed',
  'Installing Claude Code native build',
  'Claude Code successfully installed',
  'currently installing Claude',
  "Claude Code's client_id",
  'future instances of Claude Code',
  'Claude Chrome Extension',
  'Claude Code year in review animation',
  'Claude Code Insights',
  'How You Use Claude Code',
  'Paste into Claude Code',
  "Claude's Capabilities",
  'Analyze this Claude Code usage data',
  'Analyze this Claude Code session',
  'Summarize this portion of a Claude Code session',
  'winget upgrade Anthropic.ClaudeCode',
  'brew upgrade claude-code',
  'apk upgrade claude-code',
  'Claude is now exploring',
  'User approved Claude',
  'sent to Claude',
  'Claude will think',
  'Claude will respond',
  'Generate with Claude',
  'tells Claude when to use this agent',
  'Claude can delegate to',
  'Claude in Chrome',
  'Claude Code Desktop',
  'Claude Code on the web',
  'Claude on the web',
  'Claude.ai',
  'claude.ai/settings/billing',
  'code.claude.com/docs',
  'docs.claude.com/s/claude-code',
  'claude --help',
  'claude --remote',
  'Anthropic API',
  'Anthropic does not control',
  'Unable to connect to Anthropic services',
  'Claude Code might not be available',
  'Claude Code sessions',
  'Claude in Chrome enabled',
  'Claude Code on Windows requires',
  'Claude Code is unable to fetch',
  'Claude Code is running in don',
  'Share a free week of Claude Code',
  'Generated with [Claude Code]',
  'Return to Claude Code',
  'Claude Code web sessions require',
  'This prompt will launch an ultraplan session in Claude Code',
  'Claude Remote Control',
  'claude remote-control',
  'claude.ai/code',
  'Claude app',
  'Claude account',
  'Generated by Claude Code',
  'Claude Code Browser Extension',
  'Voice mode requires a Claude.ai account',
  'The most recent Claude model',
  'Get help with using Claude Code',
  'You are Claude Code',
  'agent for Claude Code',
  'Claude GitHub App',
  'Claude.ai account',
  'Claude subscription required',
  'claude.ai MCP',
  '--claudeai',
  'add-from-claude-desktop',
  'Claude Desktop',
  'Claude Code Remote session URLs',
  'Get the base URL for Claude AI',
  'Fast mode requires the native binary',
  'Create a new key at https://platform.claude.com/settings/keys',
  'Credit balance too low · Add funds',
  'Failed to open Claude Desktop',
  '*.anthropic.com',
]

const bannedVisibleDomains = [
  'https://claude.ai',
  'https://claude.com',
  'https://platform.claude.com',
  'https://claude-ai.staging.ant.dev',
  'https://clau.de',
  'https://www.anthropic.com',
  'https://anthropic.com',
]

describe('UMMAYA paint surface branding', () => {
  it('keeps migrated visible copy off Claude and Anthropic wording', () => {
    const violations: string[] = []

    for (const file of paintSurfaceFiles) {
      const source = readFileSync(join(ROOT, file), 'utf8')
      for (const phrase of bannedVisibleCopy) {
        if (source.includes(phrase)) {
          violations.push(`${file}: ${phrase}`)
        }
      }
    }

    expect(violations).toEqual([])
  })

  it('keeps migrated visible links off upstream product-owned domains', () => {
    const violations: string[] = []

    for (const file of paintSurfaceFiles) {
      const source = readFileSync(join(ROOT, file), 'utf8')
      for (const domain of bannedVisibleDomains) {
        if (source.includes(domain)) {
          violations.push(`${file}: ${domain}`)
        }
      }
    }

    expect(violations).toEqual([])
  })

  it('keeps the spinner tip source migrated while preserving the CC tip pipeline', () => {
    const registrySource = readFileSync(
      join(ROOT, 'src/services/tips/tipRegistry.ts'),
      'utf8',
    )
    const spinnerSource = readFileSync(join(ROOT, 'src/components/Spinner.tsx'), 'utf8')

    expect(registrySource).toContain(
      'Create UMMAYA skills in your project or user skill directory',
    )
    expect(registrySource).not.toContain('.claude/skills/')
    expect(spinnerSource).toContain("interrupting UMMAYA's current work")
    expect(spinnerSource).not.toContain("interrupting Claude's current work")
  })

  it('blocks upstream provider model notices from the top-of-feed tip slot', () => {
    const sanitized = sanitizeTopOfFeedTipForUmmaya({
      tip: 'Claude Fable 5 is currently unavailable. Please use Opus 4.8 or another available model. Learn more: https://www.anthropic.com/news/fable-mythos-access',
      color: 'warning',
    })

    expect(sanitized.tip).toBe('')
  })

  it('keeps shipped public source free of upstream auth provider tokens', () => {
    const violations: string[] = []

    for (const file of shippedSourceFiles) {
      const source = readFileSync(join(ROOT, file), 'utf8')
      for (const phrase of bannedProviderSurfaceTokens) {
        if (source.includes(phrase)) {
          violations.push(`${file}: ${phrase}`)
        }
      }
    }

    expect(violations).toEqual([])
  })

  it('keeps GitHub App setup on UMMAYA Friendli credentials and workflow names', () => {
    const violations: string[] = []

    for (const file of githubAppPublicSurfaceFiles) {
      const source = readFileSync(join(ROOT, file), 'utf8')
      const searchableSource = `${source}\n${inlineSourceMapContent(source)}`
      for (const phrase of bannedGitHubAppProviderCopy) {
        if (searchableSource.includes(phrase)) {
          violations.push(`${file}: ${phrase}`)
        }
      }
    }

    const githubAppConstants = readFileSync(
      join(ROOT, 'src/constants/github-app.ts'),
      'utf8',
    )

    expect(githubAppConstants).toContain(
      'UMMAYA_FRIENDLI_TOKEN: \\${{ secrets.UMMAYA_FRIENDLI_TOKEN }}',
    )
    expect(githubAppConstants).toContain('jobs:\n  ummaya:')
    expect(githubAppConstants).toContain('jobs:\n  ummaya-review:')
    expect(violations).toEqual([])
  })

  it('keeps shipped public source files free of inline source maps', () => {
    const violations: string[] = []

    for (const file of shippedSourceFiles) {
      const source = readFileSync(join(ROOT, file), 'utf8')
      if (source.includes('sourceMappingURL=data:application/json')) {
        violations.push(file)
      }
    }

    expect(violations).toEqual([])
  })

  it('keeps public WebFetch user agent off upstream client identity', () => {
    const httpSource = readFileSync(join(ROOT, 'src/utils/http.ts'), 'utf8')
    const webFetchUserAgent = httpSource.match(
      /export function getWebFetchUserAgent\(\): string \{[\s\S]*?\n\}/,
    )?.[0]

    expect(webFetchUserAgent).toBeDefined()
    expect(webFetchUserAgent).toContain('UMMAYA-User')
    expect(webFetchUserAgent).toContain('ummaya/${MACRO.VERSION}')
    expect(webFetchUserAgent).not.toContain('getClaudeCodeUserAgent')
    expect(webFetchUserAgent).not.toContain('claude-code')
  })

  it('keeps public CLI help text off upstream internal filenames and env vars', () => {
    const source = readFileSync(join(ROOT, 'src/main.tsx'), 'utf8')
    const bareHelp = source.match(/\.option\('--bare', '([^']+)'/)?.[1] ?? ''

    expect(bareHelp).not.toContain('CLAUDE.md')
    expect(bareHelp).not.toContain('CLAUDE_CODE_SIMPLE')
    expect(source).toContain("mcp.command('add-from-desktop')")
    expect(source).not.toContain("mcp.command('add-from-claude-desktop')")
  })
})
