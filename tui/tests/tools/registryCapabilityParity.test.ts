import { describe, expect, test } from 'bun:test'
import { createHash } from 'node:crypto'
import {
  assembleToolPool,
  getAllBaseTools,
  getTools,
} from '../../src/tools.js'
import { getEmptyToolPermissionContext, type Tools } from '../../src/Tool.js'
import { isDeferredTool } from '../../src/tools/ToolSearchTool/prompt.js'

const defaultModelFacingNames = [
  'ToolSearch',
  'find',
  'locate',
  'send',
  'check',
  'document',
  'workspace_glob',
  'workspace_grep',
  'workspace_read',
  'workspace_write',
  'workspace_edit',
  'workspace_bash',
] as const

const ccSupportCapabilityNames = [
  'Agent',
  'Bash',
  'Read',
  'Edit',
  'Write',
  'Glob',
  'Grep',
  'WebFetch',
  'WebSearch',
  'TodoWrite',
  'ExitPlanMode',
] as const

const rawTierOnePlusAlwaysLoadedNames = [
  'Bash',
  'Edit',
  'Write',
  'NotebookEdit',
  'WebFetch',
  'WebSearch',
  'Agent',
  'TodoWrite',
] as const

function sortedNames(tools: Tools): readonly string[] {
  return tools.map(tool => tool.name).sort((left, right) => left.localeCompare(right))
}

function sortedExpectedNames(names: readonly string[]): readonly string[] {
  return [...names].sort((left, right) => left.localeCompare(right))
}

function digestNames(names: readonly string[]): string {
  return createHash('sha256').update(names.join('\n')).digest('hex')
}

function withEnv<T>(name: string, value: string | undefined, run: () => T): T {
  const previous = process.env[name]
  if (value === undefined) {
    delete process.env[name]
  } else {
    process.env[name] = value
  }
  try {
    return run()
  } finally {
    if (previous === undefined) {
      delete process.env[name]
    } else {
      process.env[name] = previous
    }
  }
}

describe('registry capability parity', () => {
  test('keeps_ax_primitives_default_while_registering_cc_capabilities', () => {
    const permissionContext = getEmptyToolPermissionContext()

    const registeredNames = sortedNames(getAllBaseTools())
    const modelFacingNames = sortedNames(getTools(permissionContext))
    const assembledNames = sortedNames(assembleToolPool(permissionContext, []))

    expect(modelFacingNames).toEqual(sortedExpectedNames(defaultModelFacingNames))
    expect(assembledNames).toEqual(sortedExpectedNames(defaultModelFacingNames))
    for (const rawToolName of ccSupportCapabilityNames) {
      expect(modelFacingNames).not.toContain(rawToolName)
      expect(assembledNames).not.toContain(rawToolName)
    }

    expect(registeredNames).toEqual(
      expect.arrayContaining([...ccSupportCapabilityNames]),
    )

    const modelFacingTools = getTools(permissionContext)
    const alwaysLoadedViolations = modelFacingTools.filter(
      tool =>
        !isDeferredTool(tool) &&
        rawTierOnePlusAlwaysLoadedNames.includes(
          tool.name as (typeof rawTierOnePlusAlwaysLoadedNames)[number],
        ),
    )
    expect(alwaysLoadedViolations.map(tool => tool.name)).toEqual([])

    expect(digestNames(modelFacingNames)).toBe(digestNames(assembledNames))
  })

  test('keeps_ax_primitives_when_cc_support_kill_switch_is_disabled', () => {
    withEnv('UMMAYA_ENABLE_CC_SUPPORT_TOOLS', '0', () => {
      const registeredNames = sortedNames(getAllBaseTools())
      const modelFacingNames = sortedNames(getTools(getEmptyToolPermissionContext()))

      expect(modelFacingNames).toEqual(sortedExpectedNames(defaultModelFacingNames))
      for (const rawToolName of ccSupportCapabilityNames) {
        expect(registeredNames).not.toContain(rawToolName)
      }
      expect(registeredNames).toEqual(
        expect.arrayContaining([...defaultModelFacingNames]),
      )
    })
  })
})
