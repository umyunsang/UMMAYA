// SPDX-License-Identifier: Apache-2.0

const LOCAL_DOCUMENT_PATH_RE =
  /(?:~|\/)[^\s"'<>]+?\.(?:hwpx|hwp|docx|pdf|xlsx|pptx|odt|ods|odp|doc|xls|ppt|csv|txt|md|json|xml|html)/giu

export function lastLocalDocumentPath(text: string): string | undefined {
  let latest: string | undefined
  for (const match of text.matchAll(LOCAL_DOCUMENT_PATH_RE)) {
    const rawPath = match[0]?.trim()
    if (rawPath === undefined || rawPath === '') continue
    latest = trimTrailingPunctuation(rawPath)
  }
  return latest
}

function trimTrailingPunctuation(path: string): string {
  return path.replace(/[),.;:，。]+$/u, '')
}
