import { describe, expect, test } from 'bun:test'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { z } from 'zod/v4'
import { createUserMessage } from '../../../src/utils/userMessageFactories.js'
import {
  captureProviderExchange,
  createDiagnosticsTarget,
  responseForTextDelta,
  withFriendliEnv,
} from './ummaya-provider-friendli.helpers.js'

const joinRecordSchema = z.object({
  session_id: z.string().min(1),
  correlation_id: z.string().min(1),
  frame_hash: z.string().regex(/^[a-f0-9]{64}$/u),
}).passthrough()

describe('provider-direct evidence join', () => {
  test('records join keys and sanitized memdir evidence for visible assistant output', async () => {
    await withFriendliEnv(async () => {
      const diagnostics = createDiagnosticsTarget()
      const previousRoutePath = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      const previousMemdirUser = process.env.UMMAYA_MEMDIR_USER
      const memdirRoot = join(dirname(diagnostics.path), 'memdir')
      process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = diagnostics.path
      process.env.UMMAYA_MEMDIR_USER = memdirRoot

      try {
        const exchange = await captureProviderExchange({
          messages: [
            createUserMessage({ content: '테스트: 한 문장으로 인사만 해줘.' }),
          ],
          response: responseForTextDelta('안녕하세요!'),
        })

        expect(JSON.stringify(exchange.events)).toContain('안녕하세요')
        const routeJoinRecord = readFirstJoinRecord(diagnostics.path)
        expect(routeJoinRecord).not.toBeNull()
        const sessionFiles = listFiles(memdirRoot)
          .filter(path => path.endsWith('.jsonl'))
        expect(sessionFiles.length).toBeGreaterThan(0)
        const sessionEvidence = sessionFiles
          .map(path => readFileSync(path, 'utf8'))
          .join('\n')
        expect(sessionEvidence).toContain(routeJoinRecord?.session_id)
        expect(sessionEvidence).toContain(routeJoinRecord?.correlation_id)
        expect(sessionEvidence).toContain(routeJoinRecord?.frame_hash)
        expect(sessionEvidence).not.toContain('friendli-token')
      } finally {
        restoreEnv('UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE', previousRoutePath)
        restoreEnv('UMMAYA_MEMDIR_USER', previousMemdirUser)
        diagnostics.cleanup()
      }
    })
  })
})

function restoreEnv(name: string, previousValue: string | undefined): void {
  if (previousValue === undefined) {
    delete process.env[name]
    return
  }
  process.env[name] = previousValue
}

function readFirstJoinRecord(path: string): z.infer<typeof joinRecordSchema> | null {
  if (!existsSync(path)) return null
  for (const line of readFileSync(path, 'utf8').split('\n')) {
    if (line.trim().length === 0) continue
    const parsed: unknown = JSON.parse(line)
    const result = joinRecordSchema.safeParse(parsed)
    if (result.success) return result.data
  }
  return null
}

function listFiles(root: string): readonly string[] {
  if (!existsSync(root)) return []
  const files: string[] = []
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    const fullPath = join(root, entry.name)
    if (entry.isDirectory()) {
      files.push(...listFiles(fullPath))
    } else {
      files.push(fullPath)
    }
  }
  return files
}
