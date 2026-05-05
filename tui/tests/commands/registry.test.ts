// T043 — Registry-shape test
// Asserts the default KOSMOS registry shape (keys, per-entry interface) is
// structurally well-formed and consistent with FR-036 / US2 scenario 5.

import { describe, expect, it } from 'bun:test'
import { buildDefaultRegistry, createRegistry, registerCommand } from '../../src/commands/index'
import { listCommands } from '../../src/commands/dispatcher'
import type { CommandDefinition } from '../../src/commands/types'

describe('Default registry shape (FR-036)', () => {
  it('contains all four mandatory session commands', () => {
    const registry = buildDefaultRegistry()
    const names = new Set(registry.keys())

    expect(names.has('save')).toBe(true)
    expect(names.has('sessions')).toBe(true)
    expect(names.has('resume')).toBe(true)
    expect(names.has('new')).toBe(true)
  })

  it('registers /resume alias /continue', () => {
    const registry = buildDefaultRegistry()
    expect(registry.has('continue')).toBe(true)
    // Alias maps to the same definition as the canonical name
    expect(registry.get('continue')).toBe(registry.get('resume'))
  })

  it('every entry conforms to CommandDefinition interface', () => {
    const registry = buildDefaultRegistry()
    for (const [, def] of registry) {
      expect(typeof def.name).toBe('string')
      expect(def.name.length).toBeGreaterThan(0)
      expect(typeof def.description).toBe('string')
      expect(def.description.length).toBeGreaterThan(0)
      expect(typeof def.handle).toBe('function')
      if (def.aliases !== undefined) {
        expect(Array.isArray(def.aliases)).toBe(true)
      }
      if (def.argumentHint !== undefined) {
        expect(typeof def.argumentHint).toBe('string')
      }
    }
  })

  it('listCommands returns sorted, deduplicated entries', () => {
    const registry = buildDefaultRegistry()
    const commands = listCommands(registry)

    // 6 unique commands: save/sessions/resume/new (Spec 287) + plugin (Spec 1636 P5)
    //                    + migrate-sessions (Lead-Diag-3 session migration)
    expect(commands).toHaveLength(6)

    // Must be sorted alphabetically
    const names = commands.map((c) => c.name)
    expect(names).toEqual([...names].sort())
  })

  it('createRegistry starts empty', () => {
    const registry = createRegistry()
    expect(registry.size).toBe(0)
  })

  it('registerCommand indexes both name and aliases', () => {
    const registry = createRegistry()
    const def: CommandDefinition = {
      name: 'myCmd',
      description: 'My command',
      aliases: ['mc', 'm'],
      handle: () => ({ acknowledgement: 'ok' }),
    }
    registerCommand(registry, def)

    expect(registry.get('myCmd')).toBe(def)
    expect(registry.get('mc')).toBe(def)
    expect(registry.get('m')).toBe(def)
    expect(registry.size).toBe(3)
  })
})
