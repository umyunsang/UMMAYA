// SPDX-License-Identifier: Apache-2.0
// Spec 2294 — KosmosPrimitivePermissionRequest tests.
//
// Tests the active primitive arms (verify / submit-reversible / submit-irreversible)
// × the 3 decision paths (allow_once / allow_session / deny).
// Render is done via ink-testing-library; we assert on lastFrame() text.

import { describe, test, expect, mock } from 'bun:test'
import React from 'react'
import { render } from 'ink-testing-library'
import { PassThrough, Writable } from 'stream'
import { render as renderInk } from '@/ink.js'
import { AppStateProvider } from '@/state/AppState'
import { KeybindingSetup } from '@/keybindings/KeybindingProviderSetup'
import { KosmosPrimitivePermissionRequest } from '@/components/permissions/KosmosPrimitivePermissionRequest/KosmosPrimitivePermissionRequest'
import type { PrimitiveDecision } from '@/components/permissions/KosmosPrimitivePermissionRequest/KosmosPrimitivePermissionRequest'
import { DEFAULT_BINDING_BLOCKS } from '@/keybindings/defaultBindings'
import { parseBindings } from '@/keybindings/parser'
import { resolveKeyWithChordState } from '@/keybindings/resolver'
import type { Key } from '@/ink.js'

const DOWN = '\u001B[B'

function tick(ms = 20): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

const SELECT_BINDINGS = parseBindings(DEFAULT_BINDING_BLOCKS)

type TestStdin = PassThrough & {
  isTTY: true
  isRaw: boolean
  setRawMode: (mode: boolean) => void
  ref: () => TestStdin
  unref: () => TestStdin
}

type TestStdout = Writable & {
  isTTY: true
  columns: number
  rows: number
  output: string
}

function makeLocalInkStreams(): { stdin: TestStdin; stdout: TestStdout } {
  const stdin = new PassThrough() as TestStdin
  stdin.isTTY = true
  stdin.isRaw = false
  stdin.setRawMode = (mode: boolean) => {
    stdin.isRaw = mode
  }
  stdin.ref = () => stdin
  stdin.unref = () => stdin

  const stdout = new Writable({
    write(chunk, _encoding, callback) {
      stdout.output += chunk.toString()
      callback()
    },
  }) as TestStdout
  stdout.isTTY = true
  stdout.columns = 100
  stdout.rows = 32
  stdout.output = ''

  return { stdin, stdout }
}

// ---------------------------------------------------------------------------
// Wrapper: AppStateProvider is required by PermissionPrompt (uses useSetAppState)
// ---------------------------------------------------------------------------

function Wrap({ children }: { children: React.ReactNode }): React.ReactElement {
  return (
    <AppStateProvider>
      <KeybindingSetup>{children}</KeybindingSetup>
    </AppStateProvider>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeProps(
  primitive: 'verify' | 'submit',
  isIrreversible = false,
  overrides: Partial<{
    toolName: string
    receiptId: string
    onDecision: (d: PrimitiveDecision) => void
    onDismiss: () => void
  }> = {},
) {
  return {
    primitive,
    toolName: overrides.toolName ?? 'test_tool',
    isIrreversible,
    receiptId: overrides.receiptId,
    onDecision: overrides.onDecision ?? mock(() => {}),
    onDismiss: overrides.onDismiss ?? mock(() => {}),
  }
}

function key(overrides: Partial<Key>): Key {
  return {
    upArrow: false,
    downArrow: false,
    leftArrow: false,
    rightArrow: false,
    pageDown: false,
    pageUp: false,
    wheelUp: false,
    wheelDown: false,
    home: false,
    end: false,
    return: false,
    escape: false,
    ctrl: false,
    shift: false,
    fn: false,
    tab: false,
    backspace: false,
    delete: false,
    meta: false,
    super: false,
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// verify arm (Layer 1)
// ---------------------------------------------------------------------------

describe('KosmosPrimitivePermissionRequest — verify (Layer 1)', () => {
  test('renders layer 1 glyph ⓵', () => {
    const props = makeProps('verify')
    const { lastFrame } = render(
      <Wrap>
        <KosmosPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    expect(lastFrame()).toContain('⓵')
  })

  test('renders verify modal title (contains 신원)', () => {
    const props = makeProps('verify')
    const { lastFrame } = render(
      <Wrap>
        <KosmosPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    expect(lastFrame() ?? '').toContain('신원')
  })

  test('renders tool name in body', () => {
    const props = makeProps('verify', false, { toolName: 'hira_hospital_search' })
    const { lastFrame } = render(
      <Wrap>
        <KosmosPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    expect(lastFrame()).toContain('hira_hospital_search')
  })

  test('renders PIPA notice (contains 22)', () => {
    const props = makeProps('verify')
    const { lastFrame } = render(
      <Wrap>
        <KosmosPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    // PIPA §22-2 citation substring present in modal
    expect(lastFrame() ?? '').toContain('22')
  })
})

// ---------------------------------------------------------------------------
// submit — reversible arm (Layer 2)
// ---------------------------------------------------------------------------

describe('KosmosPrimitivePermissionRequest — submit reversible (Layer 2)', () => {
  test('renders layer 2 glyph ⓶', () => {
    const props = makeProps('submit', false)
    const { lastFrame } = render(
      <Wrap>
        <KosmosPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    expect(lastFrame()).toContain('⓶')
  })

  test('does NOT render "취소 불가" for reversible submit', () => {
    const props = makeProps('submit', false)
    const { lastFrame } = render(
      <Wrap>
        <KosmosPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    expect(lastFrame()).not.toContain('취소 불가')
  })
})

// ---------------------------------------------------------------------------
// submit — irreversible arm (Layer 3)
// ---------------------------------------------------------------------------

describe('KosmosPrimitivePermissionRequest — submit irreversible (Layer 3)', () => {
  test('renders layer 3 glyph ⓷', () => {
    const props = makeProps('submit', true)
    const { lastFrame } = render(
      <Wrap>
        <KosmosPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    expect(lastFrame()).toContain('⓷')
  })

  test('renders irreversible warning text (contains 취소)', () => {
    const props = makeProps('submit', true)
    const { lastFrame } = render(
      <Wrap>
        <KosmosPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    expect(lastFrame() ?? '').toContain('취소')
  })
})

// ---------------------------------------------------------------------------
// lookup arm — null layer → component returns null (bypass)
// ---------------------------------------------------------------------------

describe('KosmosPrimitivePermissionRequest — lookup (bypass)', () => {
  test('renders nothing for lookup primitive', () => {
    const onDecision = mock(() => {})
    const onDismiss = mock(() => {})
    const { lastFrame } = render(
      <Wrap>
        <KosmosPrimitivePermissionRequest
          primitive="lookup"
          toolName="resolve_location"
          onDecision={onDecision}
          onDismiss={onDismiss}
        />
      </Wrap>,
    )
    // null render → lastFrame has no permission content
    const frame = lastFrame() ?? ''
    expect(frame).not.toContain('⓵')
    expect(frame).not.toContain('⓶')
    expect(frame).not.toContain('⓷')
  })
})

// ---------------------------------------------------------------------------
// Selector labels visible in all arms
// ---------------------------------------------------------------------------

describe('KosmosPrimitivePermissionRequest — selector labels', () => {
  for (const primitive of ['verify', 'submit'] as const) {
    test(`${primitive}: shows selector labels without KOSMOS-only hotkey prefixes`, () => {
      const props = makeProps(primitive)
      const { lastFrame } = render(
        <Wrap>
          <KosmosPrimitivePermissionRequest {...props} />
        </Wrap>,
      )
      const frame = lastFrame() ?? ''
      expect(frame).toContain('한 번')
      expect(frame).toContain('세션')
      expect(frame).toContain('거부')
      expect(frame).not.toContain('Y  한 번')
      expect(frame).not.toContain('A  세션')
      expect(frame).not.toContain('N  거부')
    })
  }

  test.each([
    ['Enter', '', key({ return: true }), 'select:accept'],
    ['Down', '', key({ downArrow: true }), 'select:next'],
    ['Up', '', key({ upArrow: true }), 'select:previous'],
    ['Escape', '', key({ escape: true }), 'select:cancel'],
  ] as const)('%s resolves through the Select keybinding context', (
    _name,
    input,
    keyEvent,
    expectedAction,
  ) => {
    expect(
      resolveKeyWithChordState(
        input,
        keyEvent,
        ['Select', 'Global'],
        SELECT_BINDINGS,
        null,
      ),
    ).toEqual({ type: 'match', action: expectedAction })
  })

  test('Down Down Enter selects deny through live stdin', async () => {
    const onDecision = mock(() => {})
    const props = makeProps('verify', false, { onDecision })
    const streams = makeLocalInkStreams()
    const instance = await renderInk(
      <Wrap>
        <KosmosPrimitivePermissionRequest {...props} />
      </Wrap>,
      {
        stdin: streams.stdin,
        stdout: streams.stdout,
        stderr: streams.stdout,
        exitOnCtrlC: false,
        patchConsole: false,
      },
    )

    try {
      await tick()
      streams.stdin.write(DOWN)
      await tick()
      streams.stdin.write(DOWN)
      await tick()
      streams.stdin.write('\r')
      await tick()

      expect(onDecision).toHaveBeenCalledWith('deny', undefined)
    } finally {
      instance.unmount()
      instance.cleanup()
    }
  })

  test('numeric option 3 selects deny through live stdin', async () => {
    const onDecision = mock(() => {})
    const props = makeProps('verify', false, { onDecision })
    const streams = makeLocalInkStreams()
    const instance = await renderInk(
      <Wrap>
        <KosmosPrimitivePermissionRequest {...props} />
      </Wrap>,
      {
        stdin: streams.stdin,
        stdout: streams.stdout,
        stderr: streams.stdout,
        exitOnCtrlC: false,
        patchConsole: false,
      },
    )

    try {
      await tick()
      streams.stdin.write('3')
      await tick()

      expect(onDecision).toHaveBeenCalledWith('deny', undefined)
    } finally {
      instance.unmount()
      instance.cleanup()
    }
  })
})

// ---------------------------------------------------------------------------
// receiptId optional footer
// ---------------------------------------------------------------------------

describe('KosmosPrimitivePermissionRequest — receiptId footer', () => {
  test('shows receipt ID when provided', () => {
    const props = makeProps('verify', false, { receiptId: 'rcpt-abc12345' })
    const { lastFrame } = render(
      <Wrap>
        <KosmosPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    expect(lastFrame()).toContain('rcpt-abc12345')
  })

  test('no receipt ID text when omitted', () => {
    const props = makeProps('verify')
    const { lastFrame } = render(
      <Wrap>
        <KosmosPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    expect(lastFrame()).not.toContain('rcpt-')
  })
})
