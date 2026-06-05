// SPDX-License-Identifier: Apache-2.0
// UMMAYA document result-render boundary tests.
//
// Approach D (deep-research-migration-document-render.md): the user surface is
// the structural field-level diff, not a page raster. The retired raster gate
// is now an identity pass-through and never fabricates a render failure — a
// missing raster is no longer a failure because the raster was only ever needed
// by the discarded browser viewer. Page rasters remain Evidence-only.

import { describe, expect, it } from 'bun:test'
import {
  applyDocumentVisualRenderGateToOutput,
  extractDocumentToolResultPayload,
  isDocumentVisualRenderFailedOutput,
} from '../../../src/tools/_shared/documentToolResultRender'

describe('document result-render boundary (approach D)', () => {
  it('passes a successful render through unchanged even with no readable raster', () => {
    const original = {
      ok: true,
      result: documentRenderPayload('/tmp/ummaya-missing-render-raster.png'),
    }

    const gated = applyDocumentVisualRenderGateToOutput(original)

    // Identity: the structural diff renders regardless of raster availability.
    expect(gated).toBe(original)
    expect(isDocumentVisualRenderFailedOutput(gated)).toBe(false)
  })

  it('never fabricates a visual-render failure when the diff has no render artifacts', () => {
    const original = {
      ok: true,
      result: documentRenderPayloadWithoutRaster(),
    }

    const gated = applyDocumentVisualRenderGateToOutput(original)

    expect(gated).toBe(original)
    expect(isDocumentVisualRenderFailedOutput(gated)).toBe(false)
  })

  it('extracts a wrapped document payload from a tool output envelope', () => {
    const payload = documentRenderPayloadWithoutRaster()
    const extracted = extractDocumentToolResultPayload({ ok: true, result: payload })
    expect(extracted).not.toBeNull()
    expect(extracted?.tool_id).toBe('document_render')
  })

  it('extracts a direct document payload', () => {
    const payload = documentRenderPayloadWithoutRaster()
    const extracted = extractDocumentToolResultPayload(payload)
    expect(extracted).not.toBeNull()
    expect(extracted?.tool_id).toBe('document_render')
  })

  it('extracts the single model-facing document primitive payload', () => {
    const payload = {
      ...documentRenderPayloadWithoutRaster(),
      tool_id: 'document',
      text_summary: 'Document edit completed with automatic compact diff review evidence.',
    }

    const extracted = extractDocumentToolResultPayload({ ok: true, result: payload })

    expect(extracted).not.toBeNull()
    expect(extracted?.tool_id).toBe('document')
  })

  it('returns null for non-document outputs', () => {
    expect(extractDocumentToolResultPayload({ tool_id: 'find_hospital', result: {} })).toBeNull()
    expect(extractDocumentToolResultPayload(null)).toBeNull()
    expect(extractDocumentToolResultPayload('nope')).toBeNull()
  })
})

function documentRenderPayloadWithoutRaster(): Record<string, unknown> {
  return {
    tool_id: 'document_render',
    correlation_id: 'corr-render',
    status: 'ok',
    artifact_refs: ['derivative-doc'],
    text_summary: 'Rendered document diff evidence.',
    diff: {
      diff_id: 'diff-corr-render',
      source_artifact_id: 'working-doc',
      derivative_artifact_id: 'derivative-doc',
      changes: [
        {
          change_id: 'change-001',
          operation_id: 'fill-week',
          change_type: 'field',
          target_path: '/hwpx/text[2]',
          before_value: '12 주차 ',
          after_value: '13 주차 ',
        },
      ],
    },
  }
}

function documentRenderPayload(rasterPath: string): Record<string, unknown> {
  return {
    ...documentRenderPayloadWithoutRaster(),
    render_artifacts: [
      {
        render_artifact_id: 'render-corr-render-001',
        page_number: 1,
        render_path: rasterPath,
        render_mime_type: 'image/png',
        raster_artifact_path: rasterPath,
        raster_mime_type: 'image/png',
      },
    ],
  }
}
