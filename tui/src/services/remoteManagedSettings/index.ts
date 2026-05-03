// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Epic #2637 cascade · stub-noop replacement for CC remoteManagedSettings.
// SWAP/anti-anthropic-1p(2637): Anthropic enterprise managed settings (claude.ai 1P)
// surface is dead in KOSMOS. CC's print.ts cascade requires this import to resolve.
// Pattern follows tui/src/services/analytics/index.ts (Spec 1633 P1 stub-noop).

export async function waitForRemoteManagedSettingsToLoad(): Promise<void> {
  // Intentional no-op (Epic #2637 stub). Anthropic remote managed settings (claude.ai 1P)
  // is swap-1 dependent — permanently disabled in KOSMOS.
}
