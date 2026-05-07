import * as React from 'react'
import { Box, Text } from '../../ink.js'
import { ConfigurableShortcutHint } from '../../components/ConfigurableShortcutHint.js'
import { Dialog } from '../../components/design-system/Dialog.js'
import TextInput from '../../components/TextInput.js'
import { closeKosmosBridge } from '../../ipc/bridgeSingleton.js'
import type { LocalJSXCommandContext, LocalJSXCommandOnDone } from '../../types/command.js'
import {
  getFriendliCredentialSource,
  installFriendliCredential,
} from '../../utils/friendliAuth.js'
import { stripSignatureBlocks } from '../../utils/messages.js'

export async function call(
  onDone: LocalJSXCommandOnDone,
  context: LocalJSXCommandContext,
): Promise<React.ReactNode> {
  return (
    <Login
      onDone={async (success, apiKey) => {
        if (!success || !apiKey) {
          onDone('Login interrupted')
          return
        }

        try {
          installFriendliCredential(apiKey)
          await closeKosmosBridge()
          await Promise.resolve(context.onChangeAPIKey())
          context.setMessages(stripSignatureBlocks)
          context.setAppState(prev => ({
            ...prev,
            authVersion: prev.authVersion + 1,
          }))
          onDone('Login successful')
        } catch (error) {
          onDone(error instanceof Error ? error.message : String(error), {
            display: 'system',
          })
        }
      }}
    />
  )
}

export function Login({
  onDone,
  startingMessage,
}: {
  onDone: (success: boolean, apiKey?: string) => void
  startingMessage?: string
}): React.ReactNode {
  const [apiKey, setApiKey] = React.useState('')
  const [cursorOffset, setCursorOffset] = React.useState(0)
  const [error, setError] = React.useState<string | null>(null)
  const existingSource = getFriendliCredentialSource()

  const handleChange = React.useCallback((value: string) => {
    setApiKey(value)
    setError(null)
  }, [])

  const handleSubmit = React.useCallback(
    (value: string) => {
      const trimmed = value.trim()
      if (trimmed.length === 0) {
        setError('FriendliAI API key must not be empty.')
        return
      }
      onDone(true, trimmed)
    },
    [onDone],
  )

  const handleCancel = React.useCallback(() => {
    onDone(false)
  }, [onDone])

  return (
    <Dialog
      title="Login"
      onCancel={handleCancel}
      color="permission"
      inputGuide={loginInputGuide}
    >
      <Box flexDirection="column" gap={1}>
        <Text bold>
          {startingMessage ??
            'Paste your FriendliAI API key to sign in for this session.'}
        </Text>
        {existingSource !== 'none' && (
          <Text dimColor>Current session source: {existingSource}</Text>
        )}
        <Box>
          <Text>API key: </Text>
          <TextInput
            value={apiKey}
            onChange={handleChange}
            onSubmit={handleSubmit}
            onExit={handleCancel}
            onPaste={handleChange}
            cursorOffset={cursorOffset}
            onChangeCursorOffset={setCursorOffset}
            columns={80}
            mask="*"
            focus
            showCursor
          />
        </Box>
        {error && <Text color="error">{error}</Text>}
        <Text dimColor>The key is kept in process memory and is not saved to disk.</Text>
      </Box>
    </Dialog>
  )
}

function loginInputGuide(exitState: { pending: boolean; keyName: string }): React.ReactNode {
  return exitState.pending ? (
    <Text>Press {exitState.keyName} again to exit</Text>
  ) : (
    <ConfigurableShortcutHint
      action="confirm:no"
      context="Confirmation"
      fallback="Esc"
      description="cancel"
    />
  )
}
