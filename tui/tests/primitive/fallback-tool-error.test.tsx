import { test, expect } from 'bun:test'
import { render } from 'ink-testing-library'
import React from 'react'
import { FallbackToolUseErrorMessage } from '../../src/components/FallbackToolUseErrorMessage.js'
import { TerminalSizeContext } from '../../src/ink/components/TerminalSizeContext.js'
import { ThemeProvider } from '../../src/theme/provider.js'

test('FallbackToolUseErrorMessage renders structured error without raw JSON envelope', () => {
  const result = JSON.stringify({
    ok: false,
    error: {
      kind: 'invalid_params',
      message: 'Missing lat/lon; locate must run first',
    },
  })

  const { lastFrame } = render(
    <ThemeProvider>
      <TerminalSizeContext.Provider value={{ columns: 100, rows: 30 }}>
        <FallbackToolUseErrorMessage result={result} verbose={false} />
      </TerminalSizeContext.Provider>
    </ThemeProvider>,
  )
  const frame = lastFrame() ?? ''

  expect(frame).toContain('Missing lat/lon; locate must run first')
  expect(frame).not.toContain('"ok"')
  expect(frame).not.toContain('"error"')
})
