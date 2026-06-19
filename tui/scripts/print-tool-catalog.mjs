#!/usr/bin/env node
import { createHash } from 'node:crypto'
import { spawnSync } from 'node:child_process'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const supportedModes = ['default']

function parseMode(argv) {
  let mode = 'default'
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    if (arg === '--mode') {
      const value = argv[index + 1]
      if (value === undefined) {
        return { ok: false, error: 'missing --mode value' }
      }
      mode = value
      index += 1
      continue
    }
    if (arg.startsWith('--mode=')) {
      mode = arg.slice('--mode='.length)
      continue
    }
    return { ok: false, error: `unknown argument: ${arg}` }
  }
  if (!supportedModes.includes(mode)) {
    return { ok: false, error: `unsupported mode: ${mode}` }
  }
  return { ok: true, mode }
}

function stableHash(names) {
  return createHash('sha256').update(names.join('\n')).digest('hex')
}

function failClosed(message) {
  process.stderr.write(
    `${JSON.stringify(
      {
        schema_version: 'ummaya-tool-catalog-error.v1',
        ok: false,
        error: message,
        supported_modes: supportedModes,
      },
      null,
      2,
    )}\n`,
  )
  process.exit(2)
}

const parsedMode = parseMode(process.argv.slice(2))
if (!parsedMode.ok) {
  failClosed(parsedMode.error)
}

const scriptDir = dirname(fileURLToPath(import.meta.url))
const tuiRoot = dirname(scriptDir)
const rawMutationShellNames = [
  'Bash',
  'Edit',
  'Write',
  'NotebookEdit',
  'PowerShell',
]
const ccSupportNames = [
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
]

const bunProgram = `
  import { assembleToolPool, areCcSupportToolsEnabled, getAllBaseTools, getTools } from './src/tools.ts'
  import { getEmptyToolPermissionContext } from './src/Tool.ts'
  import { isDeferredTool } from './src/tools/ToolSearchTool/prompt.ts'

  const rawMutationShellNames = ${JSON.stringify(rawMutationShellNames)}
  const ccSupportNames = ${JSON.stringify(ccSupportNames)}
  const context = getEmptyToolPermissionContext()
  const byName = (left, right) => left.localeCompare(right)
  const namesOf = tools => tools.map(tool => tool.name).sort(byName)
  const schemaCount = tools =>
    tools.filter(tool => tool.inputJSONSchema !== undefined || tool.inputSchema !== undefined).length
  const registeredTools = getAllBaseTools()
  const modelFacingTools = getTools(context)
  const assembledTools = assembleToolPool(context, [])
  const modelFacingNames = namesOf(modelFacingTools)
  const alwaysLoadedRawMutationShellNames = modelFacingTools
    .filter(tool => !isDeferredTool(tool) && rawMutationShellNames.includes(tool.name))
    .map(tool => tool.name)
    .sort(byName)
  const registeredNames = namesOf(registeredTools)
  const payload = {
    cc_support_tools_enabled: areCcSupportToolsEnabled(),
    registered_capability_names: registeredNames,
    model_facing_names: modelFacingNames,
    assembled_model_facing_names: namesOf(assembledTools),
    model_facing_always_loaded_names: modelFacingTools
      .filter(tool => !isDeferredTool(tool))
      .map(tool => tool.name)
      .sort(byName),
    registered_cc_support_names: ccSupportNames
      .filter(name => registeredNames.includes(name))
      .sort(byName),
    cc_support_tools_hidden_or_unsupported_names: ccSupportNames
      .filter(name => !modelFacingNames.includes(name))
      .sort(byName),
    raw_tier_one_plus_always_loaded_violation_names: alwaysLoadedRawMutationShellNames,
    counts: {
      registered_capabilities: registeredTools.length,
      model_facing: modelFacingTools.length,
      assembled_model_facing: assembledTools.length,
      registered_schema_count: schemaCount(registeredTools),
      model_facing_schema_count: schemaCount(modelFacingTools),
      assembled_schema_count: schemaCount(assembledTools),
      raw_tier_one_plus_always_loaded_violations: alwaysLoadedRawMutationShellNames.length,
    },
  }
  console.log(JSON.stringify(payload))
`

const result = spawnSync('bun', ['--silent', '--eval', bunProgram], {
  cwd: tuiRoot,
  env: process.env,
  encoding: 'utf8',
})

if (result.status !== 0) {
  failClosed(`registry probe failed with status ${result.status}: ${result.stderr.trim()}`)
}

let runtimeCatalog
try {
  runtimeCatalog = JSON.parse(result.stdout)
} catch (error) {
  const message = error instanceof Error ? error.message : String(error)
  failClosed(`registry probe emitted invalid JSON: ${message}`)
}

const catalog = {
  schema_version: 'ummaya-tool-catalog.v1',
  mode: parsedMode.mode,
  kill_switch: {
    env: 'UMMAYA_ENABLE_CC_SUPPORT_TOOLS',
    value: process.env.UMMAYA_ENABLE_CC_SUPPORT_TOOLS ?? null,
    cc_support_tools_enabled: runtimeCatalog.cc_support_tools_enabled,
  },
  registered_capability_names: runtimeCatalog.registered_capability_names,
  model_facing_names: runtimeCatalog.model_facing_names,
  assembled_model_facing_names: runtimeCatalog.assembled_model_facing_names,
  model_facing_always_loaded_names:
    runtimeCatalog.model_facing_always_loaded_names,
  registered_cc_support_names: runtimeCatalog.registered_cc_support_names,
  cc_support_tools_hidden_or_unsupported_names:
    runtimeCatalog.cc_support_tools_hidden_or_unsupported_names,
  raw_tier_one_plus_always_loaded_violation_names:
    runtimeCatalog.raw_tier_one_plus_always_loaded_violation_names,
  counts: runtimeCatalog.counts,
  hashes: {
    registered_capabilities_sha256: stableHash(
      runtimeCatalog.registered_capability_names,
    ),
    model_facing_sha256: stableHash(runtimeCatalog.model_facing_names),
    assembled_model_facing_sha256: stableHash(
      runtimeCatalog.assembled_model_facing_names,
    ),
  },
}

process.stdout.write(`${JSON.stringify(catalog, null, 2)}\n`)
