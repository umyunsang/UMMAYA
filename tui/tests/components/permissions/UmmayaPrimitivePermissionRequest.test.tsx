// SPDX-License-Identifier: Apache-2.0
// Spec 2294 — UmmayaPrimitivePermissionRequest tests.
//
// Tests the active primitive arms (check / send-reversible / send-irreversible)
// × the 3 decision paths (allow_once / allow_session / deny).
// Static and stdin renders use the UMMAYA Ink runtime so the tests exercise the
// same AppStateProvider/KeybindingSetup path as the real TUI.

import { describe, test, expect, mock } from 'bun:test'
import React from 'react'
import { PassThrough, Writable } from 'stream'
import { render as renderInk } from '@/ink.js'
import { AppStateProvider } from '@/state/AppState'
import { KeybindingSetup } from '@/keybindings/KeybindingProviderSetup'
import { UmmayaPrimitivePermissionRequest } from '@/components/permissions/UmmayaPrimitivePermissionRequest/UmmayaPrimitivePermissionRequest'
import type { PrimitiveDecision } from '@/components/permissions/UmmayaPrimitivePermissionRequest/UmmayaPrimitivePermissionRequest'
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

function normalizeFrameText(output: string): string {
  return output
    .replace(/\u001B\]([^\u0007]|\u001B\\)*(\u0007|\u001B\\)/g, '')
    .replace(/\u001B\[1C/g, ' ')
    .replace(/\u001B\[[0-?]*[ -/]*[@-~]/g, '')
}

async function renderStaticFrame(element: React.ReactElement): Promise<string> {
  const streams = makeLocalInkStreams()
  const instance = await renderInk(element, {
    stdin: streams.stdin,
    stdout: streams.stdout,
    stderr: streams.stdout,
    exitOnCtrlC: false,
    patchConsole: false,
  })

  try {
    await tick()
    return normalizeFrameText(streams.stdout.output)
  } finally {
    instance.unmount()
    instance.cleanup()
  }
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
  primitive: 'check' | 'send',
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
// check arm (Layer 1)
// ---------------------------------------------------------------------------

describe('UmmayaPrimitivePermissionRequest — check (Layer 1)', () => {
  test('renders layer 1 glyph ⓵', async () => {
    const props = makeProps('check')
    const frame = await renderStaticFrame(
      <Wrap>
        <UmmayaPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    expect(frame).toContain('⓵')
  })

  test('renders check modal title (contains 신원)', async () => {
    const props = makeProps('check')
    const frame = await renderStaticFrame(
      <Wrap>
        <UmmayaPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    expect(frame).toContain('신원')
  })

  test('renders tool name in body', async () => {
    const props = makeProps('check', false, { toolName: 'hira_hospital_search' })
    const frame = await renderStaticFrame(
      <Wrap>
        <UmmayaPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    expect(frame).toContain('hira_hospital_search')
  })

  test('renders PIPA notice (contains 22)', async () => {
    const props = makeProps('check')
    const frame = await renderStaticFrame(
      <Wrap>
        <UmmayaPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    // PIPA §22-2 citation substring present in modal
    expect(frame).toContain('22')
  })
})

// ---------------------------------------------------------------------------
// send — reversible arm (Layer 2)
// ---------------------------------------------------------------------------

describe('UmmayaPrimitivePermissionRequest — send reversible (Layer 2)', () => {
  test('renders layer 2 glyph ⓶', async () => {
    const props = makeProps('send', false)
    const frame = await renderStaticFrame(
      <Wrap>
        <UmmayaPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    expect(frame).toContain('⓶')
  })

  test('does NOT render "취소 불가" for reversible send', async () => {
    const props = makeProps('send', false)
    const frame = await renderStaticFrame(
      <Wrap>
        <UmmayaPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    expect(frame).not.toContain('취소 불가')
  })
})

// ---------------------------------------------------------------------------
// send — irreversible arm (Layer 3)
// ---------------------------------------------------------------------------

describe('UmmayaPrimitivePermissionRequest — send irreversible (Layer 3)', () => {
  test('renders layer 3 glyph ⓷', async () => {
    const props = makeProps('send', true)
    const frame = await renderStaticFrame(
      <Wrap>
        <UmmayaPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    expect(frame).toContain('⓷')
  })

  test('renders irreversible warning text (contains 취소)', async () => {
    const props = makeProps('send', true)
    const frame = await renderStaticFrame(
      <Wrap>
        <UmmayaPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    expect(frame).toContain('취소')
  })
})

// ---------------------------------------------------------------------------
// lookup arm — null layer → component returns null (bypass)
// ---------------------------------------------------------------------------

describe('UmmayaPrimitivePermissionRequest — find (bypass)', () => {
  test('renders nothing for find primitive', async () => {
    const onDecision = mock(() => {})
    const onDismiss = mock(() => {})
    const frame = await renderStaticFrame(
      <Wrap>
        <UmmayaPrimitivePermissionRequest
          primitive="find"
          toolName="resolve_location"
          onDecision={onDecision}
          onDismiss={onDismiss}
        />
      </Wrap>,
    )
    // null render → lastFrame has no permission content
    expect(frame).not.toContain('⓵')
    expect(frame).not.toContain('⓶')
    expect(frame).not.toContain('⓷')
  })
})

// ---------------------------------------------------------------------------
// Selector labels visible in all arms
// ---------------------------------------------------------------------------

describe('UmmayaPrimitivePermissionRequest — selector labels', () => {
  for (const primitive of ['check', 'send'] as const) {
    test(`${primitive}: shows selector labels without UMMAYA-only hotkey prefixes`, async () => {
      const props = makeProps(primitive)
      const frame = await renderStaticFrame(
        <Wrap>
          <UmmayaPrimitivePermissionRequest {...props} />
        </Wrap>,
      )
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
    const props = makeProps('check', false, { onDecision })
    const streams = makeLocalInkStreams()
    const instance = await renderInk(
      <Wrap>
        <UmmayaPrimitivePermissionRequest {...props} />
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
    const props = makeProps('check', false, { onDecision })
    const streams = makeLocalInkStreams()
    const instance = await renderInk(
      <Wrap>
        <UmmayaPrimitivePermissionRequest {...props} />
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

describe('UmmayaPrimitivePermissionRequest — receiptId footer', () => {
  test('shows receipt ID when provided', async () => {
    const props = makeProps('check', false, { receiptId: 'rcpt-abc12345' })
    const frame = await renderStaticFrame(
      <Wrap>
        <UmmayaPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    expect(frame).toContain('rcpt-abc12345')
  })

  test('no receipt ID text when omitted', async () => {
    const props = makeProps('check')
    const frame = await renderStaticFrame(
      <Wrap>
        <UmmayaPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    expect(frame).not.toContain('rcpt-')
  })
})
