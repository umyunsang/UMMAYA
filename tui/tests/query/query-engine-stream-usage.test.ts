import { describe, expect, test } from 'bun:test'
import { getMessageStartUsageDelta } from '../../src/QueryEngine.js'
import { EMPTY_USAGE } from '../../src/services/api/emptyUsage.js'

describe('QueryEngine stream usage guard', () => {
  test('skips provider-adapted message_start events without nested usage', () => {
    expect(getMessageStartUsageDelta({ type: 'message_start' })).toBeUndefined()
  })

  test('preserves Claude Code message_start usage when present', () => {
    const usage = {
      ...EMPTY_USAGE,
      input_tokens: 7,
      output_tokens: 3,
    }

    expect(
      getMessageStartUsageDelta({
        type: 'message_start',
        message: { usage },
      }),
    ).toEqual(usage)
  })
})
