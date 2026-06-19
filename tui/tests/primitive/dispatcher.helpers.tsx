import type React from 'react'
import { expect } from 'bun:test'
import { ThemeProvider } from '@/theme/provider'
import { TerminalSizeContext } from '@/ink/components/TerminalSizeContext'

const KITTY_ESC = '\u001b_G'
const ITERM_ESC = '\u001b]1337;File='
const SIXEL_ESC = '\u001bPq'

export function wrap(element: React.ReactElement): React.ReactElement {
  return (
    <ThemeProvider>
      <TerminalSizeContext.Provider value={{ columns: 100, rows: 24 }}>
        {element}
      </TerminalSizeContext.Provider>
    </ThemeProvider>
  )
}

export function wrapNarrow(
  element: React.ReactElement,
  columns: number,
): React.ReactElement {
  return (
    <ThemeProvider>
      <TerminalSizeContext.Provider value={{ columns, rows: 24 }}>
        {element}
      </TerminalSizeContext.Provider>
    </ThemeProvider>
  )
}

export function assertNoImageEscapes(frame: string): void {
  expect(frame.includes(KITTY_ESC)).toBe(false)
  expect(frame.includes(ITERM_ESC)).toBe(false)
  expect(frame.includes(SIXEL_ESC)).toBe(false)
}

export function assertNoBrowserViewer(frame: string): void {
  expect(frame).not.toContain('Document viewer')
  expect(frame).not.toContain('document review opened')
  expect(frame).not.toContain('viewer.html')
  expect(frame).not.toContain('diff rail')
}

export function assertNoRoundedCardFrame(frame: string): void {
  for (const glyph of ['╭', '╮', '╰', '╯']) {
    expect(frame).not.toContain(glyph)
  }
}

export function assertNoRevdiffStatus(frame: string): void {
  expect(frame).not.toContain('hunk 1/')
  expect(frame).not.toContain('⊂ compact')
  expect(frame).not.toContain('± word-diff')
}
