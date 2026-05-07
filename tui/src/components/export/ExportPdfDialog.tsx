// SPDX-License-Identifier: Apache-2.0
// Source: .references/claude-code-sourcemap/restored-src/src/components/ExportDialog.tsx (CC 2.1.88, research-use)
// Spec 1635 P4 UI L2 — T067 ExportPdfDialog (FR-032, US5).
//
// Assembles a PDF export containing:
//   - Conversation transcript (citizen messages + LLM responses)
//   - Tool invocations and results
//   - Consent receipts (rcpt-<id> entries)
//
// EXCLUDES (SC-012 / FR-032 hard constraint):
//   - OTEL span IDs (traceId=, spanId=)
//   - Plugin-internal state markers (pluginInternal:)
//
// Uses pdf-lib (MIT) for PDF assembly.  Progress indicator follows
// CC ExportDialog pattern (Box + Text stream + done message).

import React, { useCallback, useEffect, useState } from 'react';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname as pathDirnameSync, join as pathJoin } from 'node:path';
import { Box, Text, useInput } from 'ink';
import { PDFDocument, rgb, type PDFFont } from 'pdf-lib';
import fontkit from '@pdf-lib/fontkit';
import { useTheme } from '../../theme/provider.js';
import { useUiL2I18n } from '../../i18n/uiL2.js';
import type { PermissionReceiptT } from '../../schemas/ui-l2/permission.js';

// ---------------------------------------------------------------------------
// Korean PDF support — Audit-7 P0-1 fix
// ---------------------------------------------------------------------------
//
// pdf-lib's StandardFonts.Helvetica uses WinAnsi 8-bit encoding and CANNOT
// represent Korean characters (any codepoint above 0xFF — e.g. 대 0xb300 —
// triggers an "encoding error" inside `font.encodeText()` and fails the PDF
// write silently with a corrupt zero-byte file).
//
// Fix: register @pdf-lib/fontkit and embed the bundled NotoSansKR-Hangul-subset
// TTF (~952 KB, OFL-1.1, common Hangul + ASCII + KR punctuation, see
// `tui/src/assets/fonts/SOURCE.md`). pdf-lib's `subset: true` further trims
// the embedded font to only the glyphs actually drawn in this PDF.
//
// The font path is resolved relative to this module via import.meta.url so it
// works in both `bun run` and bundled-binary deployment modes.

function _resolveKoreanFontPath(): string {
  // Walk up from this module's directory to the tui/src root, then into
  // assets/fonts/. The compiled JS lives at tui/src/components/export/, so
  // 3 levels up reaches tui/src/.
  const here = pathDirnameSync(fileURLToPath(import.meta.url));
  return pathJoin(here, '..', '..', 'assets', 'fonts', 'NotoSansKR-Hangul-subset.ttf');
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ConversationTurn = {
  role: 'citizen' | 'assistant';
  content: string;
  timestamp: string;
};

export type ToolInvocationRecord = {
  tool_name: string;
  input_summary: string;
  output_summary: string;
  timestamp: string;
};

export type ExportPdfDialogProps = {
  /** Conversation turns to include */
  turns: ConversationTurn[];
  /** Tool invocations to include */
  toolInvocations: ToolInvocationRecord[];
  /** Consent receipts to include */
  receipts: PermissionReceiptT[];
  /** Full path where the PDF will be written */
  outputPath: string;
  /** Called when writing is complete */
  onDone: (result: { success: boolean; message: string }) => void;
  /** Called when the citizen cancels before writing starts */
  onCancel: () => void;
};

// ---------------------------------------------------------------------------
// SC-012 leakage filter
// ---------------------------------------------------------------------------

// These patterns MUST NOT appear in the final PDF text (SC-012 / FR-032).
const FORBIDDEN_PATTERNS: RegExp[] = [
  /traceId=[A-Za-z0-9]+/g,
  /spanId=[A-Za-z0-9]+/g,
  /pluginInternal:[^\s]*/g,
];

/**
 * Sanitize a text segment, removing any OTEL or plugin-internal markers.
 * SC-012: "/export PDF contains zero OTEL span identifiers and zero
 * plugin-internal state markers in automated content scans."
 */
export function sanitizeForExport(text: string): string {
  let out = text;
  for (const pattern of FORBIDDEN_PATTERNS) {
    out = out.replace(pattern, '[redacted]');
  }
  return out;
}

/**
 * Replace any character outside the bundled NotoSansKR-Hangul-subset coverage
 * with '?'. This is the last line of defense against pdf-lib's fontkit raising
 * a "missing glyph" error mid-write. Coverage:
 *   - ASCII U+0020..U+007E
 *   - Latin-1 supplement U+00A0..U+00FF
 *   - CJK punctuation U+3000..U+303F (subset)
 *   - Hangul Compatibility Jamo U+3130..U+318F (subset)
 *   - Hangul Syllables U+AC00..U+D7A3 (common-Korean subset, ~6,000 chars)
 *   - General punctuation U+2010..U+2027, U+2030..U+203F (subset)
 */
export function _sanitizeForKoreanFont(text: string): string {
  let out = '';
  for (const ch of text) {
    const cp = ch.codePointAt(0) ?? 0;
    const isAscii = cp >= 0x0020 && cp <= 0x007e;
    const isLatin1 = cp >= 0x00a0 && cp <= 0x00ff;
    const isHangul = cp >= 0xac00 && cp <= 0xd7a3;
    const isCjkPunct = cp >= 0x3000 && cp <= 0x303f;
    const isGenPunct = cp >= 0x2010 && cp <= 0x205f;
    const isJamo = cp >= 0x3130 && cp <= 0x318f;
    if (isAscii || isLatin1 || isHangul || isCjkPunct || isGenPunct || isJamo) {
      out += ch;
    } else if (cp === 0x2026 || cp === 0x2027) {
      out += ch;
    } else if (cp === 0x2500 || cp === 0x2501 || (cp >= 0x2014 && cp <= 0x2015)) {
      // Box-drawing dashes — pdf-lib falls back gracefully if missing
      out += '-';
    } else if (cp === 0x2192 || cp === 0x2190 || cp === 0x21d2) {
      // Common arrows (often appear in tool descriptions)
      out += '->';
    } else {
      // Outside coverage — replace with '?' to avoid encode-time crash.
      out += '?';
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// PDF assembly
// ---------------------------------------------------------------------------

const LINE_HEIGHT = 14;
const FONT_SIZE = 11;
const MARGIN = 50;
const PAGE_WIDTH = 595.28;  // A4
const PAGE_HEIGHT = 841.89; // A4
const TEXT_WIDTH = PAGE_WIDTH - MARGIN * 2;

async function assemblePdf(
  turns: ConversationTurn[],
  toolInvocations: ToolInvocationRecord[],
  receipts: PermissionReceiptT[],
): Promise<Uint8Array> {
  const pdfDoc = await PDFDocument.create();

  // Audit-7 P0-1: register fontkit BEFORE any embedFont(custom_bytes) call.
  // The bundled NotoSansKR-Hangul-subset.ttf covers Hangul + ASCII so a single
  // font handles both '대화' and 'KOSMOS' / 'Tool Invocations'. pdf-lib's
  // `subset: true` strips unused glyphs from the embedded font — final PDF
  // typically <100 KB even with thousands of Korean syllables in scope.
  pdfDoc.registerFontkit(fontkit);
  const koreanFontBytes = readFileSync(_resolveKoreanFontPath());
  const font: PDFFont = await pdfDoc.embedFont(koreanFontBytes, { subset: true });
  // No separate bold variant in the subset — re-use the same font for bold
  // text but rely on color/section markers to distinguish hierarchy.
  const boldFont: PDFFont = font;

  let page = pdfDoc.addPage([PAGE_WIDTH, PAGE_HEIGHT]);
  let y = PAGE_HEIGHT - MARGIN;

  const addLine = (text: string, bold = false, color = rgb(0, 0, 0)): void => {
    if (y < MARGIN + LINE_HEIGHT) {
      page = pdfDoc.addPage([PAGE_WIDTH, PAGE_HEIGHT]);
      y = PAGE_HEIGHT - MARGIN;
    }
    const sanitized = sanitizeForExport(text);
    const f = bold ? boldFont : font;
    // Truncate long lines at TEXT_WIDTH (slice at character level — pdf-lib
    // measures correctly for Hangul codepoints once the Korean font is loaded).
    let displayText = sanitized;
    // Strip any character outside the embedded subset to prevent fontkit's
    // "WinAnsi cannot encode" / "missing glyph" errors. The Korean font covers
    // Hangul Syllables (U+AC00..U+D7A3) + ASCII + common punctuation; anything
    // else gets replaced with '?'.
    displayText = _sanitizeForKoreanFont(displayText);
    while (displayText.length > 0) {
      const textWidth = f.widthOfTextAtSize(displayText, FONT_SIZE);
      if (textWidth <= TEXT_WIDTH) break;
      displayText = displayText.slice(0, -1);
    }
    page.drawText(displayText, {
      x: MARGIN,
      y,
      size: FONT_SIZE,
      font: f,
      color,
    });
    y -= LINE_HEIGHT;
  };

  const addSection = (title: string): void => {
    addLine('');
    addLine(title, true, rgb(0.4, 0.1, 0.7));
    addLine('─'.repeat(70));
  };

  // Header
  addLine('KOSMOS — 대화 내보내기 / Conversation Export', true, rgb(0.4, 0.1, 0.7));
  addLine(`생성 시각 / Generated: ${new Date().toISOString()}`);
  addLine('');

  // Section 1: Conversation transcript
  addSection('대화 내역 / Conversation Transcript');
  if (turns.length === 0) {
    addLine('  (내역 없음 / no turns)');
  } else {
    for (const turn of turns) {
      const prefix = turn.role === 'citizen' ? '시민' : 'KOSMOS';
      addLine(`[${turn.timestamp}] ${prefix}:`);
      // Word-wrap content (simple: split at 80 chars)
      const content = sanitizeForExport(turn.content);
      for (let i = 0; i < content.length; i += 80) {
        addLine(`  ${content.slice(i, i + 80)}`);
      }
      addLine('');
    }
  }

  // Section 2: Tool invocations
  addSection('도구 호출 / Tool Invocations');
  if (toolInvocations.length === 0) {
    addLine('  (호출 없음 / no invocations)');
  } else {
    for (const inv of toolInvocations) {
      addLine(`[${inv.timestamp}] ${inv.tool_name}`, true);
      addLine(`  입력 / Input: ${sanitizeForExport(inv.input_summary)}`);
      addLine(`  결과 / Output: ${sanitizeForExport(inv.output_summary)}`);
      addLine('');
    }
  }

  // Section 3: Consent receipts
  addSection('권한 영수증 / Consent Receipts');
  if (receipts.length === 0) {
    addLine('  (영수증 없음 / no receipts)');
  } else {
    for (const receipt of receipts) {
      addLine(`${receipt.receipt_id}`, true);
      addLine(`  Layer: ${receipt.layer}  Tool: ${receipt.tool_name}`);
      addLine(`  Decision: ${receipt.decision}  At: ${receipt.decided_at}`);
      if (receipt.revoked_at) {
        addLine(`  Revoked: ${receipt.revoked_at}`);
      }
      addLine('');
    }
  }

  return pdfDoc.save();
}

// ---------------------------------------------------------------------------
// ExportPdfDialog (T067)
// ---------------------------------------------------------------------------

type ExportState = 'idle' | 'writing' | 'done' | 'error';

/**
 * PDF export dialog component.  Immediately triggers assembly when mounted
 * (no user interaction required to start writing — mirrors CC ExportDialog).
 *
 * SC-012 guarantee: sanitizeForExport() strips traceId=, spanId=, and
 * pluginInternal: markers from ALL text content before writing to PDF.
 */
export function ExportPdfDialog({
  turns,
  toolInvocations,
  receipts,
  outputPath,
  onDone,
  onCancel,
}: ExportPdfDialogProps): React.ReactElement {
  const theme = useTheme();
  const i18n = useUiL2I18n();
  const [state, setState] = useState<ExportState>('idle');
  const [errorMessage, setErrorMessage] = useState<string>('');

  // Defense-in-depth Esc dismiss — mirrors HelpV2Grouped.
  // The dialog assembles + writes immediately on mount, so Esc only fires
  // onCancel during the brief idle/writing window or on the terminal error
  // frame. Once `done` fires, onDone has already been invoked and the parent
  // tears the overlay down — Esc here becomes a no-op (no `onCancel` call
  // after success). AGENTS.md "Infrastructure insights" #3 + #4.
  useInput((_input, key) => {
    if (!key.escape) return;
    if (state === 'done') return;
    onCancel();
  });

  const runExport = useCallback(async () => {
    setState('writing');
    try {
      const bytes = await assemblePdf(turns, toolInvocations, receipts);
      // Write using Node.js fs (no new deps — stdlib)
      const { writeFileSync, mkdirSync, dirname: pathDirname } = await import('node:fs');
      const { dirname } = await import('node:path');
      mkdirSync(dirname(outputPath), { recursive: true });
      writeFileSync(outputPath, bytes);
      setState('done');
      onDone({ success: true, message: i18n.exportPdfDone(outputPath) });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMessage(msg);
      setState('error');
      onDone({ success: false, message: `Export failed: ${msg}` });
    }
  }, [turns, toolInvocations, receipts, outputPath, onDone, i18n]);

  useEffect(() => {
    void runExport();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Box flexDirection="column" paddingX={1} paddingY={1}>
      {state === 'idle' && (
        <Text color={theme.subtle}>{i18n.exportPdfWriting}</Text>
      )}
      {state === 'writing' && (
        <Box>
          <Text color={theme.kosmosCore}>{'⏳ '}</Text>
          <Text color={theme.text}>{i18n.exportPdfWriting}</Text>
        </Box>
      )}
      {state === 'done' && (
        <Box>
          <Text color={theme.success}>{'✓ '}</Text>
          <Text color={theme.text}>{i18n.exportPdfDone(outputPath)}</Text>
        </Box>
      )}
      {state === 'error' && (
        <Box flexDirection="column">
          <Box>
            <Text color={theme.error}>{'✗ Export failed: '}</Text>
            <Text color={theme.text}>{errorMessage}</Text>
          </Box>
        </Box>
      )}
    </Box>
  );
}
