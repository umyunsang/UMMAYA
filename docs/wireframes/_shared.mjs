// SPDX-License-Identifier: Apache-2.0
// Shared primitives for UMMAYA UI wireframe proposals.
//
// Run any proposal file with Bun + tui's node_modules (has Ink):
//
//   cd tui && bun ../docs/wireframes/proposal-iv.mjs
//
// All proposals render using CC-ported primitive shapes (round-rule borders,
// spinner, notice boxes, dim hints) — the wireframes deliberately avoid
// introducing new component shapes.

import React from 'react'
import { Box, Text } from 'ink'

export const h = React.createElement
export { Box, Text }

// ── Colors ──────────────────────────────────────────────────────────────
// Match tui/src/theme tokens.
export const C = {
  brand: '#4fd1c5',
  subtle: '#8a8a8a',
  dim: '#5c5c5c',
  text: '#e5e5e5',
  green: '#34d399',
  yellow: '#fbbf24',
  red: '#f87171',
  ring: '#7dd3fc',
  // Ministry coloring reserved for /agents command output only
  koroad: '#60a5fa',
  kma: '#a78bfa',
  hira: '#34d399',
  nmc: '#fbbf24',
  // Primitive ⏺ dot colors — encode the active root verb being performed
  findDot:   '#60a5fa',  // blue   · information pulling
  locateDot: '#7dd3fc',  // cyan   · address/place resolution
  checkDot:  '#f87171',  // red    · identity/delegation gates
  sendDot:   '#fb923c',  // orange · outbound writes
  pluginDot: '#a78bfa',  // purple · plugin namespace
}

// Primitive → dot color lookup
export const PRIMITIVE_DOT = {
  find: C.findDot,
  locate: C.locateDot,
  check: C.checkDot,
  send: C.sendDot,
  plugin: C.pluginDot,
}

// ── Shared partials ─────────────────────────────────────────────────────

export function Rule({ width = 70 }) {
  return h(Text, { color: C.dim }, '─'.repeat(width))
}

export function Divider({ label }) {
  return h(Box, { marginTop: 1, marginBottom: 1 },
    h(Text, { color: C.dim }, `── ${label} `.padEnd(70, '─'))
  )
}

export function CondensedLogo({ cwd = '~/UMMAYA/tui', model = 'K-EXAONE' }) {
  return h(Box, null,
    h(Text, { color: C.brand }, '✱ '),
    h(Text, { bold: true, color: C.brand }, 'UMMAYA'),
    h(Text, { color: C.subtle }, `  ·  ${model}  ·  `),
    h(Text, { color: C.dim }, cwd),
  )
}

export function WelcomeV2Block() {
  // CC WelcomeV2 14-row ASCII block — abbreviated for wireframe clarity.
  return h(Box, { flexDirection: 'column', width: 60 },
    h(Box, null,
      h(Text, { bold: true, color: C.brand }, 'Welcome to UMMAYA '),
      h(Text, { dimColor: true }, 'KSC 2026')
    ),
    h(Text, { color: C.dim }, '…'.repeat(58)),
    h(Text, null, '                                                          '),
    h(Text, null, '     *                                       █████▓▓░     '),
    h(Text, null, '                                 *         ███▓░     ░░   '),
    h(Text, null, '            ░░░░░░                        ███▓░           '),
    h(Text, null, '   ░░░░░░░░░░░░░░░                        ██▓░      ▓     '),
    h(Text, null, '                                             ░▓▓███▓▓░    '),
    h(Text, { dimColor: true }, ' *              ░░░░                         '),
    h(Text, null, '      █████████                                         *  '),
    h(Text, null, '     ██▄█████▄██                       *                   '),
    h(Text, null, '      █████████     *                                      '),
    h(Text, { color: C.dim }, '…'.repeat(58)),
  )
}

export function FeedColumn({ title, rows, width = 40 }) {
  return h(Box, { flexDirection: 'column', width },
    h(Text, { bold: true, color: C.text }, title),
    ...rows.map((r, i) => h(Box, { key: i },
      r.glyph ? h(Text, { color: r.color ?? C.subtle }, `${r.glyph} `) : null,
      h(Text, { color: r.color ?? C.text }, r.primary),
      r.secondary ? h(Text, { color: C.dim, dimColor: true }, `   ${r.secondary}`) : null,
    ))
  )
}

export function BorderedNotice({ label, color = C.brand, children, width = 70 }) {
  return h(Box, {
    borderStyle: 'round',
    borderColor: color,
    paddingX: 1,
    width,
    flexDirection: 'column',
  },
    h(Text, { bold: true, color }, label),
    children
  )
}

export function PromptBand({ label = '> ▋', borderColor = C.dim }) {
  return h(Box, { flexDirection: 'column' },
    h(Box, {
      borderStyle: 'round',
      borderColor,
      borderLeft: false,
      borderRight: false,
      borderBottom: true,
      width: 70,
    },
      h(Text, null, ` ${label}`)
    ),
  )
}

export function PromptFooter({ left, right, color = C.dim }) {
  return h(Box, { justifyContent: 'space-between', width: 70, paddingX: 2 },
    h(Text, { color, dimColor: true }, left),
    h(Text, { color, dimColor: true }, right),
  )
}

export function PhaseIndicator({ phase }) {
  return h(Box, null,
    h(Text, { color: C.dim }, '['),
    h(Text, { color: C.ring, bold: true }, phase),
    h(Text, { color: C.dim }, ']'),
  )
}

export function Spinner({ verb }) {
  return h(Box, null,
    h(Text, { color: C.ring }, '⠋ '),
    h(Text, null, verb),
  )
}

// Tool-use block — new convention (2026-04-24):
//   - Primitive name is NOT shown as text. Dot color encodes it.
//   - Ministry code (English abbreviation) is the adapter label.
//   - Live/Mock/Handoff is not encoded in the dot. Result copy and evidence
//     disclose authority boundaries.
//
// Dot color → primitive:
//     blue (find) · cyan (locate) · red (check) · orange (send)
//     purple (plugin-namespaced verb). Subscribe is deferred until UMMAYA owns
//     an app/push-notification runtime.
export function ToolUseBlock({ primitive = 'find', ministry, result, detail }) {
  const dot = PRIMITIVE_DOT[primitive] ?? C.ring
  return h(Box, { flexDirection: 'column', marginLeft: 2 },
    h(Box, null,
      h(Text, { color: dot, bold: true }, '⏺ '),
      h(Text, { bold: true }, ministry),
      detail ? h(Text, { color: C.dim, dimColor: true }, `   ${detail}`) : null,
    ),
    result
      ? h(Box, { marginLeft: 2 },
          h(Text, { color: C.subtle }, '   → '),
          h(Text, null, result),
        )
      : null
  )
}

export function UserMsg({ text }) {
  return h(Box, null,
    h(Text, { color: C.brand, bold: true }, '>  '),
    h(Text, null, text),
  )
}

export function AsstLine({ text }) {
  return h(Box, null,
    h(Text, null, text)
  )
}
