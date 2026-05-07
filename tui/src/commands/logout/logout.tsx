import * as React from 'react'
import { Text } from '../../ink.js'
import { closeKosmosBridge } from '../../ipc/bridgeSingleton.js'
import type {
  LocalJSXCommandContext,
  LocalJSXCommandOnDone,
} from '../../types/command.js'
import { clearFriendliCredential } from '../../utils/friendliAuth.js'
import { gracefulShutdownSync } from '../../utils/gracefulShutdown.js'

export async function performLogout(context?: LocalJSXCommandContext): Promise<void> {
  clearFriendliCredential()
  await closeKosmosBridge()
  if (context) {
    await Promise.resolve(context.onChangeAPIKey())
    context.setAppState(prev => ({
      ...prev,
      authVersion: prev.authVersion + 1,
    }))
  }
}

export async function call(
  _onDone: LocalJSXCommandOnDone,
  context: LocalJSXCommandContext,
): Promise<React.ReactNode> {
  await performLogout(context)

  const message = <Text>Successfully logged out from your FriendliAI session.</Text>

  setTimeout(() => {
    gracefulShutdownSync(0, 'logout')
  }, 200)

  return message
}
