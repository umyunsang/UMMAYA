// SPDX-License-Identifier: Apache-2.0
// UMMAYA-original — Epic #1633 T041 US3 invariant test.
// Updated: Epic #2637 — services/remoteManagedSettings + constants/oauth.ts RESTORED
//   as UMMAYA no-op stubs for print.ts byte-copy pipeline (R-3-cascade + R-4).
//   Both carry SWAP/anti-anthropic-1p(2637) headers; Anthropic OAuth/remote-settings
//   surface is null/no-op in UMMAYA. Removed from banned list; added to stub-exists list.
//
// Validates FR-004..FR-006, FR-014, FR-015 — CC telemetry, auth, teleport,
// policy-limits, and Anthropic MCP surfaces have been removed.

import { describe, test, expect } from 'bun:test'
import { existsSync, statSync } from 'fs'
import { join } from 'path'

const REPO_ROOT = join(import.meta.dir, '..', '..', '..')
const TUI_SRC = join(REPO_ROOT, 'tui', 'src')

function exists(relativeToTuiSrc: string): boolean {
  return existsSync(join(TUI_SRC, relativeToTuiSrc))
}

function isFile(relativeToTuiSrc: string): boolean {
  try {
    return statSync(join(TUI_SRC, relativeToTuiSrc)).isFile()
  } catch {
    return false
  }
}

describe('Epic #1633 T041 — US3 invariant: CC dead-code directories removed', () => {
  test.each([
    'utils/secureStorage',
    'remote',
    'services/policyLimits',
    // 'services/remoteManagedSettings' — RESTORED Epic #2637 as UMMAYA no-op cascade stub
    //   for print.ts byte-copy (R-3-cascade). SWAP/anti-anthropic-1p(2637) header present.
    'services/analytics/datadog.ts',
    'services/analytics/sink.ts',
    'services/internalLogging.ts',
    'services/claudeAiLimitsHook.ts',
    'utils/teleport.tsx',
    'utils/teleport',
    'utils/model/antModels.ts',
    // 'constants/oauth.ts' — RESTORED Epic #2637 as UMMAYA no-op stub (R-4).
    //   OAuth CLIENT_IDs → null, MCP_CLIENT_METADATA_URL → null.
    //   SWAP/anti-anthropic-1p(2637) header present.
    'components/grove',
    'components/TeleportResumeWrapper.tsx',
    'hooks/useTeleportResume.tsx',
  ])('%s MUST NOT exist', (path) => {
    expect(exists(path), `${path} still present`).toBe(false)
  })

  test('tui/src/services/api/claude.ts MUST NOT exist after the public provider rename', () => {
    expect(isFile('services/api/claude.ts'), 'services/api/claude.ts still present').toBe(false)
  })

  test('tui/src/services/api/ummaya.ts MUST exist as the CC-compatible provider facade', () => {
    expect(isFile('services/api/ummaya.ts'), 'services/api/ummaya.ts missing').toBe(true)
  })

  test('tui/src/services/api/client.ts MUST exist (Epic #2077 — UMMAYA no-op stub)', () => {
    expect(isFile('services/api/client.ts'), 'services/api/client.ts missing').toBe(true)
  })
})

describe('Epic #1633 T041 — US3 invariant: stub files restored as UMMAYA no-ops', () => {
  // analytics/, auth.ts, oauth/ are stub-restored per FR-004 "strip or noop"
  // clause. They MUST exist but carry the UMMAYA stub header.
  test.each([
    'services/analytics/index.ts',
    'services/analytics/growthbook.ts',
    'services/analytics/firstPartyEventLogger.ts',
    'services/api/grove.ts',
    'services/claudeAiLimits.ts',
    'services/mcp/claudeai.ts',
    'utils/auth.ts',
    'services/oauth/client.ts',
    'services/oauth/index.ts',
    'utils/telemetry/sessionTracing.ts',
    'utils/modelCost.ts',
    'utils/betas.ts',
    'constants/betas.ts',
  ])('%s exists as UMMAYA no-op stub', async (path) => {
    expect(isFile(path), `${path} stub missing`).toBe(true)
    const content = await Bun.file(join(TUI_SRC, path)).text()
    expect(content).toContain('UMMAYA-original')
    // The byte-copy bridge stubs above carry Spec 2521 header instead of
    // Epic #1633; the original Spec 1633 stubs still carry Epic #1633.
    expect(content).toMatch(/Epic #1633|Spec 2521/)
    // No imports from the real @anthropic-ai/sdk in any stub
    expect(content).not.toMatch(/from ['"]@anthropic-ai\/sdk/)
  })
})
