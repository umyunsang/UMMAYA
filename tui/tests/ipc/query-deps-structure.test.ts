import { describe, expect, test } from 'bun:test'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const TUI_ROOT = join(__dirname, '../..')

describe('query deps structure', () => {
  test('keeps the production model dependency on the UMMAYA-named CC-shaped provider', () => {
    const source = readFileSync(join(TUI_ROOT, 'src/query/deps.ts'), 'utf8')

    expect(source).toContain(
      "import { queryModelWithStreaming } from '../services/api/ummaya.js'",
    )
    expect(source).toContain('callModel: queryModelWithStreaming')
    expect(source).not.toContain('../services/api/claude.js')
    expect(source).not.toContain('getOrCreateUmmayaBridge')
    expect(source).not.toContain('ChatRequestFrame')
    expect(source).not.toContain('IPCFrame')
    expect(source).not.toContain('bridge.frames()')
  })
})
