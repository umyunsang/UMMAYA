// SPDX-License-Identifier: Apache-2.0
// UMMAYA-original — document primitive timeout policy.

const DEFAULT_DOCUMENT_TIMEOUT_MS = 120_000

export function resolveDocumentPrimitiveTimeoutMs(): number {
  const env = process.env['UMMAYA_TUI_DOCUMENT_TIMEOUT_MS']
  if (env) {
    const parsed = Number.parseInt(env, 10)
    if (Number.isFinite(parsed) && parsed > 0) return parsed
  }
  return DEFAULT_DOCUMENT_TIMEOUT_MS
}
