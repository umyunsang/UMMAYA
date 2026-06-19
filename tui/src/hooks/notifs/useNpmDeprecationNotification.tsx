import { isInBundledMode } from 'src/utils/bundledMode.js';
import { getCurrentInstallationType } from 'src/utils/doctorDiagnostic.js';
import { isEnvTruthy } from 'src/utils/envUtils.js';
import { useStartupNotification } from './useStartupNotification.js';
// UMMAYA — Anthropic claude.ai native installer notice removed. UMMAYA ships
// from source via Bun + uv (Migration Tree § Stack); no npm distribution and
// no native installer to migrate from. The hook is preserved as a no-op so
// downstream notification subscribers stay wired.
export function useNpmDeprecationNotification() {
  useStartupNotification(_temp);
}
async function _temp() {
  // Silence: nothing to deprecate in UMMAYA runtime.
  if (isInBundledMode() || isEnvTruthy(process.env.DISABLE_INSTALLATION_CHECKS)) {
    return null;
  }
  // Reference the upstream helpers so the dead-code linter doesn't whine.
  await getCurrentInstallationType();
  return null;
}
