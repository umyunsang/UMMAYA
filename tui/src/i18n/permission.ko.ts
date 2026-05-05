// SPDX-License-Identifier: Apache-2.0
// Spec 2294 — KOSMOS Primitive Permission UI — Korean strings.
//
// Citations:
//   PIPA §22-2: 개인정보처리자는 개인정보 처리에 관한 사항을 공개하여야 한다
//   PIPA §26:   수탁자는 위탁받은 업무의 목적 외로 개인정보를 처리하여서는 아니 된다
//
// Each modal shows:
//   title   — what is being requested (one line)
//   body    — context + PIPA citation (one paragraph)
//   selector — Y=한번만 / A=세션자동 / N=거부
//   toast   — post-decision status line

export interface PermissionI18nKo {
  // Per-primitive modal titles
  verifyModalTitle: string
  submitModalTitle: (isIrreversible: boolean) => string
  subscribeModalTitle: string

  // Per-primitive modal body (tool_name injected by caller)
  verifyModalBody: (toolName: string) => string
  submitModalBody: (toolName: string, isIrreversible: boolean) => string
  subscribeModalBody: (toolName: string) => string

  // Layer badge labels (reuse LAYER_VISUAL.ariaLabel in EN; here Korean)
  layer1Label: string
  layer2Label: string
  layer3Label: string

  // Receipt ID label shown in modal footer
  receiptIdLabel: (receiptId: string) => string

  // Y/A/N selector labels
  selectorAllowOnce: string
  selectorAllowSession: string
  selectorDeny: string

  // Post-decision toast messages
  toastAllowedOnce: (toolName: string) => string
  toastAllowedSession: (toolName: string) => string
  toastDenied: (toolName: string) => string

  // PIPA citation line (shown at modal bottom)
  pipaNotice: string
}

const permissionKo: PermissionI18nKo = {
  // Modal titles
  verifyModalTitle: '신원 확인 권한 요청',
  submitModalTitle: (isIrreversible) =>
    isIrreversible ? '취소 불가 제출 — 권한 요청' : '제출 권한 요청',
  subscribeModalTitle: '구독 권한 요청',

  // Modal bodies
  verifyModalBody: (toolName) =>
    `"${toolName}" 도구가 신원 확인을 수행하려 합니다. ` +
    '공공기관 신원 검증에 관한 귀하의 개인정보가 처리됩니다. ' +
    '(개인정보보호법 제22조의2 — 고지 의무)',

  submitModalBody: (toolName, isIrreversible) =>
    isIrreversible
      ? `"${toolName}" 도구가 취소 불가능한 정부 서비스 요청을 제출하려 합니다. ` +
        '이 작업은 실행 후 되돌릴 수 없습니다. ' +
        '수탁자는 위탁받은 업무 목적 외로 개인정보를 처리하지 않습니다. ' +
        '(개인정보보호법 제26조 — 수탁자 의무)'
      : `"${toolName}" 도구가 정부 서비스 요청을 제출하려 합니다. ` +
        '귀하의 요청 데이터가 해당 기관에 전달됩니다. ' +
        '(개인정보보호법 제22조의2 — 고지 의무)',

  subscribeModalBody: (toolName) =>
    `"${toolName}" 도구가 실시간 알림 구독을 시작하려 합니다. ` +
    '구독이 활성화되는 동안 지속적으로 데이터를 수신합니다. ' +
    '(개인정보보호법 제22조의2 — 고지 의무)',

  // Layer labels
  layer1Label: '낮은 위험 (레이어 1)',
  layer2Label: '중간 위험 (레이어 2)',
  layer3Label: '높은 위험 (레이어 3)',

  // Receipt footer
  receiptIdLabel: (receiptId) => `영수증 ID: ${receiptId}`,

  // Selector
  selectorAllowOnce: 'Y  한 번만 허용',
  selectorAllowSession: 'A  세션 동안 자동 허용',
  selectorDeny: 'N  거부',

  // Toast
  toastAllowedOnce: (toolName) => `"${toolName}" 한 번 허용됨`,
  toastAllowedSession: (toolName) => `"${toolName}" 세션 동안 자동 허용됨`,
  toastDenied: (toolName) => `"${toolName}" 거부됨`,

  // PIPA notice (shown in modal footer)
  pipaNotice: '개인정보보호법 제22조의2·제26조에 따라 고지합니다.',
}

export default permissionKo
