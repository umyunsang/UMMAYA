// SWAP: build-pipeline cosmetic (sourceMappingURL stripped + import block reformatted)
// CC reference: .references/claude-code-sourcemap/restored-src/src/replLauncher.tsx
// Divergence LOC: ~10 (sourceMappingURL strip + brace formatting)
// Spec citation: Epic #2639 (audit § 5.7 + § 5.3 — W8 sourceMappingURL strip)
// Justification: Build-pipeline cosmetic divergence; no semantic change.
import React from 'react';
import type { StatsStore } from './context/stats.js';
import type { Root } from './ink.js';
import type { Props as REPLProps } from './screens/REPL.js';
import type { AppState } from './state/AppStateStore.js';
import type { FpsMetrics } from './utils/fpsTracker.js';
type AppWrapperProps = {
  getFpsMetrics: () => FpsMetrics | undefined;
  stats?: StatsStore;
  initialState: AppState;
};
export async function launchRepl(root: Root, appProps: AppWrapperProps, replProps: REPLProps, renderAndRun: (root: Root, element: React.ReactNode) => Promise<void>): Promise<void> {
  const { App } = await import('./components/App.js');
  const { REPL } = await import('./screens/REPL.js');
  await renderAndRun(root, <App {...appProps}>
      <REPL {...replProps} />
    </App>);
}
