export const DOCUMENT_TOOL_NAME = 'document'
export const DOCUMENT_RENDER_TOOL_NAME = 'document_render'
export type DocumentToolName =
  | typeof DOCUMENT_TOOL_NAME
  | typeof DOCUMENT_RENDER_TOOL_NAME

export const DOCUMENT_COMPLETION_PROMPT_MARKER = 'Document primitive result complete'
export const DOCUMENT_COMPLETION_PROMPT =
  `${DOCUMENT_COMPLETION_PROMPT_MARKER}: the document tool_result for the latest citizen request is already visible in the TUI. Do not call another document, workspace, render, or tool-search tool in this turn. Answer in Korean only. Write the final Korean answer now from the actual tool_result only. Keep it to one or two short sentences: state whether the document was updated, blocked, failed, or needs explicit input; when the status is needs_input or the path is missing, ask the user to provide an exact existing file path or make an explicit selection; mention only changed field labels/values or required selection that are present in the visible diff; include the saved path only when the tool_result reports one. Do not invent units, parenthetical labels, workflow steps, style claims, or extra facts. Do not say an image, screenshot, viewport, render artifact, browser view, viewer, or visual artifact was generated. The inline TUI diff above is the user-visible proof.`
export const DOCUMENT_INTENT_RE =
  /(문서|공문서|양식|서식|파일|작성|저장|렌더|미리보기|변경사항|\bdiff\b|\bcompact\b|\bdocument\b|\bfile\b|\bform\b|\brender\b|\bsave\b|\bwrite\b)/iu
export const DOCUMENT_WRITE_RE =
  /(작성|수정|편집|채우|채워|입력|변경|저장|write|edit|fill|apply|save)/iu
export const DOCUMENT_READ_ONLY_RE =
  /(읽기\s*전용|수정\s*없이|변경\s*없이|저장\s*없이|수정하지\s*마|저장하지\s*마|작성하지\s*마|쓰지\s*마|열람만|확인만|inspect|extract|read\s*only)/iu
export const DOCUMENT_DIFF_ONLY_FINAL_RE =
  /(실제(?:로)?\s*바뀐\s*내용만|바뀐\s*내용만|변경된\s*부분만|변경사항만|actual\s+changed\s+content\s+only|only\s+changed)/iu
export const DOCUMENT_DIFF_AND_SAVE_ONLY_FINAL_RE =
  /(실제(?:로)?\s*바뀐\s*내용\s*(?:과|및|랑|하고)\s*저장\s*(?:위치|경로)만|변경(?:된)?\s*(?:내용|부분|사항).{0,24}저장\s*(?:위치|경로)만|changed.{0,24}(?:save|saved).{0,24}(?:location|path).{0,24}only)/iu
const LOCAL_DOCUMENT_PATH_RE =
  /(?:^|[\s"'(])((?:~|\/|\.{1,2}\/)[^\s"'<>]+?\.(?:hwpx|hwp|docx|pdf|xlsx|pptx))(?=$|[\s"'),.?!:;，。]|[가-힣])/iu
const DOCUMENT_INSPECT_STRUCTURE_RE =
  /(구조|빈칸|문항|양식|필드|항목|inspect|extract)/iu

export type DocumentExpectedFormat =
  | 'hwpx'
  | 'hwp'
  | 'docx'
  | 'pdf'
  | 'xlsx'
  | 'pptx'

export function localDocumentPathFromText(userText: string): string | undefined {
  return LOCAL_DOCUMENT_PATH_RE.exec(userText)?.[1]
}

export function documentExpectedFormatFromPath(
  path: string,
): DocumentExpectedFormat | undefined {
  const ext = path.split('.').pop()?.toLowerCase()
  switch (ext) {
    case 'hwpx':
    case 'hwp':
    case 'docx':
    case 'pdf':
    case 'xlsx':
    case 'pptx':
      return ext
    default:
      return undefined
  }
}

export function isExactLocalReadOnlyDocumentPrompt(userText: string): boolean {
  return localDocumentPathFromText(userText) !== undefined &&
    (DOCUMENT_READ_ONLY_RE.test(userText) ||
      DOCUMENT_INSPECT_STRUCTURE_RE.test(userText))
}
