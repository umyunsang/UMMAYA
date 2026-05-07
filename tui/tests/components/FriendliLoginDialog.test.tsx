// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — /login dialog input behavior tests.

import { beforeAll, describe, expect, it, mock } from 'bun:test'
import React from 'react'
import { Box, Text, useInput, useStdin } from 'ink'
import { render } from 'ink-testing-library'
import { ThemeProvider } from '../../src/theme/provider.js'

let FriendliLoginDialog: typeof import('../../src/components/FriendliLoginDialog.js').FriendliLoginDialog

beforeAll(async () => {
  await mock.module('../../src/ink.js', () => ({
    Box,
    Text,
    useInput,
    useStdin,
  }))
  FriendliLoginDialog = (
    await import('../../src/components/FriendliLoginDialog.js')
  ).FriendliLoginDialog
})

async function flush(): Promise<void> {
  await new Promise<void>((r) => setTimeout(r, 0))
  await new Promise<void>((r) => setTimeout(r, 0))
}

function renderDialog(overrides: {
  onConfirm?: (apiKey: string) => void
  onCancel?: () => void
} = {}) {
  return render(
    <ThemeProvider>
      <FriendliLoginDialog
        existingSource="none"
        onConfirm={overrides.onConfirm ?? (() => {})}
        onCancel={overrides.onCancel ?? (() => {})}
      />
    </ThemeProvider>,
  )
}

describe('FriendliLoginDialog', () => {
  it('masks input and confirms a trimmed API key on Enter', async () => {
    const onConfirm = mock((_apiKey: string) => {})
    const { stdin, lastFrame, unmount } = renderDialog({ onConfirm })

    for (const ch of '  friendli-test-key  ') {
      stdin.write(ch)
      await flush()
    }

    const frame = lastFrame() ?? ''
    expect(frame).not.toContain('friendli-test-key')
    expect(frame).toContain('*********************')

    stdin.write('\r')
    await flush()

    expect(onConfirm).toHaveBeenCalledWith('friendli-test-key')
    unmount()
  })

  it('cancels on Escape', async () => {
    const onCancel = mock(() => {})
    const { stdin, unmount } = renderDialog({ onCancel })

    stdin.write('\x1b')
    await flush()

    expect(onCancel).toHaveBeenCalledTimes(1)
    unmount()
  })
})
