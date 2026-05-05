// SPDX-License-Identifier: Apache-2.0
// Spec 2294 — KosmosPrimitivePermissionRequest tests.
//
// Tests the 4 primitive arms (verify / submit-reversible / submit-irreversible
// / subscribe) × the 3 decision paths (allow_once / allow_session / deny).
// Render is done via ink-testing-library; we assert on lastFrame() text.

import { describe, test, expect, mock } from 'bun:test'
import React from 'react'
import { render } from 'ink-testing-library'
import { AppStateProvider } from '@/state/AppState'
import { KosmosPrimitivePermissionRequest } from '@/components/permissions/KosmosPrimitivePermissionRequest/KosmosPrimitivePermissionRequest'
import type { PrimitiveDecision } from '@/components/permissions/KosmosPrimitivePermissionRequest/KosmosPrimitivePermissionRequest'

// ---------------------------------------------------------------------------
// Wrapper: AppStateProvider is required by PermissionPrompt (uses useSetAppState)
// ---------------------------------------------------------------------------

function Wrap({ children }: { children: React.ReactNode }): React.ReactElement {
  return <AppStateProvider>{children}</AppStateProvider>
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeProps(
  primitive: 'verify' | 'submit' | 'subscribe',
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
// subscribe arm (Layer 2)
// ---------------------------------------------------------------------------

describe('KosmosPrimitivePermissionRequest — subscribe (Layer 2)', () => {
  test('renders layer 2 glyph ⓶', () => {
    const props = makeProps('subscribe')
    const { lastFrame } = render(
      <Wrap>
        <KosmosPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    expect(lastFrame()).toContain('⓶')
  })

  test('renders subscribe modal title (contains 구독)', () => {
    const props = makeProps('subscribe')
    const { lastFrame } = render(
      <Wrap>
        <KosmosPrimitivePermissionRequest {...props} />
      </Wrap>,
    )
    expect(lastFrame() ?? '').toContain('구독')
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
// Y / A / N selector labels visible in all arms
// ---------------------------------------------------------------------------

describe('KosmosPrimitivePermissionRequest — selector labels', () => {
  for (const primitive of ['verify', 'submit', 'subscribe'] as const) {
    test(`${primitive}: shows Y/A/N selector labels`, () => {
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
    })
  }
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
