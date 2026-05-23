#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0

import { createHash } from 'node:crypto'
import {
  chmodSync,
  copyFileSync,
  createReadStream,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import { basename, join, resolve } from 'node:path'
import { spawnSync } from 'node:child_process'

const BUN_VERSION = '1.3.14'
const SUPPORTED_ARCHES = new Set(['arm64', 'x64'])
const BUN_ASSETS = {
  arm64: {
    name: 'bun-darwin-aarch64.zip',
    sha256: 'd8b96221828ad6f97ac7ac0ab7e95872341af763001e8803e8267652c2652620',
  },
  x64: {
    name: 'bun-darwin-x64-baseline.zip',
    sha256: '3e35ad6f53971a9834bf9e6786e2adf72b5f1921cc9a9c5fde073d2972944076',
  },
}

function parseArgs(argv) {
  const parsed = {
    arch: process.arch,
    outDir: 'dist/homebrew',
    keepWorkdir: false,
  }

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    if (arg === '--arch') {
      parsed.arch = argv[++index]
    } else if (arg === '--out-dir') {
      parsed.outDir = argv[++index]
    } else if (arg === '--keep-workdir') {
      parsed.keepWorkdir = true
    } else if (arg === '-h' || arg === '--help') {
      usage()
      process.exit(0)
    } else {
      throw new Error(`Unknown argument: ${arg}`)
    }
  }

  if (!SUPPORTED_ARCHES.has(parsed.arch)) {
    throw new Error(`Unsupported --arch ${parsed.arch}; expected arm64 or x64`)
  }
  return parsed
}

function usage() {
  process.stdout.write(`Usage: scripts/build-homebrew-cask-artifact.mjs [--arch arm64|x64] [--out-dir dist/homebrew]\n`)
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    encoding: 'utf8',
    stdio: options.capture ? ['ignore', 'pipe', 'pipe'] : 'inherit',
    ...options,
  })
  if (result.error) {
    throw result.error
  }
  if (result.status !== 0) {
    const details = options.capture
      ? `\nstdout:\n${result.stdout}\nstderr:\n${result.stderr}`
      : ''
    throw new Error(`${command} ${args.join(' ')} failed with status ${result.status}${details}`)
  }
  return result
}

function sha256(path) {
  return new Promise((resolve, reject) => {
    const hash = createHash('sha256')
    const stream = createReadStream(path)
    stream.on('data', (chunk) => hash.update(chunk))
    stream.on('error', reject)
    stream.on('end', () => resolve(hash.digest('hex')))
  })
}

function packageVersion() {
  return JSON.parse(readFileSync('package.json', 'utf8')).version
}

async function downloadBunRuntime(workdir, arch) {
  const asset = BUN_ASSETS[arch]
  if (!asset) {
    throw new Error(`Unsupported Bun runtime arch: ${arch}`)
  }
  const url = `https://github.com/oven-sh/bun/releases/download/bun-v${BUN_VERSION}/${asset.name}`
  const zipPath = join(workdir, asset.name)
  const unzipDir = join(workdir, 'bun-runtime')
  run('curl', ['-fL', url, '-o', zipPath])
  const digest = await sha256(zipPath)
  if (digest !== asset.sha256) {
    throw new Error(
      `Bun ${BUN_VERSION} ${arch} archive SHA-256 mismatch: expected ${asset.sha256}, got ${digest}`,
    )
  }
  mkdirSync(unzipDir, { recursive: true })
  run('unzip', ['-q', zipPath, '-d', unzipDir])

  const folder = asset.name.replace(/\.zip$/, '')
  const binaryPath = join(unzipDir, folder, 'bun')
  if (!existsSync(binaryPath)) {
    throw new Error(`Downloaded Bun archive did not contain ${folder}/bun`)
  }
  return binaryPath
}

function writeWrapper(path) {
  writeFileSync(
    path,
    `#!/bin/bash
set -euo pipefail

source_path="\${BASH_SOURCE[0]}"
while [ -h "$source_path" ]; do
  source_dir="$(cd -P "$(dirname "$source_path")" >/dev/null 2>&1 && pwd)"
  target_path="$(readlink "$source_path")"
  if [[ "$target_path" == /* ]]; then
    source_path="$target_path"
  else
    source_path="$source_dir/$target_path"
  fi
done

root_dir="$(cd -P "$(dirname "$source_path")" >/dev/null 2>&1 && pwd)"
export PATH="$root_dir/runtime:$PATH"
exec "$root_dir/runtime/bun" "$root_dir/package/bin/ummaya" "$@"
`,
  )
  chmodSync(path, 0o755)
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  const version = packageVersion()
  const root = process.cwd()
  const outDir = resolve(args.outDir)
  const workdir = mkdtempSync(join(tmpdir(), `ummaya-cask-${version}-${args.arch}-`))
  const stageRoot = join(workdir, 'stage')
  const artifactRoot = join(stageRoot, `ummaya-${version}-macos-${args.arch}`)
  const packageDir = join(artifactRoot, 'package')
  const runtimeDir = join(artifactRoot, 'runtime')

  try {
    mkdirSync(outDir, { recursive: true })
    mkdirSync(stageRoot, { recursive: true })
    mkdirSync(runtimeDir, { recursive: true })

    const packReportPath = join(workdir, 'npm-pack.json')
    const packReports = JSON.parse(run('npm', ['pack', '--json', '--pack-destination', workdir], {
      cwd: root,
      capture: true,
    }).stdout)
    writeFileSync(packReportPath, JSON.stringify(packReports, null, 2))
    const pack = Array.isArray(packReports) ? packReports[0] : packReports
    const tarball = join(workdir, pack.filename)

    run('tar', ['-xzf', tarball, '-C', artifactRoot])
    if (!existsSync(packageDir)) {
      throw new Error(`npm tarball extraction did not create ${packageDir}`)
    }

    run(
      'npm',
      [
        'install',
        '--omit=dev',
        '--legacy-peer-deps',
        '--no-audit',
        '--no-fund',
        '--cpu',
        args.arch,
        '--os',
        'darwin',
      ],
      {
        cwd: packageDir,
        env: {
          ...process.env,
          npm_config_cpu: args.arch,
          npm_config_os: 'darwin',
        },
      },
    )

    const bunBinary = await downloadBunRuntime(workdir, args.arch)
    copyFileSync(bunBinary, join(runtimeDir, 'bun'))
    chmodSync(join(runtimeDir, 'bun'), 0o755)
    writeWrapper(join(artifactRoot, 'ummaya'))

    const artifactName = `ummaya-${version}-macos-${args.arch}.tar.gz`
    const artifactPath = join(outDir, artifactName)
    run('tar', ['-czf', artifactPath, '-C', artifactRoot, '.'])
    const digest = await sha256(artifactPath)
    writeFileSync(`${artifactPath}.sha256`, `${digest}  ${artifactName}\n`)
    writeFileSync(
      join(outDir, `ummaya-${version}-macos-${args.arch}.json`),
      `${JSON.stringify(
        {
          version,
          arch: args.arch,
          artifact: basename(artifactPath),
          sha256: digest,
          bunVersion: BUN_VERSION,
        },
        null,
        2,
      )}\n`,
    )
    console.log(`${artifactPath}`)
    console.log(`${digest}`)
  } finally {
    if (args.keepWorkdir) {
      console.error(`kept workdir: ${workdir}`)
    } else {
      rmSync(workdir, { recursive: true, force: true })
    }
  }
}

main()
