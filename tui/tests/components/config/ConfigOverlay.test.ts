// SPDX-License-Identifier: Apache-2.0
// Spec 1635 P4 UI L2 — T071 config component tests (FR-030, US5).

import { describe, it, expect } from 'bun:test';
import {
  KOSMOS_CONFIG_CATALOG,
  executeConfig,
} from '../../../src/commands/config.js';

describe('ConfigOverlay — KOSMOS_CONFIG_CATALOG (FR-030)', () => {
  it('catalog contains at least one secret entry', () => {
    const secrets = KOSMOS_CONFIG_CATALOG.filter((e) => e.isSecret);
    expect(secrets.length).toBeGreaterThan(0);
  });

  it('catalog contains at least one non-secret entry', () => {
    const nonSecrets = KOSMOS_CONFIG_CATALOG.filter((e) => !e.isSecret);
    expect(nonSecrets.length).toBeGreaterThan(0);
  });

  it('all entries have both ko and en labels', () => {
    for (const entry of KOSMOS_CONFIG_CATALOG) {
      expect(typeof entry.label_ko).toBe('string');
      expect(entry.label_ko.length).toBeGreaterThan(0);
      expect(typeof entry.label_en).toBe('string');
      expect(entry.label_en.length).toBeGreaterThan(0);
    }
  });

  it('all entries have a non-empty key', () => {
    for (const entry of KOSMOS_CONFIG_CATALOG) {
      expect(typeof entry.key).toBe('string');
      expect(entry.key.length).toBeGreaterThan(0);
    }
  });

  it('KOSMOS_FRIENDLI_TOKEN is marked as secret', () => {
    const entry = KOSMOS_CONFIG_CATALOG.find(
      (e) => e.key === 'KOSMOS_FRIENDLI_TOKEN',
    );
    expect(entry).toBeDefined();
    expect(entry?.isSecret).toBe(true);
  });
});

describe('executeConfig — command result (FR-030)', () => {
  it('returns entries array matching catalog length', () => {
    const result = executeConfig();
    expect(result.entries).toHaveLength(KOSMOS_CONFIG_CATALOG.length);
  });

  it('entries have value field (may be empty string)', () => {
    const result = executeConfig();
    for (const entry of result.entries) {
      expect(typeof entry.value).toBe('string');
    }
  });

  it('openSecretEditorFor is null by default', () => {
    const result = executeConfig();
    expect(result.openSecretEditorFor).toBeNull();
  });

  it('openSecretEditorFor is set when key is passed', () => {
    const result = executeConfig('KOSMOS_FRIENDLI_TOKEN');
    expect(result.openSecretEditorFor).toBe('KOSMOS_FRIENDLI_TOKEN');
  });
});
