#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0

import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const reportPath = process.argv[2]
if (!reportPath) {
  throw new Error('Usage: scripts/check-npm-package.mjs <npm-pack-json>')
}

const report = JSON.parse(readFileSync(reportPath, 'utf8'))
const pack = Array.isArray(report) ? report[0] : report
if (!pack || !Array.isArray(pack.files)) {
  throw new Error('npm pack report must contain a files array')
}

const maxPackedBytes = Number(process.env.UMMAYA_NPM_MAX_PACKED_BYTES ?? 15_000_000)
const maxUnpackedBytes = Number(process.env.UMMAYA_NPM_MAX_UNPACKED_BYTES ?? 70_000_000)
const maxEntries = Number(process.env.UMMAYA_NPM_MAX_ENTRIES ?? 2_800)

const files = pack.files.map((entry) => entry.path)
const fileSet = new Set(files)

function sourceFilesUnder(relativeDir) {
  return readdirSync(relativeDir, { withFileTypes: true })
    .flatMap((entry) => {
      const relativePath = join(relativeDir, entry.name)
      if (entry.isDirectory()) return sourceFilesUnder(relativePath)
      if (!entry.isFile()) return []
      return /\.(tsx?|jsx?)$/.test(entry.name) ? [relativePath] : []
    })
    .sort()
}

function inlineSourceMapContent(source) {
  const marker = 'sourceMappingURL=data:application/json;charset=utf-8;base64,'
  const line = source.split('\n').find((item) => item.includes(marker))
  if (!line) return ''

  const encoded = line.slice(line.indexOf(marker) + marker.length).trim()
  const decoded = JSON.parse(Buffer.from(encoded, 'base64').toString('utf8'))
  return decoded.sourcesContent?.join('\n') ?? ''
}

function readJsonVersion(path) {
  return JSON.parse(readFileSync(path, 'utf8')).version
}

function readTomlTableVersion(path, tableName) {
  const text = readFileSync(path, 'utf8')
  const tableHeader = `[${tableName}]`
  const start = text.indexOf(tableHeader)
  if (start === -1) {
    throw new Error(`${path} missing ${tableHeader}`)
  }
  const rest = text.slice(start + tableHeader.length)
  const nextTable = rest.search(/\n\[/)
  const section = nextTable === -1 ? rest : rest.slice(0, nextTable)
  const match = section.match(/^version\s*=\s*"([^"]+)"\s*$/m)
  if (!match) {
    throw new Error(`${path} ${tableHeader} missing version`)
  }
  return match[1]
}

function assertSameVersion(label, actual, expected) {
  if (actual !== expected) {
    throw new Error(`${label} version ${actual} does not match package.json ${expected}`)
  }
}

const rootPackageVersion = readJsonVersion('package.json')
assertSameVersion('npm pack report', pack.version, rootPackageVersion)
assertSameVersion('tui/package.json', readJsonVersion('tui/package.json'), rootPackageVersion)
assertSameVersion(
  'pyproject.toml [project]',
  readTomlTableVersion('pyproject.toml', 'project'),
  rootPackageVersion,
)
assertSameVersion(
  'pyproject.toml [tool.commitizen]',
  readTomlTableVersion('pyproject.toml', 'tool.commitizen'),
  rootPackageVersion,
)

const npmShrinkwrap = JSON.parse(readFileSync('npm-shrinkwrap.json', 'utf8'))
assertSameVersion('npm-shrinkwrap.json', npmShrinkwrap.version, rootPackageVersion)
assertSameVersion(
  'npm-shrinkwrap.json packages[""]',
  npmShrinkwrap.packages?.['']?.version,
  rootPackageVersion,
)

const packageLock = JSON.parse(readFileSync('package-lock.json', 'utf8'))
assertSameVersion('package-lock.json', packageLock.version, rootPackageVersion)
assertSameVersion(
  'package-lock.json packages[""]',
  packageLock.packages?.['']?.version,
  rootPackageVersion,
)

const launcherText = readFileSync('bin/ummaya', 'utf8')
const launcherContracts = [
  'configurePackageEnv',
  'UMMAYA_PACKAGE_ROOT',
  'UMMAYA_BACKEND_CMD_JSON',
  'UMMAYA_ALLOW_BACKEND_CMD_OVERRIDE',
  'UMMAYA_TUI_PRIMITIVE_TIMEOUT_MS',
  '.venv',
  '--directory',
  '--frozen',
  '--no-dev',
]
for (const expected of launcherContracts) {
  if (!launcherText.includes(expected)) {
    throw new Error(`bin/ummaya missing packaged launcher contract: ${expected}`)
  }
}
if (launcherText.includes('UMMAYA_PACKAGE_ROOT ??=')) {
  throw new Error('bin/ummaya must not preserve stale UMMAYA_PACKAGE_ROOT')
}
if (launcherText.includes('UMMAYA_BACKEND_CMD_JSON ??=')) {
  throw new Error('bin/ummaya must not preserve stale UMMAYA_BACKEND_CMD_JSON')
}

const required = [
  'bin/ummaya',
  'package.json',
  'bun.lock',
  'npm-shrinkwrap.json',
  'README.md',
  'LICENSE',
  'assets/ummaya-banner-dark.svg',
  'assets/ummaya-banner-light.svg',
  'assets/ummaya-logo.svg',
  'pyproject.toml',
  'uv.lock',
  'src/ummaya/__init__.py',
  'prompts/manifest.yaml',
  'tui/src/entrypoints/cli.tsx',
  'tui/src/runtime/bun-bundle.ts',
  'tui/src/runtime/bundle-package/index.ts',
  'tui/src/runtime/bundle-package/package.json',
  'tui/src/stubs/macro-preload.ts',
  'docs/plugins/security-review.md',
  'specs/2803-document-production-hardening/contracts/document-tools.schema.json',
  'tests/fixtures/documents/public_forms/baselines.yaml',
  'tests/fixtures/plugin_validation/checklist_manifest.yaml',
]

const deny = [
  /(^|\/)\.env($|[./])/,
  /^\.github\//,
  /^\.references\//,
  /^\.specify\//,
  /(^|\/)secrets(\/|$)/,
  /^specs\/(?!2803-document-production-hardening\/contracts\/document-tools\.schema\.json$)/,
  /(^|\/)node_modules(\/|$)/,
  /(^|\/)\.venv(\/|$)/,
  /(^|\/)dist(\/|$)/,
  /(^|\/)coverage\.xml$/,
  /(^|\/)\.DS_Store$/,
  /(^|\/)__pycache__(\/|$)/,
  /(^|\/)__tests__(\/|$)/,
  /\.(test|snap)\.(ts|tsx|js|jsx|snap)$/,
]

const missing = required.filter((path) => !fileSet.has(path))
if (missing.length > 0) {
  throw new Error(`npm package missing required paths:\n${missing.join('\n')}`)
}

const forbidden = files.filter((path) => deny.some((pattern) => pattern.test(path)))
if (forbidden.length > 0) {
  throw new Error(`npm package contains forbidden paths:\n${forbidden.join('\n')}`)
}

const githubAppPublicSurfaceFiles = [
  'tui/src/constants/github-app.ts',
  'tui/src/components/WorkflowMultiselectDialog.tsx',
  ...sourceFilesUnder('tui/src/commands/install-github-app'),
]

const missingGitHubAppPublicSurface = githubAppPublicSurfaceFiles.filter(
  (path) => !fileSet.has(path),
)
if (missingGitHubAppPublicSurface.length > 0) {
  throw new Error(
    `npm package missing GitHub App public surface paths:\n${missingGitHubAppPublicSurface.join('\n')}`,
  )
}

const bannedGitHubAppPublicSurfaceCopy = [
  'ANTHROPIC_API_KEY',
  'CLAUDE_API_KEY',
  'CLAUDE_CODE_OAUTH_TOKEN',
  'FRIENDLI_TOKEN: \\${{ secrets.FRIENDLI_TOKEN }}',
  'secrets.FRIENDLI_TOKEN',
  'anthropic_api_key',
  'claude_code_oauth_token',
  '.github/workflows/claude.yml',
  '.github/workflows/claude-code-review.yml',
  'add-claude-github-actions',
  'selected_claude_workflow',
  'selected_claude_review_workflow',
  'anthropics/claude-cli',
  'github.com/anthropics/claude-code-action',
  'anthropics/claude-code-action',
  'claude-code-action',
  'loginWithClaudeAi',
  'getAnthropicApiKey',
  'isAnthropicAuthEnabled',
  'Claude AI',
  'https://github.com/apps/claude',
  'Claude GitHub App',
  'Claude PR assistance',
  'Claude workflow',
  'Claude Code Review',
  'Claude PR Assistant',
  'A Claude workflow file',
]

const githubAppPublicSurfaceViolations = []
for (const path of githubAppPublicSurfaceFiles) {
  const source = readFileSync(path, 'utf8')
  const hasInlineSourceMap = source.includes('sourceMappingURL=data:application/json')
  if (hasInlineSourceMap) {
    githubAppPublicSurfaceViolations.push(`${path}: inline source map`)
  }

  const searchableSource = `${source}\n${inlineSourceMapContent(source)}`
  for (const phrase of bannedGitHubAppPublicSurfaceCopy) {
    if (searchableSource.includes(phrase)) {
      githubAppPublicSurfaceViolations.push(`${path}: ${phrase}`)
    }
  }
}
if (githubAppPublicSurfaceViolations.length > 0) {
  throw new Error(
    `npm package GitHub App public surface contains upstream residue:\n${githubAppPublicSurfaceViolations.join('\n')}`,
  )
}

if (pack.size > maxPackedBytes) {
  throw new Error(`npm package packed size ${pack.size} exceeds ${maxPackedBytes}`)
}
if (pack.unpackedSize > maxUnpackedBytes) {
  throw new Error(
    `npm package unpacked size ${pack.unpackedSize} exceeds ${maxUnpackedBytes}`,
  )
}
if (files.length > maxEntries) {
  throw new Error(`npm package entry count ${files.length} exceeds ${maxEntries}`)
}

console.log(
  `check-npm-package: clean (${pack.size} packed bytes, ${pack.unpackedSize} unpacked bytes, ${files.length} files, ${githubAppPublicSurfaceFiles.length} GitHub App public surface files)`,
)
