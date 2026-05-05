// SPDX-License-Identifier: Apache-2.0
//
// Spec 1979 — KOSMOS citizen plugin install/uninstall/list flow component.
// Audit-6 P1 fixes:
//   - payload_start/delta/end triplet consumed for /plugin list (P1 fix)
//   - exit_code → citizen-friendly Korean error messages (P1 fix)
//   - was_idempotent_noop → "이미 제거됨" instead of "제거 완료" (P1 fix)
//   - onComplete carries receipt + PIPA hash for permanent system message (P1 fix)
//
// Source pattern (per memory feedback_cc_source_migration_pattern):
//   .references/claude-code-sourcemap/restored-src/src/commands/plugin/plugin.tsx
//   .references/claude-code-sourcemap/restored-src/src/components/permissions/PermissionPrompt.tsx
//
// CC 2.1.88's permission UX uses:
//   - <Select options={...} onChange={...} onCancel={...} /> for option selection
//   - Arrow keys + Enter for navigation (NOT direct Y/N/A keystrokes)
//   - Esc for cancellation
//
// KOSMOS-internal Y/N/A direct-keystroke pattern (earlier dev iteration) is
// replaced here by CC's Select-based pattern for consistency with the rest
// of the TUI (PluginBrowser, PermissionGauntletModal in Spec 1978, etc).

import { Box, Text, useInput } from 'ink';
import * as React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { Select, type OptionWithDescription } from '../CustomSelect/index.js';
import { getKosmosBridgeSessionId, getOrCreateKosmosBridge } from '../../ipc/bridgeSingleton.js';
import { useTheme } from '../../theme/provider.js';

// ---------------------------------------------------------------------------
// Exit-code → citizen-friendly Korean message map
// Mirrors installer.py exit-code table § contracts/plugin-install.cli.md
// ---------------------------------------------------------------------------

const _EXIT_CODE_KO: Record<number, string> = {
  0: '성공',
  1: '카탈로그 조회 실패 — 네트워크 또는 URL을 확인하세요',
  2: '번들 무결성 검증 실패 — SHA-256 해시가 카탈로그와 다릅니다',
  3: 'SLSA 서명 검증 실패 — 플러그인 출처를 확인할 수 없습니다',
  4: '매니페스트 검증 실패 — 플러그인 패키지가 손상되었습니다',
  5: '동의 거부 — 설치가 취소되었습니다',
  6: 'I/O 오류 — 파일 시스템 권한 또는 디스크 공간을 확인하세요',
  7: 'slsa-verifier 바이너리 없음 — 자동 설치 시도 중',
};

function _exitCodeKo(exitCode: number | undefined | null, errorKind?: string | null): string {
  if (errorKind === 'bundle_sha_mismatch') return _EXIT_CODE_KO[2] ?? `오류 코드 ${exitCode ?? '?'}`;
  if (errorKind === 'slsa_skip_in_production') return 'KOSMOS_PLUGIN_SLSA_SKIP은 production 환경에서 거부됩니다';
  if (errorKind === 'slsa_skip_layer_3_forbidden') return 'Layer 3 플러그인은 SLSA 검증이 필수입니다';
  if (errorKind === 'binary_not_found' || errorKind === 'slsa_bootstrap_failed') return _EXIT_CODE_KO[7] ?? `오류 코드 ${exitCode ?? '?'}`;
  if (errorKind === 'consent_rejected') return _EXIT_CODE_KO[5] ?? '동의 거부';
  if (exitCode != null && exitCode in _EXIT_CODE_KO) return _EXIT_CODE_KO[exitCode]!;
  return `알 수 없는 오류 (코드 ${exitCode ?? '?'})`;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type PluginListEntry = {
  plugin_id: string;
  name: string;
  version: string;
  tier: string;
  permission_layer: number;
  processes_pii: boolean;
  is_active: boolean;
  description_ko: string;
};

export type PluginInstallFlowProps = {
  /** Sub-command parsed by /plugin command (install / uninstall / list). */
  sub: 'install' | 'uninstall' | 'list';
  /** Catalog name for install/uninstall (omitted for list). */
  name?: string;
  /** Optional --version pin. */
  requestedVersion?: string;
  /** --dry-run flag. */
  dryRun?: boolean;
  /** Called with the final acknowledgement when the flow completes. */
  onComplete: (summary?: string, options?: { display?: 'system' | 'skip' | 'user' }) => void;
};

type FlowState =
  | { kind: 'idle' }
  | { kind: 'sent' }
  | { kind: 'progress'; phase: number; messageKo: string }
  | { kind: 'awaiting_consent'; requestId: string; descriptionKo: string; descriptionEn: string }
  | { kind: 'completed'; summary: string; plugins?: PluginListEntry[] }
  | { kind: 'failed'; summary: string };

// ---------------------------------------------------------------------------
// Frame builder
// ---------------------------------------------------------------------------

function _newCorrelationId(): string {
  return crypto.randomUUID();
}

function _now(): string {
  return new Date().toISOString();
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const _ROUND_TRIP_TIMEOUT_MS = 90_000;

export function PluginInstallFlow({
  sub,
  name,
  requestedVersion,
  dryRun,
  onComplete,
}: PluginInstallFlowProps): React.ReactElement {
  const theme = useTheme();
  const [state, setState] = useState<FlowState>({ kind: 'idle' });
  const [correlationId] = useState<string>(_newCorrelationId());
  // Accumulate payload_delta chunks for the list sub-command.
  const payloadBufRef = useRef<string>('');

  // Send a permission_response frame (allow_once / allow_session / deny).
  const sendPermissionResponse = useCallback(
    (requestId: string, decision: 'allow_once' | 'allow_session' | 'deny') => {
      const bridge = getOrCreateKosmosBridge();
      const sessionId = getKosmosBridgeSessionId();
      bridge.send({
        kind: 'permission_response',
        version: '1.0',
        session_id: sessionId,
        correlation_id: requestId,
        ts: _now(),
        role: 'tui',
        request_id: requestId,
        decision,
      } as never);
      setState({
        kind: 'progress',
        phase: 5,
        messageKo: decision === 'deny' ? '📝 동의 거부 처리 중…' : '📝 동의 처리 중…',
      });
    },
    [],
  );

  // CC PermissionPrompt pattern: 3 options with arrow+Enter selection.
  const consentOptions: OptionWithDescription<'allow_once' | 'allow_session' | 'deny'>[] = useMemo(
    () => [
      { label: '한 번만 허용 (Allow once)', value: 'allow_once' },
      { label: '세션 내 자동 허용 (Allow for session)', value: 'allow_session' },
      { label: '거부 (Deny)', value: 'deny' },
    ],
    [],
  );

  // Keystroke passthrough for focus routing diagnostics.
  useInput((_input, _key) => {
    // no-op: present to keep stdin raw mode active so child Select hooks fire.
  });

  // Main round-trip effect: emit request + iterate frames until terminal.
  useEffect(() => {
    let cancelled = false;
    const bridge = getOrCreateKosmosBridge();
    const sessionId = getKosmosBridgeSessionId();
    payloadBufRef.current = '';

    // Build + send the request frame.
    const requestPayload: Record<string, unknown> = {
      kind: 'plugin_op',
      version: '1.0',
      session_id: sessionId,
      correlation_id: correlationId,
      ts: _now(),
      role: 'tui',
      op: 'request',
      request_op: sub,
    };
    if (sub === 'install') {
      requestPayload.name = name ?? '';
      requestPayload.requested_version = requestedVersion ?? null;
      requestPayload.dry_run = Boolean(dryRun);
    } else if (sub === 'uninstall') {
      requestPayload.name = name ?? '';
    }
    bridge.send(requestPayload as never);
    setState({ kind: 'sent' });

    // Iterate frames until terminal complete (or timeout / cancellation).
    const deadline = Date.now() + _ROUND_TRIP_TIMEOUT_MS;
    (async () => {
      try {
        for await (const frame of bridge.frames()) {
          if (cancelled) return;
          if (Date.now() > deadline) {
            setState({ kind: 'failed', summary: '✗ 라운드트립 타임아웃 (90s)' });
            onComplete('✗ 라운드트립 타임아웃 (90s)', { display: 'system' });
            return;
          }
          const f = frame as {
            kind?: string;
            correlation_id?: string;
            op?: string;
            result?: string;
            exit_code?: number | null;
            receipt_id?: string | null;
            error_kind?: string | null;
            error_message?: string | null;
            was_idempotent_noop?: boolean | null;
            progress_phase?: number;
            progress_message_ko?: string;
            progress_message_en?: string;
            request_id?: string;
            description_ko?: string;
            description_en?: string;
            // payload triplet fields
            payload?: string;
            delta_seq?: number;
            status?: string;
          };

          // permission_request — IPCConsentBridge correlates by request_id, NOT
          // by our top-level correlation_id. Match on request_id presence.
          if (f.kind === 'permission_request' && f.request_id) {
            setState({
              kind: 'awaiting_consent',
              requestId: f.request_id,
              descriptionKo: f.description_ko ?? '플러그인 설치 동의 요청',
              descriptionEn: f.description_en ?? 'Plugin install consent request',
            });
            continue;
          }

          if (f.correlation_id !== correlationId) continue;

          if (f.kind === 'plugin_op' && f.op === 'progress') {
            setState({
              kind: 'progress',
              phase: f.progress_phase ?? 0,
              messageKo: f.progress_message_ko ?? '',
            });
            continue;
          }

          // Spec 032 payload triplet — accumulate delta chunks for /plugin list.
          if (f.kind === 'payload_start') {
            payloadBufRef.current = '';
            continue;
          }
          if (f.kind === 'payload_delta' && typeof f.payload === 'string') {
            payloadBufRef.current += f.payload;
            continue;
          }
          if (f.kind === 'payload_end') {
            // Payload fully assembled; parse will happen on the following
            // plugin_op/complete frame where we render the list.
            continue;
          }

          if (f.kind === 'plugin_op' && f.op === 'complete') {
            const exitCode = f.exit_code ?? 1;
            const errorKind = f.error_kind ?? null;
            const isSuccess = f.result === 'success';
            const isIdempotentNoop = Boolean(f.was_idempotent_noop);

            let summary: string;
            let plugins: PluginListEntry[] | undefined;

            if (isSuccess) {
              if (sub === 'install' && name) {
                summary = `✓ ${name} 플러그인 설치 완료`;
                if (f.receipt_id) {
                  summary += ` · 영수증 ${f.receipt_id}`;
                }
              } else if (sub === 'uninstall' && name) {
                summary = isIdempotentNoop
                  ? `ℹ ${name} 플러그인이 이미 제거된 상태입니다`
                  : `✓ ${name} 플러그인 제거 완료`;
              } else {
                // list — parse payload buffer
                try {
                  const parsed = JSON.parse(payloadBufRef.current) as { entries?: unknown[] };
                  plugins = (parsed.entries ?? []) as PluginListEntry[];
                  summary =
                    plugins.length === 0
                      ? '📋 설치된 플러그인이 없습니다 · No plugins installed'
                      : `📋 설치된 플러그인 ${plugins.length}개`;
                } catch {
                  plugins = [];
                  summary = '📋 플러그인 목록 조회 완료 (목록 파싱 오류)';
                }
              }
            } else {
              const reasonKo = _exitCodeKo(exitCode, errorKind);
              if (sub === 'install' && name) {
                summary = `✗ ${name} 플러그인 설치 실패 — ${reasonKo}`;
              } else if (sub === 'uninstall' && name) {
                summary = `✗ ${name} 플러그인 제거 실패 — ${reasonKo}`;
              } else {
                summary = `✗ 목록 조회 실패 — ${reasonKo}`;
              }
            }

            setState({ kind: isSuccess ? 'completed' : 'failed', summary, plugins });
            // Build a rich message including receipt ID and PIPA hash if available.
            let richSummary = summary;
            if (isSuccess && sub === 'install' && f.receipt_id) {
              richSummary += `\n영수증 ID: ${f.receipt_id}`;
              // Append PIPA hash asynchronously if available.
              try {
                const { CANONICAL_PIPA_ACK_SHA256 } = await import('../../ipc/pipa.generated.js');
                richSummary += `\nPIPA §26 SHA-256: ${CANONICAL_PIPA_ACK_SHA256}`;
              } catch {
                // pipa.generated.js may not be present in test builds — continue.
              }
            }
            if (!isSuccess && f.error_message) {
              richSummary += `\n상세: ${f.error_message}`;
            }
            if (isSuccess && sub === 'list' && plugins && plugins.length > 0) {
              richSummary +=
                '\n' +
                plugins
                  .map(
                    (p) =>
                      `  • ${p.plugin_id} v${p.version} [${p.tier}][L${p.permission_layer}]${p.is_active ? '' : ' (비활성)'}`,
                  )
                  .join('\n');
            }
            onComplete(richSummary, { display: 'system' });
            return;
          }
        }
      } catch (err) {
        if (cancelled) return;
        const summary = `✗ IPC 오류: ${err instanceof Error ? err.message : String(err)}`;
        setState({ kind: 'failed', summary });
        onComplete(summary, { display: 'system' });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [sub, name, requestedVersion, dryRun, correlationId, onComplete]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <Box flexDirection="column" paddingX={1} paddingY={1}>
      <Box marginBottom={1}>
        <Text bold color={theme.kosmosCore}>
          {'✻ '}
        </Text>
        <Text bold>
          {sub === 'install'
            ? `KOSMOS 플러그인 설치: ${name}`
            : sub === 'uninstall'
              ? `KOSMOS 플러그인 제거: ${name}`
              : 'KOSMOS 플러그인 목록 조회'}
        </Text>
      </Box>

      {state.kind === 'sent' ? (
        <Text color={theme.subtle}>{'⏳  요청 전송 — 백엔드 응답 대기 중…'}</Text>
      ) : null}

      {state.kind === 'progress' ? (
        <Text>{`⏳  Phase ${state.phase}/7 — ${state.messageKo}`}</Text>
      ) : null}

      {state.kind === 'awaiting_consent' ? (
        <Box flexDirection="column">
          <Box marginBottom={1}>
            <Text>{state.descriptionKo}</Text>
          </Box>
          <Box marginBottom={1}>
            <Text dimColor>{state.descriptionEn}</Text>
          </Box>
          <Box marginBottom={1}>
            <Text bold>{'설치를 진행하시겠습니까? (Do you want to proceed?)'}</Text>
          </Box>
          <Select
            options={consentOptions}
            onChange={(value) => sendPermissionResponse(state.requestId, value)}
            onCancel={() => sendPermissionResponse(state.requestId, 'deny')}
          />
          <Box marginTop={1}>
            <Text dimColor>{'Esc 취소 (Esc to cancel)'}</Text>
          </Box>
        </Box>
      ) : null}

      {state.kind === 'completed' ? (
        <Box flexDirection="column">
          <Text color={theme.kosmosCore}>{state.summary}</Text>
          {state.plugins && state.plugins.length > 0 ? (
            <Box flexDirection="column" marginTop={1}>
              {state.plugins.map((p) => (
                <Text key={p.plugin_id} dimColor={!p.is_active}>
                  {`  • ${p.plugin_id} v${p.version} [${p.tier}][L${p.permission_layer}]${p.is_active ? '' : ' (비활성)'} — ${p.description_ko}`}
                </Text>
              ))}
            </Box>
          ) : null}
        </Box>
      ) : null}

      {state.kind === 'failed' ? <Text color="red">{state.summary}</Text> : null}
    </Box>
  );
}
