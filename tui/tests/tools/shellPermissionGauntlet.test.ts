import { describe, expect, test } from 'bun:test'
import type { Tool, ToolPermissionContext, ToolUseContext } from '../../src/Tool.js'
import { getEmptyToolPermissionContext } from '../../src/Tool.js'
import { getDefaultAppState, type AppState } from '../../src/state/AppStateStore.js'
import { BashTool } from '../../src/tools/BashTool/BashTool.js'
import { getDestructiveCommandWarning as getBashDestructiveCommandWarning } from '../../src/tools/BashTool/destructiveCommandWarning.js'
import { PowerShellTool } from '../../src/tools/PowerShellTool/PowerShellTool.js'
import { getDestructiveCommandWarning as getPowerShellDestructiveCommandWarning } from '../../src/tools/PowerShellTool/destructiveCommandWarning.js'
import { getReplPrimitiveTools } from '../../src/tools/REPLTool/primitiveTools.js'
import { REPLTool } from '../../src/tools/REPLTool/REPLTool.js'
import { getWorkspaceTools } from '../../src/tools/WorkspaceToolAdapter/WorkspaceToolAdapter.js'
import type { AssistantMessage } from '../../src/types/message.js'
import {
  createFileStateCacheWithSizeLimit,
  READ_FILE_STATE_CACHE_SIZE,
} from '../../src/utils/fileStateCache.js'
import { hasPermissionsToUseTool } from '../../src/utils/permissions/permissions.js'

type ShellInput = {
  readonly command: string
  readonly timeout?: number
  readonly run_in_background?: boolean
  readonly dangerouslyDisableSandbox?: boolean
}

function shellPermissionContext(mode: ToolPermissionContext['mode']): ToolPermissionContext {
  return {
    ...getEmptyToolPermissionContext(),
    mode,
    isBypassPermissionsModeAvailable: mode === 'bypassPermissions',
  }
}

function toolUseContextFor(
  toolPermissionContext: ToolPermissionContext,
  tools: readonly Tool[],
): ToolUseContext {
  let appState: AppState = {
    ...getDefaultAppState(),
    toolPermissionContext,
    mcp: { clients: [] },
  }

  return {
    abortController: new AbortController(),
    options: {
      commands: [],
      debug: false,
      mainLoopModel: 'test-model',
      isNonInteractiveSession: false,
      tools,
      verbose: false,
      thinkingConfig: { type: 'disabled' },
      mcpClients: [],
      mcpResources: {},
      agentDefinitions: { activeAgents: [], allAgents: [] },
    },
    readFileState: createFileStateCacheWithSizeLimit(READ_FILE_STATE_CACHE_SIZE),
    getAppState: () => appState,
    setAppState: update => {
      appState = update(appState)
    },
    setInProgressToolUseIDs: () => {},
    setResponseLength: () => {},
    updateFileHistoryState: () => {},
    updateAttributionState: () => {},
    messages: [],
  } satisfies ToolUseContext
}

async function permissionDecision(
  tool: Tool,
  input: ShellInput,
  mode: ToolPermissionContext['mode'] = 'default',
) {
  const context = toolUseContextFor(shellPermissionContext(mode), [
    BashTool,
    PowerShellTool,
    tool,
  ])
  const assistantMessage: AssistantMessage = {
    role: 'assistant',
    content: [{ type: 'text', text: 'shell permission gauntlet' }],
  }

  return hasPermissionsToUseTool(
    tool,
    { ...input },
    context,
    assistantMessage,
    `toolu_task10_${tool.name}`,
  )
}

function contentText(content: unknown): string {
  if (typeof content === 'string') return content
  if (!Array.isArray(content)) return ''
  return content
    .map(item => {
      if (typeof item === 'string') return item
      if (typeof item !== 'object' || item === null) return ''
      if (!('text' in item)) return ''
      return typeof item.text === 'string' ? item.text : ''
    })
    .join('\n')
}

function workspaceBashTool(): Tool {
  const tool = getWorkspaceTools().find(candidate => candidate.name === 'workspace_bash')
  if (!tool) throw new Error('workspace_bash must be registered')
  return tool
}

describe('shell permission gauntlet', () => {
  test('pins current read-only shell command classification', () => {
    expect(BashTool.isReadOnly({ command: 'git status --short' })).toBe(true)
    expect(BashTool.isReadOnly({ command: 'find . -name "*.ts"' })).toBe(true)
    expect(BashTool.isReadOnly({ command: 'rm -rf ./tmp' })).toBe(false)
    expect(PowerShellTool.isReadOnly({ command: 'Get-ChildItem .' })).toBe(false)
    expect(PowerShellTool.isReadOnly({ command: 'Remove-Item ./tmp -Force' })).toBe(false)
    expect(workspaceBashTool().isReadOnly({ command: 'ls -la' })).toBe(true)
  })

  test('requires_permission_for_shell_and_warns_destructive_commands', async () => {
    const bashDecision = await permissionDecision(BashTool, {
      command: 'git reset --hard HEAD',
    })
    const workspaceDecision = await permissionDecision(workspaceBashTool(), {
      command: 'rm -rf ./tmp',
    })
    const powerShellDecision = await permissionDecision(PowerShellTool, {
      command: 'Remove-Item -Recurse -Force ./tmp',
    })

    expect(bashDecision.behavior).toBe('ask')
    expect(workspaceDecision.behavior).toBe('ask')
    expect(powerShellDecision.behavior).toBe('ask')
    expect(getBashDestructiveCommandWarning('git reset --hard HEAD')).toContain(
      'discard',
    )
    expect(
      getPowerShellDestructiveCommandWarning(
        'Remove-Item -Recurse -Force ./tmp',
      ),
    ).toContain('recursively')
    expect(REPLTool.isEnabled()).toBe(false)
    expect(getReplPrimitiveTools().map(tool => tool.name)).toContain(BashTool.name)
  })

  test('shows_long_command_visibility_and_cancel_boundary', () => {
    const longCommand = `printf '${'x'.repeat(220)}'`
    const summary = BashTool.getToolUseSummary?.({ command: longCommand })
    const backgroundResult = BashTool.mapToolResultToToolResultBlockParam(
      {
        stdout: '',
        stderr: '',
        interrupted: false,
        backgroundTaskId: 'task-10-bg',
        assistantAutoBackgrounded: true,
      },
      'toolu_task10_background',
    )
    const cancelResult = BashTool.mapToolResultToToolResultBlockParam(
      {
        stdout: '',
        stderr: '',
        interrupted: true,
      },
      'toolu_task10_cancel',
    )

    expect(summary?.length).toBeLessThan(longCommand.length)
    expect(contentText(backgroundResult.content)).toContain('moved to the background')
    expect(contentText(backgroundResult.content)).toContain('still running')
    expect(cancelResult.is_error).toBe(true)
    expect(contentText(cancelResult.content)).toContain('aborted before completion')
  })

  test('blocks_bypass_permissions_for_destructive_or_protected_shell_classes', async () => {
    const bashDestructive = await permissionDecision(
      BashTool,
      { command: 'git reset --hard HEAD' },
      'bypassPermissions',
    )
    const bashProtectedAx = await permissionDecision(
      BashTool,
      { command: 'curl https://api.data.go.kr/openapi/service' },
      'bypassPermissions',
    )
    const workspaceProtectedAx = await permissionDecision(
      workspaceBashTool(),
      { command: 'curl https://www.gov.kr/portal/main' },
      'bypassPermissions',
    )
    const powerShellProtectedAx = await permissionDecision(
      PowerShellTool,
      { command: 'Invoke-WebRequest https://www.hometax.go.kr/' },
      'bypassPermissions',
    )

    for (const decision of [
      bashDestructive,
      bashProtectedAx,
      workspaceProtectedAx,
      powerShellProtectedAx,
    ]) {
      expect(decision.behavior).toBe('ask')
      expect(decision.decisionReason?.type).toBe('safetyCheck')
    }
  })
})
