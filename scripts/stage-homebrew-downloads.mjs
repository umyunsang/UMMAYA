#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0

import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  writeFileSync,
} from 'node:fs'
import { basename, join } from 'node:path'

const DEFAULT_BASE_URL = 'https://ummaya-docs.pages.dev/downloads/homebrew'
const ARCHES = ['arm64', 'x64']

function parseArgs(argv) {
  const args = {
    root: 'docs-site/dist/downloads/homebrew',
    baseUrl: DEFAULT_BASE_URL,
    preserveRemote: false,
  }

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    if (arg === '--artifact-dir') {
      args.artifactDir = argv[++index]
    } else if (arg === '--tag') {
      args.tag = argv[++index]
    } else if (arg === '--root') {
      args.root = argv[++index]
    } else if (arg === '--base-url') {
      args.baseUrl = argv[++index].replace(/\/$/, '')
    } else if (arg === '--preserve-remote') {
      args.preserveRemote = true
    } else if (arg === '-h' || arg === '--help') {
      usage()
      process.exit(0)
    } else {
      throw new Error(`Unknown argument: ${arg}`)
    }
  }

  if (args.artifactDir && !args.tag) {
    throw new Error('--tag is required when --artifact-dir is provided')
  }
  if (args.tag && !/^v\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$/.test(args.tag)) {
    throw new Error(`Invalid release tag: ${args.tag}`)
  }
  return args
}

function usage() {
  process.stdout.write(`Usage: scripts/stage-homebrew-downloads.mjs [--artifact-dir dist/homebrew --tag vX.Y.Z] [--root docs-site/dist/downloads/homebrew] [--base-url URL] [--preserve-remote]\n`)
}

async function fetchJson(url) {
  const response = await fetch(url)
  if (response.status === 404) {
    return null
  }
  if (!response.ok) {
    throw new Error(`Failed to fetch ${url}: HTTP ${response.status}`)
  }
  return response.json()
}

async function downloadFile(url, path) {
  const response = await fetch(url)
  if (response.status === 404) {
    return false
  }
  if (!response.ok) {
    throw new Error(`Failed to fetch ${url}: HTTP ${response.status}`)
  }
  const bytes = Buffer.from(await response.arrayBuffer())
  mkdirSync(join(path, '..'), { recursive: true })
  writeFileSync(path, bytes)
  return true
}

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'))
}

function writeJson(path, data) {
  writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`)
}

function stageLocalArtifacts({ artifactDir, baseUrl, root, tag }) {
  const version = tag.replace(/^v/, '')
  const versionDir = join(root, tag)
  mkdirSync(versionDir, { recursive: true })

  const artifacts = {}
  for (const arch of ARCHES) {
    const stem = `ummaya-${version}-macos-${arch}`
    const metadataPath = join(artifactDir, `${stem}.json`)
    const archivePath = join(artifactDir, `${stem}.tar.gz`)
    const shaPath = join(artifactDir, `${stem}.tar.gz.sha256`)
    for (const path of [metadataPath, archivePath, shaPath]) {
      if (!existsSync(path)) {
        throw new Error(`Missing local cask artifact: ${path}`)
      }
      copyFileSync(path, join(versionDir, basename(path)))
    }
    artifacts[arch] = readJson(metadataPath)
  }

  const manifest = {
    version,
    tag,
    baseUrl: `${baseUrl}/${tag}`,
    artifacts,
  }
  writeJson(join(versionDir, 'manifest.json'), manifest)
  return manifest
}

async function preserveRemoteArtifacts({ baseUrl, root }) {
  const manifests = new Map()
  const versions = await fetchJson(`${baseUrl}/versions.json`)
  const latest = await fetchJson(`${baseUrl}/latest.json`)
  const remoteManifests = []

  if (versions?.versions) {
    for (const item of versions.versions) {
      if (item?.tag) {
        remoteManifests.push(item)
      }
    }
  } else if (latest?.tag) {
    remoteManifests.push(latest)
  }

  for (const manifest of remoteManifests) {
    const versionDir = join(root, manifest.tag)
    mkdirSync(versionDir, { recursive: true })
    let complete = true
    for (const arch of ARCHES) {
      const metadata = manifest.artifacts?.[arch]
      if (!metadata?.artifact) {
        complete = false
        continue
      }
      const names = [
        metadata.artifact,
        `${metadata.artifact}.sha256`,
        `ummaya-${manifest.version}-macos-${arch}.json`,
      ]
      for (const name of names) {
        const ok = await downloadFile(`${baseUrl}/${manifest.tag}/${name}`, join(versionDir, name))
        complete &&= ok
      }
    }
    if (complete) {
      writeJson(join(versionDir, 'manifest.json'), manifest)
      manifests.set(manifest.tag, manifest)
    }
  }
  return { latest, manifests }
}

function compareVersionsDesc(left, right) {
  const parse = (version) => version.split(/[.-]/).map((part) => (/^\d+$/.test(part) ? Number(part) : part))
  const a = parse(left.version)
  const b = parse(right.version)
  const length = Math.max(a.length, b.length)
  for (let index = 0; index < length; index += 1) {
    const av = a[index] ?? 0
    const bv = b[index] ?? 0
    if (typeof av === 'number' && typeof bv === 'number' && av !== bv) {
      return bv - av
    }
    const diff = String(bv).localeCompare(String(av))
    if (diff !== 0) {
      return diff
    }
  }
  return 0
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  mkdirSync(args.root, { recursive: true })

  const staged = new Map()
  let latest

  if (args.preserveRemote) {
    const remote = await preserveRemoteArtifacts(args)
    latest = remote.latest
    for (const [tag, manifest] of remote.manifests) {
      staged.set(tag, manifest)
    }
  }

  if (args.artifactDir) {
    const manifest = stageLocalArtifacts(args)
    staged.set(manifest.tag, manifest)
    latest = manifest
  }

  if (!latest && staged.size > 0) {
    latest = [...staged.values()].sort(compareVersionsDesc)[0]
  }

  if (latest) {
    writeJson(join(args.root, 'latest.json'), latest)
  }

  writeJson(join(args.root, 'versions.json'), {
    versions: [...staged.values()].sort(compareVersionsDesc),
  })

  console.log(`stage-homebrew-downloads: staged ${staged.size} version(s) under ${args.root}`)
}

main()
