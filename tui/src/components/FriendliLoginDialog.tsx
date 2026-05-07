// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — /login dialog for process-scoped FriendliAI API keys.

import React, { useCallback, useEffect, useLayoutEffect, useState } from 'react'
import { Box, Text, useInput, useStdin } from '../ink.js'
import { useTheme } from '../theme/provider.js'
import type { InputEvent } from '../ink.js'
import type { FriendliCredentialSource } from '../utils/friendliAuth.js'

export type FriendliLoginDialogProps = {
  existingSource: FriendliCredentialSource
  onConfirm: (apiKey: string) => void
  onCancel: () => void
}

const MASK_CHAR = '*'

export function FriendliLoginDialog({
  existingSource,
  onConfirm,
  onCancel,
}: FriendliLoginDialogProps): React.ReactElement {
  const theme = useTheme()
  const { internal_eventEmitter, setRawMode } = useStdin()
  const [buffer, setBuffer] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleInput = useCallback(
    (
      input: string,
      key: {
        return: boolean
        escape: boolean
        backspace: boolean
        delete: boolean
        ctrl: boolean
      },
    ) => {
      if (key.escape) {
        onCancel()
        return
      }

      if (key.return) {
        const value = buffer.trim()
        if (value.length === 0) {
          setError('FriendliAI API key must not be empty.')
          return
        }
        onConfirm(value)
        return
      }

      if (key.backspace || key.delete) {
        setBuffer(s => s.slice(0, -1))
        setError(null)
        return
      }

      if (!key.ctrl && input.length > 0) {
        setBuffer(s => s + input)
        setError(null)
      }
    },
    [buffer, onCancel, onConfirm],
  )

  useLayoutEffect(() => {
    setRawMode(true)
    return () => setRawMode(false)
  }, [setRawMode])

  useEffect(() => {
    if (!internal_eventEmitter) return undefined
    const handleEvent = (event: InputEvent | unknown): void => {
      if (
        typeof event !== 'object' ||
        event === null ||
        !('input' in event) ||
        !('key' in event)
      ) {
        return
      }
      const inputEvent = event as InputEvent
      ;(inputEvent as { stopImmediatePropagation?: () => void }).stopImmediatePropagation?.()
      handleInput(inputEvent.input, inputEvent.key)
    }
    internal_eventEmitter.prependListener('input', handleEvent)
    return () => {
      internal_eventEmitter.removeListener('input', handleEvent)
    }
  }, [handleInput, internal_eventEmitter])

  useInput(handleInput)

  const sourceLabel =
    existingSource === 'none' ? 'not logged in' : `current source: ${existingSource}`
  const masked = MASK_CHAR.repeat(buffer.length)

  return (
    <Box
      flexDirection="column"
      paddingX={1}
      paddingY={1}
      borderStyle="round"
      borderColor={theme.kosmosCore}
    >
      <Box marginBottom={1}>
        <Text bold color={theme.wordmark}>
          FriendliAI Login
        </Text>
      </Box>

      <Box marginBottom={1}>
        <Text color={theme.subtle}>{sourceLabel}</Text>
      </Box>

      <Box marginBottom={1}>
        <Text color={theme.subtle}>API key: </Text>
        <Text color={theme.text}>{masked.length > 0 ? `${masked}█` : '█'}</Text>
      </Box>

      {error && (
        <Box marginBottom={1}>
          <Text color={theme.error}>{error}</Text>
        </Box>
      )}

      <Box>
        <Text dimColor>Enter login · Esc cancel · key is not saved to disk</Text>
      </Box>
    </Box>
  )
}
