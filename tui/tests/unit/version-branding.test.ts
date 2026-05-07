import { describe, expect, it } from 'bun:test'
import packageJson from '../../package.json' with { type: 'json' }

describe('KOSAX version branding', () => {
  it('uses the stable release version without issue-number build metadata', () => {
    expect(packageJson.version).toBe('0.1.0')
    expect(packageJson.version).not.toMatch(/\+\d+$/)
    expect(packageJson.version).not.toContain('+1978')
  })
})
