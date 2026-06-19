import { describe, expect, test } from 'bun:test'
import { spawnSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

const repoRoot = resolve(import.meta.dir, '../../..')
const tuiRoot = join(repoRoot, 'tui')
const manifestPath = join(repoRoot, 'docs/research/cc-tool-layer-inventory.json')
const task4TestId =
  'tui/tests/tools/ccToolParityClassification.test.ts::classifies_each_tool_with_a_supported_status'
const deferredTask4Message = 'Parity classification is intentionally deferred to Task 4.'
const parityArtifactPrefix = '.omo/evidence/cc-original-tool-layer-port/parity/'
const runtimeAnchorNames = [
  'StreamingToolExecutor',
  'toolExecution',
  'toolOrchestration',
  'toolHooks',
] as const
const allowedStatuses = new Set([
  'source-parity',
  'behavior-parity',
  'modified',
  'inactive',
  'registry-hidden',
  'unsupported',
  'missing',
])
const allowedDiffStatuses = new Set([
  'identical',
  'different',
  'missing-cc-source',
  'missing-ummaya-source',
  'not-applicable',
])

type ParityStatus =
  | 'source-parity'
  | 'behavior-parity'
  | 'modified'
  | 'inactive'
  | 'registry-hidden'
  | 'unsupported'
  | 'missing'

type DiffStatus =
  | 'identical'
  | 'different'
  | 'missing-cc-source'
  | 'missing-ummaya-source'
  | 'not-applicable'

type InventoryRow = {
  readonly tool_name: string
  readonly cc_source_path: string
  readonly ummaya_path: string
  readonly parity_status: ParityStatus
  readonly status?: ParityStatus
  readonly diff_status?: DiffStatus
  readonly accepted_divergence: string
  readonly blocked_reason?: string
  readonly parity_diff_artifact?: string
  readonly test_evidence?: readonly string[]
}

type RuntimeAnchor = {
  readonly name: string
  readonly cc_source_path: string
  readonly ummaya_path: string
  readonly parity_status: ParityStatus
  readonly status?: ParityStatus
  readonly diff_status?: DiffStatus
  readonly accepted_divergence: string
  readonly parity_diff_artifact?: string
  readonly test_evidence?: readonly string[]
}

type InventoryManifest = {
  readonly schema_version: string
  readonly tools: readonly InventoryRow[]
  readonly runtime?: readonly RuntimeAnchor[]
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

function isConcreteSourcePath(path: string): boolean {
  return path !== '' && path !== 'missing' && path !== 'not-present-in-cc'
}

function artifactExists(relativePath: string | undefined): boolean {
  if (!relativePath) return false
  return existsSync(join(repoRoot, relativePath))
}

describe('CC tool parity classification', () => {
  test('classifies_each_tool_with_a_supported_status', () => {
    const manifest = runInventory()

    expect(manifest.schema_version).toBe('cc-tool-layer-inventory.v1')
    expect(JSON.parse(readFileSync(manifestPath, 'utf8'))).toEqual(manifest)

    for (const row of manifest.tools) {
      expect(row.status).toBe(row.parity_status)
      expect(allowedStatuses.has(row.status ?? '')).toBe(true)
      expect(allowedDiffStatuses.has(row.diff_status ?? '')).toBe(true)
      expect(row.accepted_divergence.length).toBeGreaterThan(0)
      expect(row.accepted_divergence).not.toBe(deferredTask4Message)
      expect(row.test_evidence).toContain(task4TestId)

      const hasSourceOrBlocker =
        isConcreteSourcePath(row.cc_source_path) ||
        isConcreteSourcePath(row.ummaya_path) ||
        Boolean(row.blocked_reason)
      expect(hasSourceOrBlocker).toBe(true)

      if (row.status === 'modified') {
        expect(row.parity_diff_artifact?.startsWith(parityArtifactPrefix)).toBe(
          true,
        )
        expect(artifactExists(row.parity_diff_artifact)).toBe(true)
      }
    }

    const runtimeAnchors = manifest.runtime ?? []
    expect(runtimeAnchors.map(anchor => anchor.name).sort()).toEqual(
      [...runtimeAnchorNames].sort(),
    )
    for (const anchor of runtimeAnchors) {
      expect(anchor.status).toBe(anchor.parity_status)
      expect(allowedStatuses.has(anchor.status ?? '')).toBe(true)
      expect(allowedDiffStatuses.has(anchor.diff_status ?? '')).toBe(true)
      expect(isConcreteSourcePath(anchor.cc_source_path)).toBe(true)
      expect(isConcreteSourcePath(anchor.ummaya_path)).toBe(true)
      expect(anchor.accepted_divergence.length).toBeGreaterThan(0)
      expect(anchor.test_evidence).toContain(task4TestId)
      if (anchor.status === 'modified') {
        expect(
          anchor.parity_diff_artifact?.startsWith(parityArtifactPrefix),
        ).toBe(true)
        expect(artifactExists(anchor.parity_diff_artifact)).toBe(true)
      }
    }
  })
})
