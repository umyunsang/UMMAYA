import type { Command } from '../../commands.js'
import { isEnvTruthy } from '../../utils/envUtils.js'
import { hasFriendliCredential } from '../../utils/friendliAuth.js'

export default () =>
  ({
    type: 'local-jsx',
    name: 'login',
    description: hasFriendliCredential()
      ? 'Switch FriendliAI API keys'
      : 'Sign in with your FriendliAI API key',
    isEnabled: () => !isEnvTruthy(process.env.DISABLE_LOGIN_COMMAND),
    load: () => import('./login.js'),
  }) satisfies Command
