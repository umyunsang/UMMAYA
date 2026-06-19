import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join, relative } from 'node:path'
import { GENERATED_AT, PARITY_ARTIFACT_ROOT } from './config.mjs'

export function createSourceSnapshotHelpers(repoRoot, parityArtifactRoot) {
  function relativePath(path) {
    return relative(repoRoot, path).replaceAll('\\', '/')
  }

  function readRequired(path) {
    if (!existsSync(path)) {
      throw new Error(`Required source path is missing: ${relativePath(path)}`)
    }
    return readFileSync(path, 'utf8')
  }

  function hashText(text) {
    return createHash('sha256').update(text).digest('hex')
  }

  function absolutePath(path) {
    return join(repoRoot, path.replace(/\/$/u, ''))
  }

  function listSourceFiles(root) {
    if (statSync(root).isFile()) return [root]
    return readdirSync(root, { withFileTypes: true })
      .flatMap(entry => {
        const path = join(root, entry.name)
        return entry.isDirectory() ? listSourceFiles(path) : [path]
      })
      .sort((left, right) => left.localeCompare(right))
  }

  function readSnapshot(path) {
    if (!isConcretePath(path) || !existsSync(absolutePath(path))) return undefined
    const root = absolutePath(path)
    const rootStat = statSync(root)
    const files = listSourceFiles(root).map(filePath => {
      const text = readFileSync(filePath, 'utf8')
      const relativeToSource = rootStat.isFile()
        ? relative(dirname(root), filePath).replaceAll('\\', '/')
        : relative(root, filePath).replaceAll('\\', '/')
      return {
        path: relativeToSource,
        sha256: hashText(text),
        line_count: text.split('\n').length - 1,
      }
    })
    return {
      digest: hashText(files.map(file => `${file.path}:${file.sha256}`).join('\n')),
      file_count: files.length,
      files,
    }
  }

  function compareSources(ccPath, ummayaPath) {
    const cc = readSnapshot(ccPath)
    const ummaya = readSnapshot(ummayaPath)
    if (!cc && !ummaya) return { diff_status: 'not-applicable', cc, ummaya }
    if (!cc && isConcretePath(ccPath)) return { diff_status: 'missing-cc-source', cc, ummaya }
    if (!ummaya && isConcretePath(ummayaPath)) {
      return { diff_status: 'missing-ummaya-source', cc, ummaya }
    }
    if (!cc || !ummaya) return { diff_status: 'not-applicable', cc, ummaya }
    return {
      diff_status: cc.digest === ummaya.digest ? 'identical' : 'different',
      cc,
      ummaya,
    }
  }

  function changedFiles(comparison) {
    const ccFiles = new Map((comparison.cc?.files ?? []).map(file => [file.path, file]))
    const ummayaFiles = new Map(
      (comparison.ummaya?.files ?? []).map(file => [file.path, file]),
    )
    const paths = [...new Set([...ccFiles.keys(), ...ummayaFiles.keys()])].sort()
    return paths
      .map(path => ({
        path,
        cc_sha256: ccFiles.get(path)?.sha256 ?? 'missing',
        ummaya_sha256: ummayaFiles.get(path)?.sha256 ?? 'missing',
        cc_line_count: ccFiles.get(path)?.line_count ?? 0,
        ummaya_line_count: ummayaFiles.get(path)?.line_count ?? 0,
      }))
      .filter(file => file.cc_sha256 !== file.ummaya_sha256)
  }

  function writeDiffArtifact(name, ccPath, ummayaPath, status, comparison) {
    const relativeArtifactPath = `${PARITY_ARTIFACT_ROOT}/${artifactName(name)}`
    const changes = changedFiles(comparison)
    const payload = {
      schema_version: 'cc-tool-parity-diff.v1',
      generated_at: GENERATED_AT,
      name,
      status,
      diff_status: comparison.diff_status,
      cc_source_path: ccPath,
      ummaya_path: ummayaPath,
      cc_digest: comparison.cc?.digest ?? 'not-applicable',
      ummaya_digest: comparison.ummaya?.digest ?? 'not-applicable',
      cc_file_count: comparison.cc?.file_count ?? 0,
      ummaya_file_count: comparison.ummaya?.file_count ?? 0,
      changed_files: changes.slice(0, 40),
      omitted_changed_file_count: Math.max(changes.length - 40, 0),
    }
    mkdirSync(parityArtifactRoot, { recursive: true })
    writeFileSync(join(repoRoot, relativeArtifactPath), `${JSON.stringify(payload, null, 2)}\n`)
    return relativeArtifactPath
  }

  return { compareSources, readRequired, relativePath, writeDiffArtifact }
}

export function isConcretePath(path) {
  return path !== 'missing' && path !== 'not-present-in-cc'
}

function artifactName(name) {
  return `${name.replace(/[^A-Za-z0-9_-]/gu, '-')}.json`
}
