import { existsSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { internalDirectories } from './config.mjs'

export function listToolDirectories(root, relativePath) {
  if (!existsSync(root)) {
    throw new Error(`Required tool directory is missing: ${relativePath(root)}`)
  }
  return readdirSync(root, { withFileTypes: true })
    .filter(entry => entry.isDirectory() && !internalDirectories.has(entry.name))
    .map(entry => entry.name)
    .sort((left, right) => left.localeCompare(right))
}

export function collectSourceTools(sourceText, root, relativePath) {
  const tools = new Map()
  const staticImport =
    /import\s+\{([^}]+)\}\s+from\s+['"]([^'"]+)['"]/gu
  const requireProperty =
    /require\(['"]([^'"]+)['"]\)\s*(?:as\s+[^)]*)?\)?\s*\.\s*([A-Z][A-Za-z0-9_]*Tool)\b/gsu

  for (const match of sourceText.matchAll(staticImport)) {
    const importPath = match[2]
    if (!importPath || !isToolImportPath(importPath)) continue
    for (const toolName of parseImportSpecifiers(match[1] ?? '')) {
      tools.set(toolName, resolveSourcePath(root, importPath, toolName, relativePath))
    }
  }
  for (const match of sourceText.matchAll(requireProperty)) {
    const importPath = match[1]
    const toolName = match[2]
    if (!importPath || !toolName || !isToolImportPath(importPath)) continue
    tools.set(toolName, resolveSourcePath(root, importPath, toolName, relativePath))
  }
  return tools
}

export function mergeRowSeed(seeds, toolName, patch) {
  const existing = seeds.get(toolName) ?? { tool_name: toolName }
  seeds.set(toolName, { ...existing, ...patch })
}

function parseImportSpecifiers(specifiers) {
  return specifiers
    .split(',')
    .map(specifier => specifier.trim().replace(/^type\s+/, ''))
    .map(specifier => specifier.split(/\s+as\s+/u).at(-1)?.trim() ?? '')
    .filter(specifier => /^[A-Z][A-Za-z0-9_]*(Tool|Primitive)$/u.test(specifier))
}

function isToolImportPath(importPath) {
  const normalized = normalizeRelativeSource(importPath)
  return (
    normalized.startsWith('tools/') ||
    /(?:^|\/)(?:[A-Z][A-Za-z0-9_]*(?:Tool|Primitive)|testing)\//u.test(
      normalized,
    )
  )
}

function normalizeRelativeSource(importPath) {
  return importPath
    .replace(/^\.\//u, '')
    .replace(/\.js$/u, '.ts')
    .replaceAll('\\', '/')
}

function possibleSourcePaths(root, importPath) {
  const normalized = normalizeRelativeSource(importPath)
  const exactTs = join(root, normalized)
  const exactTsx = exactTs.replace(/\.ts$/u, '.tsx')
  return [exactTs, exactTsx]
}

function resolveSourcePath(root, importPath, fallbackGroup, relativePath) {
  if (importPath) {
    for (const candidate of possibleSourcePaths(root, importPath)) {
      if (existsSync(candidate)) return relativePath(candidate)
    }
    return 'missing'
  }
  const directory = join(root, fallbackGroup)
  return existsSync(directory) ? `${relativePath(directory)}/` : 'missing'
}
