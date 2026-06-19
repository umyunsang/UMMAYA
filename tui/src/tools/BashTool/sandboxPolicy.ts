import { createRequire } from 'node:module'

type SandboxInput = {
  readonly command?: string
  readonly dangerouslyDisableSandbox?: boolean
}

type ShouldUseSandbox = (input: SandboxInput) => boolean
type ShellSandboxManager = {
  readonly annotateStderrWithSandboxFailures: (
    command: string,
    stderr: string,
  ) => string
  readonly isSandboxEnabledInSettings: () => boolean
  readonly areUnsandboxedCommandsAllowed: () => boolean
}

const requireModule = createRequire(import.meta.url)
let cachedShouldUseSandbox: ShouldUseSandbox | undefined
let cachedSandboxManager: ShellSandboxManager | undefined

function isSandboxModule(
  value: unknown,
): value is { readonly shouldUseSandbox: ShouldUseSandbox } {
  if (typeof value !== 'object' || value === null) return false
  const module = value as { readonly shouldUseSandbox?: unknown }
  return typeof module.shouldUseSandbox === 'function'
}

export function shouldUseSandboxForShell(input: SandboxInput): boolean {
  if (cachedShouldUseSandbox !== undefined) return cachedShouldUseSandbox(input)
  const loaded: unknown = requireModule('./shouldUseSandbox.js')
  if (!isSandboxModule(loaded)) {
    throw new Error('Bash sandbox policy module did not expose shouldUseSandbox')
  }
  cachedShouldUseSandbox = loaded.shouldUseSandbox
  return loaded.shouldUseSandbox(input)
}

function isSandboxAdapterModule(
  value: unknown,
): value is { readonly SandboxManager: ShellSandboxManager } {
  if (typeof value !== 'object' || value === null) return false
  const module = value as { readonly SandboxManager?: unknown }
  if (typeof module.SandboxManager !== 'object' || module.SandboxManager === null) {
    return false
  }
  const manager = module.SandboxManager as Partial<ShellSandboxManager>
  return (
    typeof manager.annotateStderrWithSandboxFailures === 'function' &&
    typeof manager.isSandboxEnabledInSettings === 'function' &&
    typeof manager.areUnsandboxedCommandsAllowed === 'function'
  )
}

function loadSandboxManager(): ShellSandboxManager {
  if (cachedSandboxManager !== undefined) return cachedSandboxManager
  const loaded: unknown = requireModule('../../utils/sandbox/sandbox-adapter.js')
  if (!isSandboxAdapterModule(loaded)) {
    throw new Error('Sandbox adapter module did not expose SandboxManager')
  }
  cachedSandboxManager = loaded.SandboxManager
  return loaded.SandboxManager
}

export function annotateShellStderrWithSandboxFailures(
  command: string,
  stderr: string,
): string {
  return loadSandboxManager().annotateStderrWithSandboxFailures(command, stderr)
}

export function isShellSandboxEnabledInSettings(): boolean {
  return loadSandboxManager().isSandboxEnabledInSettings()
}

export function areUnsandboxedShellCommandsAllowed(): boolean {
  return loadSandboxManager().areUnsandboxedCommandsAllowed()
}
