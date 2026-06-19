// SPDX-License-Identifier: Apache-2.0

import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import {
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import test from 'node:test'

const requiredPackagePaths = [
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

const githubAppPublicSurfacePaths = [
  'tui/src/constants/github-app.ts',
  'tui/src/components/WorkflowMultiselectDialog.tsx',
  ...sourceFilesUnder('tui/src/commands/install-github-app'),
]

function rootPackageVersion() {
  return JSON.parse(readFileSync('package.json', 'utf8')).version
}

function defaultPackageGateEnv() {
  const env = { ...process.env }
  delete env.UMMAYA_NPM_MAX_ENTRIES
  delete env.UMMAYA_NPM_MAX_PACKED_BYTES
  delete env.UMMAYA_NPM_MAX_UNPACKED_BYTES
  return env
}

function syntheticPackReport(entryCount) {
  const baselinePaths = [...requiredPackagePaths, ...githubAppPublicSurfacePaths]

  assert.ok(
    entryCount >= baselinePaths.length,
    'entry count must include all required package and GitHub App surface paths',
  )

  const version = rootPackageVersion()
  const paths = [...baselinePaths]
  for (let index = 0; paths.length < entryCount; index += 1) {
    paths.push(`src/ummaya/package_gate_fixture/module_${String(index).padStart(4, '0')}.py`)
  }

  return [
    {
      id: `ummaya-${version}.tgz`,
      name: 'ummaya',
      version,
      size: 10_000_000,
      unpackedSize: 60_000_000,
      files: paths.map((path) => ({ path, size: 1, mode: 0o644 })),
    },
  ]
}

function writePackageFile(packageRoot, path, content) {
  const target = join(packageRoot, path)
  mkdirSync(dirname(target), { recursive: true })
  writeFileSync(target, content)
}

function createSyntheticTarball(tempDir, report) {
  const packageRoot = join(tempDir, 'package')
  mkdirSync(packageRoot, { recursive: true })

  for (const entry of report[0].files) {
    writePackageFile(packageRoot, entry.path, `clean fixture for ${entry.path}\n`)
  }

  const tarballPath = join(tempDir, report[0].filename)
  const result = spawnSync('tar', ['-czf', tarballPath, '-C', tempDir, 'package'], {
    encoding: 'utf8',
  })
  assert.equal(result.status, 0, `failed to create synthetic tarball\nstderr:\n${result.stderr}`)
}

function runPackageCheck(entryCount, packedFileOverrides = new Map()) {
  const tempDir = mkdtempSync(join(tmpdir(), 'ummaya-package-gate-'))
  try {
    const report = syntheticPackReport(entryCount)
    report[0].filename = report[0].id
    createSyntheticTarball(tempDir, report)
    for (const [path, content] of packedFileOverrides) {
      writePackageFile(join(tempDir, 'package'), path, content)
    }
    if (packedFileOverrides.size > 0) {
      const tarballPath = join(tempDir, report[0].filename)
      const result = spawnSync('tar', ['-czf', tarballPath, '-C', tempDir, 'package'], {
        encoding: 'utf8',
      })
      assert.equal(result.status, 0, `failed to update synthetic tarball\nstderr:\n${result.stderr}`)
    }

    const reportPath = join(tempDir, 'npm-pack.json')
    writeFileSync(reportPath, JSON.stringify(report, null, 2))
    return spawnSync(process.execPath, ['scripts/check-npm-package.mjs', reportPath], {
      cwd: process.cwd(),
      encoding: 'utf8',
      env: defaultPackageGateEnv(),
    })
  } finally {
    rmSync(tempDir, { force: true, recursive: true })
  }
}

test('accepts a 2742-entry runtime package under the default entry gate', () => {
  const result = runPackageCheck(2742)

  assert.equal(
    result.status,
    0,
    `expected package check to pass for 2742 entries\nstdout:\n${result.stdout}\nstderr:\n${result.stderr}`,
  )
  assert.match(result.stdout, /check-npm-package: clean .*2742 files/)
})

test('rejects a 2801-entry package under the default entry gate', () => {
  const result = runPackageCheck(2801)

  assert.notEqual(result.status, 0, 'expected package check to fail above the entry gate')
  assert.match(result.stderr, /npm package entry count 2801 exceeds/)
})

test('rejects upstream residue inside packed tarball content', () => {
  const result = runPackageCheck(
    2742,
    new Map([
      [
        'src/ummaya/package_gate_fixture/module_0000.py',
        'loginWithClaudeAi\n//# sourceMappingURL=data:application/json\n',
      ],
    ]),
  )

  assert.notEqual(result.status, 0, 'expected package check to fail on packed tarball residue')
  assert.match(result.stderr, /module_0000\.py: loginWithClaudeAi/)
  assert.match(result.stderr, /module_0000\.py: sourceMappingURL=data:application\/json/)
})
