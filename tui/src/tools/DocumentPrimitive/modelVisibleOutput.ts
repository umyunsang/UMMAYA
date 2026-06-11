// SPDX-License-Identifier: Apache-2.0

export function modelVisibleDocumentOutput(output: unknown): unknown {
  return rewriteModelVisibleDocumentValue(output)
}

function rewriteModelVisibleDocumentValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(item => rewriteModelVisibleDocumentValue(item))
  }
  const record = recordFrom(value)
  if (record === null) {
    return value
  }

  const rewritten: Record<string, unknown> = {}
  for (const [key, nested] of Object.entries(record)) {
    rewritten[key] = rewriteModelVisibleDocumentValue(nested)
  }

  const displayLabel = nonEmptyString(rewritten.display_label)
  if (displayLabel !== undefined && typeof rewritten.target_path === 'string') {
    rewritten.target_path = displayLabel
  }
  return rewritten
}

function recordFrom(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? Object.fromEntries(Object.entries(value))
    : null
}

function nonEmptyString(value: unknown): string | undefined {
  if (typeof value !== 'string') {
    return undefined
  }
  const trimmed = value.trim()
  return trimmed === '' ? undefined : trimmed
}
