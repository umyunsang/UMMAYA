// SPDX-License-Identifier: Apache-2.0

import { describe, expect, mock, test } from 'bun:test'
import React from 'react'
import { Text } from 'ink'
import { render } from 'ink-testing-library'

import { InputEvent } from '../../src/ink/events/input-event'
import {
  INITIAL_STATE,
  parseMultipleKeypresses,
  type ParsedKey,
} from '../../src/ink/parse-keypress'
import { usePasteHandler } from '../../src/hooks/usePasteHandler'
import type { Key } from '../../src/ink'

function tick(ms = 20): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function keyEvents(input: string): InputEvent[] {
  const [events] = parseMultipleKeypresses(INITIAL_STATE, input)
  return events
    .filter((event): event is ParsedKey => event.kind === 'key')
    .map(event => new InputEvent(event))
}

type HarnessProps = {
  onInput: (input: string, key: Key) => void
  onPaste: (text: string) => void
  onImagePaste?: () => void
  onReady: (send: (event: InputEvent) => void) => void
}

function PasteHandlerHarness({
  onInput,
  onPaste,
  onImagePaste,
  onReady,
}: HarnessProps): React.ReactElement {
  const { wrappedOnInput } = usePasteHandler({
    onInput,
    onPaste,
    onImagePaste,
  })

  React.useEffect(() => {
    onReady((event: InputEvent) => {
      wrappedOnInput(event.input, event.key, event)
    })
  }, [onReady, wrappedOnInput])

  return <Text>ready</Text>
}

describe('usePasteHandler paste + Enter submission', () => {
  test('routes bracketed pasted slash command plus immediate Enter through coalesced submit input', async () => {
    const onInput = mock((_: string, __: Key) => {})
    const onPaste = mock((_: string) => {})
    let send: ((event: InputEvent) => void) | null = null

    const { unmount } = render(
      <PasteHandlerHarness
        onInput={onInput}
        onPaste={onPaste}
        onReady={nextSend => {
          send = nextSend
        }}
      />,
    )
    await tick()

    for (const event of keyEvents('\x1b[200~/login\x1b[201~\r')) {
      send?.(event)
    }
    await tick(150)

    expect(onInput).toHaveBeenCalledTimes(1)
    expect(onInput.mock.calls[0]?.[0]).toBe('/login\r')
    expect(onInput.mock.calls[0]?.[1].return).toBe(false)
    expect(onPaste).not.toHaveBeenCalled()

    unmount()
  })

  test('lets pasted image paths complete through the paste pipeline when Enter follows', async () => {
    const onInput = mock((_: string, __: Key) => {})
    const onPaste = mock((_: string) => {})
    const onImagePaste = mock(() => {})
    let send: ((event: InputEvent) => void) | null = null

    const { unmount } = render(
      <PasteHandlerHarness
        onInput={onInput}
        onPaste={onPaste}
        onImagePaste={onImagePaste}
        onReady={nextSend => {
          send = nextSend
        }}
      />,
    )
    await tick()

    for (const event of keyEvents(
      '\x1b[200~/tmp/ummaya-paste-smoke.png\x1b[201~\r',
    )) {
      send?.(event)
    }
    await tick(250)

    expect(onInput).not.toHaveBeenCalled()
    expect(onPaste).toHaveBeenCalledWith('/tmp/ummaya-paste-smoke.png')

    unmount()
  })

  test('keeps normal bracketed paste on the paste callback when Enter does not follow', async () => {
    const onInput = mock((_: string, __: Key) => {})
    const onPaste = mock((_: string) => {})
    let send: ((event: InputEvent) => void) | null = null

    const { unmount } = render(
      <PasteHandlerHarness
        onInput={onInput}
        onPaste={onPaste}
        onReady={nextSend => {
          send = nextSend
        }}
      />,
    )
    await tick()

    for (const event of keyEvents('\x1b[200~/login\x1b[201~')) {
      send?.(event)
    }
    await tick(150)

    expect(onInput).not.toHaveBeenCalled()
    expect(onPaste).toHaveBeenCalledTimes(1)
    expect(onPaste).toHaveBeenCalledWith('/login')

    unmount()
  })
})
