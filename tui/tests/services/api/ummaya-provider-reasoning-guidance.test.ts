import { describe, expect, test } from 'bun:test'
import { createUserMessage } from '../../../src/utils/userMessageFactories.js'
import {
  captureProviderExchange,
  serializedMessages,
  withFriendliEnv,
} from './ummaya-provider-friendli.helpers.js'

async function withReasoningMode<T>(
  mode: string,
  run: () => Promise<T>,
): Promise<T> {
  const previous = process.env.UMMAYA_K_EXAONE_REASONING_MODE
  try {
    process.env.UMMAYA_K_EXAONE_REASONING_MODE = mode
    return await run()
  } finally {
    if (previous === undefined) {
      delete process.env.UMMAYA_K_EXAONE_REASONING_MODE
    } else {
      process.env.UMMAYA_K_EXAONE_REASONING_MODE = previous
    }
  }
}

describe('UMMAYA provider reasoning guidance', () => {
  test('adds concise-thinking guidance only when provider thinking is enabled', async () => {
    await withFriendliEnv(async () => {
      await withReasoningMode('deep', async () => {
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({ content: '17*19만 계산해줘.' })],
        })

        expect(JSON.stringify(exchange.request)).toContain(
          '"enable_thinking":true',
        )
        expect(serializedMessages(exchange.request)).toContain(
          'Do not spend the whole completion budget on thinking',
        )
      })

      await withReasoningMode('balanced', async () => {
        const exchange = await captureProviderExchange({
          messages: [createUserMessage({ content: '17*19만 계산해줘.' })],
        })

        expect(JSON.stringify(exchange.request)).toContain(
          '"enable_thinking":false',
        )
        expect(serializedMessages(exchange.request)).not.toContain(
          'Do not spend the whole completion budget on thinking',
        )
      })
    })
  })
})
