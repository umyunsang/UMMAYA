import { logError } from '../../../utils/log.js'

export function dataIdleDeadline(timeoutMs: number | undefined): number {
  return timeoutMs === undefined
    ? Number.POSITIVE_INFINITY
    : performance.now() + timeoutMs
}

export function dataIdleTimeoutRemaining(
  timeoutMs: number | undefined,
  deadline: number,
): number | undefined {
  if (timeoutMs === undefined) return undefined
  return deadline - performance.now()
}

export async function readNextStreamChunk(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  timeoutMs: number | undefined,
): Promise<ReadableStreamReadResult<Uint8Array> | 'timeout'> {
  if (timeoutMs === undefined) return await reader.read()
  if (timeoutMs <= 0) return 'timeout'
  let timeoutId: ReturnType<typeof setTimeout> | undefined
  const timeout = new Promise<'timeout'>(resolve => {
    timeoutId = setTimeout(() => resolve('timeout'), timeoutMs)
  })
  const result = await Promise.race([reader.read(), timeout])
  if (timeoutId !== undefined) clearTimeout(timeoutId)
  return result
}

export async function cancelReader(
  reader: ReadableStreamDefaultReader<Uint8Array>,
): Promise<void> {
  try {
    await reader.cancel()
  } catch (error) {
    logError(error instanceof Error ? error : new Error(String(error)))
  }
}
