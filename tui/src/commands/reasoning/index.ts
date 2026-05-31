import type { Command } from '../../commands.js'
import { shouldInferenceConfigCommandBeImmediate } from '../../utils/immediateCommand.js'

export default {
  type: 'local-jsx',
  name: 'reasoning',
  description: 'Set K-EXAONE reasoning mode',
  argumentHint: '[fast|balanced|deep|diagnostic|auto|unset]',
  get immediate() {
    return shouldInferenceConfigCommandBeImmediate()
  },
  load: () => import('./reasoning.js'),
} satisfies Command
