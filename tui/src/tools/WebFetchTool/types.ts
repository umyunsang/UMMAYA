import type { SourceVerification } from './sourceVerification.js'

export type WebFetchOutput = {
  readonly bytes: number
  readonly code: number
  readonly codeText: string
  readonly result: string
  readonly durationMs: number
  readonly url: string
  readonly sourceVerification?: SourceVerification
}

export type WebFetchCallInput = {
  readonly url: string
  readonly prompt: string
}

export type WebFetchCallContext = {
  readonly abortController: AbortController
  readonly options: {
    readonly isNonInteractiveSession: boolean
  }
}
