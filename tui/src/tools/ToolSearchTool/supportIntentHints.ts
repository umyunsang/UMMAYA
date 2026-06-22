import type { Tool } from '../../Tool.js'

const SOURCE_SUPPORT_INTENT_PATTERN =
  /출처|근거|인용|참고\s*문헌|레퍼런스|출전|증빙|증거|자료\s*(?:출처|근거|조사|검색)|최신|현재\s*(?:정보|자료)|웹\s*검색|source|citation|evidence|provenance|reference|bibliography|current\s+(?:information|source|research)|latest|web\s*search|search\s+the\s+web|https?:\/\//iu

const MCP_SUPPORT_INTENT_PATTERN =
  /(?:\bmcp\b|mcp__|(?=.*(?:리소스|자원|resources?))(?=.*(?:신뢰\s*경계|신뢰|경계|trust|boundary|connected\s+servers?|서버\s*(?:리소스|자원)|servers?\s+resources?)))/iu

const AGENT_SUPPORT_INTENT_PATTERN =
  /에이전트|sub-?agent|agent|별도\s*작업|하위\s*작업|작업자|작업\s*도구|진행\s*상황|취소\s*가능|cancel(?:lable)?\s+task|delegat(?:e|ion)|background\s+task/iu

const SHELL_SUPPORT_INTENT_PATTERN = new RegExp(
  [
    String.raw`(?:\b(?:shell|bash)\b|쉘|셸)\s*(?:명령(?:어)?|커맨드|실행|돌려|수행|호출|권한|차단|으로|로|에서)`,
    String.raw`(?:명령(?:어)?|커맨드)\s*(?:을|를|으로)?\s*(?:실행|돌려|수행|호출|입력|쳐)`,
    String.raw`터미널(?:에서|로)\s*(?:\x60|[a-z0-9_.-]+|명령(?:어)?|커맨드|실행|돌려|수행|호출)`,
    String.raw`\bgit\s+(?:status|diff|log|show|add|commit|push|pull|fetch|branch|checkout|switch|merge|rebase|tag|remote|rev-parse|describe|stash|restore|reset|clean)\b`,
    String.raw`git\s*(?:상태|로그|diff|변경\s*사항|커밋|브랜치|태그|원격|추적)\s*(?:확인|조회|검사|보여|알려|출력|실행|돌려)?`,
    String.raw`\x60[^\x60]*(?:\bgit\b|\bgh\b|\bbun\b|\bnpm\b|\bpnpm\b|\byarn\b|\buv\b|\bpython3?\b|\bpytest\b|\bruff\b|\bmypy\b|\btmux\b|\bls\b|\bpwd\b|\bcat\b|\bsed\b|\bawk\b|\brg\b|\bgrep\b|\bfind\b|\bmkdir\b|\brm\b|\bcp\b|\bmv\b|\bchmod\b|\bcurl\b|\bbrew\b|\bdocker\b|\bmake\b|\bnode\b)[^\x60]*\x60`,
  ].join('|'),
  'iu',
)

const KOREAN_QUERY_EXPANSIONS: readonly {
  readonly pattern: RegExp
  readonly terms: readonly string[]
}[] = [
  {
    pattern:
      /(?=.*(?:저장소|작업\s*공간|워크\s*스페이스|로컬|프로젝트|코드\s*베이스|repository|repo|workspace|codebase))(?=.*(?:파일|경로|첫\s*줄|읽|검색|찾|grep|read))/iu,
    terms: ['+workspace', 'local', 'file', 'read', 'grep', 'search'],
  },
  {
    pattern: SOURCE_SUPPORT_INTENT_PATTERN,
    terms: [
      'web',
      'search',
      'current',
      'information',
      'fetch',
      'url',
      'source',
      'verification',
    ],
  },
  {
    pattern: MCP_SUPPORT_INTENT_PATTERN,
    terms: ['mcp', 'resources', 'list', 'connected', 'servers'],
  },
  {
    pattern: AGENT_SUPPORT_INTENT_PATTERN,
    terms: ['+agent', 'delegate', 'subagent', 'task', 'cancel', 'progress'],
  },
  {
    pattern: SHELL_SUPPORT_INTENT_PATTERN,
    terms: ['shell', 'bash', 'commands', 'permission', 'blocked'],
  },
  {
    pattern: /쓰기|작성|저장|파일|메모|승인|작업공간/iu,
    terms: ['create', 'overwrite', 'local', 'text', 'files', 'permission', 'blocked'],
  },
]

const SUPPORT_TOOL_NAMES_BY_PATTERN: readonly {
  readonly pattern: RegExp
  readonly toolNames: readonly string[]
}[] = [
  {
    pattern:
      /(?=.*(?:저장소|작업\s*공간|워크\s*스페이스|로컬|프로젝트|코드\s*베이스|repository|repo|workspace|codebase))(?=.*(?:파일|경로|첫\s*줄|읽|검색|찾|grep|read))/iu,
    toolNames: ['workspace_grep', 'workspace_read'],
  },
  {
    pattern: SOURCE_SUPPORT_INTENT_PATTERN,
    toolNames: ['WebSearch', 'WebFetch'],
  },
  {
    pattern: MCP_SUPPORT_INTENT_PATTERN,
    toolNames: ['ListMcpResourcesTool'],
  },
  {
    pattern: AGENT_SUPPORT_INTENT_PATTERN,
    toolNames: ['Agent'],
  },
  {
    pattern: SHELL_SUPPORT_INTENT_PATTERN,
    toolNames: ['workspace_bash'],
  },
  {
    pattern: /쓰기|작성|저장|파일|메모|승인|작업공간/iu,
    toolNames: ['workspace_write'],
  },
]

export function expandedToolSearchTerms(queryLower: string): string[] {
  const terms = queryLower.split(/\s+/).filter(term => term.length > 0)
  for (const expansion of KOREAN_QUERY_EXPANSIONS) {
    if (expansion.pattern.test(queryLower)) {
      terms.push(...expansion.terms)
    }
  }
  return [...new Set(terms)]
}

export function expandedIntentTermSet(queryLower: string): ReadonlySet<string> {
  const expandedTerms: string[] = []
  for (const expansion of KOREAN_QUERY_EXPANSIONS) {
    if (expansion.pattern.test(queryLower)) {
      expandedTerms.push(
        ...expansion.terms.map(term =>
          term.startsWith('+') ? term.slice(1) : term,
        ),
      )
    }
  }
  return new Set(expandedTerms)
}

export function selectRecoveredSupportToolNamesForQuery(
  query: string,
): readonly string[] {
  const queryLower = query.toLowerCase()
  const shellIntent = SHELL_SUPPORT_INTENT_PATTERN.test(queryLower)
  const localWorkspaceFileIntent =
    /(?:저장소|작업\s*공간|워크\s*스페이스|로컬|프로젝트|코드\s*베이스|repository|repo|workspace|codebase)/iu.test(
      queryLower,
    ) &&
    /(?:파일|경로|첫\s*줄|읽|검색|찾|grep|read)/iu.test(queryLower)
  if (localWorkspaceFileIntent && !shellIntent) {
    return ['workspace_grep', 'workspace_read']
  }

  const toolNames: string[] = []
  for (const supportClass of SUPPORT_TOOL_NAMES_BY_PATTERN) {
    if (supportClass.pattern.test(queryLower)) {
      toolNames.push(...supportClass.toolNames)
    }
  }
  return [...new Set(toolNames)]
}

function sanitizeSearchHint(searchHint: string): string {
  return searchHint
    .replace(/[<>]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

export function formatDeferredToolSearchLine(tool: Tool): string {
  const searchHint = tool.searchHint ? sanitizeSearchHint(tool.searchHint) : ''
  return searchHint ? `${tool.name} - ${searchHint}` : tool.name
}
