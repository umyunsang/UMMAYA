import { describe, expect, test } from 'bun:test'
import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

const repoRoot = resolve(import.meta.dir, '../../..')
const tuiRoot = join(repoRoot, 'tui')
const manifestPath = join(repoRoot, 'docs/research/cc-tool-layer-inventory.json')
const task5TestId =
  'tui/tests/tools/ccToolExposurePolicy.test.ts::requires_permission_for_tier_one_and_above'
const permissionModes = [
  'default',
  'plan',
  'acceptEdits',
  'bypass-blocked',
] as const
const protectedWallTerms = ['AX', 'PIPA', 'identity'] as const

type ExposureState =
  | 'always-loaded'
  | 'deferred-searchable'
  | 'permission-gated-callable'
  | 'hidden'
  | 'unsupported'

type PermissionModeBoundary = (typeof permissionModes)[number] | 'not-applicable'

type PermissionModeMatrix = {
  readonly default: string
  readonly plan: string
  readonly acceptEdits: string
  readonly 'bypass-blocked': string
}

type ExposurePolicy = {
  readonly policy_id: string
  readonly trust_tier: number
  readonly allowed_exposure_states: readonly ExposureState[]
  readonly permission_mode_matrix: PermissionModeMatrix
  readonly bypass_permissions_overrides_protected_walls: false
  readonly bypass_permissions_restriction: string
  readonly protected_primitive_routing_allowed: boolean
}

type InventoryRow = {
  readonly tool_name: string
  readonly cc_group: string
  readonly exposure_state: ExposureState
  readonly trust_tier: number
  readonly permission_mode_boundary: PermissionModeBoundary
  readonly default_roots: string
  readonly protected_primitive_routing: boolean
  readonly protected_primitive_reason: string
  readonly exposure_policy_id: string
  readonly tests: readonly string[]
  readonly evidence: readonly string[]
}

type BypassPermissionsPolicy = {
  readonly cannot_override: readonly string[]
  readonly enforcement: string
}

type InventoryManifest = {
  readonly schema_version: string
  readonly exposure_policy_matrix: readonly ExposurePolicy[]
  readonly permission_mode_boundaries: readonly (typeof permissionModes)[number][]
  readonly bypass_permissions_policy: BypassPermissionsPolicy
  readonly tools: readonly InventoryRow[]
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isStringArray(value: unknown): value is readonly string[] {
  return Array.isArray(value) && value.every(item => typeof item === 'string')
}

function isPermissionModeMatrix(value: unknown): value is PermissionModeMatrix {
  if (!isRecord(value)) return false
  return permissionModes.every(mode => typeof value[mode] === 'string')
}

function isExposurePolicy(value: unknown): value is ExposurePolicy {
  if (!isRecord(value)) return false
  return (
    typeof value.policy_id === 'string' &&
    typeof value.trust_tier === 'number' &&
    Array.isArray(value.allowed_exposure_states) &&
    isPermissionModeMatrix(value.permission_mode_matrix) &&
    value.bypass_permissions_overrides_protected_walls === false &&
    typeof value.bypass_permissions_restriction === 'string' &&
    typeof value.protected_primitive_routing_allowed === 'boolean'
  )
}

function isInventoryRow(value: unknown): value is InventoryRow {
  if (!isRecord(value)) return false
  return (
    typeof value.tool_name === 'string' &&
    typeof value.cc_group === 'string' &&
    typeof value.exposure_state === 'string' &&
    typeof value.trust_tier === 'number' &&
    typeof value.permission_mode_boundary === 'string' &&
    typeof value.default_roots === 'string' &&
    typeof value.protected_primitive_routing === 'boolean' &&
    typeof value.protected_primitive_reason === 'string' &&
    typeof value.exposure_policy_id === 'string' &&
    isStringArray(value.tests) &&
    isStringArray(value.evidence)
  )
}

function assertInventoryManifest(value: unknown): asserts value is InventoryManifest {
  if (!isRecord(value)) {
    throw new Error('Inventory manifest must be a JSON object.')
  }
  if (
    value.schema_version !== 'cc-tool-layer-inventory.v1' ||
    !Array.isArray(value.exposure_policy_matrix) ||
    !value.exposure_policy_matrix.every(isExposurePolicy) ||
    !isStringArray(value.permission_mode_boundaries) ||
    !isRecord(value.bypass_permissions_policy) ||
    !isStringArray(value.bypass_permissions_policy.cannot_override) ||
    typeof value.bypass_permissions_policy.enforcement !== 'string' ||
    !Array.isArray(value.tools) ||
    !value.tools.every(isInventoryRow)
  ) {
    throw new Error(
      'Inventory manifest must include a policy matrix, bypass policy, and policy-covered rows.',
    )
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

function isTierZeroReadSearch(row: InventoryRow): boolean {
  return row.trust_tier === 0 && row.cc_group === 'file-search-edit'
}

function isProtectedAlwaysLoadedPrimitive(row: InventoryRow): boolean {
  return (
    row.exposure_state === 'always-loaded' &&
    row.trust_tier >= 1 &&
    row.protected_primitive_routing
  )
}

describe('CC tool exposure policy', () => {
  test('requires_permission_for_tier_one_and_above', () => {
    const manifest = runInventory()
    const manifestFromDisk: unknown = JSON.parse(readFileSync(manifestPath, 'utf8'))
    expect(manifestFromDisk).toEqual(manifest)

    expect(manifest.permission_mode_boundaries).toEqual([...permissionModes])
    for (const term of protectedWallTerms) {
      expect(manifest.bypass_permissions_policy.cannot_override).toContain(term)
      expect(manifest.bypass_permissions_policy.enforcement).toContain(term)
    }

    const policyByTier = new Map(
      manifest.exposure_policy_matrix.map(policy => [policy.trust_tier, policy]),
    )
    expect([...policyByTier.keys()].sort()).toEqual([0, 1, 2, 3, 4, 5])

    for (const policy of manifest.exposure_policy_matrix) {
      expect(policy.policy_id).toBe(`tier-${policy.trust_tier}`)
      for (const mode of permissionModes) {
        expect(policy.permission_mode_matrix[mode].length).toBeGreaterThan(0)
      }
      expect(policy.bypass_permissions_overrides_protected_walls).toBe(false)
      expect(policy.bypass_permissions_restriction).toContain('bypassPermissions')
      for (const term of protectedWallTerms) {
        expect(policy.bypass_permissions_restriction).toContain(term)
      }
    }

    for (const row of manifest.tools) {
      const policy = policyByTier.get(row.trust_tier)
      expect(policy).toBeDefined()
      expect(row.exposure_policy_id).toBe(policy?.policy_id)
      expect(policy?.allowed_exposure_states).toContain(row.exposure_state)
      expect(row.tests).toContain(task5TestId)
      expect(row.evidence).toContain(
        '.omo/evidence/cc-original-tool-layer-port/task-5-green.txt',
      )

      if (isTierZeroReadSearch(row)) {
        expect(['always-loaded', 'deferred-searchable']).toContain(
          row.exposure_state,
        )
        expect(row.default_roots).toBe('workspace')
      }

      if (row.trust_tier >= 1) {
        expect(
          [
            'permission-gated-callable',
            'hidden',
            'unsupported',
            ...(isProtectedAlwaysLoadedPrimitive(row) ? ['always-loaded'] : []),
          ],
        ).toContain(row.exposure_state)
      }

      if (row.exposure_state === 'always-loaded' && row.trust_tier >= 1) {
        expect(row.cc_group).toBe('ummaya-primitive')
        expect(row.protected_primitive_routing).toBe(true)
        expect(row.protected_primitive_reason).toContain('protected primitive')
        expect(policy?.protected_primitive_routing_allowed).toBe(true)
      }

      if (row.exposure_state === 'permission-gated-callable') {
        expect(row.permission_mode_boundary).not.toBe('not-applicable')
      }
    }
  })
})
