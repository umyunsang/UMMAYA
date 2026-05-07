// SPDX-License-Identifier: Apache-2.0
// Spec 2294 — KOSMOS Primitive Permission UI — English strings.
//
// Citations:
//   PIPA §22-2: Personal information processors shall disclose matters related
//               to the processing of personal information.
//   PIPA §26:   Trustees shall not process personal information beyond the
//               scope of the entrusted duties.
//
// Shape mirrors permission.ko.ts — any new key must be added to both files
// and to the PermissionI18nKo interface (which is re-used for EN shape).

import type { PermissionI18nKo } from './permission.ko.js'

// Re-use the same interface shape for EN (same keys, different strings).
export type PermissionI18nEn = PermissionI18nKo

const permissionEn: PermissionI18nEn = {
  // Modal titles
  verifyModalTitle: 'Identity Verification — Permission Required',
  submitModalTitle: (isIrreversible) =>
    isIrreversible ? 'Irreversible Submission — Permission Required' : 'Submit — Permission Required',

  // Modal bodies
  verifyModalBody: (toolName) =>
    `"${toolName}" wants to perform an identity verification. ` +
    'Your personal information will be processed for public-service authentication. ' +
    '(PIPA §22-2 — Disclosure obligation)',

  submitModalBody: (toolName, isIrreversible) =>
    isIrreversible
      ? `"${toolName}" wants to submit an irreversible government-service request. ` +
        'This action cannot be undone after execution. ' +
        'Trustees will not process your data beyond the stated purpose. ' +
        '(PIPA §26 — Trustee obligation)'
      : `"${toolName}" wants to submit a government-service request. ` +
        'Your request data will be forwarded to the relevant agency. ' +
        '(PIPA §22-2 — Disclosure obligation)',

  // Layer labels
  layer1Label: 'Low risk (Layer 1)',
  layer2Label: 'Medium risk (Layer 2)',
  layer3Label: 'High risk (Layer 3)',

  // Receipt footer
  receiptIdLabel: (receiptId) => `Receipt ID: ${receiptId}`,

  // Selector
  selectorAllowOnce: 'Allow once',
  selectorAllowSession: 'Allow for this session',
  selectorDeny: 'Deny',
  acceptFeedbackPlaceholder: 'tell KOSMOS what to do next',
  rejectFeedbackPlaceholder: 'tell KOSMOS what to do differently',

  // Toast
  toastAllowedOnce: (toolName) => `"${toolName}" allowed once`,
  toastAllowedSession: (toolName) => `"${toolName}" auto-allowed for session`,
  toastDenied: (toolName) => `"${toolName}" denied`,

  // PIPA notice (shown in modal footer)
  pipaNotice: 'Disclosed pursuant to PIPA §22-2 and §26.',
}

export default permissionEn
