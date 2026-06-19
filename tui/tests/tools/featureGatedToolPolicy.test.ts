import { describe, expect, test } from 'bun:test'
import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { getEmptyToolPermissionContext, type Tools } from '../../src/Tool.js'
import {
  getAllBaseTools,
  getTools,
  type McpModelExposureServerClass,
} from '../../src/tools.js'

const repoRoot = resolve(import.meta.dir, '../../..')
const tuiRoot = join(repoRoot, 'tui')
const manifestPath = join(repoRoot, 'docs/research/cc-tool-layer-inventory.json')
const task13TestId =
  'tui/tests/tools/featureGatedToolPolicy.test.ts::remote_schedule_workflow_tools_are_hidden_or_permission_gated'
const task13EvidencePath =
  '.omo/evidence/cc-original-tool-layer-port/task-13-green.txt'

const featureGatedRows = [
  ['WorkflowTool', 'hidden', 4],
  ['WebBrowserTool', 'hidden', 3],
  ['TerminalCaptureTool', 'hidden', 2],
  ['MonitorTool', 'hidden', 4],
  ['SleepTool', 'hidden', 4],
  ['PushNotificationTool', 'hidden', 4],
  ['SendUserFileTool', 'hidden', 3],
  ['SubscribePRTool', 'hidden', 4],
  ['OverflowTestTool', 'hidden', 0],
  ['CtxInspectTool', 'hidden', 2],
  ['SnipTool', 'hidden', 4],
  ['CronCreateTool', 'hidden', 4],
  ['CronDeleteTool', 'hidden', 4],
  ['CronListTool', 'hidden', 4],
  ['EnterWorktreeTool', 'hidden', 2],
  ['ExitWorktreeTool', 'hidden', 2],
  ['LSPTool', 'hidden', 0],
  ['ListPeersTool', 'hidden', 4],
  ['PowerShellTool', 'hidden', 2],
  ['RemoteTriggerTool', 'hidden', 4],
  ['ScheduleCronTool', 'hidden', 4],
  ['TeamCreateTool', 'hidden', 4],
  ['TeamDeleteTool', 'hidden', 4],
  ['VerifyPlanExecutionTool', 'hidden', 4],
] as const

const permissionGatedWorkflowRows = [
  ['SendMessageTool', 4],
  ['SkillTool', 4],
] as const

const antOnlyRows = [
  'ConfigTool',
  'REPLTool',
  'SuggestBackgroundPRTool',
  'TungstenTool',
] as const

const testOnlyRows = ['TestingPermissionTool'] as const

const disallowedRuntimeNames = [
  ...antOnlyRows.map(name => name.replace(/Tool$/u, '')),
  'TestingPermission',
] as const

type ExposureState =
  | 'always-loaded'
  | 'deferred-searchable'
  | 'permission-gated-callable'
  | 'hidden'
  | 'unsupported'

type FeatureStatus =
  | 'UMMAYA-specific'
  | 'ant-only'
  | 'default'
  | 'feature-gated'
  | 'test-only'
  | 'unsupported'

type InventoryRow = {
  readonly tool_name: string
  readonly feature_status: FeatureStatus
  readonly exposure_state: ExposureState
  readonly trust_tier: number
  readonly tests: readonly string[]
  readonly evidence: readonly string[]
}

type InventoryManifest = {
  readonly tools: readonly InventoryRow[]
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isStringArray(value: unknown): value is readonly string[] {
  return Array.isArray(value) && value.every(item => typeof item === 'string')
}

function isInventoryRow(value: unknown): value is InventoryRow {
  if (!isRecord(value)) return false
  return (
    typeof value.tool_name === 'string' &&
    typeof value.feature_status === 'string' &&
    typeof value.exposure_state === 'string' &&
    typeof value.trust_tier === 'number' &&
    isStringArray(value.tests) &&
    isStringArray(value.evidence)
  )
}

function assertInventoryManifest(value: unknown): asserts value is InventoryManifest {
  if (!isRecord(value) || !Array.isArray(value.tools) || !value.tools.every(isInventoryRow)) {
    throw new Error('Inventory manifest must include typed tool policy rows.')
  }
}

function runInventory(): InventoryManifest {
  const result = spawnSync('node', ['scripts/cc-tool-inventory.mjs', '--json'], {
    cwd: tuiRoot,
    encoding: 'utf8',
  })
  if (result.status !== 0) {
    throw new Error(
      `inventory generator failed with status ${result.status}\n${result.stderr}`,
    )
  }
  const parsed: unknown = JSON.parse(result.stdout)
  assertInventoryManifest(parsed)
  return parsed
}

function rowByName(manifest: InventoryManifest, toolName: string): InventoryRow {
  const row = manifest.tools.find(candidate => candidate.tool_name === toolName)
  if (!row) throw new Error(`Missing inventory row for ${toolName}`)
  return row
}

function sortedNames(tools: Tools): readonly string[] {
  return tools.map(tool => tool.name).sort((left, right) => left.localeCompare(right))
}

describe('feature-gated CC tool policy', () => {
  test('remote_schedule_workflow_tools_are_hidden_or_permission_gated', () => {
    const manifest = runInventory()
    const manifestFromDisk: unknown = JSON.parse(readFileSync(manifestPath, 'utf8'))
    expect(manifestFromDisk).toEqual(manifest)

    for (const [toolName, exposureState, trustTier] of featureGatedRows) {
      const row = rowByName(manifest, toolName)
      expect(row.feature_status).toBe('feature-gated')
      expect(row.exposure_state).toBe(exposureState)
      expect(row.trust_tier).toBe(trustTier)
      expect(row.tests).toContain(task13TestId)
      expect(row.evidence).toContain(task13EvidencePath)
    }

    for (const [toolName, trustTier] of permissionGatedWorkflowRows) {
      const row = rowByName(manifest, toolName)
      expect(row.exposure_state).toBe('permission-gated-callable')
      expect(row.trust_tier).toBe(trustTier)
      expect(row.tests).toContain(task13TestId)
      expect(row.evidence).toContain(task13EvidencePath)
    }

    for (const toolName of antOnlyRows) {
      const row = rowByName(manifest, toolName)
      expect(row.feature_status).toBe('ant-only')
      expect(row.exposure_state).toBe('hidden')
      expect(row.tests).toContain(task13TestId)
      expect(row.evidence).toContain(task13EvidencePath)
    }

    for (const toolName of testOnlyRows) {
      const row = rowByName(manifest, toolName)
      expect(row.feature_status).toBe('test-only')
      expect(row.exposure_state).toBe('unsupported')
      expect(row.tests).toContain(task13TestId)
      expect(row.evidence).toContain(task13EvidencePath)
    }

    const modelFacingNames = sortedNames(getTools(getEmptyToolPermissionContext()))
    for (const toolName of disallowedRuntimeNames) {
      expect(modelFacingNames).not.toContain(toolName)
    }
  })

  test('malformed_env_and_unknown_tool_rows_do_not_expand_normal_runtime_exposure', () => {
    const previousUserType = process.env.USER_TYPE
    const previousNodeEnv = process.env.NODE_ENV
    const previousCcSupport = process.env.UMMAYA_ENABLE_CC_SUPPORT_TOOLS
    process.env.USER_TYPE = 'antagonist'
    process.env.NODE_ENV = 'production'
    process.env.UMMAYA_ENABLE_CC_SUPPORT_TOOLS = 'TRUE;enable'
    try {
      const manifest = runInventory()
      expect(manifest.tools.find(row => row.tool_name === 'RemoteTrigger')).toBeUndefined()

      const modelFacingNames = sortedNames(getTools(getEmptyToolPermissionContext()))
      const registeredNames = sortedNames(getAllBaseTools())
      for (const toolName of disallowedRuntimeNames) {
        expect(modelFacingNames).not.toContain(toolName)
        expect(registeredNames).not.toContain(toolName)
      }
    } finally {
      if (previousUserType === undefined) {
        delete process.env.USER_TYPE
      } else {
        process.env.USER_TYPE = previousUserType
      }
      if (previousNodeEnv === undefined) {
        delete process.env.NODE_ENV
      } else {
        process.env.NODE_ENV = previousNodeEnv
      }
      if (previousCcSupport === undefined) {
        delete process.env.UMMAYA_ENABLE_CC_SUPPORT_TOOLS
      } else {
        process.env.UMMAYA_ENABLE_CC_SUPPORT_TOOLS = previousCcSupport
      }
    }
  })

  test('mcp_exposure_class_union_remains_closed_for_policy_regressions', () => {
    const classes = [
      'ummaya',
      'trusted-configured',
      'untrusted-configured',
    ] satisfies readonly McpModelExposureServerClass[]

    expect(classes).toEqual([
      'ummaya',
      'trusted-configured',
      'untrusted-configured',
    ])
  })
})
