// SPDX-License-Identifier: Apache-2.0
// Stage-1 NO-OP stub — CC-fidelity placeholder. Consumer sites carry
// temporary CC-fidelity type suppressions and will be wired to real
// UMMAYA implementations in the CC TUI Fidelity Meta-Epic.
import type { TextBlockParam } from '@anthropic-ai/sdk/resources/index.mjs'
import type { ReactNode } from 'react'

type MessageStubProps = {
  readonly addMargin: boolean
  readonly param: TextBlockParam
}

export function UserCrossSessionMessage(
  _props: MessageStubProps,
): ReactNode {
  return null
}

export default UserCrossSessionMessage
