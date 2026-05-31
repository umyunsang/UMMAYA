// SPDX-License-Identifier: Apache-2.0
// UMMAYA terminal mascot.
//
// Run: cd tui && bun ../docs/wireframes/ummaya-mascot-proposal.mjs

import { render } from 'ink'
import { h, Box, Text, C, Divider } from './_shared.mjs'

const PALETTES = {
  home: { body: '#f59e0b', background: '#7c2d12', name: 'Home character' },
  service: { body: '#34d399', background: '#064e3b', name: 'Service green' },
  civic: { body: '#60a5fa', background: '#1e3a8a', name: 'Civic blue' },
}

const POSES = {
  default: {
    roof: '   ▟▀▀▀▙   ',
    faceL: '  ▟',
    eyes: '▛███▜',
    faceR: '▙  ',
    wallL: ' ▟',
    wall: '███████',
    wallR: '▙ ',
    baseL: '▝▜',
    door: '██▟█▙██',
    baseR: '▛▘',
    feet: '   ▘▘ ▝▝   ',
  },
  'look-left': {
    roof: '   ▟▀▀▀▙   ',
    faceL: '  ▟',
    eyes: '▟███▟',
    faceR: '▙  ',
    wallL: ' ▟',
    wall: '███████',
    wallR: '▙ ',
    baseL: '▝▜',
    door: '██▟█▙██',
    baseR: '▛▘',
    feet: '   ▘▘ ▝▝   ',
  },
  'look-right': {
    roof: '   ▟▀▀▀▙   ',
    faceL: '  ▟',
    eyes: '▙███▙',
    faceR: '▙  ',
    wallL: ' ▟',
    wall: '███████',
    wallR: '▙ ',
    baseL: '▝▜',
    door: '██▟█▙██',
    baseR: '▛▘',
    feet: '   ▘▘ ▝▝   ',
  },
  'arms-up': {
    roof: '  ▗▟▀▀▀▙▖  ',
    faceL: '  ▟',
    eyes: '▛███▜',
    faceR: '▙  ',
    wallL: ' ▜',
    wall: '███████',
    wallR: '▛ ',
    baseL: ' ▜',
    door: '██▟█▙██',
    baseR: '▛ ',
    feet: '   ▘▘ ▝▝   ',
  },
}

function Mascot({ pose = 'default', palette }) {
  const p = POSES[pose]
  const { body, background } = palette
  return h(Box, { flexDirection: 'column' },
    h(Text, { color: body }, p.roof),
    h(Text, null,
      h(Text, { color: body }, p.faceL),
      h(Text, { color: body, backgroundColor: background }, p.eyes),
      h(Text, { color: body }, p.faceR),
    ),
    h(Text, null,
      h(Text, { color: body }, p.wallL),
      h(Text, { color: body, backgroundColor: background }, p.wall),
      h(Text, { color: body }, p.wallR),
    ),
    h(Text, null,
      h(Text, { color: body }, p.baseL),
      h(Text, { color: body, backgroundColor: background }, p.door),
      h(Text, { color: body }, p.baseR),
    ),
    h(Text, { color: body }, p.feet),
  )
}

function Splash({ pose, palette }) {
  return h(Box, { flexDirection: 'row' },
    h(Box, { flexDirection: 'column', marginRight: 3 },
      h(Mascot, { pose, palette }),
    ),
    h(Box, { flexDirection: 'column' },
      h(Text, null,
        h(Text, { bold: true }, 'UMMAYA '),
        h(Text, { color: C.subtle }, 'KSC 2026'),
      ),
      h(Text, { color: C.subtle }, 'National AX citizen-agent harness'),
      h(Text, { color: C.dim, dimColor: true }, '~/UMMAYA/tui'),
    ),
  )
}

function PaletteBlock({ paletteKey }) {
  const palette = PALETTES[paletteKey]
  const poses = ['default', 'look-left', 'look-right', 'arms-up']
  return h(Box, { flexDirection: 'column', marginBottom: 2 },
    h(Text, { bold: true, color: C.brand }, palette.name),
    h(Box, { marginTop: 1, marginLeft: 2 },
      h(Splash, { pose: 'default', palette }),
    ),
    h(Box, { marginTop: 1, marginLeft: 2, flexDirection: 'row' },
      ...poses.map((p, i) => h(Box, {
        key: p,
        marginRight: i < poses.length - 1 ? 2 : 0,
        flexDirection: 'column',
      },
        h(Text, { color: C.dim, dimColor: true }, p),
        h(Mascot, { pose: p, palette }),
      )),
    ),
  )
}

function App() {
  return h(Box, { flexDirection: 'column' },
    h(Text, { bold: true, color: C.brand },
      'UMMAYA terminal mascot'),
    h(Text, { color: C.subtle },
      '5 rows: roof, CC-style eyes, house body, door, feet.'),

    h(Divider, { label: 'Selected palette' }),
    h(PaletteBlock, { paletteKey: 'home' }),

    h(Divider, { label: 'Alternates' }),
    h(PaletteBlock, { paletteKey: 'service' }),
    h(PaletteBlock, { paletteKey: 'civic' }),
  )
}

render(h(App))
