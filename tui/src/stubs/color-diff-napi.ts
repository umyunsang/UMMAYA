// [P0 stub · color-diff-napi]
// Anthropic's internal native module is not publicly available. KOSMOS disables
// syntax highlighting at the source level (CLAUDE_CODE_SYNTAX_HIGHLIGHT=0 is
// the documented gate); these exports keep consumer types honest.
/* eslint-disable @typescript-eslint/no-explicit-any */

export type SyntaxTheme = {
  name: string;
  colors: Record<string, string>;
};

export const ColorDiff: any = class {
  constructor(..._args: unknown[]) {}
  diff() { return []; }
  // Audit-3 P0-1 fix: CC StructuredDiff (TrustDialog 의 CLAUDE.md preview)
  // 가 `colorDiff.render(theme, width, dim)` 를 호출. stub 에 render 가
  // 없어서 fresh-install boot 시 `undefined is not a function` → React
  // render error → process crash. KOSMOS 는 syntax highlighting 비활성
  // 이므로 빈 배열 반환 (StructuredDiff 가 raw text fallback 으로 그림).
  render(..._args: unknown[]) { return []; }
};

export const ColorFile: any = class {
  constructor(..._args: unknown[]) {}
  read() { return ''; }
  render(..._args: unknown[]) { return []; }
};

export const getSyntaxTheme = (..._args: unknown[]): SyntaxTheme => ({
  name: 'no-op',
  colors: {},
});

export default { ColorDiff, ColorFile, getSyntaxTheme };
