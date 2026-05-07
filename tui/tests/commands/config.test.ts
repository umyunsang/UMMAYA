// SPDX-License-Identifier: Apache-2.0
// Spec 1635 P4 UI L2 — T071 /config command tests (FR-030, US5).

import { describe, it, expect } from 'bun:test';
import {
  executeConfig,
  applyConfigChanges,
  KOSMOS_CONFIG_CATALOG,
} from '../../src/commands/config.js';

describe('executeConfig (FR-030)', () => {
  it('emits entries matching catalog count', () => {
    const result = executeConfig();
    expect(result.entries).toHaveLength(KOSMOS_CONFIG_CATALOG.length);
  });

  it('each entry has key, value, isSecret fields', () => {
    const result = executeConfig();
    for (const entry of result.entries) {
      expect(typeof entry.key).toBe('string');
      expect(typeof entry.value).toBe('string');
      expect(typeof entry.isSecret).toBe('boolean');
    }
  });

  it('does not expose secret entries through /config', () => {
    const result = executeConfig();
    const secretEntries = result.entries.filter((e) => e.isSecret);
    expect(secretEntries).toHaveLength(0);
    expect(result.entries.find((e) => e.key.includes('FRIENDLI'))).toBeUndefined();
  });

  it('openSecretEditorFor defaults to null', () => {
    const result = executeConfig();
    expect(result.openSecretEditorFor).toBeNull();
  });

  it('openSecretEditorFor reflects the passed key', () => {
    const result = executeConfig('KOSMOS_DATA_GO_KR_API_KEY');
    expect(result.openSecretEditorFor).toBe('KOSMOS_DATA_GO_KR_API_KEY');
  });
});

describe('applyConfigChanges — FR-030 safety guard', () => {
  it('applies non-secret env var changes', () => {
    const originalValue = process.env['KOSMOS_TUI_LOCALE'];
    applyConfigChanges([
      {
        key: 'KOSMOS_TUI_LOCALE',
        label_ko: '언어',
        label_en: 'Language',
        value: 'en',
        isSecret: false,
      },
    ]);
    expect(process.env['KOSMOS_TUI_LOCALE']).toBe('en');
    // Restore
    if (originalValue === undefined) {
      delete process.env['KOSMOS_TUI_LOCALE'];
    } else {
      process.env['KOSMOS_TUI_LOCALE'] = originalValue;
    }
  });

  it('NEVER applies secret entries (safety guard)', () => {
    const originalValue = process.env['KOSMOS_FRIENDLI_TOKEN'];
    const maliciousValue = 'LEAKED_KEY_12345';
    applyConfigChanges([
      {
        key: 'KOSMOS_FRIENDLI_TOKEN',
        label_ko: 'API 키',
        label_en: 'API key',
        value: maliciousValue,
        isSecret: true,
      },
    ]);
    // Value must NOT have been written
    expect(process.env['KOSMOS_FRIENDLI_TOKEN']).not.toBe(maliciousValue);
    // Restore
    if (originalValue === undefined) {
      delete process.env['KOSMOS_FRIENDLI_TOKEN'];
    } else {
      process.env['KOSMOS_FRIENDLI_TOKEN'] = originalValue;
    }
  });

  it('skips entries with empty value', () => {
    const original = process.env['KOSMOS_TUI_THEME'];
    process.env['KOSMOS_TUI_THEME'] = 'dark';
    applyConfigChanges([
      {
        key: 'KOSMOS_TUI_THEME',
        label_ko: '테마',
        label_en: 'Theme',
        value: '',
        isSecret: false,
      },
    ]);
    // Empty value should not overwrite existing
    expect(process.env['KOSMOS_TUI_THEME']).toBe('dark');
    // Restore
    if (original === undefined) {
      delete process.env['KOSMOS_TUI_THEME'];
    } else {
      process.env['KOSMOS_TUI_THEME'] = original;
    }
  });
});
