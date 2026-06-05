#!/usr/bin/env bun
/**
 * dump-plugin-frames.tsx — Visual frame dump for UMMAYA plugin surfaces.
 *
 * Renders each plugin-related Ink surface via ink-testing-library and
 * writes the rendered ANSI-stripped frame to
 * `tui/test-output/plugin-frames/<surface>.txt` so the citizen-facing
 * UI can be reviewed without running the full TUI binary.
 *
 * Surfaces dumped:
 *   - PluginBrowser (active + inactive states, no plugins, navigation hint)
 *   - /plugin slash command acknowledgements (install / list / pipa-text)
 *
 * Usage:
 *   bun run scripts/dump-plugin-frames.tsx
 *   open tui/test-output/plugin-frames/
 */

import React from 'react'
import { render } from 'ink-testing-library'
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { ThemeProvider } from '../src/theme/provider.js'
import {
  PluginBrowser,
  type PluginEntry,
} from '../src/components/plugins/PluginBrowser.js'
import pluginCommand from '../src/commands/plugin.js'
import type {
  PluginOpFrame,
  SessionEventFrame,
} from '../src/ipc/frames.generated.js'

// ---------------------------------------------------------------------------
// Output directory — under tui/test-output/plugin-frames/
// ---------------------------------------------------------------------------

const SCRIPT_DIR = fileURLToPath(new URL('.', import.meta.url))
const TUI_ROOT = join(SCRIPT_DIR, '..')
const OUT_DIR = join(TUI_ROOT, 'test-output', 'plugin-frames')

mkdirSync(OUT_DIR, { recursive: true })

// ---------------------------------------------------------------------------
// ANSI strip — ink-testing-library returns rendered text including ANSI
// color codes. For visual review we keep ANSI in one variant (.ansi.txt)
// and emit a plain-text version (.txt) for diff-friendliness.
// ---------------------------------------------------------------------------

// Match all ANSI control sequences. Pattern from
// chalk/ansi-regex (MIT) — embedded inline to avoid an extra dep.
const ANSI_PATTERN = new RegExp(
  [
    '[\\u001B\\u009B][[\\]()#;?]*(?:(?:(?:(?:;[-a-zA-Z\\d\\/#&.:=?%@~_]+)*|[a-zA-Z\\d]+(?:;[-a-zA-Z\\d\\/#&.:=?%@~_]*)*)?\\u0007)',
    '(?:(?:\\d{1,4}(?:;\\d{0,4})*)?[\\dA-PR-TZcf-nq-uy=><~]))',
  ].join('|'),
  'g',
)

function stripAnsi(s: string): string {
  return s.replace(ANSI_PATTERN, '')
}

function dump(name: string, frame: string | undefined): void {
  if (!frame) {
    console.warn(`⚠ ${name}: empty frame`)
    return
  }
  writeFileSync(join(OUT_DIR, `${name}.ansi.txt`), frame, 'utf-8')
  writeFileSync(join(OUT_DIR, `${name}.txt`), stripAnsi(frame), 'utf-8')
  const lines = stripAnsi(frame).split('\n').length
  console.log(`✓ ${name} (${lines} lines)`)
}

// ---------------------------------------------------------------------------
// Surface 1 — PluginBrowser with 4 plugins (3 active, 1 inactive)
// ---------------------------------------------------------------------------

const SAMPLE_PLUGINS: PluginEntry[] = [
  {
    id: 'seoul_subway',
    name: 'ummaya-plugin-seoul-subway',
    version: '0.1.0',
    description_ko: '서울 지하철 실시간 도착 정보',
    description_en: 'Seoul subway realtime arrival',
    isActive: true,
  },
  {
    id: 'post_office',
    name: 'ummaya-plugin-post-office',
    version: '0.1.0',
    description_ko: '우체국 등기 / EMS 배송 추적',
    description_en: 'Korea Post tracking',
    isActive: true,
  },
  {
    id: 'nts_homtax',
    name: 'ummaya-plugin-nts-homtax',
    version: '0.1.0',
    description_ko: '국세청 홈택스 자료 조회 (Mock)',
    description_en: 'NTS Hometax mock',
    isActive: false,
  },
  {
    id: 'nhis_check',
    name: 'ummaya-plugin-nhis-check',
    version: '0.1.0',
    description_ko: 'NHIS 건강검진 결과 (Mock)',
    description_en: 'NHIS health checkup mock',
    isActive: true,
  },
]

{
  const noop = () => undefined
  const result = render(
    <ThemeProvider>
      <PluginBrowser
        plugins={SAMPLE_PLUGINS}
        onToggle={noop}
        onDetail={noop}
        onRemove={noop}
        onMarketplace={noop}
        onDismiss={noop}
      />
    </ThemeProvider>,
  )
  dump('plugin-browser-4-entries', result.lastFrame())
  result.unmount()
}

// Empty state
{
  const noop = () => undefined
  const result = render(
    <ThemeProvider>
      <PluginBrowser
        plugins={[]}
        onToggle={noop}
        onDetail={noop}
        onRemove={noop}
        onMarketplace={noop}
        onDismiss={noop}
      />
    </ThemeProvider>,
  )
  dump('plugin-browser-empty', result.lastFrame())
  result.unmount()
}

// ---------------------------------------------------------------------------
// Surface 2 — /plugin slash command acknowledgements
// (text-only — we render a small wrapper that displays the result string)
// ---------------------------------------------------------------------------

import { Text, Box } from '../src/ink.js'

function CommandAck(props: { command: string; result: string }) {
  return (
    <Box flexDirection="column" paddingX={1}>
      <Text color="cyan">{`> ${props.command}`}</Text>
      <Box marginTop={1}>
        <Text>{props.result}</Text>
      </Box>
    </Box>
  )
}

function runCommand(input: string): {
  ack: string
  pluginFrames: PluginOpFrame[]
  sessionFrames: SessionEventFrame[]
} {
  const pluginFrames: PluginOpFrame[] = []
  const sessionFrames: SessionEventFrame[] = []
  const result = pluginCommand.handle({
    args: input.replace(/^\/plugin\s*/, '').trim(),
    sendFrame: (f) => sessionFrames.push(f),
    sendPluginOp: (f) => pluginFrames.push(f),
  })
  if (typeof result === 'object' && 'acknowledgement' in result) {
    return { ack: result.acknowledgement, pluginFrames, sessionFrames }
  }
  return { ack: '<no acknowledgement>', pluginFrames, sessionFrames }
}

// [label, command] — both identical. Tuple form leaves room for future divergence.
const SLASH_INPUTS: Array<[string, string]> = [
  ['/plugin', '/plugin'], // empty subcommand → usage
  ['/plugin install seoul-subway', '/plugin install seoul-subway'],
  [
    '/plugin install seoul-subway --version 1.2.0 --dry-run',
    '/plugin install seoul-subway --version 1.2.0 --dry-run',
  ],
  ['/plugin list', '/plugin list'],
  ['/plugin uninstall seoul-subway', '/plugin uninstall seoul-subway'],
  ['/plugin pipa-text', '/plugin pipa-text'],
  ['/plugin reinstall foo', '/plugin reinstall foo'], // unknown subcommand
]

const slashSummary: string[] = []

for (const [label, input] of SLASH_INPUTS) {
  const { ack, pluginFrames } = runCommand(input)
  const result = render(
    <ThemeProvider>
      <CommandAck command={label} result={ack} />
    </ThemeProvider>,
  )
  const slug = label.replace(/[^a-z0-9-]+/gi, '_').replace(/^_+|_+$/g, '')
  dump(`slash-${slug}`, result.lastFrame())
  result.unmount()

  slashSummary.push(
    `# \`${label}\``,
    '',
    `**Acknowledgement**:`,
    '```',
    ack,
    '```',
    '',
    `**Plugin frames emitted**: ${pluginFrames.length}`,
    ...(pluginFrames.length > 0
      ? [
          '```json',
          JSON.stringify(pluginFrames[0], null, 2),
          '```',
        ]
      : []),
    '',
  )
}

writeFileSync(
  join(OUT_DIR, '00-slash-summary.md'),
  ['# /plugin slash command — visual review summary', '', ...slashSummary].join('\n'),
  'utf-8',
)

console.log(`\n✓ All frames written to ${OUT_DIR}`)
