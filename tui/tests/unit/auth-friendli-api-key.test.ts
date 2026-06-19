// SPDX-License-Identifier: Apache-2.0
// FriendliAI credential tests using the CC auth.ts API-key surface.

import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  mock,
  spyOn,
  type Mock,
} from 'bun:test'
import { createHash } from 'node:crypto'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const TUI_ROOT = join(__dirname, '../..')
const TEST_UMMAYA_CONFIG_DIR = '/tmp/ummaya-auth-config'
const TEST_LEGACY_CLAUDE_CONFIG_DIR = '/tmp/claude-auth-config'

type ExecaOptions = {
  readonly input?: string
  readonly reject?: boolean
  readonly shell?: boolean
}

type ExecaCall = {
  readonly file: string
  readonly args: readonly string[]
  readonly options: ExecaOptions
}

type ExecaResult = {
  readonly exitCode: number
  readonly stdout: string
  readonly stderr: string
}

const execaCalls: ExecaCall[] = []
const execaSyncCalls: ExecaCall[] = []
let keychainStoredValue: string | null = null
let keychainWriteSucceeds = true
let keychainReadSucceeds = true

function decodeHexFromSecurityInput(input: string): string | null {
  const match = input.match(/ -X "([0-9a-f]+)"/)
  const hex = match?.[1]
  return hex ? Buffer.from(hex, 'hex').toString('utf8') : null
}

function makeResult(exitCode: number, stdout = ''): ExecaResult {
  return { exitCode, stdout, stderr: '' }
}

const execaMock: Mock<
  (
    file: string,
    argsOrOptions?: readonly string[] | ExecaOptions,
    maybeOptions?: ExecaOptions,
  ) => Promise<ExecaResult>
> = mock(async (file, argsOrOptions = [], maybeOptions = {}) => {
  const args = Array.isArray(argsOrOptions) ? argsOrOptions : []
  const options = Array.isArray(argsOrOptions) ? maybeOptions : argsOrOptions
  execaCalls.push({ file, args, options })

  if (file === 'security' && args.join(' ') === '-i') {
    if (!keychainWriteSucceeds) return makeResult(1)
    const input = options.input ?? ''
    keychainStoredValue = decodeHexFromSecurityInput(input)
    return makeResult(0)
  }

  if (file === 'security' && args.includes('delete-generic-password')) {
    keychainStoredValue = null
    return makeResult(0)
  }

  return makeResult(0)
})

const execaSyncMock: Mock<
  (file: string, args?: readonly string[], options?: ExecaOptions) => ExecaResult
> = mock((file, args = [], options = {}) => {
  execaSyncCalls.push({ file, args, options })
  if (
    file === 'security' &&
    args.includes('find-generic-password') &&
    keychainReadSucceeds &&
    keychainStoredValue
  ) {
    return makeResult(0, keychainStoredValue)
  }
  return makeResult(44)
})

mock.module('execa', () => ({
  execa: execaMock,
  execaSync: execaSyncMock,
}))

const auth = await import(join(TUI_ROOT, 'src/utils/auth.js'))
const config = await import(join(TUI_ROOT, 'src/utils/config.js'))

const {
  FRIENDLI_LOGIN_REQUIRED_MESSAGE,
  FRIENDLI_PRIMARY_ENV,
  assertFriendliApiKeyForUse,
  clearApiKeyHelperCache,
  getAnthropicApiKeyWithSource,
  removeApiKey,
  saveApiKey,
} = auth

const { getGlobalConfig } = config

const savedEnv: Record<string, string | undefined> = {}
let platformSpy: ReturnType<typeof spyOn>

function expectedConfigHash(): string {
  return createHash('sha256')
    .update(TEST_UMMAYA_CONFIG_DIR.normalize('NFC'))
    .digest('hex')
    .substring(0, 16)
}

function expectedServiceName(): string {
  return `UMMAYA FriendliAI API Key (${expectedConfigHash()})`
}

function expectedAccountName(): string {
  return `ummaya-friendli:${expectedConfigHash()}`
}

function resetCallReceipts(): void {
  execaCalls.length = 0
  execaSyncCalls.length = 0
  execaMock.mockClear()
  execaSyncMock.mockClear()
}

function seedStaleConfig(apiKey: string): void {
  config.saveGlobalConfig(current => ({
    ...current,
    primaryApiKey: apiKey,
  }))
  clearApiKeyHelperCache()
}

beforeEach(async () => {
  savedEnv.NODE_ENV = process.env.NODE_ENV
  savedEnv[FRIENDLI_PRIMARY_ENV] = process.env[FRIENDLI_PRIMARY_ENV]
  savedEnv.UMMAYA_CONFIG_DIR = process.env.UMMAYA_CONFIG_DIR
  savedEnv.CLAUDE_CONFIG_DIR = process.env.CLAUDE_CONFIG_DIR
  process.env.NODE_ENV = 'test'
  process.env.UMMAYA_CONFIG_DIR = TEST_UMMAYA_CONFIG_DIR
  process.env.CLAUDE_CONFIG_DIR = TEST_LEGACY_CLAUDE_CONFIG_DIR
  delete process.env[FRIENDLI_PRIMARY_ENV]
  platformSpy = spyOn(process, 'platform', 'get').mockReturnValue('darwin')
  keychainStoredValue = null
  keychainWriteSucceeds = true
  keychainReadSucceeds = true
  await removeApiKey()
  resetCallReceipts()
})

afterEach(async () => {
  process.env.NODE_ENV = 'test'
  await removeApiKey()
  platformSpy.mockRestore()
  for (const key of [
    'NODE_ENV',
    FRIENDLI_PRIMARY_ENV,
    'UMMAYA_CONFIG_DIR',
    'CLAUDE_CONFIG_DIR',
  ] as const) {
    const value = savedEnv[key]
    if (value === undefined) {
      delete process.env[key]
    } else {
      process.env[key] = value
    }
  }
  resetCallReceipts()
})

describe('auth.ts FriendliAI API-key swap', () => {
  it('treats UMMAYA_FRIENDLI_TOKEN as the primary key without reading keychain or config', () => {
    // Given
    seedStaleConfig('stale-config-token')
    keychainStoredValue = 'saved-keychain-token'
    process.env[FRIENDLI_PRIMARY_ENV] = 'env-token'
    resetCallReceipts()

    // When
    const result = getAnthropicApiKeyWithSource()

    // Then
    expect(result).toEqual({ key: 'env-token', source: FRIENDLI_PRIMARY_ENV })
    expect(assertFriendliApiKeyForUse()).toBe('env-token')
    expect(execaSyncCalls).toHaveLength(0)
  })

  it('persists /login keys in the UMMAYA macOS Keychain without plaintext config storage', async () => {
    // Given
    const token = 'saved-keychain-token'

    // When
    await saveApiKey(`  ${token}  `)

    // Then
    expect(process.env[FRIENDLI_PRIMARY_ENV]).toBe(token)
    expect(getGlobalConfig().primaryApiKey).toBeUndefined()
    expect(execaCalls).toHaveLength(1)
    expect(execaCalls[0]).toMatchObject({
      file: 'security',
      args: ['-i'],
    })
    expect(execaCalls[0]?.args.join(' ')).not.toContain(token)
    expect(execaCalls[0]?.options.input).not.toContain(token)
    expect(execaCalls[0]?.options.input).toContain(Buffer.from(token).toString('hex'))

    delete process.env[FRIENDLI_PRIMARY_ENV]
    expect(getAnthropicApiKeyWithSource()).toEqual({
      key: token,
      source: '/login managed key',
    })
  })

  it('uses a UMMAYA-scoped keychain service and account that honors UMMAYA_CONFIG_DIR', async () => {
    // Given
    const token = 'namespace-token'

    // When
    await saveApiKey(token)

    // Then
    const input = execaCalls[0]?.options.input ?? ''
    expect(input).toContain(`-a "${expectedAccountName()}"`)
    expect(input).toContain(`-s "${expectedServiceName()}"`)
    expect(input).not.toContain('Claude Code')
    expect(input).not.toContain(TEST_LEGACY_CLAUDE_CONFIG_DIR)
  })

  it('prefers the UMMAYA keychain value over stale config when env is absent', () => {
    // Given
    keychainStoredValue = 'fresh-keychain-token'
    seedStaleConfig('stale-config-token')
    resetCallReceipts()

    // When
    const result = getAnthropicApiKeyWithSource()

    // Then
    expect(result).toEqual({
      key: 'fresh-keychain-token',
      source: '/login managed key',
    })
    expect(execaSyncCalls[0]).toMatchObject({
      file: 'security',
      args: [
        'find-generic-password',
        '-a',
        expectedAccountName(),
        '-w',
        '-s',
        expectedServiceName(),
      ],
    })
  })

  it('falls back to config when keychain read is missing or failing', () => {
    // Given
    keychainReadSucceeds = false
    seedStaleConfig('fallback-config-token')
    resetCallReceipts()

    // When
    const result = getAnthropicApiKeyWithSource()

    // Then
    expect(result).toEqual({
      key: 'fallback-config-token',
      source: '/login managed key',
    })
    expect(execaSyncCalls).toHaveLength(1)
  })

  it('falls back to plaintext config when keychain write fails', async () => {
    // Given
    const token = 'write-fallback-token'
    keychainWriteSucceeds = false

    // When
    await saveApiKey(token)

    // Then
    expect(getGlobalConfig().primaryApiKey).toBe(token)
    delete process.env[FRIENDLI_PRIMARY_ENV]
    expect(getAnthropicApiKeyWithSource()).toEqual({
      key: token,
      source: '/login managed key',
    })
  })

  it('removes env, keychain, config, and cached key material', async () => {
    // Given
    await saveApiKey('remove-token')
    delete process.env[FRIENDLI_PRIMARY_ENV]
    expect(getAnthropicApiKeyWithSource().key).toBe('remove-token')
    resetCallReceipts()

    // When
    await removeApiKey()

    // Then
    expect(process.env[FRIENDLI_PRIMARY_ENV]).toBeUndefined()
    expect(keychainStoredValue).toBeNull()
    expect(getGlobalConfig().primaryApiKey).toBeUndefined()
    expect(getAnthropicApiKeyWithSource()).toEqual({ key: null, source: 'none' })
    expect(
      execaCalls.some(
        call =>
          call.file === 'security' &&
          call.args.includes('delete-generic-password'),
      ),
    ).toBe(true)
  })

  it('fails closed when no FriendliAI key is present', () => {
    // Given
    resetCallReceipts()

    // When / Then
    expect(() => assertFriendliApiKeyForUse()).toThrow(FRIENDLI_LOGIN_REQUIRED_MESSAGE)
  })

  it('rejects empty and multiline /login keys', async () => {
    // Given / When / Then
    await expect(saveApiKey('   ')).rejects.toThrow('must not be empty')
    await expect(saveApiKey('key\nsecond-line')).rejects.toThrow('single line')
  })
})
