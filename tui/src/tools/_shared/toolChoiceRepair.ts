import type { Tools } from '../../Tool.js'
import type { Message } from '../../types/message.js'
import type { BetaToolChoiceTool } from '../../sdk-compat.js'

export interface UmmayaTuiRepairPolicy {
  readonly id: string
  readonly kind: 'display_or_answer_repair'
  readonly owner: string
  readonly evidenceEvent: string
  readonly removalCondition: string
}

export interface UmmayaBackendRepairReceipt {
  readonly source: 'backend_route_decision' | 'backend_validation'
  readonly reason: string
  readonly evidenceEvent: string
  readonly toolName?: string
}

export interface ForcedUmmayaToolUse {
  readonly name: string
  readonly input: Record<string, unknown>
}

export const UMMAYA_TUI_REPAIR_POLICIES: readonly UmmayaTuiRepairPolicy[] = []

export {
  backfillUmmayaObservableToolInputFromUserQuery,
  buildDocumentCompletionPromptIfNeeded,
  buildIgnoredDocumentToolChoiceBlockedText,
  repairUmmayaDocumentToolInputForDispatch,
  repairUmmayaExplicitDocumentToolUseFromUserQuery,
  selectRecoveredDocumentToolChoiceNameForMessages,
  selectUmmayaClientForcedToolUse,
  shouldSuppressDocumentToolCallsForAnswerSynthesis,
  shouldWithholdIgnoredDocumentToolChoiceText,
} from './toolChoiceRepair/documentRepair.js'
export {
  buildIgnoredSupportToolChoiceBlockedText,
  scrubIgnoredSupportToolChoiceMessage,
  selectRecoveredSupportToolChoiceNameForMessages,
  shouldSuppressUmmayaToolCallsForAnswerSynthesis,
  shouldWithholdIgnoredSupportToolChoiceText,
} from './toolChoiceRepair/supportRepair.js'
export {
  buildGenericPendingFinalAnswerRepairPromptIfNeeded,
  buildGenericPendingFinalAnswerToolUseBlockedText,
  selectUmmayaClientForcedToolUseForPublicData,
  shouldBlockToolUseAfterGenericPendingFinalAnswerRepair,
  shouldWithholdGenericPendingFinalAnswer,
} from './toolChoiceRepair/publicDataRepair.js'
export {
  selectRecoveredSupportToolChoiceNameForMessages as selectRecoveredSupportToolChoiceNameForMessagesFromSupportRepair,
} from './toolChoiceRepair/supportRepair.js'

export function selectUmmayaToolChoiceOverride(_params: {
  readonly messages: readonly Message[]
  readonly tools: Tools
}): BetaToolChoiceTool | undefined {
  return undefined
}
