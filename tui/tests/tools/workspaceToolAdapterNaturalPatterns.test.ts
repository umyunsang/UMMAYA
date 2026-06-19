import { describe, expect, test } from 'bun:test'
import { homedir } from 'node:os'
import { toolByName } from './workspaceToolAdapter.helpers.js'

function userMessage(content: string) {
  return {
    messages: [
      {
        type: 'user',
        message: {
          role: 'user',
          content,
        },
      },
    ],
  }
}

describe('workspace tool adapter natural path patterns', () => {
  test('infers Downloads path for natural workspace glob folder hints', async () => {
    const glob = toolByName('workspace_glob')
    const input: Record<string, unknown> = { pattern: '**/*.hwpx' }

    await expect(
      glob.validateInput?.(
        input,
        userMessage(
          '다운로드 폴더에 있는 주간활동일지 HWPX 문서를 찾아서 13주차로 작성해줘.',
        ) as never,
      ),
    ).resolves.toEqual({ result: true })

    expect(input.path).toBe(`${homedir()}/Downloads`)
  })

  test('normalizes malformed HWPX glob patterns from natural document search hints', async () => {
    const glob = toolByName('workspace_glob')
    const input: Record<string, unknown> = { pattern: '**/*.hwp *.hwpx' }

    await expect(
      glob.validateInput?.(
        input,
        userMessage(
          '다운로드 폴더에 있는 주간활동일지 HWPX 문서를 찾아서 13주차로 작성해줘.',
        ) as never,
      ),
    ).resolves.toEqual({ result: true })

    expect(input.pattern).toBe('**/*.hwpx')
    expect(input.path).toBe(`${homedir()}/Downloads`)
  })

  test('widens HWPX basename prefix globs for document title substring searches', async () => {
    const glob = toolByName('workspace_glob')
    const input: Record<string, unknown> = { pattern: '**/주간활동일지*.hwpx' }

    await expect(
      glob.validateInput?.(
        input,
        userMessage(
          '다운로드 폴더에 있는 SW중심대학사업 현장미러형연계프로젝트 주간활동일지 HWPX 문서를 찾아줘.',
        ) as never,
      ),
    ).resolves.toEqual({ result: true })

    expect(input.pattern).toBe('**/*주간활동일지*.hwpx')
    expect(input.path).toBe(`${homedir()}/Downloads`)
  })

  test('widens HWP basename prefix globs for downloaded public-form searches', async () => {
    const glob = toolByName('workspace_glob')
    const input: Record<string, unknown> = { pattern: '**/참가서약서*.hwp' }

    await expect(
      glob.validateInput?.(
        input,
        userMessage(
          '다운로드 폴더에 있는 2026년도 AX 아이디어 경진대회 참가서약서 HWP 문서를 찾아줘.',
        ) as never,
      ),
    ).resolves.toEqual({ result: true })

    expect(input.pattern).toBe('**/*참가서약서*.hwp')
    expect(input.path).toBe(`${homedir()}/Downloads`)
  })

  test('keeps explicit workspace glob paths unchanged', async () => {
    const glob = toolByName('workspace_glob')
    const input: Record<string, unknown> = {
      pattern: '**/*.hwpx',
      path: '/tmp',
    }

    await glob.validateInput?.(input, { messages: [] } as never)

    expect(input.path).toBe('/tmp')
  })
})
