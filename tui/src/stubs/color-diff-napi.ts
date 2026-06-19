// [P0 stub · color-diff-napi]
// Anthropic's internal native module is not publicly available. UMMAYA disables
// syntax highlighting at the source level (CLAUDE_CODE_SYNTAX_HIGHLIGHT=0 is
// the documented gate); these exports keep consumer types honest.

export type SyntaxTheme = {
  readonly name: string
  readonly colors: Record<string, string>
}

export class ColorDiff {
  constructor(
    _hunk: unknown,
    _firstLine: string | null,
    _filePath: string,
    _prefixContent?: string | null,
  ) {}

  diff(): string[] {
    return []
  }

  render(_themeName: string, _width: number, _dim: boolean): string[] | null {
    return []
  }
}

export class ColorFile {
  constructor(
    _code: string,
    _filePath: string,
  ) {}

  read(): string {
    return ''
  }

  render(_themeName: string, _width: number, _dim: boolean): string[] | null {
    return []
  }
}

export const getSyntaxTheme = (..._args: unknown[]): SyntaxTheme => ({
  name: 'no-op',
  colors: {},
})

export default { ColorDiff, ColorFile, getSyntaxTheme }
