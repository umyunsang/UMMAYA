#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0

import { readFileSync } from 'node:fs'

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
const maxEntries = Number(process.env.UMMAYA_NPM_MAX_ENTRIES ?? 2_700)

const files = pack.files.map((entry) => entry.path)
const fileSet = new Set(files)

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

function readHomebrewCaskVersion(path) {
  const text = readFileSync(path, 'utf8')
  const match = text.match(/^\s*version\s+"([^"]+)"\s*$/m)
  if (!match) {
    throw new Error(`${path} missing cask version`)
  }
  return match[1]
}

function readHomebrewCaskSha256(path) {
  const text = readFileSync(path, 'utf8')
  const single = text.match(/^\s*sha256\s+"([^"]+)"\s*$/m)
  if (single) {
    return [single[1]]
  }

  const arch = text.match(
    /^\s*sha256\s+arm:\s+"([0-9a-f]{64})",\s*\n\s*intel:\s+"([0-9a-f]{64})"\s*$/m,
  )
  if (!arch) {
    throw new Error(`${path} missing cask sha256`)
  }
  return [arch[1], arch[2]]
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

const caskSha256Values = readHomebrewCaskSha256('Casks/ummaya.rb')
assertSameVersion('Casks/ummaya.rb', readHomebrewCaskVersion('Casks/ummaya.rb'), rootPackageVersion)
for (const caskSha256 of caskSha256Values) {
  if (!/^[0-9a-f]{64}$/.test(caskSha256)) {
    throw new Error(`Casks/ummaya.rb sha256 is not a 64-character lowercase hex digest`)
  }
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
  'tui/src/stubs/macro-preload.ts',
  'docs/plugins/security-review.md',
  'tests/fixtures/plugin_validation/checklist_manifest.yaml',
]

const deny = [
  /(^|\/)\.env($|[./])/,
  /^\.github\//,
  /^\.references\//,
  /^\.specify\//,
  /(^|\/)secrets(\/|$)/,
  /^specs\//,
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
  `check-npm-package: clean (${pack.size} packed bytes, ${pack.unpackedSize} unpacked bytes, ${files.length} files)`,
)
