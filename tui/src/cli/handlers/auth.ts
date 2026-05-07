/* eslint-disable custom-rules/no-process-exit -- CLI subcommand handler intentionally exits */
// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — FriendliAI session-auth CLI stubs.
//
// FriendliAI API keys are process-scoped in KOSMOS. The interactive TUI /login
// command can place a key into the running process and its lazily spawned
// Python backend. A standalone `kosmos auth login` process cannot mutate the
// parent shell or an already running TUI without persisting a secret, so it
// intentionally guides citizens back to the in-session command.

import {
  clearFriendliCredential,
  getFriendliCredentialSource,
} from '../../utils/friendliAuth.js'
import { jsonStringify } from '../../utils/slowOperations.js'

export async function installOAuthTokens(_tokens: unknown): Promise<void> {
  throw new Error('KOSMOS does not install Anthropic OAuth tokens. Use /login inside the TUI.')
}

export async function authLogin(_opts: {
  email?: string
  sso?: boolean
  console?: boolean
  claudeai?: boolean
} = {}): Promise<void> {
  process.stdout.write(
    'KOSMOS FriendliAI login is session-scoped. Start the TUI and run /login; the API key is not saved to disk.\n',
  )
  process.exit(0)
}

export async function authStatus(opts: {
  json?: boolean
  text?: boolean
}): Promise<void> {
  const source = getFriendliCredentialSource()
  const loggedIn = source !== 'none'

  if (opts.text) {
    if (loggedIn) {
      process.stdout.write(`FriendliAI API key: ${source}\n`)
    } else {
      process.stdout.write('Not logged in. Start the KOSMOS TUI and run /login.\n')
    }
  } else {
    process.stdout.write(
      jsonStringify(
        {
          loggedIn,
          authMethod: loggedIn ? 'friendli_api_key' : 'none',
          apiProvider: 'friendliai',
          apiKeySource: loggedIn ? source : null,
          persistence: 'process_env',
        },
        null,
        2,
      ) + '\n',
    )
  }

  process.exit(loggedIn ? 0 : 1)
}

export async function authLogout(): Promise<void> {
  clearFriendliCredential()
  process.stdout.write(
    'FriendliAI credential cleared from this process. In the TUI, run /logout to clear the active session key and close the backend bridge.\n',
  )
  process.exit(0)
}
