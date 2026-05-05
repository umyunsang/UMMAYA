// SPDX-License-Identifier: Apache-2.0
// Spec 2643 (Lead-S9 Esc-cascade fix) — AgentsCommandView Esc dismiss tests.
//
// Regression guard: snap-003~final.txt across the S9 smoke run were 7
// byte-identical frames after `/agents` mount, proving every keystroke
// (including Esc) was dropped because (a) AgentsCommandView did not own
// `useInput`, and (b) REPL.tsx mounted it via `setToolJSX({ isLocalJSXCommand:
// true })`, which flips PromptInput.tsx:244 `isLocalJSXCommandActive=true`
// and deactivates EVERY useInput hook in the parent prompt subtree
// (AGENTS.md "Infrastructure insights" #3).
//
// These tests prove:
//   - AgentsCommandView mounts and renders the panel without crashing
//   - Esc keystroke calls onExit
//   - Non-Esc keystrokes do NOT call onExit

import { describe, expect, it, mock } from 'bun:test'
import * as React from 'react'
import { render } from 'ink-testing-library'
import { renderAgentsCommand } from '../../src/commands/agents.tsx'

describe('AgentsCommandView — Esc dismiss (Lead-S9 regression)', () => {
  it('mounts without throwing and produces a frame', () => {
    const { lastFrame } = render(
      React.createElement(React.Fragment, null, renderAgentsCommand('', () => {})),
    )
    expect(lastFrame()).toBeDefined()
  })

  it('calls onExit when Esc (\\x1b) is sent', async () => {
    const onExit = mock(() => {})
    const { stdin } = render(
      React.createElement(React.Fragment, null, renderAgentsCommand('', onExit)),
    )

    stdin.write('\x1b') // Escape
    await new Promise((r) => setTimeout(r, 20))

    expect(onExit).toHaveBeenCalledTimes(1)
  })

  it('does NOT call onExit on non-Esc keystrokes (a, Enter, space)', async () => {
    const onExit = mock(() => {})
    const { stdin } = render(
      React.createElement(React.Fragment, null, renderAgentsCommand('', onExit)),
    )

    stdin.write('a')
    stdin.write('\r') // Enter
    stdin.write(' ')
    await new Promise((r) => setTimeout(r, 20))

    expect(onExit).not.toHaveBeenCalled()
  })

  it('--detail flag still mounts and dismisses on Esc', async () => {
    const onExit = mock(() => {})
    const { stdin, lastFrame } = render(
      React.createElement(
        React.Fragment,
        null,
        renderAgentsCommand('--detail', onExit),
      ),
    )

    expect(lastFrame()).toBeDefined()
    stdin.write('\x1b')
    await new Promise((r) => setTimeout(r, 20))

    expect(onExit).toHaveBeenCalledTimes(1)
  })

  it('does not throw when onExit is undefined and Esc is sent', async () => {
    const { stdin } = render(
      React.createElement(
        React.Fragment,
        null,
        renderAgentsCommand('', undefined),
      ),
    )

    expect(() => {
      stdin.write('\x1b')
    }).not.toThrow()
    await new Promise((r) => setTimeout(r, 20))
  })
})
