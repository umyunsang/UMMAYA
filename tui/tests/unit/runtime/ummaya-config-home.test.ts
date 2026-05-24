import { afterEach, describe, expect, it } from 'bun:test'
import { homedir } from 'os'
import { join } from 'path'
import { getGlobalClaudeFile } from '../../../src/utils/env.js'
import { getClaudeConfigHomeDir } from '../../../src/utils/envUtils.js'

function clearMemoized(fn: { cache?: { clear?: () => void } }): void {
  fn.cache?.clear?.()
}

function clearConfigPathCaches(): void {
  clearMemoized(
    getClaudeConfigHomeDir as typeof getClaudeConfigHomeDir & {
      cache?: { clear?: () => void }
    },
  )
  clearMemoized(
    getGlobalClaudeFile as typeof getGlobalClaudeFile & {
    cache?: { clear?: () => void }
    },
  )
}

describe('UMMAYA config home boundary', () => {
  afterEach(() => {
    delete process.env.UMMAYA_CONFIG_DIR
    delete process.env.CLAUDE_CONFIG_DIR
    clearConfigPathCaches()
  })

  it('stores runtime state under ~/.ummaya by default', () => {
    clearConfigPathCaches()

    expect(getClaudeConfigHomeDir()).toBe(join(homedir(), '.ummaya').normalize('NFC'))
    expect(getGlobalClaudeFile()).toBe(
      join(homedir(), '.ummaya', '.config.json').normalize('NFC'),
    )
  })

  it('prefers UMMAYA_CONFIG_DIR over the legacy Claude config override', () => {
    process.env.CLAUDE_CONFIG_DIR = '/tmp/legacy-claude-config'
    process.env.UMMAYA_CONFIG_DIR = '/tmp/ummaya-config'
    clearConfigPathCaches()

    expect(getClaudeConfigHomeDir()).toBe('/tmp/ummaya-config')
    expect(getGlobalClaudeFile()).toBe('/tmp/ummaya-config/.config.json')
  })

  it('does not fall back to the legacy ~/.claude.json auth file', () => {
    clearConfigPathCaches()

    expect(getGlobalClaudeFile()).not.toBe(
      join(homedir(), '.claude.json').normalize('NFC'),
    )
  })
})
