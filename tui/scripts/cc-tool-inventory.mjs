#!/usr/bin/env node
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  GENERATED_AT,
  PARITY_ARTIFACT_ROOT,
  SCHEMA_VERSION,
  TASK4_EVIDENCE_PATH,
  TASK4_TEST_ID,
  bypassPermissionsPolicy,
  exposurePolicyMatrix,
  permissionModeBoundaries,
} from './cc-tool-inventory/config.mjs'
import {
  collectSourceTools,
  listToolDirectories,
  mergeRowSeed,
} from './cc-tool-inventory/sourceDiscovery.mjs'
import { createSourceSnapshotHelpers } from './cc-tool-inventory/sourceSnapshots.mjs'
import { buildRow } from './cc-tool-inventory/toolRows.mjs'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const tuiRoot = dirname(scriptDir)
const repoRoot = dirname(tuiRoot)
const restoredToolsTs = join(
  repoRoot,
  '.references/claude-code-sourcemap/restored-src/src/tools.ts',
)
const restoredToolsRoot = join(
  repoRoot,
  '.references/claude-code-sourcemap/restored-src/src/tools',
)
const restoredSourceRoot = dirname(restoredToolsTs)
const ummayaToolsTs = join(repoRoot, 'tui/src/tools.ts')
const ummayaToolsRoot = join(repoRoot, 'tui/src/tools')
const ummayaSourceRoot = dirname(ummayaToolsTs)
const ummayaCcSupportToolsTs = join(
  repoRoot,
  'tui/src/tools/ToolSearchTool/ccSupportTools.ts',
)
const ummayaCcSupportSourceRoot = dirname(ummayaCcSupportToolsTs)
const manifestPath = join(repoRoot, 'docs/research/cc-tool-layer-inventory.json')
const parityArtifactRoot = join(repoRoot, PARITY_ARTIFACT_ROOT)
const runtimeAnchors = [
  ['StreamingToolExecutor', 'StreamingToolExecutor.ts'],
  ['toolExecution', 'toolExecution.ts'],
  ['toolOrchestration', 'toolOrchestration.ts'],
  ['toolHooks', 'toolHooks.ts'],
]
const {
  compareSources,
  readRequired,
  relativePath,
  writeDiffArtifact,
} = createSourceSnapshotHelpers(repoRoot, parityArtifactRoot)

function buildRuntimeAnchor([name, fileName]) {
  const ccPath = relativePath(
    join(repoRoot, '.references/claude-code-sourcemap/restored-src/src/services/tools', fileName),
  )
  const ummayaPath = relativePath(join(repoRoot, 'tui/src/services/tools', fileName))
  const comparison = compareSources(ccPath, ummayaPath)
  const parity = comparison.diff_status === 'identical' ? 'source-parity' : 'modified'
  const diffArtifact =
    parity === 'modified'
      ? writeDiffArtifact(name, ccPath, ummayaPath, parity, comparison)
      : 'not-applicable'
  return {
    name,
    source_path: ccPath,
    cc_source_path: ccPath,
    ummaya_path: ummayaPath,
    parity_status: parity,
    status: parity,
    diff_status: comparison.diff_status,
    parity_diff_artifact: diffArtifact,
    accepted_divergence:
      parity === 'source-parity'
        ? 'No accepted divergence; runtime source digest matches restored Claude Code.'
        : 'Runtime tool-loop source differs from restored Claude Code; Task 4 records a bounded diff artifact.',
    tests: [TASK4_TEST_ID],
    evidence: [TASK4_EVIDENCE_PATH],
    test_evidence: [TASK4_TEST_ID],
  }
}

function collectSeeds(restoredImported, ummayaImported) {
  const seeds = new Map()
  for (const directory of listToolDirectories(restoredToolsRoot, relativePath)) {
    mergeRowSeed(seeds, directory, {
      cc_source_path: `${relativePath(join(restoredToolsRoot, directory))}/`,
    })
  }
  for (const [toolName, ccPath] of restoredImported) {
    mergeRowSeed(seeds, toolName, { cc_source_path: ccPath })
  }
  for (const directory of listToolDirectories(ummayaToolsRoot, relativePath)) {
    mergeRowSeed(seeds, directory, {
      ummaya_path: `${relativePath(join(ummayaToolsRoot, directory))}/`,
    })
  }
  for (const [toolName, ummayaPath] of ummayaImported) {
    mergeRowSeed(seeds, toolName, { ummaya_path: ummayaPath })
  }
  return seeds
}

function buildTools() {
  const restoredSource = readRequired(restoredToolsTs)
  const ummayaSource = readRequired(ummayaToolsTs)
  const ummayaCcSupportSource = readRequired(ummayaCcSupportToolsTs)
  const restoredImported = collectSourceTools(restoredSource, restoredSourceRoot, relativePath)
  const ummayaImported = new Map([
    ...collectSourceTools(ummayaSource, ummayaSourceRoot, relativePath),
    ...collectSourceTools(
      ummayaCcSupportSource,
      ummayaCcSupportSourceRoot,
      relativePath,
    ),
  ])
  return [...collectSeeds(restoredImported, ummayaImported).values()]
    .map(seed => ({
      cc_source_path: 'not-present-in-cc',
      ummaya_path: 'missing',
      ...seed,
    }))
    .map(seed => buildRow(seed, compareSources, writeDiffArtifact))
    .sort((left, right) => left.tool_name.localeCompare(right.tool_name))
}

function buildManifest() {
  mkdirSync(parityArtifactRoot, { recursive: true })
  return {
    schema_version: SCHEMA_VERSION,
    generated_at: GENERATED_AT,
    permission_mode_boundaries: permissionModeBoundaries,
    bypass_permissions_policy: bypassPermissionsPolicy,
    exposure_policy_matrix: exposurePolicyMatrix,
    source_refs: [
      '.references/claude-code-sourcemap/restored-src/src/tools.ts',
      '.references/claude-code-sourcemap/restored-src/src/tools/',
      '.references/claude-code-sourcemap/restored-src/src/services/tools/StreamingToolExecutor.ts',
      '.references/claude-code-sourcemap/restored-src/src/services/tools/toolExecution.ts',
      '.references/claude-code-sourcemap/restored-src/src/services/tools/toolOrchestration.ts',
      '.references/claude-code-sourcemap/restored-src/src/services/tools/toolHooks.ts',
      'tui/src/tools.ts',
      'tui/src/tools/ToolSearchTool/ccSupportTools.ts',
      'tui/src/tools/',
      'tui/src/services/tools/StreamingToolExecutor.ts',
      'tui/src/services/tools/toolExecution.ts',
      'tui/src/services/tools/toolOrchestration.ts',
      'tui/src/services/tools/toolHooks.ts',
    ],
    runtime: runtimeAnchors.map(buildRuntimeAnchor),
    tools: buildTools(),
  }
}

function main() {
  const args = process.argv.slice(2)
  if (args.length > 1 || (args.length === 1 && args[0] !== '--json')) {
    console.error('Usage: node tui/scripts/cc-tool-inventory.mjs [--json]')
    process.exit(2)
  }
  const output = `${JSON.stringify(buildManifest(), null, 2)}\n`
  mkdirSync(dirname(manifestPath), { recursive: true })
  writeFileSync(manifestPath, output)
  if (args[0] === '--json') process.stdout.write(output)
}

main()
