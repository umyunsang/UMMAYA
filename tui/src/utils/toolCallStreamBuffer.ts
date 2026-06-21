const RAW_JSON_TOOL_CALL_KEY_START_RE =
  /^\s*\{\s*["'](?:name|tool)["']\s*:\s*["'][^"']+["']/iu

export function looksLikeRawJsonToolCallStart(text: string): boolean {
  return RAW_JSON_TOOL_CALL_KEY_START_RE.test(text)
}

export function firstRawJsonToolCallStartOffset(text: string): number {
  let braceOffset = text.indexOf('{')
  while (braceOffset >= 0) {
    if (looksLikeRawJsonToolCallStart(text.slice(braceOffset))) {
      return braceOffset
    }
    braceOffset = text.indexOf('{', braceOffset + 1)
  }
  return -1
}

export function looksLikePotentialRawJsonToolCallStart(text: string): boolean {
  const trimmedStart = text.trimStart()
  if (!trimmedStart.startsWith('{')) return false

  let index = 1
  while (index < trimmedStart.length && /\s/u.test(trimmedStart[index] ?? '')) {
    index += 1
  }
  if (index >= trimmedStart.length) return true

  const quote = trimmedStart[index]
  if (quote !== '"' && quote !== "'") return false
  index += 1

  let key = ''
  while (index < trimmedStart.length && trimmedStart[index] !== quote) {
    key += trimmedStart[index]
    index += 1
  }
  const lowerKey = key.toLowerCase()
  const keyCandidates = ['name', 'tool'] as const
  if (!keyCandidates.some(candidate => candidate.startsWith(lowerKey))) {
    return false
  }
  if (index >= trimmedStart.length) return true
  if (lowerKey !== 'name' && lowerKey !== 'tool') return false

  index += 1
  while (index < trimmedStart.length && /\s/u.test(trimmedStart[index] ?? '')) {
    index += 1
  }
  if (index >= trimmedStart.length) return true
  if (trimmedStart[index] !== ':') return false
  index += 1
  while (index < trimmedStart.length && /\s/u.test(trimmedStart[index] ?? '')) {
    index += 1
  }
  if (index >= trimmedStart.length) return true
  return trimmedStart[index] === '"' || trimmedStart[index] === "'"
}

export function firstRawJsonToolCallBufferStartOffset(text: string): number {
  let braceOffset = text.indexOf('{')
  while (braceOffset >= 0) {
    if (looksLikePotentialRawJsonToolCallStart(text.slice(braceOffset))) {
      return braceOffset
    }
    braceOffset = text.indexOf('{', braceOffset + 1)
  }
  return -1
}

export function firstTextualToolCallBufferStartOffset(
  text: string,
  openTag: string,
): number {
  const tagOffset = text.indexOf(openTag)
  if (tagOffset >= 0) return tagOffset

  const maxSuffixLength = Math.min(openTag.length - 1, text.length)
  for (let length = maxSuffixLength; length > 0; length -= 1) {
    if (text.endsWith(openTag.slice(0, length))) {
      return text.length - length
    }
  }
  return -1
}
