import { existsSync, readFileSync } from 'fs'
import { join } from 'path'
import { describe, expect, test } from 'bun:test'

const taskToolFiles = [
  'TaskOutputTool/TaskOutputTool.tsx',
  'TaskUpdateTool/TaskUpdateTool.ts',
  'TaskOutputTool/schemas.ts',
  'TaskOutputTool/lookup.ts',
  'TaskOutputTool/serialization.ts',
  'TaskOutputTool/render.tsx',
  'TaskUpdateTool/schemas.ts',
  'TaskUpdateTool/completion.ts',
  'TaskUpdateTool/statusUpdate.ts',
  'TaskUpdateTool/serialization.ts',
] as const

function sourcePath(pathFromToolsRoot: string): string {
  return join(import.meta.dir, '..', pathFromToolsRoot)
}

function pureLoc(source: string): number {
  return source
    .split('\n')
    .filter(line => line.trim() !== '')
    .filter(line => !line.trimStart().startsWith('//'))
    .length
}

describe('task tool split contract', () => {
  test('TaskOutput and TaskUpdate responsibilities stay in small modules', () => {
    for (const pathFromToolsRoot of taskToolFiles) {
      const path = sourcePath(pathFromToolsRoot)

      expect(existsSync(path)).toBe(true)
      expect(pureLoc(readFileSync(path, 'utf8'))).toBeLessThanOrEqual(250)
    }
  })
})
