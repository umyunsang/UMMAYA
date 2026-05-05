// SPDX-License-Identifier: Apache-2.0
// realuse-audit-2026-05-05 § G2 (PR #2773) — overlay Esc-dismiss snapshot
// regression. Pins the contract that HelpV2Grouped + AgentsCommandView call
// their dismiss callback when Esc is pressed, via the defense-in-depth
// `useInput((_, k) => k.escape && handler())` fallback (AGENTS.md insight
// #4) — the in-process chord registry is wired in only at process boot,
// so the test layer asserts the overlay's own Esc handler.
//
// These tests live at the ink-testing-library layer (Layer 1b in the
// AGENTS.md verification chain) — fastest regression net for overlay
// dismissal. Layer 5 tmux smoke covers the boot path under a real PTY.

import React from 'react'
import { describe, expect, it } from 'bun:test'
import { render } from 'ink-testing-library'
import { ThemeProvider } from '../../src/theme/provider'
import { KeybindingProviderSetup } from '../../src/keybindings/KeybindingProviderSetup'
import { HelpV2Grouped } from '../../src/components/help/HelpV2Grouped'
import { renderAgentsCommand } from '../../src/commands/agents'

function tick(ms = 20): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

const ESC = ''

// KeybindingProviderSetup requires non-undefined handlerOverrides + announcer.
const noopHandlers: Record<string, Record<string, () => void>> = {}
const noopAnnouncer = { announce: () => undefined }

describe('G2 — HelpV2Grouped Esc dismiss (F-alpha-05, F-delta-04)', () => {
  it('calls onDismiss when Esc is pressed', async () => {
    let dismissCount = 0
    const result = render(
      <ThemeProvider>
        <KeybindingProviderSetup
          handlerOverrides={noopHandlers}
          announcer={noopAnnouncer}
          activeContexts={['Help', 'Chat', 'Global']}
        >
          <HelpV2Grouped onDismiss={() => (dismissCount += 1)} />
        </KeybindingProviderSetup>
      </ThemeProvider>,
    )
    await tick()
    expect(result.lastFrame()).toContain('도움말')
    expect(result.lastFrame()).toContain('Esc')

    result.stdin.write(ESC)
    await tick(40)
    expect(dismissCount).toBeGreaterThanOrEqual(1)
    result.unmount()
  })
})

describe('G2 — AgentsCommandView Esc dismiss (F-ε-05)', () => {
  it('calls onExit when Esc is pressed in /agents overlay', async () => {
    let exitCount = 0
    const node = renderAgentsCommand('', () => (exitCount += 1))
    const result = render(
      <ThemeProvider>
        <KeybindingProviderSetup
          handlerOverrides={noopHandlers}
          announcer={noopAnnouncer}
          activeContexts={['Chat', 'Global']}
        >
          {node}
        </KeybindingProviderSetup>
      </ThemeProvider>,
    )
    await tick()
    expect(result.lastFrame()).toContain('ESC 종료')

    result.stdin.write(ESC)
    await tick(40)
    expect(exitCount).toBeGreaterThanOrEqual(1)
    result.unmount()
  })

  it('calls onExit in --detail mode too', async () => {
    let exitCount = 0
    const node = renderAgentsCommand('--detail', () => (exitCount += 1))
    const result = render(
      <ThemeProvider>
        <KeybindingProviderSetup
          handlerOverrides={noopHandlers}
          announcer={noopAnnouncer}
          activeContexts={['Chat', 'Global']}
        >
          {node}
        </KeybindingProviderSetup>
      </ThemeProvider>,
    )
    await tick()
    expect(result.lastFrame()).toContain('ESC 종료')

    result.stdin.write(ESC)
    await tick(40)
    expect(exitCount).toBeGreaterThanOrEqual(1)
    result.unmount()
  })
})
