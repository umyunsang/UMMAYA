// SPDX-License-Identifier: Apache-2.0
// Spec 1635 P4 UI L2 — Slash command catalog SSOT (FR-014/029, T010).
//
// Single source of truth consumed by:
// - autocomplete dropdown (FR-014, tui/src/components/PromptInput/PromptInputFooterSuggestions.tsx)
// - /help 4-group output (FR-029, tui/src/components/help/HelpV2Grouped.tsx)
//
// Schema: tui/src/schemas/ui-l2/slash-command.ts
//         specs/1635-ui-l2-citizen-port/contracts/slash-commands.schema.json
import {
  type SlashCommandCatalogEntryT,
  type SlashCommandGroupT,
} from '../schemas/ui-l2/slash-command.js';

export const UI_L2_SLASH_COMMANDS: readonly SlashCommandCatalogEntryT[] = [
  {
    name: '/onboarding',
    group: 'session',
    description_ko: '온보딩 시퀀스를 처음부터 다시 진행합니다',
    description_en: 'Restart onboarding from step 1',
    arg_signature: '[step-name]',
    hidden: false,
  },
  {
    name: '/lang',
    group: 'session',
    description_ko: '언어를 한국어/영어로 전환합니다',
    description_en: 'Switch language between Korean and English',
    arg_signature: 'ko|en',
    hidden: false,
  },
  {
    name: '/login',
    group: 'session',
    description_ko: 'FriendliAI API 키로 현재 세션에 로그인합니다',
    description_en: 'Log in for this session with a FriendliAI API key',
    arg_signature: null,
    hidden: false,
  },
  {
    name: '/logout',
    group: 'session',
    description_ko: 'FriendliAI API 키를 현재 세션에서 제거합니다',
    description_en: 'Log out and clear the session FriendliAI API key',
    arg_signature: null,
    hidden: false,
  },
  {
    name: '/consent list',
    group: 'permission',
    description_ko: '본 세션의 권한 영수증 목록을 표시합니다',
    description_en: 'List permission receipts for the current session',
    arg_signature: null,
    hidden: false,
  },
  {
    name: '/consent revoke',
    group: 'permission',
    description_ko: '발급된 권한 영수증을 철회합니다',
    description_en: 'Revoke a previously granted permission receipt',
    arg_signature: 'rcpt-<id>',
    hidden: false,
  },
  {
    name: '/agents',
    group: 'tool',
    description_ko: 'Manage agent configurations',
    description_en: 'Manage agent configurations',
    arg_signature: null,
    hidden: false,
  },
  {
    name: '/help',
    group: 'session',
    description_ko: '명령 목록을 4개 그룹으로 묶어 표시합니다',
    description_en: 'Show commands grouped into four sections',
    arg_signature: null,
    hidden: false,
  },
  // Session lifecycle commands — kosmos-migration-tree.md § L1-A · A5
  // promises four distinct citizen-facing modes: --continue / --resume /
  // --fork / new. Surfaced in the autocomplete dropdown (FR-014) so the
  // citizen can discover them without reading docs. Decision:
  // docs/decisions/fork-command-decision.md (2026-05-04).
  {
    name: '/resume',
    group: 'session',
    description_ko: '이전 대화를 검색하여 이어서 진행합니다',
    description_en: 'Resume a previous conversation',
    arg_signature: '[id|search]',
    hidden: false,
  },
  {
    name: '/continue',
    group: 'session',
    description_ko: '가장 최근 대화를 즉시 이어서 진행합니다',
    description_en: 'Continue the most recent conversation',
    arg_signature: null,
    hidden: false,
  },
  {
    name: '/fork',
    group: 'session',
    description_ko: '현재 대화를 새 세션으로 분기합니다 (메시지 보존)',
    description_en: 'Fork the current conversation into a new session',
    arg_signature: '[name]',
    hidden: false,
  },
  {
    name: '/branch',
    group: 'session',
    description_ko: '현재 대화를 분기합니다 (/fork 의 별칭)',
    description_en: 'Alias for /fork — branch the current conversation',
    arg_signature: '[name]',
    hidden: false,
  },
  {
    name: '/config',
    group: 'storage',
    description_ko: '설정 오버레이를 엽니다 (.env 비밀값은 격리 편집)',
    description_en: 'Open configuration overlay (.env secrets isolated)',
    arg_signature: null,
    hidden: false,
  },
  {
    name: '/plugins',
    group: 'tool',
    description_ko: '플러그인 브라우저를 엽니다',
    description_en: 'Open the plugin browser',
    arg_signature: null,
    hidden: false,
  },
  {
    name: '/export',
    group: 'storage',
    description_ko: '대화·도구·영수증을 PDF로 내보냅니다',
    description_en: 'Export conversation + tools + receipts to PDF',
    arg_signature: null,
    hidden: false,
  },
  {
    name: '/history',
    group: 'storage',
    description_ko: '과거 세션을 날짜·세션·Layer 필터로 검색합니다',
    description_en: 'Search past sessions by date / session / layer filter',
    arg_signature: '[--date FROM..TO] [--session <id>] [--layer <n>]',
    hidden: false,
  },
  {
    name: '/migrate-sessions',
    group: 'storage',
    description_ko: 'CC 워크스페이스 JSONL 세션을 KOSMOS memdir로 마이그레이션합니다',
    description_en: 'Migrate CC-workspace JSONL sessions to the KOSMOS memdir sessions directory',
    arg_signature: '[--dry-run] [--filter-cwd <regex>] [--prune]',
    hidden: false,
  },
];

export function findCatalogEntry(name: string): SlashCommandCatalogEntryT | undefined {
  return UI_L2_SLASH_COMMANDS.find((e) => e.name === name);
}

export function entriesInGroup(group: SlashCommandGroupT): SlashCommandCatalogEntryT[] {
  return UI_L2_SLASH_COMMANDS.filter((e) => e.group === group && !e.hidden);
}

/**
 * Prefix-match helper for the autocomplete dropdown (FR-014). Matches on
 * the command name only; the dropdown component owns highlight rendering.
 */
export function matchPrefix(prefix: string): SlashCommandCatalogEntryT[] {
  const p = prefix.trim().toLowerCase();
  if (p === '' || p === '/') return [...UI_L2_SLASH_COMMANDS].filter((e) => !e.hidden);
  return UI_L2_SLASH_COMMANDS.filter((e) => !e.hidden && e.name.toLowerCase().startsWith(p));
}
