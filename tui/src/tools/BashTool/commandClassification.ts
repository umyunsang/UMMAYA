import type { AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS } from '../../services/analytics/index.js';
import { splitCommand_DEPRECATED, splitCommandWithOperators } from '../../utils/bash/commands.js';

const BASH_SEARCH_COMMANDS = new Set(['find', 'grep', 'rg', 'ag', 'ack', 'locate', 'which', 'whereis']);
const BASH_READ_COMMANDS = new Set(['cat', 'head', 'tail', 'less', 'more', 'wc', 'stat', 'file', 'strings', 'jq', 'awk', 'cut', 'sort', 'uniq', 'tr']);
const BASH_LIST_COMMANDS = new Set(['ls', 'tree', 'du']);
const BASH_SEMANTIC_NEUTRAL_COMMANDS = new Set(['echo', 'printf', 'true', 'false', ':']);
const BASH_SILENT_COMMANDS = new Set(['mv', 'cp', 'rm', 'mkdir', 'rmdir', 'chmod', 'chown', 'chgrp', 'touch', 'ln', 'cd', 'export', 'unset', 'wait']);
const DISALLOWED_AUTO_BACKGROUND_COMMANDS = ['sleep'];
const COMMON_BACKGROUND_COMMANDS = ['npm', 'yarn', 'pnpm', 'node', 'python', 'python3', 'go', 'cargo', 'make', 'docker', 'terraform', 'webpack', 'vite', 'jest', 'pytest', 'curl', 'wget', 'build', 'test', 'serve', 'watch', 'dev'] as const;

type SearchReadClassification = {
  readonly isSearch: boolean;
  readonly isRead: boolean;
  readonly isList: boolean;
};

const NOT_SEARCH_OR_READ: SearchReadClassification = {
  isSearch: false,
  isRead: false,
  isList: false
};

export function isSearchOrReadBashCommand(command: string): SearchReadClassification {
  let partsWithOperators: string[];
  try {
    partsWithOperators = splitCommandWithOperators(command);
  } catch (error) {
    if (error instanceof Error) {
      return NOT_SEARCH_OR_READ;
    }
    throw error;
  }
  if (partsWithOperators.length === 0) {
    return NOT_SEARCH_OR_READ;
  }
  let hasSearch = false;
  let hasRead = false;
  let hasList = false;
  let hasNonNeutralCommand = false;
  let skipNextAsRedirectTarget = false;
  for (const part of partsWithOperators) {
    if (skipNextAsRedirectTarget) {
      skipNextAsRedirectTarget = false;
      continue;
    }
    if (part === '>' || part === '>>' || part === '>&') {
      skipNextAsRedirectTarget = true;
      continue;
    }
    if (part === '||' || part === '&&' || part === '|' || part === ';') {
      continue;
    }
    const baseCommand = part.trim().split(/\s+/)[0];
    if (!baseCommand || BASH_SEMANTIC_NEUTRAL_COMMANDS.has(baseCommand)) {
      continue;
    }
    hasNonNeutralCommand = true;
    const isPartSearch = BASH_SEARCH_COMMANDS.has(baseCommand);
    const isPartRead = BASH_READ_COMMANDS.has(baseCommand);
    const isPartList = BASH_LIST_COMMANDS.has(baseCommand);
    if (!isPartSearch && !isPartRead && !isPartList) {
      return NOT_SEARCH_OR_READ;
    }
    if (isPartSearch) hasSearch = true;
    if (isPartRead) hasRead = true;
    if (isPartList) hasList = true;
  }
  if (!hasNonNeutralCommand) {
    return NOT_SEARCH_OR_READ;
  }
  return {
    isSearch: hasSearch,
    isRead: hasRead,
    isList: hasList
  };
}

export function isSilentBashCommand(command: string): boolean {
  let partsWithOperators: string[];
  try {
    partsWithOperators = splitCommandWithOperators(command);
  } catch (error) {
    if (error instanceof Error) {
      return false;
    }
    throw error;
  }
  if (partsWithOperators.length === 0) {
    return false;
  }
  let hasNonFallbackCommand = false;
  let lastOperator: string | null = null;
  let skipNextAsRedirectTarget = false;
  for (const part of partsWithOperators) {
    if (skipNextAsRedirectTarget) {
      skipNextAsRedirectTarget = false;
      continue;
    }
    if (part === '>' || part === '>>' || part === '>&') {
      skipNextAsRedirectTarget = true;
      continue;
    }
    if (part === '||' || part === '&&' || part === '|' || part === ';') {
      lastOperator = part;
      continue;
    }
    const baseCommand = part.trim().split(/\s+/)[0];
    if (!baseCommand || (lastOperator === '||' && BASH_SEMANTIC_NEUTRAL_COMMANDS.has(baseCommand))) {
      continue;
    }
    hasNonFallbackCommand = true;
    if (!BASH_SILENT_COMMANDS.has(baseCommand)) {
      return false;
    }
  }
  return hasNonFallbackCommand;
}

export function isAutobackgroundingAllowed(command: string): boolean {
  const parts = splitCommand_DEPRECATED(command);
  if (parts.length === 0) return true;
  const baseCommand = parts[0]?.trim();
  if (!baseCommand) return true;
  return !DISALLOWED_AUTO_BACKGROUND_COMMANDS.includes(baseCommand);
}

export function detectBlockedSleepPattern(command: string): string | null {
  const parts = splitCommand_DEPRECATED(command);
  if (parts.length === 0) return null;
  const first = parts[0]?.trim() ?? '';
  const match = /^sleep\s+(\d+)\s*$/.exec(first);
  const secondsText = match?.[1];
  if (!secondsText) return null;
  const seconds = parseInt(secondsText, 10);
  if (seconds < 2) return null;
  const rest = parts.slice(1).join(' ').trim();
  return rest ? `sleep ${seconds} followed by: ${rest}` : `standalone sleep ${seconds}`;
}

export function getCommandTypeForLogging(command: string): AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS {
  const parts = splitCommand_DEPRECATED(command);
  if (parts.length === 0) return 'other' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS;
  for (const part of parts) {
    const baseCommand = part.split(' ')[0] || '';
    if (COMMON_BACKGROUND_COMMANDS.includes(baseCommand as (typeof COMMON_BACKGROUND_COMMANDS)[number])) {
      return baseCommand as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS;
    }
  }
  return 'other' as AnalyticsMetadata_I_VERIFIED_THIS_IS_NOT_CODE_OR_FILEPATHS;
}
