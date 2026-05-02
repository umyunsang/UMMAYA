// SPDX-License-Identifier: Apache-2.0
//
// Source pattern: .references/claude-code-sourcemap/restored-src/src/commands/plugin/{index.tsx,plugin.tsx}
//   CC 2.1.88's plugin command:
//     1. index.tsx — Command def with type=local-jsx, name=plugin
//     2. plugin.tsx — call() returns <PluginSettings onComplete={onDone} args={args} />
//
//   The pattern: call() returns a React component; the component handles all
//   interaction internally (consent, progress, completion); component
//   unmounts via onDone after terminal state. CC's marketplace surface
//   is replaced by KOSMOS's PluginInstallFlow (see ../components/plugins/).
//
// Spec 1979 — citizen plugin lifecycle slash command.
//
// Subcommands (per migration tree § B8 + contracts/plugin-install.cli.md):
//   /plugin install <name> [--version v] [--dry-run]
//   /plugin list
//   /plugin uninstall <name>
//   /plugin pipa-text                 — print canonical PIPA §26 hash

import * as React from 'react';

import type { Command, LocalJSXCommandModule } from '../types/command.js';
import type { CommandHandlerArgs, CommandResult } from './types.js';
import { CANONICAL_PIPA_ACK_SHA256 } from '../ipc/pipa.generated.js';
import { PluginInstallFlow } from '../components/plugins/PluginInstallFlow.js';

const _USAGE_KO =
  '사용법: /plugin <install|list|uninstall|pipa-text> [...]';

function _parseSubcommand(raw: string): { sub: string; rest: string } {
  const trimmed = raw.trim();
  if (trimmed.length === 0) return { sub: '', rest: '' };
  const space = trimmed.indexOf(' ');
  if (space === -1) return { sub: trimmed, rest: '' };
  return { sub: trimmed.slice(0, space), rest: trimmed.slice(space + 1).trim() };
}

function _parseInstallArgs(rest: string): {
  name: string | undefined;
  version: string | undefined;
  dryRun: boolean;
} {
  const tokens = rest.split(/\s+/).filter((t) => t.length > 0);
  let name: string | undefined;
  let version: string | undefined;
  let dryRun = false;
  for (let i = 0; i < tokens.length; i += 1) {
    const tok = tokens[i];
    if (!tok) continue;
    if (tok === '--version') {
      version = tokens[i + 1];
      i += 1;
    } else if (tok === '--dry-run') {
      dryRun = true;
    } else if (!name && !tok.startsWith('--')) {
      name = tok;
    }
  }
  return { name, version, dryRun };
}

// ---------------------------------------------------------------------------
// LocalJSXCommand `call` — mirrors CC's pattern of returning a React component
// ---------------------------------------------------------------------------

const call: LocalJSXCommandModule['call'] = async (onDone, _context, args) => {
  const { sub, rest } = _parseSubcommand(args ?? '');

  // Non-interactive subcommands fire onDone immediately + return null.
  if (sub === 'pipa-text') {
    const text = [
      'PIPA §26 trustee acknowledgment canonical SHA-256:',
      `  ${CANONICAL_PIPA_ACK_SHA256}`,
      'Source: docs/plugins/security-review.md (마커 사이 텍스트)',
      'manifest.yaml 의 acknowledgment_sha256 필드에 위 값을 그대로 기록하세요.',
    ].join('\n');
    setTimeout(() => onDone(text, { display: 'system' }), 0);
    return null;
  }

  if (sub === '') {
    setTimeout(() => onDone(_USAGE_KO, { display: 'system' }), 0);
    return null;
  }

  if (sub === 'install') {
    const { name, version, dryRun } = _parseInstallArgs(rest);
    if (!name) {
      setTimeout(
        () => onDone('플러그인 이름이 필요합니다: /plugin install <name>', { display: 'system' }),
        0,
      );
      return null;
    }
    return (
      <PluginInstallFlow
        sub="install"
        name={name}
        requestedVersion={version}
        dryRun={dryRun}
        onComplete={onDone}
      />
    );
  }

  if (sub === 'uninstall') {
    const targetName = rest.trim().split(/\s+/)[0];
    if (!targetName) {
      setTimeout(
        () => onDone('플러그인 이름이 필요합니다: /plugin uninstall <name>', { display: 'system' }),
        0,
      );
      return null;
    }
    return <PluginInstallFlow sub="uninstall" name={targetName} onComplete={onDone} />;
  }

  if (sub === 'list') {
    return <PluginInstallFlow sub="list" onComplete={onDone} />;
  }

  // Unknown subcommand
  setTimeout(
    () => onDone(`알 수 없는 subcommand: ${sub}\n${_USAGE_KO}`, { display: 'system' }),
    0,
  );
  return null;
};

// ---------------------------------------------------------------------------
// Procedural CommandDefinition.handle — Spec 1636 P5 / T053-T057 contract
// ---------------------------------------------------------------------------
//
// `tests/commands/plugin.test.ts` and `tests/commands/registry.test.ts`
// expect every default-registry entry to expose `handle(args) → CommandResult`.
// The slash command's *interactive* flow is the React `call()` above (Ink
// component + progress UI); the procedural `handle` is the deterministic
// IPC-frame emitter that satisfies the FR-036 registry-shape invariant.
//
// Both surfaces co-exist: the dispatcher prefers `call` when running through
// the Ink stack (because `type: 'local-jsx'` is set), and falls back to
// `handle` for the headless / test paths.

function _handle(rawArgs: CommandHandlerArgs): CommandResult {
  const { args: raw, sendPluginOp } = rawArgs;
  const { sub, rest } = _parseSubcommand(raw);

  if (sub === '') {
    return { acknowledgement: _USAGE_KO };
  }

  if (sub === 'pipa-text') {
    const text = [
      'PIPA §26 trustee acknowledgment canonical SHA-256:',
      `  ${CANONICAL_PIPA_ACK_SHA256}`,
      'Source: docs/plugins/security-review.md (마커 사이 텍스트)',
      'manifest.yaml 의 acknowledgment_sha256 필드에 위 값을 그대로 기록하세요.',
    ].join('\n');
    return { acknowledgement: text };
  }

  if (sub === 'install') {
    const { name, version, dryRun } = _parseInstallArgs(rest);
    if (!name) {
      return { acknowledgement: '플러그인 이름이 필요합니다: /plugin install <name>' };
    }
    if (!sendPluginOp) {
      return {
        acknowledgement:
          'IPC 가 연결되지 않았습니다 — backend 가 시작될 때까지 기다려 주세요.',
      };
    }
    sendPluginOp({
      kind: 'plugin_op',
      version: '1.0',
      role: 'tui',
      session_id: '',
      correlation_id: crypto.randomUUID(),
      ts: new Date().toISOString(),
      op: 'request',
      request_op: 'install',
      name,
      ...(version ? { requested_version: version } : {}),
      ...(dryRun ? { dry_run: true } : {}),
    });
    return {
      acknowledgement: `/plugin install ${name}${version ? ` --version ${version}` : ''}${dryRun ? ' --dry-run' : ''} 요청을 backend 에 보냈습니다.`,
    };
  }

  if (sub === 'list') {
    if (!sendPluginOp) {
      return {
        acknowledgement:
          'IPC 가 연결되지 않았습니다 — backend 가 시작될 때까지 기다려 주세요.',
      };
    }
    sendPluginOp({
      kind: 'plugin_op',
      version: '1.0',
      role: 'tui',
      session_id: '',
      correlation_id: crypto.randomUUID(),
      ts: new Date().toISOString(),
      op: 'request',
      request_op: 'list',
    });
    return { acknowledgement: '/plugin list 요청을 backend 에 보냈습니다.' };
  }

  if (sub === 'uninstall') {
    const targetName = rest.trim().split(/\s+/)[0];
    if (!targetName) {
      return { acknowledgement: '플러그인 이름이 필요합니다: /plugin uninstall <name>' };
    }
    if (!sendPluginOp) {
      return {
        acknowledgement:
          'IPC 가 연결되지 않았습니다 — backend 가 시작될 때까지 기다려 주세요.',
      };
    }
    sendPluginOp({
      kind: 'plugin_op',
      version: '1.0',
      role: 'tui',
      session_id: '',
      correlation_id: crypto.randomUUID(),
      ts: new Date().toISOString(),
      op: 'request',
      request_op: 'uninstall',
      name: targetName,
    });
    return {
      acknowledgement: `/plugin uninstall ${targetName} 요청을 backend 에 보냈습니다.`,
    };
  }

  return {
    acknowledgement: `알 수 없는 subcommand: ${sub}\n${_USAGE_KO}`,
  };
}

// Hybrid Command — interactive `call` (Ink) + procedural `handle` (FR-036).
type _PluginCommand = Command & {
  handle: (args: CommandHandlerArgs) => CommandResult;
};

const pluginCommand: _PluginCommand = {
  type: 'local-jsx',
  name: 'plugin',
  description: 'KOSMOS 플러그인 설치 / 목록 / 제거 / PIPA 해시 (Install / list / uninstall KOSMOS plugins)',
  argumentHint: '<install|list|uninstall|pipa-text> [name]',
  immediate: true,
  load: async () => ({ call }),
  handle: _handle,
};

export default pluginCommand;
