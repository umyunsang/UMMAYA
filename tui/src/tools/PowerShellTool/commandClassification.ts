import type { AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS } from '../../services/analytics/index.js';
import { resolveToCanonical } from './readOnlyValidation.js';

const PS_SEARCH_COMMANDS = new Set(['select-string', 'get-childitem', 'findstr', 'where.exe']);
const PS_READ_COMMANDS = new Set(['get-content', 'get-item', 'test-path', 'resolve-path', 'get-process', 'get-service', 'get-childitem', 'get-location', 'get-filehash', 'get-acl', 'format-hex']);
const PS_SEMANTIC_NEUTRAL_COMMANDS = new Set(['write-output', 'write-host']);
const DISALLOWED_AUTO_BACKGROUND_COMMANDS = ['start-sleep', 'sleep'];
const COMMON_BACKGROUND_COMMANDS = ['npm', 'yarn', 'pnpm', 'node', 'python', 'python3', 'go', 'cargo', 'make', 'docker', 'terraform', 'webpack', 'vite', 'jest', 'pytest', 'curl', 'Invoke-WebRequest', 'build', 'test', 'serve', 'watch', 'dev'] as const;

type SearchReadClassification = {
  readonly isSearch: boolean;
  readonly isRead: boolean;
};

const NOT_SEARCH_OR_READ: SearchReadClassification = {
  isSearch: false,
  isRead: false
};

export function isSearchOrReadPowerShellCommand(command: string): SearchReadClassification {
  const trimmed = command.trim();
  if (!trimmed) {
    return NOT_SEARCH_OR_READ;
  }
  const parts = trimmed.split(/\s*[;|]\s*/).filter(Boolean);
  if (parts.length === 0) {
    return NOT_SEARCH_OR_READ;
  }
  let hasSearch = false;
  let hasRead = false;
  let hasNonNeutralCommand = false;
  for (const part of parts) {
    const baseCommand = part.trim().split(/\s+/)[0];
    if (!baseCommand) {
      continue;
    }
    const canonical = resolveToCanonical(baseCommand);
    if (PS_SEMANTIC_NEUTRAL_COMMANDS.has(canonical)) {
      continue;
    }
    hasNonNeutralCommand = true;
    const isPartSearch = PS_SEARCH_COMMANDS.has(canonical);
    const isPartRead = PS_READ_COMMANDS.has(canonical);
    if (!isPartSearch && !isPartRead) {
      return NOT_SEARCH_OR_READ;
    }
    if (isPartSearch) hasSearch = true;
    if (isPartRead) hasRead = true;
  }
  if (!hasNonNeutralCommand) {
    return NOT_SEARCH_OR_READ;
  }
  return {
    isSearch: hasSearch,
    isRead: hasRead
  };
}

export function isAutobackgroundingAllowed(command: string): boolean {
  const firstWord = command.trim().split(/\s+/)[0];
  if (!firstWord) return true;
  const canonical = resolveToCanonical(firstWord);
  return !DISALLOWED_AUTO_BACKGROUND_COMMANDS.includes(canonical);
}

export function detectBlockedSleepPattern(command: string): string | null {
  const first = command.trim().split(/[;|&\r\n]/)[0]?.trim() ?? '';
  const match = /^(?:start-sleep|sleep)(?:\s+-s(?:econds)?)?\s+(\d+)\s*$/i.exec(first);
  const secondsText = match?.[1];
  if (!secondsText) return null;
  const seconds = parseInt(secondsText, 10);
  if (seconds < 2) return null;
  const rest = command.trim().slice(first.length).replace(/^[\s;|&]+/, '');
  return rest ? `Start-Sleep ${seconds} followed by: ${rest}` : `standalone Start-Sleep ${seconds}`;
}

export function getCommandTypeForLogging(command: string): AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS {
  const trimmed = command.trim();
  const firstWord = trimmed.split(/\s+/)[0] || '';
  for (const cmd of COMMON_BACKGROUND_COMMANDS) {
    if (firstWord.toLowerCase() === cmd.toLowerCase()) {
      return cmd as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS;
    }
  }
  return 'other' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS;
}
