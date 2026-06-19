import { PS_TOKENIZER_DASH_CHARS } from '../../utils/powershell/parser.js'
import { resolveToCanonical } from './readOnlyValidation.js'

const LINK_ITEM_TYPES = new Set(['symboliclink', 'junction', 'hardlink'])

function isItemTypeParamAbbrev(param: string): boolean {
  return (
    (param.length >= 3 && '-itemtype'.startsWith(param)) ||
    (param.length >= 3 && '-type'.startsWith(param))
  )
}

export function isSymlinkCreatingCommand(cmd: {
  name: string
  args: string[]
}): boolean {
  const canonical = resolveToCanonical(cmd.name)
  if (canonical !== 'new-item') return false

  for (let index = 0; index < cmd.args.length; index++) {
    const raw = cmd.args[index] ?? ''
    if (raw.length === 0) continue

    const first = raw.charAt(0)
    const normalized =
      PS_TOKENIZER_DASH_CHARS.has(first) || first === '/'
        ? '-' + raw.slice(1)
        : raw
    const lower = normalized.toLowerCase()
    const colonIdx = lower.indexOf(':', 1)
    const paramRaw = colonIdx > 0 ? lower.slice(0, colonIdx) : lower
    const param = paramRaw.replace(/`/g, '')
    if (!isItemTypeParamAbbrev(param)) continue

    const rawVal =
      colonIdx > 0
        ? lower.slice(colonIdx + 1)
        : (cmd.args[index + 1]?.toLowerCase() ?? '')
    const value = rawVal.replace(/`/g, '').replace(/^['"]|['"]$/g, '')
    if (LINK_ITEM_TYPES.has(value)) return true
  }

  return false
}
