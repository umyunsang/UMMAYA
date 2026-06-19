const MAX_LINES_TO_SHOW = 3

export function isShellOutputLineTruncated(content: string): boolean {
  let position = 0
  for (let line = 0; line <= MAX_LINES_TO_SHOW; line++) {
    position = content.indexOf('\n', position)
    if (position === -1) return false
    position++
  }
  return position < content.length
}
