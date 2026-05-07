// SPDX-License-Identifier: Apache-2.0
// KOSMOS-1633 P2 / KOSMOS-1978 T005 — Anthropic API key verification removed.
//
// Original CC module: .references/claude-code-sourcemap/restored-src/src/hooks/useApiKeyVerification.ts
// CC version: 2.1.88
// KOSMOS deviation: KOSMOS uses a single fixed provider (FriendliAI Serverless
// + K-EXAONE per kosmos-migration-tree.md § L1-A A1). Authentication is the
// `KOSMOS_FRIENDLI_TOKEN` (or `FRIENDLI_API_KEY`) env var consumed by the
// Python backend via `src/kosmos/llm/config.py`. The TUI never authenticates
// with Anthropic — every Anthropic credential lookup path (Keychain, OAuth,
// apiKeyHelper, Console subscription) is intentionally severed.
//
// This hook preserves the `VerificationStatus` discriminated-union shape so
// every existing consumer (PromptInputFooter, Notifications, REPL.tsx, etc)
// type-checks and reads `apiKeyStatus === 'valid'` as a green light. The
// status is computed from `KOSMOS_FRIENDLI_TOKEN` / `FRIENDLI_API_KEY` env
// presence — no network round-trip, no Anthropic API call.

import { useCallback, useState } from 'react'
import { hasFriendliCredential } from '../utils/friendliAuth.js'

export type VerificationStatus =
  | 'loading'
  | 'valid'
  | 'invalid'
  | 'missing'
  | 'error'

export type ApiKeyVerificationResult = {
  status: VerificationStatus
  reverify: () => Promise<void>
  error: Error | null
}

export function useApiKeyVerification(): ApiKeyVerificationResult {
  const [status, setStatus] = useState<VerificationStatus>(() =>
    hasFriendliCredential() ? 'valid' : 'missing',
  )
  // KOSMOS deviation: error is always null — no network failure path here.
  const [error] = useState<Error | null>(null)

  const verify = useCallback(async (): Promise<void> => {
    setStatus(hasFriendliCredential() ? 'valid' : 'missing')
  }, [])

  return {
    status,
    reverify: verify,
    error,
  }
}
