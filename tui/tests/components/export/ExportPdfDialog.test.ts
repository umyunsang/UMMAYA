// SPDX-License-Identifier: Apache-2.0
// Spec 1635 P4 UI L2 — T071 export component tests (FR-032, US5).
//
// CRITICAL — SC-012 assertion:
//   "/export PDF contains zero OTEL span identifiers and zero plugin-internal
//   state markers in automated content scans across 20 sample sessions."
//
// This test asserts that sanitizeForExport() strips ALL forbidden patterns
// from text before it can reach the PDF assembly.  The test is the CI gate
// for SC-012.

import { describe, it, expect } from 'bun:test';
import { sanitizeForExport } from '../../../src/components/export/ExportPdfDialog.js';

// ---------------------------------------------------------------------------
// SC-012 leakage patterns
// ---------------------------------------------------------------------------

const FORBIDDEN_PATTERNS = [
  /traceId=[A-Za-z0-9]+/,
  /spanId=[A-Za-z0-9]+/,
  /pluginInternal:[^\s]*/,
];

function containsForbiddenPattern(text: string): boolean {
  return FORBIDDEN_PATTERNS.some((p) => p.test(text));
}

// ---------------------------------------------------------------------------
// SC-012 core tests
// ---------------------------------------------------------------------------

describe('sanitizeForExport — SC-012 OTEL leakage prevention (FR-032)', () => {
  it('strips traceId= markers', () => {
    const input = 'Some log line traceId=abc123def456 and more text';
    const output = sanitizeForExport(input);
    expect(containsForbiddenPattern(output)).toBe(false);
    expect(output).not.toContain('traceId=');
  });

  it('strips spanId= markers', () => {
    const input = 'Span info spanId=9f8e7d6c5b4a3210 end';
    const output = sanitizeForExport(input);
    expect(containsForbiddenPattern(output)).toBe(false);
    expect(output).not.toContain('spanId=');
  });

  it('strips pluginInternal: markers', () => {
    const input = 'pluginInternal:stateSnapshot::version=3.2.1 pluginInternal:event::type=load';
    const output = sanitizeForExport(input);
    expect(containsForbiddenPattern(output)).toBe(false);
    expect(output).not.toContain('pluginInternal:');
  });

  it('handles multiple forbidden patterns in a single string', () => {
    const input =
      'traceId=aaabbbccc spanId=111222333 pluginInternal:loaded::ok and normal text';
    const output = sanitizeForExport(input);
    expect(containsForbiddenPattern(output)).toBe(false);
  });

  it('preserves normal conversation text unchanged', () => {
    const input = '안녕하세요! 운전면허 갱신 절차를 알려드리겠습니다.';
    const output = sanitizeForExport(input);
    expect(output).toBe(input);
  });

  it('preserves receipt IDs (rcpt- prefix is allowed)', () => {
    const input = 'Consent receipt issued: rcpt-abc123xyz456';
    const output = sanitizeForExport(input);
    expect(output).toBe(input);
  });

  it('preserves tool names without forbidden patterns', () => {
    const input = 'Tool: koroad_accident_hazard_search Input: {"location": "서울"}';
    const output = sanitizeForExport(input);
    expect(output).toBe(input);
  });

  it('replaces forbidden patterns with [redacted] placeholder', () => {
    const input = 'See traceId=abc123 for details';
    const output = sanitizeForExport(input);
    expect(output).toContain('[redacted]');
  });

  // ---------------------------------------------------------------------------
  // 20 sample session simulation (SC-012: "across 20 sample sessions")
  // ---------------------------------------------------------------------------

  it('SC-012: 20 sample export texts are all clean after sanitization', () => {
    const sampleTexts: string[] = [
      // Normal citizen messages
      '복지부 의료급여 신청 방법을 알려주세요.',
      '교통 사고 데이터를 조회했습니다.',
      '안녕하세요! 무엇을 도와드릴까요?',
      '주민등록증 발급 절차가 궁금합니다.',
      '국민건강보험 납입 이력 확인 부탁드립니다.',
      // Tool invocation summaries
      'Tool: hira_hospital_search - 결과: 3개 병원',
      'Tool: kma_forecast_fetch - 결과: 맑음 25°C',
      'Tool: nmc_emergency_search - 결과: 응급실 2곳',
      // Receipts (should NOT be sanitized)
      'rcpt-abc12345678 Layer:2 allow_once',
      'rcpt-xyz98765432 Layer:1 allow_session',
      // Text WITH embedded forbidden patterns (must be cleaned)
      `Normal message traceId=cafebabe spanId=deadbeef extra`,
      `pluginInternal:loaded::plugin=test-1.0 payload`,
      `Info: traceId=00000000 spanId=ffffffff something happened`,
      `Debug data: pluginInternal:event::click`,
      `Mixed: hello traceId=aaa spanId=bbb pluginInternal:x::y world`,
      // Edge cases
      'Empty string test: ',
      '한글만: 이 텍스트에는 금지된 패턴이 없습니다.',
      'Numbers only: 1234567890',
      'URL-like: https://api.kosmos.kr/v1/lookup',
      'Receipt-only: rcpt-testid001',
    ];

    for (const sample of sampleTexts) {
      const sanitized = sanitizeForExport(sample);
      expect(containsForbiddenPattern(sanitized)).toBe(false);
    }
  });
});

// ---------------------------------------------------------------------------
// executeExport — command shape tests (FR-032)
// ---------------------------------------------------------------------------

describe('executeExport — command result (FR-032)', () => {
  it('output path ends with .pdf', async () => {
    const { executeExport } = await import('../../../src/commands/export.js');
    const result = executeExport([], [], []);
    expect(result.outputPath).toMatch(/\.pdf$/);
  });

  it('output path is in ~/Downloads', async () => {
    const { executeExport } = await import('../../../src/commands/export.js');
    const { homedir } = await import('node:os');
    const result = executeExport([], [], []);
    expect(result.outputPath).toContain(homedir());
  });

  it('returns turns, toolInvocations, and receipts unchanged', async () => {
    const { executeExport } = await import('../../../src/commands/export.js');
    const turns = [{ role: 'citizen' as const, content: 'hello', timestamp: '2026-04-25T00:00:00Z' }];
    const result = executeExport(turns, [], []);
    expect(result.turns).toHaveLength(1);
    expect(result.turns[0]?.content).toBe('hello');
  });
});

// ---------------------------------------------------------------------------
// Audit-7 P0-1 — Korean PDF font sanitizer tests
// ---------------------------------------------------------------------------

describe('_sanitizeForKoreanFont — Korean PDF Audit-7 P0-1', () => {
  it('preserves ASCII characters unchanged', async () => {
    const { _sanitizeForKoreanFont } = await import('../../../src/components/export/ExportPdfDialog.js');
    const input = 'Hello, KOSMOS! 1234567890';
    expect(_sanitizeForKoreanFont(input)).toBe(input);
  });

  it('preserves Hangul Syllables (U+AC00..U+D7A3)', async () => {
    const { _sanitizeForKoreanFont } = await import('../../../src/components/export/ExportPdfDialog.js');
    const input = '안녕하세요 대화 내보내기 권한 영수증';
    expect(_sanitizeForKoreanFont(input)).toBe(input);
  });

  it('preserves common KOSMOS agency names without mangling', async () => {
    const { _sanitizeForKoreanFont } = await import('../../../src/components/export/ExportPdfDialog.js');
    const tests = [
      '도로교통공단 교통사고 다발지역',
      '기상청 단기예보',
      '건강보험심사평가원',
      '국립중앙의료원 응급의료센터',
      '시민, 어린이집, 보건소',
    ];
    for (const t of tests) {
      expect(_sanitizeForKoreanFont(t)).toBe(t);
    }
  });

  it('replaces box-drawing dashes with ASCII hyphen', async () => {
    const { _sanitizeForKoreanFont } = await import('../../../src/components/export/ExportPdfDialog.js');
    // U+2500 = ─
    expect(_sanitizeForKoreanFont('─'.repeat(3))).toBe('---');
  });

  it('replaces unsupported codepoints with ?', async () => {
    const { _sanitizeForKoreanFont } = await import('../../../src/components/export/ExportPdfDialog.js');
    // U+1F600 (emoji) is outside Hangul/ASCII/CJK-punct ranges
    const input = 'Hello 😀 world';
    const output = _sanitizeForKoreanFont(input);
    expect(output).toContain('Hello');
    expect(output).toContain('world');
    expect(output).toContain('?');
  });

  it('preserves CJK punctuation U+3000-U+303F', async () => {
    const { _sanitizeForKoreanFont } = await import('../../../src/components/export/ExportPdfDialog.js');
    const input = '「자료 출처」'; // U+300C, U+300D
    expect(_sanitizeForKoreanFont(input)).toBe(input);
  });
});

// ---------------------------------------------------------------------------
// Audit-7 P0-1 — End-to-end Korean PDF generation
// ---------------------------------------------------------------------------

describe('Audit-7 P0-1: Korean PDF end-to-end generation', () => {
  it('writes a non-empty PDF with Korean header text without crashing', async () => {
    // Defer the dynamic import so the test isolates pdf-lib + fontkit + bundled font discovery.
    const pdfLib = await import('pdf-lib');
    const fontkitMod = (await import('@pdf-lib/fontkit')) as { default?: unknown };
    const fontkit = (fontkitMod.default ?? fontkitMod) as Parameters<typeof pdfLib.PDFDocument.prototype.registerFontkit>[0];
    const { readFileSync } = await import('node:fs');
    const { fileURLToPath } = await import('node:url');
    const { dirname, join } = await import('node:path');

    // Resolve the bundled font from the source tree (mirrors the runtime resolver).
    const here = dirname(fileURLToPath(import.meta.url));
    // tests/components/export/ → src/assets/fonts/
    const fontPath = join(here, '..', '..', '..', 'src', 'assets', 'fonts', 'NotoSansKR-Hangul-subset.ttf');
    const fontBytes = readFileSync(fontPath);
    expect(fontBytes.byteLength).toBeGreaterThan(50_000);
    expect(fontBytes.byteLength).toBeLessThan(1_048_576); // <1 MB AGENTS.md hard rule

    const pdfDoc = await pdfLib.PDFDocument.create();
    pdfDoc.registerFontkit(fontkit);
    const font = await pdfDoc.embedFont(fontBytes, { subset: true });
    const page = pdfDoc.addPage([595.28, 841.89]);

    page.drawText('대화 내보내기 / Conversation Export', {
      x: 50, y: 800, size: 14, font, color: pdfLib.rgb(0, 0, 0),
    });
    page.drawText('안녕하세요 KOSMOS — Audit-7 P0-1 fix', {
      x: 50, y: 770, size: 11, font, color: pdfLib.rgb(0, 0, 0),
    });

    const bytes = await pdfDoc.save();
    expect(bytes.byteLength).toBeGreaterThan(2000); // real PDF, not zero-byte fail
    // PDF files start with "%PDF-"
    const header = new TextDecoder('latin1').decode(bytes.slice(0, 5));
    expect(header).toBe('%PDF-');
  });
});
