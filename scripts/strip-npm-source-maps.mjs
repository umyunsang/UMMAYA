#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0

import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'

const INLINE_SOURCE_MAP_MARKER = 'sourceMappingURL=data:application/json'
const BACKUP_DIR = '.ummaya-npm-prepack-backup'
const MANIFEST_FILE = 'manifest.json'
const SOURCE_ROOTS = ['tui/src']

function parseArgs(argv) {
  let mode = null
  let root = process.cwd()

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    if (arg === '--strip' || arg === '--restore') {
      mode = arg.slice(2)
    } else if (arg === '--root') {
      root = resolve(argv[++index] ?? '')
    } else {
      throw new Error(`Unknown argument: ${arg}`)
    }
  }

  if (mode !== 'strip' && mode !== 'restore') {
    throw new Error('Usage: scripts/strip-npm-source-maps.mjs (--strip|--restore) [--root <path>]')
  }

  return { mode, root }
}

function sourceFilesUnder(root, relativeDir) {
  const absoluteDir = join(root, relativeDir)
  if (!existsSync(absoluteDir)) {
    return []
  }

  return readdirSync(absoluteDir, { withFileTypes: true })
    .flatMap((entry) => {
      const relativePath = join(relativeDir, entry.name)
      if (entry.isDirectory()) return sourceFilesUnder(root, relativePath)
      if (!entry.isFile()) return []
      return /\.(tsx?|jsx?)$/.test(entry.name) ? [relativePath] : []
    })
    .sort()
}

function stripInlineSourceMapLines(source, filePath) {
  const newline = source.includes('\r\n') ? '\r\n' : '\n'
  const lines = source.split(/\r\n|\n/u)
  let removed = 0
  const strippedLines = lines.filter((line) => {
    if (!line.includes(INLINE_SOURCE_MAP_MARKER)) return true
    if (!/^\s*\/\/# sourceMappingURL=data:application\/json/u.test(line)) {
      throw new Error(`${filePath} contains an inline source map marker inside code`)
    }
    removed += 1
    return false
  })

  if (removed === 0) {
    throw new Error(`${filePath} contains no full-line inline source map`)
  }

  const stripped = strippedLines.join(newline)
  if (stripped.includes(INLINE_SOURCE_MAP_MARKER)) {
    throw new Error(`${filePath} still contains an inline source map after stripping`)
  }
  return stripped
}

function manifestPath(root) {
  return join(root, BACKUP_DIR, MANIFEST_FILE)
}

function strip(root) {
  const backupRoot = join(root, BACKUP_DIR)
  if (existsSync(backupRoot)) {
    throw new Error(`${BACKUP_DIR} already exists; run --restore before stripping again`)
  }

  const changed = []
  for (const sourceRoot of SOURCE_ROOTS) {
    for (const file of sourceFilesUnder(root, sourceRoot)) {
      const absolutePath = join(root, file)
      const source = readFileSync(absolutePath, 'utf8')
      if (!source.includes(INLINE_SOURCE_MAP_MARKER)) continue

      changed.push({ file, stripped: stripInlineSourceMapLines(source, file) })
    }
  }

  if (changed.length === 0) {
    console.error('strip-npm-source-maps: stripped 0 file(s)')
    return
  }

  mkdirSync(backupRoot, { recursive: true })
  for (const { file } of changed) {
    const absolutePath = join(root, file)
    const backupPath = join(backupRoot, 'files', file)
    mkdirSync(dirname(backupPath), { recursive: true })
    copyFileSync(absolutePath, backupPath)
  }

  writeFileSync(
    manifestPath(root),
    `${JSON.stringify({ version: 1, files: changed.map(({ file }) => file).sort() }, null, 2)}\n`,
  )

  for (const { file, stripped } of changed) {
    writeFileSync(join(root, file), stripped)
  }
  console.error(`strip-npm-source-maps: stripped ${changed.length} file(s)`)
}

function restore(root) {
  const backupRoot = join(root, BACKUP_DIR)
  const path = manifestPath(root)
  if (!existsSync(path)) {
    console.error(`strip-npm-source-maps: no ${BACKUP_DIR} manifest to restore`)
    return
  }

  const manifest = JSON.parse(readFileSync(path, 'utf8'))
  if (manifest.version !== 1 || !Array.isArray(manifest.files)) {
    throw new Error(`${relative(root, path)} is not a supported source-map backup manifest`)
  }

  for (const file of manifest.files) {
    if (typeof file !== 'string') {
      throw new Error(`${relative(root, path)} contains a non-string file path`)
    }
    const backupPath = join(backupRoot, 'files', file)
    const targetPath = join(root, file)
    mkdirSync(dirname(targetPath), { recursive: true })
    copyFileSync(backupPath, targetPath)
  }
  rmSync(backupRoot, { recursive: true, force: true })
  console.error(`strip-npm-source-maps: restored ${manifest.files.length} file(s)`)
}

const args = parseArgs(process.argv.slice(2))
if (args.mode === 'strip') {
  strip(args.root)
} else {
  restore(args.root)
}
