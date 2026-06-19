import type { Usage } from './types.js'

export function cleanupStream(stream: ReadableStream<unknown> | undefined): void {
  void stream?.cancel()
}

function addNumber(left: number | undefined, right: number | undefined): number {
  return (left ?? 0) + (right ?? 0)
}

export function updateUsage(usage: Usage, partUsage: Partial<Usage> | undefined): Usage {
  if (!partUsage) return usage
  return {
    ...usage,
    input_tokens: addNumber(usage.input_tokens, partUsage.input_tokens),
    output_tokens: addNumber(usage.output_tokens, partUsage.output_tokens),
    cache_creation_input_tokens: addNumber(
      usage.cache_creation_input_tokens,
      partUsage.cache_creation_input_tokens,
    ),
    cache_read_input_tokens: addNumber(
      usage.cache_read_input_tokens,
      partUsage.cache_read_input_tokens,
    ),
  }
}

export function accumulateUsage(totalUsage: Usage, messageUsage: Usage): Usage {
  return updateUsage(totalUsage, messageUsage)
}
