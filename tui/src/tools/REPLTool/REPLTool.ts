// SPDX-License-Identifier: Apache-2.0
// KOSMOS-1633 P2 / KOSMOS-1978 T009 — stub-noop tool.
//
// Original CC: `tui/src/tools/REPLTool/REPLTool.ts` — Anthropic's Python REPL
// tool for the Code Interpreter feature. KOSMOS does not ship a Python REPL
// inside the TUI (citizens use Korean public-API queries via the primitive
// surface; `Bash` tool covers shell execution). Stub returns an empty Tool
// object so dynamic import in main.tsx links cleanly.

export const REPLTool = {
  name: 'REPLTool_disabled',
  description: 'KOSMOS-1978: REPLTool not active in citizen TUI.',
  inputSchema: { type: 'object', properties: {} } as const,
  isEnabled: () => false,
}

export default REPLTool
