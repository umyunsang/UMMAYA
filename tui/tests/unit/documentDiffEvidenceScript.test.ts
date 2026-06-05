// SPDX-License-Identifier: Apache-2.0
// Evidence Fabric UX artifact test for document diff frame dumping.

import { afterEach, describe, expect, it } from 'bun:test'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const tempDirs: string[] = []

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
    const exitCode = await proc.exited
    const stderr = await new Response(proc.stderr).text()

    expect(exitCode, stderr).toBe(0)
    const manifest = JSON.parse(readFileSync(join(outDir, 'manifest.json'), 'utf8')) as Array<{
      slug: string
      tool_id: string
      frame_path: string
      has_saved_exports?: boolean
    }>
    const scenario = manifest.find(
      (entry) => entry.slug === 'single-primitive-document-fill',
    )

    expect(scenario?.tool_id).toBe('document')
    expect(scenario?.frame_path).toBe('single-primitive-document-fill.txt')

    const frame = readFileSync(join(outDir, scenario!.frame_path), 'utf8')
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

    const styleSaveScenario = manifest.find(
      (entry) => entry.slug === 'single-primitive-style-save',
    )
    expect(styleSaveScenario?.tool_id).toBe('document')
    expect(styleSaveScenario?.has_saved_exports).toBe(true)

    const styleSaveFrame = readFileSync(
      join(outDir, styleSaveScenario!.frame_path),
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
      join(outDir, scenario!.frame_path),
      'utf8',
    )
    expect(fillFrame).not.toContain('Saved:')
  })
})
