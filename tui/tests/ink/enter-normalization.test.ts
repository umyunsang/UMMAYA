// SPDX-License-Identifier: Apache-2.0

import { describe, expect, test } from 'bun:test'

import { InputEvent } from '../../src/ink/events/input-event'
import { INITIAL_STATE, parseMultipleKeypresses } from '../../src/ink/parse-keypress'

describe('Enter key normalization', () => {
  test('treats LF as Return so terminal variants still submit input', () => {
    const [parsed] = parseMultipleKeypresses(INITIAL_STATE, '\n')
    const keypress = parsed[0]

    expect(keypress?.kind).toBe('key')
    if (keypress?.kind !== 'key') {
      throw new Error('expected LF to parse as a keypress')
    }

    const event = new InputEvent(keypress)
    expect(event.key.return).toBe(true)
    expect(event.input).toBe('')
  })
})
