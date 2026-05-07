// SPDX-License-Identifier: Apache-2.0
// Spec 1635 P4 UI L2 — bilingual string bundle (FR-004 ko-primary + en-fallback).
//
// Isolated from the legacy Spec 287 i18n bundle (tui/src/i18n/keys.ts) to
// avoid expanding the existing I18nBundle interface. UI L2 components import
// from this module directly.
import type { UfoMascotPoseT } from '../schemas/ui-l2/ufo.js';
import type { ErrorEnvelopeTypeT } from '../schemas/ui-l2/error.js';
import type { PermissionLayerT } from '../schemas/ui-l2/permission.js';
import type { OnboardingStepNameT } from '../schemas/ui-l2/onboarding.js';
import type { AccessibilityToggleKey } from '../schemas/ui-l2/a11y.js';

export type UiL2Bundle = {
  // UI-A onboarding
  onboardingHeader: (step: OnboardingStepNameT, total: number, current: number) => string;
  onboardingNext: string;
  onboardingBack: string;
  onboardingSkip: string;
  preflightTitle: string;
  preflightOk: (item: string) => string;
  preflightFail: (item: string) => string;
  themeStepTitle: string;
  pipaConsentTitle: string;
  pipaConsentBody: string;
  pipaTrusteeNotice: string;
  ministryScopeTitle: string;
  terminalSetupTitle: string;
  a11yToggleLabel: (key: AccessibilityToggleKey) => string;

  // UI-B REPL
  streamingHint: string;
  ctrlOExpand: string;
  ctrlOCollapse: string;
  pdfRenderingInline: string;
  pdfFallbackOpen: string;
  pdfFallbackText: (path: string, sizeKb: number, sha: string) => string;
  errorTitle: (type: ErrorEnvelopeTypeT) => string;
  errorRetryHint: string;

  // UI-C permission
  permissionLayer: (layer: PermissionLayerT) => string;
  permissionAllowOnce: string;
  permissionAllowSession: string;
  permissionDeny: string;
  permissionLayer3Reinforcement: string;
  receiptIssued: (id: string) => string;
  consentRevoked: (id: string) => string;
  consentAlreadyRevoked: string;
  bypassReinforcement: string;

  // UI-E auxiliary
  helpGroupSession: string;
  helpGroupPermission: string;
  helpGroupTool: string;
  helpGroupStorage: string;
  langChanged: (locale: 'ko' | 'en') => string;
  configOverlayTitle: string;
  envSecretEditorTitle: string;
  pluginBrowserTitle: string;
  pluginToggleHint: string;
  exportPdfWriting: string;
  exportPdfDone: (path: string) => string;
  historySearchTitle: string;

  // UFO mascot aria labels (UFO is rendered visually; aria for screen readers)
  ufoMascot: (pose: UfoMascotPoseT) => string;
};

const KO: UiL2Bundle = {
  onboardingHeader: (step, total, current) => `온보딩 ${current}/${total} · ${step}`,
  onboardingNext: '다음 (Enter)',
  onboardingBack: '이전 (Esc)',
  onboardingSkip: '건너뛰기',
  preflightTitle: '환경 점검',
  preflightOk: (item) => `✓ ${item}`,
  preflightFail: (item) => `✗ ${item}`,
  themeStepTitle: '테마 미리보기',
  pipaConsentTitle: 'PIPA 동의',
  pipaConsentBody: '이 시스템은 시민님의 개인정보를 처리하기 위해 동의가 필요합니다.',
  pipaTrusteeNotice:
    'PIPA §26에 따라 KOSMOS는 개인정보 수탁자로서 책임을 집니다. 동의 후에도 언제든 /consent revoke 로 철회할 수 있습니다.',
  ministryScopeTitle: '부처 옵트인 범위',
  terminalSetupTitle: '터미널 설정 + 접근성',
  a11yToggleLabel: (key) => {
    switch (key) {
      case 'screen_reader': return '스크린리더 친화 모드';
      case 'large_font': return '큰 글씨';
      case 'high_contrast': return '고대비';
      case 'reduced_motion': return '애니메이션 줄이기';
    }
  },

  streamingHint: '응답 수신 중…',
  ctrlOExpand: 'Ctrl-O로 펼치기',
  ctrlOCollapse: 'Ctrl-O로 접기',
  pdfRenderingInline: 'PDF 인라인 렌더 중…',
  pdfFallbackOpen: '📄 PDF 열기 시도 중…',
  pdfFallbackText: (path, sizeKb, sha) => `📄 ${path} · ${sizeKb} KB · sha256:${sha.slice(0, 12)}…`,
  errorTitle: (type) => {
    switch (type) {
      case 'llm': return 'LLM 응답 오류';
      case 'tool': return '도구 호출 오류';
      case 'network': return '네트워크 오류';
    }
  },
  errorRetryHint: '다시 시도하시겠습니까? (R)',

  permissionLayer: (layer) => `Layer ${layer}`,
  permissionAllowOnce: '이번 한 번만 허용',
  permissionAllowSession: '세션 동안 자동 허용',
  permissionDeny: '거부',
  permissionLayer3Reinforcement: '⚠️ 이 작업은 시민님 계정으로 외부 시스템에 영향을 줍니다.',
  receiptIssued: (id) => `발급됨 ${id}`,
  consentRevoked: (id) => `철회 완료 ${id}`,
  consentAlreadyRevoked: '이미 철회됨',
  bypassReinforcement:
    '이 모드는 모든 권한 모달을 우회합니다. 정말로 진행하시겠습니까?',

  helpGroupSession: '세션',
  helpGroupPermission: '권한',
  helpGroupTool: '도구',
  helpGroupStorage: '저장',
  langChanged: (locale) => `언어가 ${locale === 'ko' ? '한국어' : '영어'}로 변경되었습니다.`,
  configOverlayTitle: '설정',
  envSecretEditorTitle: '.env 비밀값 편집 (격리 모드)',
  pluginBrowserTitle: '플러그인 브라우저',
  pluginToggleHint: 'Space 활성 토글 · i 상세 · r 제거 · a 스토어',
  exportPdfWriting: 'PDF 생성 중…',
  exportPdfDone: (path) => `PDF 저장됨: ${path}`,
  historySearchTitle: '과거 세션 검색',

  ufoMascot: (pose) => {
    switch (pose) {
      case 'idle': return 'KOSMOS UFO 마스코트 (대기)';
      case 'thinking': return 'KOSMOS UFO 마스코트 (생각 중)';
      case 'success': return 'KOSMOS UFO 마스코트 (성공)';
      case 'error': return 'KOSMOS UFO 마스코트 (오류)';
    }
  },
};

const EN: UiL2Bundle = {
  onboardingHeader: (step, total, current) => `Onboarding ${current}/${total} · ${step}`,
  onboardingNext: 'Next (Enter)',
  onboardingBack: 'Back (Esc)',
  onboardingSkip: 'Skip',
  preflightTitle: 'Preflight check',
  preflightOk: (item) => `✓ ${item}`,
  preflightFail: (item) => `✗ ${item}`,
  themeStepTitle: 'Theme preview',
  pipaConsentTitle: 'PIPA consent',
  pipaConsentBody: 'This system requires your consent to process personal data.',
  pipaTrusteeNotice:
    'Under PIPA §26, KOSMOS acts as a data trustee. You can revoke consent any time via /consent revoke.',
  ministryScopeTitle: 'Ministry opt-in scope',
  terminalSetupTitle: 'Terminal setup + accessibility',
  a11yToggleLabel: (key) => {
    switch (key) {
      case 'screen_reader': return 'Screen-reader friendly mode';
      case 'large_font': return 'Large font';
      case 'high_contrast': return 'High contrast';
      case 'reduced_motion': return 'Reduced motion';
    }
  },

  streamingHint: 'Receiving response…',
  ctrlOExpand: 'Ctrl-O to expand',
  ctrlOCollapse: 'Ctrl-O to collapse',
  pdfRenderingInline: 'Rendering PDF inline…',
  pdfFallbackOpen: '📄 Opening PDF in external viewer…',
  pdfFallbackText: (path, sizeKb, sha) => `📄 ${path} · ${sizeKb} KB · sha256:${sha.slice(0, 12)}…`,
  errorTitle: (type) => {
    switch (type) {
      case 'llm': return 'LLM response error';
      case 'tool': return 'Tool invocation error';
      case 'network': return 'Network error';
    }
  },
  errorRetryHint: 'Retry? (R)',

  permissionLayer: (layer) => `Layer ${layer}`,
  permissionAllowOnce: 'Allow once',
  permissionAllowSession: 'Allow for the session',
  permissionDeny: 'Deny',
  permissionLayer3Reinforcement:
    '⚠️ This operation will affect external systems on your behalf.',
  receiptIssued: (id) => `Issued ${id}`,
  consentRevoked: (id) => `Revoked ${id}`,
  consentAlreadyRevoked: 'Already revoked',
  bypassReinforcement:
    'This mode bypasses ALL permission modals. Are you sure you want to continue?',

  helpGroupSession: 'Session',
  helpGroupPermission: 'Permission',
  helpGroupTool: 'Tool',
  helpGroupStorage: 'Storage',
  langChanged: (locale) => `Language changed to ${locale === 'ko' ? 'Korean' : 'English'}.`,
  configOverlayTitle: 'Settings',
  envSecretEditorTitle: '.env secret editor (isolated)',
  pluginBrowserTitle: 'Plugin browser',
  pluginToggleHint: 'Space toggle · i detail · r remove · a marketplace',
  exportPdfWriting: 'Writing PDF…',
  exportPdfDone: (path) => `PDF saved: ${path}`,
  historySearchTitle: 'History search',

  ufoMascot: (pose) => {
    switch (pose) {
      case 'idle': return 'KOSMOS UFO mascot (idle)';
      case 'thinking': return 'KOSMOS UFO mascot (thinking)';
      case 'success': return 'KOSMOS UFO mascot (success)';
      case 'error': return 'KOSMOS UFO mascot (error)';
    }
  },
};

/**
 * Resolve the current locale from KOSMOS_TUI_LOCALE on every call so that
 * /lang ko|en (which mutates process.env at runtime) takes effect on the
 * next render without a process restart. Per Codex review on PR #1847.
 */
function currentLocale(): 'ko' | 'en' {
  return process.env['KOSMOS_TUI_LOCALE'] === 'en' ? 'en' : 'ko';
}

/** Backwards-compat default export — equals KO unless KOSMOS_TUI_LOCALE=en at module load. */
export const uiL2I18n: UiL2Bundle = currentLocale() === 'en' ? EN : KO;

/**
 * Hook returning the active i18n bundle. Reads KOSMOS_TUI_LOCALE on every
 * call so /lang ko|en applies on the next render frame. Components that
 * already capture this value into closures (event handlers, useCallback
 * deps) will need to remount or re-execute the closure to pick up the
 * new locale — that is by design (FR-004 + Codex P2 fix).
 */
export function useUiL2I18n(): UiL2Bundle {
  return currentLocale() === 'en' ? EN : KO;
}

export function getUiL2I18n(locale: 'ko' | 'en'): UiL2Bundle {
  return locale === 'en' ? EN : KO;
}
