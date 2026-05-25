#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0

import { createHash } from 'node:crypto'
import {
  chmodSync,
  copyFileSync,
  createReadStream,
  existsSync,
  lstatSync,
  lutimesSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  renameSync,
  readFileSync,
  realpathSync,
  rmSync,
  utimesSync,
  writeFileSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import { basename, join, resolve } from 'node:path'
import { spawnSync } from 'node:child_process'

const BUN_VERSION = '1.3.14'
const ARCHIVE_MTIME = new Date('2020-01-01T00:00:00.000Z')
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

function collectArchiveEntries(root) {
  const entries = []

  function visit(relativeDir) {
    const absoluteDir = join(root, relativeDir)
    const names = readdirSync(absoluteDir).sort()
    for (const name of names) {
      const relativePath = relativeDir === '.' ? `./${name}` : `${relativeDir}/${name}`
      entries.push(relativePath)
      if (lstatSync(join(root, relativePath)).isDirectory()) {
        visit(relativePath)
      }
    }
  }

  visit('.')
  return entries
}

function normalizeArchiveMetadata(root, entries) {
  for (const entry of ['.', ...entries]) {
    const absolutePath = join(root, entry)
    const stat = lstatSync(absolutePath)
    if (stat.isSymbolicLink()) {
      lutimesSync(absolutePath, ARCHIVE_MTIME, ARCHIVE_MTIME)
    } else {
      utimesSync(absolutePath, ARCHIVE_MTIME, ARCHIVE_MTIME)
    }
  }
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

function writeWrapper(path, runtimeSha256) {
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
runtime_bun="$root_dir/runtime/bun"
runtime_sha256="${runtimeSha256}"
package_root="$root_dir/package"

json_escape() {
  printf '%s' "$1" | sed 's/\\\\/\\\\\\\\/g; s/"/\\\\"/g'
}

export UMMAYA_PACKAGE_ROOT="$package_root"
if [[ "\${UMMAYA_ALLOW_BACKEND_CMD_OVERRIDE:-}" != "1" || -z "\${UMMAYA_BACKEND_CMD_JSON:-}" ]]; then
  package_root_json="$(json_escape "$package_root")"
  if [[ -x "$package_root/.venv/bin/python" ]]; then
    python_json="$(json_escape "$package_root/.venv/bin/python")"
    export UMMAYA_BACKEND_CMD_JSON="[\\"$python_json\\",\\"-m\\",\\"ummaya.cli\\",\\"--ipc\\",\\"stdio\\"]"
  else
    export UMMAYA_BACKEND_CMD_JSON="[\\"uv\\",\\"--directory\\",\\"$package_root_json\\",\\"run\\",\\"--frozen\\",\\"--no-dev\\",\\"ummaya\\",\\"--ipc\\",\\"stdio\\"]"
  fi
fi
export UMMAYA_TUI_PRIMITIVE_TIMEOUT_MS="\${UMMAYA_TUI_PRIMITIVE_TIMEOUT_MS:-90000}"

use_cached_runtime=0
if [[ "\${UMMAYA_FORCE_RUNTIME_CACHE:-}" == "1" ]]; then
  use_cached_runtime=1
elif [[ "$root_dir" == */Caskroom/ummaya/* ]]; then
  use_cached_runtime=1
fi

if [[ "$use_cached_runtime" == "1" && -n "\${HOME:-}" ]]; then
  cache_home="\${XDG_CACHE_HOME:-$HOME/.cache}"
  cache_dir="$cache_home/ummaya/runtime/bun-$runtime_sha256"
  cache_bun="$cache_dir/bun"
  cache_marker="$cache_dir/.sha256"
  cache_ok=0
  if [[ -x "$cache_bun" && -f "$cache_marker" && "$(cat "$cache_marker")" == "$runtime_sha256" ]]; then
    cache_ok=1
  fi
  if [[ "$cache_ok" != "1" ]]; then
    mkdir -p "$cache_dir"
    /bin/cp -X "$runtime_bun" "$cache_bun"
    chmod 0755 "$cache_bun"
    printf '%s\n' "$runtime_sha256" > "$cache_marker"
  fi
  export PATH="$cache_dir:$PATH"
  exec "$cache_bun" "$package_root/bin/ummaya" "$@"
fi

export PATH="$root_dir/runtime:$PATH"
exec "$runtime_bun" "$package_root/bin/ummaya" "$@"
`,
  )
  chmodSync(path, 0o755)
}

function smokeWrapper(artifactRoot, arch) {
  if (arch !== process.arch) {
    console.error(`Skipping wrapper smoke for ${arch} on ${process.arch}`)
    return
  }

  const smokeCwd = mkdtempSync(join(tmpdir(), 'ummaya wrapper smoke cwd '))
  try {
    const wrapper = join(artifactRoot, 'ummaya')
    const packageRoot = join(artifactRoot, 'package')
    const result = spawnSync(wrapper, [], {
      cwd: smokeCwd,
      env: {
        ...process.env,
        UMMAYA_LAUNCHER_INSPECT: '1',
        UMMAYA_BACKEND_CMD_JSON: '["stale","backend"]',
      },
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    if (result.error) {
      throw result.error
    }
    if (result.status !== 0) {
      throw new Error(
        `Homebrew wrapper smoke failed with status ${result.status}\nstdout:\n${result.stdout}\nstderr:\n${result.stderr}`,
      )
    }
    const payload = JSON.parse(result.stdout.trim())
    const expectedPackageRoot = realpathSync(packageRoot)
    if (payload.packageRoot !== expectedPackageRoot) {
      throw new Error(
        `Wrapper package root ${payload.packageRoot} did not match ${expectedPackageRoot}`,
      )
    }
    const expected = [
      'uv',
      '--directory',
      expectedPackageRoot,
      'run',
      '--frozen',
      '--no-dev',
      'ummaya',
      '--ipc',
      'stdio',
    ]
    if (JSON.stringify(payload.backendCommand) !== JSON.stringify(expected)) {
      throw new Error(
        `Wrapper backend command ${JSON.stringify(payload.backendCommand)} did not match ${JSON.stringify(expected)}`,
      )
    }
    if (payload.primitiveTimeoutMs !== '90000') {
      throw new Error(`Wrapper primitive timeout ${payload.primitiveTimeoutMs} did not match 90000`)
    }
  } finally {
    rmSync(smokeCwd, { recursive: true, force: true })
  }
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
        '--omit=optional',
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
    const runtimePath = join(runtimeDir, 'bun')
    copyFileSync(bunBinary, runtimePath)
    chmodSync(runtimePath, 0o755)
    const runtimeSha256 = await sha256(runtimePath)
    writeWrapper(join(artifactRoot, 'ummaya'), runtimeSha256)
    smokeWrapper(artifactRoot, args.arch)

    const artifactName = `ummaya-${version}-macos-${args.arch}.tar.gz`
    const artifactPath = join(outDir, artifactName)
    const archiveEntries = collectArchiveEntries(artifactRoot)
    normalizeArchiveMetadata(artifactRoot, archiveEntries)
    const archiveListPath = join(workdir, 'archive-files.txt')
    const tarPath = join(outDir, `ummaya-${version}-macos-${args.arch}.tar`)
    writeFileSync(archiveListPath, `${archiveEntries.join('\n')}\n`)
    rmSync(tarPath, { force: true })
    rmSync(artifactPath, { force: true })
    run('tar', [
      '--no-recursion',
      '--uid',
      '0',
      '--gid',
      '0',
      '--uname',
      'root',
      '--gname',
      'wheel',
      '-cf',
      tarPath,
      '-C',
      artifactRoot,
      '-T',
      archiveListPath,
    ])
    run('gzip', ['-n', '-9', tarPath])
    renameSync(`${tarPath}.gz`, artifactPath)
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
