import { afterEach, beforeEach, describe, expect, test } from 'bun:test'
import { readdir, readFile } from 'node:fs/promises'
import { basename, join } from 'node:path'
import {
  resetStateForTests,
  setIsInteractive,
} from '../../bootstrap/state.js'
import { inputSchema } from './schemas.js'

const AGENT_TOOL_DIR = join(process.cwd(), 'src/tools/AgentTool')
const FORK_FEATURE_ENV = 'CLAUDE_CODE_FEATURE_FORK_SUBAGENT'
const REQUIRED_CORE_MODULES = [
  'schemas.ts',
  'launchRouting.ts',
  'lifecycle.ts',
  'resultMapping.ts',
  'permissions.ts',
] as const

function pureLoc(source: string): number {
  return source
    .split('\n')
    .filter(line => {
      const trimmed = line.trim()
      return trimmed.length > 0 && !trimmed.startsWith('//')
    }).length
}

describe('AgentTool core split contract', () => {
  let previousForkFeature: string | undefined

  beforeEach(() => {
    previousForkFeature = process.env[FORK_FEATURE_ENV]
    delete process.env[FORK_FEATURE_ENV]
    resetStateForTests()
  })

  afterEach(() => {
    if (previousForkFeature === undefined) {
      delete process.env[FORK_FEATURE_ENV]
    } else {
      process.env[FORK_FEATURE_ENV] = previousForkFeature
    }
    resetStateForTests()
  })

  test('AgentTool shell stays small and core responsibilities live in modules', async () => {
    const entries = new Set(await readdir(AGENT_TOOL_DIR))
    const missingModules = REQUIRED_CORE_MODULES.filter(
      moduleName => !entries.has(moduleName),
    )
    const shellSource = await readFile(
      join(AGENT_TOOL_DIR, 'AgentTool.tsx'),
      'utf8',
    )

    expect(missingModules).toEqual([])
    expect(pureLoc(shellSource)).toBeLessThanOrEqual(250)

    for (const moduleName of REQUIRED_CORE_MODULES) {
      const moduleSource = await readFile(join(AGENT_TOOL_DIR, moduleName), 'utf8')
      expect(pureLoc(moduleSource), basename(moduleName)).toBeLessThanOrEqual(
        250,
      )
    }
  })

  test('fork subagent schema omits explicit background knob after prior schema access', async () => {
    // Given: the normal Agent schema has already been read in this process.
    setIsInteractive(true)

    const foregroundParsed = inputSchema().safeParse({
      description: 'Collect proof',
      prompt: 'Verify AgentTool schema parity.',
      run_in_background: true,
    })

    if (!foregroundParsed.success) {
      throw new Error('AgentTool schema rejected valid foreground input')
    }

    expect(Object.hasOwn(foregroundParsed.data, 'run_in_background')).toBe(true)

    // When: fork subagent mode becomes the active schema gate.
    process.env[FORK_FEATURE_ENV] = '1'

    const forkParsed = inputSchema().safeParse({
      description: 'Collect proof',
      prompt: 'Verify AgentTool schema parity.',
      run_in_background: true,
    })

    if (!forkParsed.success) {
      throw new Error('AgentTool schema rejected valid fork input')
    }

    // Then: stale foreground schema state cannot re-expose the background knob.
    expect(Object.hasOwn(forkParsed.data, 'run_in_background')).toBe(false)
  })
})
