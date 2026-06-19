import type { BetaWebSearchTool20250305 } from 'src/sdk-compat.js'
import type { Input } from './schemas.js'

export function makeToolSchema(input: Input): BetaWebSearchTool20250305 {
  return {
    type: 'web_search_20250305',
    name: 'web_search',
    allowed_domains: input.allowed_domains,
    blocked_domains: input.blocked_domains,
    max_uses: 8,
  }
}
