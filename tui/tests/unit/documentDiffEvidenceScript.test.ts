// SPDX-License-Identifier: Apache-2.0
// Evidence Fabric UX artifact test for document diff frame dumping.

import { afterEach, describe, expect, it } from 'bun:test'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const tempDirs: string[] = []
const EVIDENCE_SCRIPT_TIMEOUT_MS = 12_000
const EVIDENCE_SCRIPT_TEST_TIMEOUT_MS = 15_000

interface ManifestEntry {
  readonly slug: string
  readonly tool_id: string
  readonly frame_path: string
  readonly has_saved_exports?: boolean
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function parseManifestEntry(value: unknown): ManifestEntry {
  if (!isRecord(value)) {
    throw new Error('Document diff manifest entry must be an object')
  }
  const slug = value['slug']
  const toolId = value['tool_id']
  const framePath = value['frame_path']
  const hasSavedExports = value['has_saved_exports']
  if (
    typeof slug !== 'string' ||
    typeof toolId !== 'string' ||
    typeof framePath !== 'string' ||
    (hasSavedExports !== undefined && typeof hasSavedExports !== 'boolean')
  ) {
    throw new Error('Document diff manifest entry has an invalid shape')
  }
  return {
    slug,
    tool_id: toolId,
    frame_path: framePath,
    ...(hasSavedExports === undefined
      ? {}
      : { has_saved_exports: hasSavedExports }),
  }
}

function parseManifest(value: unknown): ManifestEntry[] {
  if (!Array.isArray(value)) {
    throw new Error('Document diff manifest must be an array')
  }
  return value.map(parseManifestEntry)
}

function requireManifestEntry(
  manifest: readonly ManifestEntry[],
  slug: string,
): ManifestEntry {
  const entry = manifest.find((candidate) => candidate.slug === slug)
  if (entry === undefined) {
    throw new Error(`Missing document diff evidence scenario: ${slug}`)
  }
  return entry
}

afterEach(() => {
  for (const dir of tempDirs.splice(0)) {
    rmSync(dir, { recursive: true, force: true })
  }
})

describe('dump-document-diff-frames evidence script', () => {
  it('captures the single model-facing document primitive result surface', async () => {
    const outDir = mkdtempSync(join(tmpdir(), 'ummaya-document-diff-evidence-'))
    tempDirs.push(outDir)

    const proc = Bun.spawn(['bun', 'run', 'scripts/dump-document-diff-frames.tsx'], {
      cwd: join(import.meta.dir, '..', '..'),
      env: {
        ...process.env,
        UMMAYA_EVIDENCE_OUT_DIR: outDir,
      },
      stdout: 'pipe',
      stderr: 'pipe',
    })
    const stdoutPromise = new Response(proc.stdout).text()
    const stderrPromise = new Response(proc.stderr).text()

    const timeout = setTimeout(() => {
      proc.kill()
    }, EVIDENCE_SCRIPT_TIMEOUT_MS)
    const exitCode = await proc.exited
    clearTimeout(timeout)
    const [stdout, stderr] = await Promise.all([stdoutPromise, stderrPromise])

    expect(exitCode, `${stderr}\n${stdout}`).toBe(0)
    const manifest = parseManifest(
      JSON.parse(readFileSync(join(outDir, 'manifest.json'), 'utf8')),
    )
    const scenario = requireManifestEntry(
      manifest,
      'single-primitive-document-fill',
    )

    expect(scenario.tool_id).toBe('document')
    expect(scenario.frame_path).toBe('single-primitive-document-fill.txt')

    const frame = readFileSync(join(outDir, scenario.frame_path), 'utf8')
    expect(frame).toContain('Changed 1 field')
    expect(frame).toContain('12주차')
    expect(frame).toContain('13주차')
    expect(frame).toContain('text[1]')
    expect(frame).not.toContain('Document OK')
    expect(frame).not.toContain('document_render')
    expect(frame).not.toContain('viewer.html')
    for (const glyph of ['╭', '╮', '╰', '╯']) {
      expect(frame).not.toContain(glyph)
    }

    const styleSaveScenario = requireManifestEntry(
      manifest,
      'single-primitive-style-save',
    )
    expect(styleSaveScenario.tool_id).toBe('document')
    expect(styleSaveScenario.has_saved_exports).toBe(true)

    const styleSaveFrame = readFileSync(
      join(outDir, styleSaveScenario.frame_path),
      'utf8',
    )
    expect(styleSaveFrame).toContain('Changed 2 fields')
    expect(styleSaveFrame).toContain('접수번호 서식')
    expect(styleSaveFrame).toContain('Malgun Gothic 12pt bold')
    expect(styleSaveFrame).toContain('UMMAYA-2026-0007')
    expect(styleSaveFrame).toContain(
      'Saved: /tmp/ummaya/tui-exports/seoul-culture-application-plan.docx',
    )
    expect(styleSaveFrame).not.toContain('9f59d2f1e8c4b0a8d1cafe')

    const fillFrame = readFileSync(
      join(outDir, scenario.frame_path),
      'utf8',
    )
    expect(fillFrame).not.toContain('Saved:')
  }, EVIDENCE_SCRIPT_TEST_TIMEOUT_MS)
})
