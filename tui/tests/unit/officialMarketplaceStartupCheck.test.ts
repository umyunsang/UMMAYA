import { afterEach, describe, expect, it } from 'bun:test'
import { isOfficialMarketplaceAutoInstallDisabled } from '../../src/utils/plugins/officialMarketplaceStartupCheck.js'

const OLD_DISABLE = process.env.CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL
const OLD_ENABLE = process.env.UMMAYA_ENABLE_ANTHROPIC_MARKETPLACE_AUTOINSTALL

afterEach(() => {
  if (OLD_DISABLE === undefined) {
    delete process.env.CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL
  } else {
    process.env.CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL = OLD_DISABLE
  }

  if (OLD_ENABLE === undefined) {
    delete process.env.UMMAYA_ENABLE_ANTHROPIC_MARKETPLACE_AUTOINSTALL
  } else {
    process.env.UMMAYA_ENABLE_ANTHROPIC_MARKETPLACE_AUTOINSTALL = OLD_ENABLE
  }
})

describe('official marketplace startup check', () => {
  it('disables Anthropic marketplace auto-install by default in UMMAYA', () => {
    delete process.env.CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL
    delete process.env.UMMAYA_ENABLE_ANTHROPIC_MARKETPLACE_AUTOINSTALL

    expect(isOfficialMarketplaceAutoInstallDisabled()).toBe(true)
  })

  it('allows explicit UMMAYA opt-in for Anthropic marketplace auto-install', () => {
    delete process.env.CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL
    process.env.UMMAYA_ENABLE_ANTHROPIC_MARKETPLACE_AUTOINSTALL = '1'

    expect(isOfficialMarketplaceAutoInstallDisabled()).toBe(false)
  })

  it('keeps the upstream disable env var as an overriding kill switch', () => {
    process.env.CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL = '1'
    process.env.UMMAYA_ENABLE_ANTHROPIC_MARKETPLACE_AUTOINSTALL = '1'

    expect(isOfficialMarketplaceAutoInstallDisabled()).toBe(true)
  })
})
