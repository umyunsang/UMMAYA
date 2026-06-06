import { describe, expect, test } from 'bun:test'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { appendRoutePermissionPromptDiagnostic } from '../../src/tools/AdapterTool/routeDiagnostics.js'

describe('route diagnostics', () => {
  test('records prompted permission boundary for concrete adapters', () => {
    const previousPath = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
    const dir = mkdtempSync(join(tmpdir(), 'ummaya-route-prompt-'))
    const path = join(dir, 'route.jsonl')
    process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = path

    try {
      appendRoutePermissionPromptDiagnostic({
        toolName: 'mock_verify_module_simple_auth',
        input: { scope_list: ['send:gov24.minwon'] },
        toolUseID: 'tool-use-1',
        messageID: 'message-1',
        queryChainID: 'chain-1',
        queryDepth: 0,
        permissionMode: 'default',
      })

      const record = JSON.parse(readFileSync(path, 'utf8').trim()) as Record<
        string,
        unknown
      >
      expect(record).toEqual(
        expect.objectContaining({
          event: 'route_tool_permission',
          tool_name: 'mock_verify_module_simple_auth',
          tool_surface: 'concrete_adapter',
          permission_behavior: 'ask',
          result_status: 'prompted',
        }),
      )
    } finally {
      if (previousPath === undefined) {
        delete process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
      } else {
        process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE = previousPath
      }
      rmSync(dir, { recursive: true, force: true })
    }
  })
})
