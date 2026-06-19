// SPDX-License-Identifier: Apache-2.0
// SWAP/no-cc-source(2637): UMMAYA-only stub. CC source absent
// (find .references/.../src -name "systemThemeWatcher.ts" returns 0). decisions.md S9 § Stage-1 cite.
// CC consumer references (ThemeProvider.tsx:69) imply CC has runtime equivalents but they're
// not in restored-src — UMMAYA NO-OP is justified until TUI Fidelity Meta-Epic
// decides on UMMAYA-original implementation.
import type { TerminalQuerier } from '../ink/terminal-querier.js'
import type { SystemTheme } from './systemTheme.js'

type ThemeChangeHandler = (theme: SystemTheme) => void

export function watchSystemTheme(
  _querier: TerminalQuerier,
  _onThemeChange: ThemeChangeHandler,
): () => void {
  return () => {}
}

export default watchSystemTheme
