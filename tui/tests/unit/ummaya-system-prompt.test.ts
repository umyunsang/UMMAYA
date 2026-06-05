// SPDX-License-Identifier: Apache-2.0

import { describe, expect, test } from 'bun:test'

describe('UMMAYA system prompt migration', () => {
  test('frames the active TUI prompt as public-service work with visible tool-loop progress', async () => {
    const previousNodeEnv = process.env.NODE_ENV
    process.env.NODE_ENV = 'test'
    try {
      const { getSystemPrompt } = await import(
        '../../src/constants/prompts.js'
      )
      const sections = await getSystemPrompt(
        [],
        'LGAI-EXAONE/K-EXAONE-236B-A23B',
      )
      const prompt = sections.join('\n\n')

      expect(prompt).toContain('Korean public-service')
      expect(prompt).toContain('Before every tool call')
      expect(prompt).toContain('After every tool result')
      expect(prompt).toContain(
        'include a text block before the next tool call',
      )
      expect(prompt).toContain('Do not use generic status-only boilerplate')
      expect(prompt).toContain('Do not expose hidden chain-of-thought')
      expect(prompt).toContain('Bind final-answer values exactly')
      expect(prompt).toContain('For KMA current observations')
      expect(prompt).not.toContain('with software engineering tasks')
      expect(prompt).not.toContain(
        'The user will primarily request you to perform software engineering tasks',
      )
      expect(prompt).not.toContain('authorized security testing')
      expect(prompt).not.toContain('CTF challenges')
      expect(prompt).not.toContain('deleting files/branches')
      expect(prompt).not.toContain('git reset --hard')
    } finally {
      if (previousNodeEnv === undefined) {
        delete process.env.NODE_ENV
      } else {
        process.env.NODE_ENV = previousNodeEnv
      }
    }
  })
})
