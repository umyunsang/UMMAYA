// SPDX-License-Identifier: Apache-2.0
// Spec 1635 P4 UI L2 — T071 help component tests (FR-029, US5).

import { describe, it, expect } from 'bun:test';
import {
  groupCatalog,
  GROUP_ORDER,
} from '../../../src/schemas/ui-l2/slash-command.js';
import { UI_L2_SLASH_COMMANDS } from '../../../src/commands/catalog.js';

describe('HelpV2Grouped — groupCatalog correctness (FR-029)', () => {
  it('produces exactly 4 groups', () => {
    const grouped = groupCatalog(UI_L2_SLASH_COMMANDS);
    const keys = Object.keys(grouped);
    expect(keys).toHaveLength(4);
    for (const g of GROUP_ORDER) {
      expect(keys).toContain(g);
    }
  });

  it('every catalog entry appears in exactly one group', () => {
    const grouped = groupCatalog(UI_L2_SLASH_COMMANDS);
    const allEntries = [
      ...grouped.session,
      ...grouped.permission,
      ...grouped.tool,
      ...grouped.storage,
    ];
    // No duplicates
    const names = allEntries.map((e) => e.name);
    const unique = new Set(names);
    expect(unique.size).toBe(names.length);

    // Every non-hidden catalog entry is represented
    const expected = UI_L2_SLASH_COMMANDS.filter((e) => !e.hidden).map((e) => e.name);
    for (const name of expected) {
      expect(names).toContain(name);
    }
  });

  it('session group contains core session commands', () => {
    const grouped = groupCatalog(UI_L2_SLASH_COMMANDS);
    const names = grouped.session.map((e) => e.name);
    expect(names).toContain('/help');
    expect(names).toContain('/onboarding');
    expect(names).toContain('/lang');
    expect(names).toContain('/login');
    expect(names).toContain('/logout');
  });

  it('permission group contains /consent list and /consent revoke', () => {
    const grouped = groupCatalog(UI_L2_SLASH_COMMANDS);
    const names = grouped.permission.map((e) => e.name);
    expect(names).toContain('/consent list');
    expect(names).toContain('/consent revoke');
  });

  it('tool group contains /agents and /plugins', () => {
    const grouped = groupCatalog(UI_L2_SLASH_COMMANDS);
    const names = grouped.tool.map((e) => e.name);
    expect(names).toContain('/agents');
    expect(names).toContain('/plugins');
  });

  it('storage group contains /config, /export, /history', () => {
    const grouped = groupCatalog(UI_L2_SLASH_COMMANDS);
    const names = grouped.storage.map((e) => e.name);
    expect(names).toContain('/config');
    expect(names).toContain('/export');
    expect(names).toContain('/history');
  });

  it('groups are sorted alphabetically within each group', () => {
    const grouped = groupCatalog(UI_L2_SLASH_COMMANDS);
    for (const g of GROUP_ORDER) {
      const names = grouped[g].map((e) => e.name);
      const sorted = [...names].sort((a, b) => a.localeCompare(b));
      expect(names).toEqual(sorted);
    }
  });

  it('hidden entries are excluded from groupCatalog output', () => {
    const grouped = groupCatalog(UI_L2_SLASH_COMMANDS);
    const allVisible = [
      ...grouped.session,
      ...grouped.permission,
      ...grouped.tool,
      ...grouped.storage,
    ];
    for (const entry of allVisible) {
      expect(entry.hidden).toBe(false);
    }
  });
});
