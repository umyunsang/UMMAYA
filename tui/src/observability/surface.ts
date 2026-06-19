// SPDX-License-Identifier: Apache-2.0
// Spec 1635 P4 UI L2 — ummaya.ui.surface OTEL attribute emitter (FR-037).
//
// Wraps the existing Spec 021 GenAI emit path with no new collector route
// (FR-038 + SC-008: zero new external network egress). The emitted span
// attribute lets the existing observability stack (Spec 028 OTLP collector
// → local Langfuse) count surface usage.
import { trace } from '@opentelemetry/api';

export type UiSurface =
  | 'repl'
  | 'permission_gauntlet'
  | 'agents'
  | 'help'
  | 'config'
  | 'plugins'
  | 'export'
  | 'history';

export const UI_SURFACES: readonly UiSurface[] = [
  'repl',
  'permission_gauntlet',
  'agents',
  'help',
  'config',
  'plugins',
  'export',
  'history',
] as const;

const SURFACE_ATTRIBUTE_KEY = 'ummaya.ui.surface';
const TRACER_NAME = 'ummaya/ui-l2';

/**
 * Emit `ummaya.ui.surface=<surface>` on the active span when present. When no span
 * is active (e.g., outside a tracing context), open and immediately close a
 * one-shot span so the surface activation is recorded.
 *
 * The function is fail-soft: OTEL provider failures become a console
 * warning rather than a crash so a logging fault never blocks the UI.
 */
export function emitSurfaceActivation(surface: UiSurface, attrs?: Record<string, string | number | boolean>): void {
  try {
    const tracer = trace.getTracer(TRACER_NAME);
    const active = trace.getActiveSpan();
    if (active) {
      active.setAttribute(SURFACE_ATTRIBUTE_KEY, surface);
      if (attrs) {
        for (const [k, v] of Object.entries(attrs)) {
          active.setAttribute(k, v);
        }
      }
      return;
    }
    const span = tracer.startSpan(`ui.${surface}.activate`);
    span.setAttribute(SURFACE_ATTRIBUTE_KEY, surface);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        span.setAttribute(k, v);
      }
    }
    span.end();
  } catch (err) {
    // Fail-soft: never block the UI on a telemetry fault.
    console.warn(`[ui-l2] OTEL emit failed for surface=${surface}:`, err);
  }
}
