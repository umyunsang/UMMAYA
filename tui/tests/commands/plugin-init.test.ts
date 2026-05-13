// SPDX-License-Identifier: Apache-2.0
//
// T019 — Negative-path tests for `ummaya plugin init <name>` per
// specs/1636-plugin-dx-5tier/contracts/plugin-init.cli.md.
//
// Covers the 4 contract negative paths plus a happy-path emission shape
// check. The runPluginInit core never reaches the network — it is a pure
// filesystem writer driven by Pydantic-mirroring TypeScript templates.
// We assert that property explicitly via the network egress test.

import { afterEach, beforeEach, describe, expect, it } from 'bun:test'
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import * as yaml from 'yaml'

import {
  mainPluginInit,
  parsePluginInitArgv,
  runPluginInit,
  type PluginInitOptions,
} from '../../src/commands/plugin-init'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeTmp(): string {
  return mkdtempSync(join(tmpdir(), 'plugin-init-'))
}

function baseOptions(overrides: Partial<PluginInitOptions> = {}): PluginInitOptions {
  return {
    name: 'demo_plugin',
    tier: 'live',
    layer: 1,
    pii: false,
    searchHintKo: '데모 플러그인 조회 추천',
    searchHintEn: 'demo plugin lookup recommended',
    ...overrides,
  }
}

let tmp: string

beforeEach(() => {
  tmp = makeTmp()
})

afterEach(() => {
  rmSync(tmp, { recursive: true, force: true })
})

// ---------------------------------------------------------------------------
// Happy-path emission shape
// ---------------------------------------------------------------------------

describe('runPluginInit — happy path', () => {
  it('emits the full file tree per contract', () => {
    const result = runPluginInit(baseOptions({ cwd: tmp }))

    expect(result.exitCode).toBe(0)
    expect(result.outDir).toBe(join(tmp, 'demo_plugin'))
    expect(result.filesWritten).toContain('pyproject.toml')
    expect(result.filesWritten).toContain('manifest.yaml')
    expect(result.filesWritten).toContain('plugin_demo_plugin/adapter.py')
    expect(result.filesWritten).toContain('plugin_demo_plugin/schema.py')
    expect(result.filesWritten).toContain('plugin_demo_plugin/__init__.py')
    expect(result.filesWritten).toContain('tests/test_adapter.py')
    expect(result.filesWritten).toContain('tests/conftest.py')
    expect(result.filesWritten).toContain(
      'tests/fixtures/plugin.demo_plugin.find.json',
    )
    expect(result.filesWritten).toContain('.github/workflows/plugin-validation.yml')
    expect(result.filesWritten).toContain('.github/workflows/release-with-slsa.yml')
    expect(result.filesWritten).toContain('README.ko.md')
    expect(result.filesWritten).toContain('README.en.md')
    expect(result.filesWritten).toContain('.gitignore')
  })

  it('emitted manifest validates structurally as a PluginManifest YAML', () => {
    const result = runPluginInit(baseOptions({ cwd: tmp }))
    const manifestPath = join(result.outDir!, 'manifest.yaml')
    const manifest = yaml.parse(readFileSync(manifestPath, 'utf-8'))

    expect(manifest.plugin_id).toBe('demo_plugin')
    expect(manifest.adapter.tool_id).toBe('plugin.demo_plugin.find')
    expect(manifest.adapter.primitive).toBe('find')
    expect(manifest.tier).toBe('live')
    expect(manifest.processes_pii).toBe(false)
    expect(manifest.pipa_trustee_acknowledgment).toBeNull()
    expect(manifest.otel_attributes['ummaya.plugin.id']).toBe('demo_plugin')
    expect(manifest.permission_layer).toBe(1)
  })

  it('mock tier sets mock_source_spec in the manifest', () => {
    const result = runPluginInit(baseOptions({ cwd: tmp, tier: 'mock' }))
    const manifest = yaml.parse(
      readFileSync(join(result.outDir!, 'manifest.yaml'), 'utf-8'),
    )
    expect(manifest.tier).toBe('mock')
    expect(typeof manifest.mock_source_spec).toBe('string')
    expect(manifest.mock_source_spec.length).toBeGreaterThan(0)
  })
})

// ---------------------------------------------------------------------------
// Contract negative #1 — invalid name
// ---------------------------------------------------------------------------

describe('runPluginInit — invalid name', () => {
  it.each([
    ['Uppercase'],
    ['hyphen-name'],
    ['9starts_with_digit'],
    [''],
  ])('rejects %s', (badName: string) => {
    const result = runPluginInit(baseOptions({ name: badName, cwd: tmp }))
    expect(result.exitCode).toBe(1)
    expect(result.errorKind).toBe('invalid_name')
    expect(result.errorMessage).toContain('^[a-z][a-z0-9_]*$')
  })

  it('rejects names longer than 64 chars', () => {
    const long = 'a'.repeat(65)
    const result = runPluginInit(baseOptions({ name: long, cwd: tmp }))
    expect(result.exitCode).toBe(1)
    expect(result.errorKind).toBe('invalid_name')
  })
})

// ---------------------------------------------------------------------------
// Contract negative #2 — non-empty out without --force
// ---------------------------------------------------------------------------

describe('runPluginInit — non-empty out dir', () => {
  it('refuses to overwrite a non-empty out without --force', () => {
    const out = join(tmp, 'demo_plugin')
    mkdirSync(out, { recursive: true })
    writeFileSync(join(out, 'existing.txt'), 'do not delete')

    const result = runPluginInit(baseOptions({ cwd: tmp }))
    expect(result.exitCode).toBe(2)
    expect(result.errorKind).toBe('out_dir_non_empty')
    expect(result.errorMessage).toContain('--force')
    expect(readFileSync(join(out, 'existing.txt'), 'utf-8')).toBe('do not delete')
  })

  it('overwrites a non-empty out when --force is passed', () => {
    const out = join(tmp, 'demo_plugin')
    mkdirSync(out, { recursive: true })
    writeFileSync(join(out, 'existing.txt'), 'old')

    const result = runPluginInit(baseOptions({ cwd: tmp, force: true }))
    expect(result.exitCode).toBe(0)
    expect(existsSync(join(out, 'existing.txt'))).toBe(false)
    expect(existsSync(join(out, 'manifest.yaml'))).toBe(true)
  })

  it('accepts an empty out directory without --force', () => {
    const out = join(tmp, 'demo_plugin')
    mkdirSync(out, { recursive: true })
    expect(readdirSync(out).length).toBe(0)

    const result = runPluginInit(baseOptions({ cwd: tmp }))
    expect(result.exitCode).toBe(0)
  })
})

// ---------------------------------------------------------------------------
// Contract negative #3 — --pii without acknowledgment
// ---------------------------------------------------------------------------

describe('runPluginInit — PIPA acknowledgment', () => {
  it('rejects pii=true without pipaAcknowledgment', () => {
    const result = runPluginInit(baseOptions({ cwd: tmp, pii: true }))
    expect(result.exitCode).toBe(3)
    expect(result.errorKind).toBe('pipa_acknowledgment_error')
    expect(result.errorMessage).toContain('docs/plugins/security-review.md')
  })

  it('rejects pii=false with pipaAcknowledgment supplied', () => {
    const result = runPluginInit(
      baseOptions({
        cwd: tmp,
        pii: false,
        pipaAcknowledgment: {
          trustee_org_name: 'UMMAYA Demo',
          trustee_contact: 'demo@example.com',
          pii_fields_handled: ['phone_number'],
          legal_basis: 'PIPA §15-1-2',
          acknowledgment_sha256: 'a'.repeat(64),
        },
      }),
    )
    expect(result.exitCode).toBe(3)
  })

  it('rejects malformed acknowledgment_sha256', () => {
    const result = runPluginInit(
      baseOptions({
        cwd: tmp,
        pii: true,
        pipaAcknowledgment: {
          trustee_org_name: 'UMMAYA Demo',
          trustee_contact: 'demo@example.com',
          pii_fields_handled: ['phone_number'],
          legal_basis: 'PIPA §15-1-2',
          acknowledgment_sha256: 'not-a-hash',
        },
      }),
    )
    expect(result.exitCode).toBe(3)
    expect(result.errorMessage).toContain('^[a-f0-9]{64}$')
  })

  it('accepts a well-formed acknowledgment block', () => {
    const result = runPluginInit(
      baseOptions({
        cwd: tmp,
        pii: true,
        pipaAcknowledgment: {
          trustee_org_name: 'UMMAYA Demo',
          trustee_contact: 'demo@example.com',
          pii_fields_handled: ['phone_number'],
          legal_basis: 'PIPA §15-1-2',
          acknowledgment_sha256: 'a'.repeat(64),
        },
      }),
    )
    expect(result.exitCode).toBe(0)
    const manifest = yaml.parse(
      readFileSync(join(result.outDir!, 'manifest.yaml'), 'utf-8'),
    )
    expect(manifest.processes_pii).toBe(true)
    expect(manifest.pipa_trustee_acknowledgment.trustee_org_name).toBe('UMMAYA Demo')
  })
})

// ---------------------------------------------------------------------------
// Contract negative #4 — network egress
// ---------------------------------------------------------------------------

describe('runPluginInit — no outbound network', () => {
  it('does not perform any HTTP request during scaffolding', () => {
    // Patch the global fetch to detect a network attempt; runPluginInit must
    // never hit the wire.
    const originalFetch = globalThis.fetch
    let fetchCalls = 0
    globalThis.fetch = (() => {
      fetchCalls += 1
      throw new Error('runPluginInit attempted a network call — Constitution §IV')
    }) as typeof globalThis.fetch
    try {
      const result = runPluginInit(baseOptions({ cwd: tmp }))
      expect(result.exitCode).toBe(0)
      expect(fetchCalls).toBe(0)
    } finally {
      globalThis.fetch = originalFetch
    }
  })
})

// ---------------------------------------------------------------------------
// argv parser
// ---------------------------------------------------------------------------

describe('parsePluginInitArgv', () => {
  it('parses --tier / --layer / --pii / --out / --force', () => {
    const parsed = parsePluginInitArgv([
      'demo_plugin',
      '--tier',
      'mock',
      '--layer',
      '2',
      '--pii',
      '--out',
      './x',
      '--force',
      '--non-interactive',
    ])
    expect(parsed.errors).toEqual([])
    expect(parsed.name).toBe('demo_plugin')
    expect(parsed.options.tier).toBe('mock')
    expect(parsed.options.layer).toBe(2)
    expect(parsed.options.pii).toBe(true)
    expect(parsed.options.out).toBe('./x')
    expect(parsed.options.force).toBe(true)
    expect(parsed.nonInteractive).toBe(true)
  })

  it('--no-pii sets pii=false', () => {
    const parsed = parsePluginInitArgv(['demo', '--no-pii', '--non-interactive'])
    expect(parsed.options.pii).toBe(false)
  })

  it('rejects bad --tier values', () => {
    const parsed = parsePluginInitArgv(['demo', '--tier', 'oops'])
    expect(parsed.errors.length).toBeGreaterThan(0)
  })

  it('rejects bad --layer values', () => {
    const parsed = parsePluginInitArgv(['demo', '--layer', '7'])
    expect(parsed.errors.length).toBeGreaterThan(0)
  })
})

// ---------------------------------------------------------------------------
// CLI entry
// ---------------------------------------------------------------------------

describe('mainPluginInit', () => {
  it('returns exit 1 with no name', () => {
    const result = mainPluginInit([])
    expect(result.exitCode).toBe(1)
    expect(result.errorKind).toBe('missing_name')
  })

  it('returns exit 1 with --non-interactive but no --tier', () => {
    const result = mainPluginInit([
      'demo',
      '--non-interactive',
      '--layer',
      '1',
      '--no-pii',
    ])
    expect(result.exitCode).toBe(1)
    expect(result.errorKind).toBe('non_interactive_missing_value')
  })

  it('returns exit 1 with interactive_pending when prompts would be needed', () => {
    const result = mainPluginInit(['demo'])
    expect(result.exitCode).toBe(1)
    expect(result.errorKind).toBe('interactive_pending')
  })

  it('non-interactive happy path scaffolds', () => {
    const out = join(tmp, 'demo_plugin')
    const result = mainPluginInit([
      'demo_plugin',
      '--non-interactive',
      '--tier',
      'live',
      '--layer',
      '1',
      '--no-pii',
      '--out',
      out,
    ])
    expect(result.exitCode).toBe(0)
    expect(existsSync(join(out, 'manifest.yaml'))).toBe(true)
  })

  it('returns exit 3 when --pii is set without --pipa-* flags', () => {
    const out = join(tmp, 'demo_plugin')
    const result = mainPluginInit([
      'demo_plugin',
      '--non-interactive',
      '--tier',
      'live',
      '--layer',
      '2',
      '--pii',
      '--out',
      out,
    ])
    expect(result.exitCode).toBe(3)
    expect(result.errorKind).toBe('pipa_acknowledgment_error')
    expect(result.errorMessage).toContain('docs/plugins/security-review.md')
  })

  it('--pii with all five --pipa-* flags scaffolds with PIPA block', () => {
    const out = join(tmp, 'demo_plugin')
    const result = mainPluginInit([
      'demo_plugin',
      '--non-interactive',
      '--tier',
      'live',
      '--layer',
      '2',
      '--pii',
      '--pipa-org',
      'UMMAYA Demo',
      '--pipa-contact',
      'demo@example.com',
      '--pipa-fields',
      'phone_number,resident_registration_number',
      '--pipa-legal-basis',
      'PIPA §15-1-2',
      '--pipa-sha256',
      'a'.repeat(64),
      '--out',
      out,
    ])
    expect(result.exitCode).toBe(0)
    const manifest = yaml.parse(readFileSync(join(out, 'manifest.yaml'), 'utf-8'))
    expect(manifest.processes_pii).toBe(true)
    expect(manifest.pipa_trustee_acknowledgment.trustee_org_name).toBe('UMMAYA Demo')
    expect(manifest.pipa_trustee_acknowledgment.pii_fields_handled).toEqual([
      'phone_number',
      'resident_registration_number',
    ])
    expect(manifest.pipa_trustee_acknowledgment.legal_basis).toBe('PIPA §15-1-2')
    expect(manifest.pipa_trustee_acknowledgment.acknowledgment_sha256).toBe(
      'a'.repeat(64),
    )
  })
})
