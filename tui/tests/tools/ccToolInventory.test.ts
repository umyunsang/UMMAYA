import { describe, expect, test } from 'bun:test'
import { spawnSync } from 'node:child_process'
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'

const repoRoot = resolve(import.meta.dir, '../../..')
const tuiRoot = join(repoRoot, 'tui')
const manifestPath = join(repoRoot, 'docs/research/cc-tool-layer-inventory.json')
const requiredFields = [
  'tool_name',
  'cc_group',
  'cc_source_path',
  'ummaya_path',
  'feature_status',
  'parity_status',
  'registered_capability',
  'exposure_state',
  'trust_tier',
  'permission_mode_boundary',
  'permission_policy',
  'default_roots',
  'mcp_server_class',
  'accepted_divergence',
  'tests',
  'evidence',
] as const

type InventoryRow = {
  readonly tool_name: string
  readonly cc_group: string
  readonly cc_source_path: string
  readonly ummaya_path: string
  readonly feature_status: string
  readonly parity_status: string
  readonly blocked_reason: string
  readonly registered_capability: boolean
  readonly exposure_state: string
  readonly trust_tier: number
  readonly permission_mode_boundary: string
  readonly permission_policy: string
  readonly default_roots: string
  readonly mcp_server_class: string
  readonly accepted_divergence: string
  readonly tests: readonly string[]
  readonly evidence: readonly string[]
}

type InventoryManifest = {
  readonly schema_version: string
  readonly generated_at: string
  readonly source_refs: readonly string[]
  readonly tools: readonly InventoryRow[]
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
  return JSON.parse(result.stdout) as InventoryManifest
}

function toolNamesFrom(path: string): readonly string[] {
  return readdirSync(path, { withFileTypes: true })
    .filter(
      entry =>
        entry.isDirectory() &&
        !entry.name.startsWith('_') &&
        entry.name !== 'shared' &&
        entry.name !== 'testing',
    )
    .map(entry => entry.name)
    .sort((left, right) => left.localeCompare(right))
}

function sourceFilesUnder(path: string): readonly string[] {
  if (!existsSync(path)) return []
  if (statSync(path).isFile()) return [path]
  return readdirSync(path, { withFileTypes: true })
    .flatMap(entry => sourceFilesUnder(join(path, entry.name)))
    .sort((left, right) => left.localeCompare(right))
}

describe('CC tool inventory generator', () => {
  test('emits restored cc tool groups from source tree', () => {
    const manifest = runInventory()
    const names = manifest.tools.map(row => row.tool_name)

    expect(manifest.schema_version).toBe('cc-tool-layer-inventory.v1')
    expect(manifest.generated_at).toBe('2026-06-12T00:00:00.000Z')
    expect(manifest.source_refs).toEqual(
      expect.arrayContaining([
        '.references/claude-code-sourcemap/restored-src/src/tools.ts',
        '.references/claude-code-sourcemap/restored-src/src/tools/',
        'tui/src/tools.ts',
        'tui/src/tools/',
      ]),
    )
    expect(manifest.tools.length).toBeGreaterThan(40)
    expect(existsSync(manifestPath)).toBe(true)
    expect(JSON.parse(readFileSync(manifestPath, 'utf8'))).toEqual(manifest)

    for (const row of manifest.tools) {
      for (const field of requiredFields) {
        expect(row).toHaveProperty(field)
      }
      expect(Number.isInteger(row.trust_tier)).toBe(true)
      expect(row.trust_tier).toBeGreaterThanOrEqual(0)
      expect(row.trust_tier).toBeLessThanOrEqual(5)
      expect(Array.isArray(row.tests)).toBe(true)
      expect(Array.isArray(row.evidence)).toBe(true)
    }

    for (const requiredTool of [
      'WebFetchTool',
      'WebSearchTool',
      'AgentTool',
      'BashTool',
      'FileReadTool',
      'MCPTool',
      'ToolSearchTool',
    ]) {
      expect(names).toContain(requiredTool)
    }

    for (const ummayaTool of [
      'TranslateTool',
      'CalculatorTool',
      'DateParserTool',
      'ExportPDFTool',
      'LookupPrimitive',
      'ResolveLocationPrimitive',
      'SubmitPrimitive',
      'VerifyPrimitive',
      'DocumentPrimitive',
      'AdapterTool',
      'WorkspaceToolAdapter',
    ]) {
      expect(names).toContain(ummayaTool)
    }

    for (const ccTool of toolNamesFrom(
      join(repoRoot, '.references/claude-code-sourcemap/restored-src/src/tools'),
    )) {
      expect(names).toContain(ccTool)
    }
    for (const ummayaTool of toolNamesFrom(join(repoRoot, 'tui/src/tools'))) {
      expect(names).toContain(ummayaTool)
    }

    expect(new Set(manifest.tools.map(row => row.feature_status))).toEqual(
      new Set([
        'default',
        'feature-gated',
        'ant-only',
        'test-only',
        'unsupported',
        'UMMAYA-specific',
      ]),
    )
  })

  test('websearch_callable_catalog_row_has_no_not_implemented_source_path', () => {
    const manifest = JSON.parse(readFileSync(manifestPath, 'utf8')) as InventoryManifest
    const row = manifest.tools.find(tool => tool.tool_name === 'WebSearchTool')

    expect(row).toBeDefined()
    if (!row) return

    const callableWithoutBlockedReason =
      row.exposure_state.includes('callable') && row.blocked_reason.length === 0
    if (!callableWithoutBlockedReason) {
      expect(row.blocked_reason.length).toBeGreaterThan(0)
      return
    }

    const sourceText = sourceFilesUnder(join(repoRoot, row.ummaya_path))
      .map(path => readFileSync(path, 'utf8'))
      .join('\n')

    expect(sourceText).not.toContain("throw new Error('not implemented')")
    expect(sourceText).not.toContain('throw new Error("not implemented")')
  })

  test('cc_support_catalog_imports_record_concrete_ummaya_sources', () => {
    const manifest = runInventory()
    const row = manifest.tools.find(tool => tool.tool_name === 'ExitPlanModeV2Tool')

    expect(row).toBeDefined()
    if (!row) return

    expect(row.ummaya_path).toBe(
      'tui/src/tools/ExitPlanModeTool/ExitPlanModeV2Tool.ts',
    )
    expect(row.registered_capability).toBe(true)
    expect(row.exposure_state).not.toBe('unsupported')
  })
})
