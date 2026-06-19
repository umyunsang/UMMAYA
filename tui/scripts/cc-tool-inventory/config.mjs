export const GENERATED_AT = '2026-06-12T00:00:00.000Z'
export const SCHEMA_VERSION = 'cc-tool-layer-inventory.v1'
export const TASK3_TEST_ID =
  'tui/tests/tools/ccToolInventory.test.ts::emits restored cc tool groups from source tree'
export const TASK4_TEST_ID =
  'tui/tests/tools/ccToolParityClassification.test.ts::classifies_each_tool_with_a_supported_status'
export const TASK5_TEST_ID =
  'tui/tests/tools/ccToolExposurePolicy.test.ts::requires_permission_for_tier_one_and_above'
export const TASK13_TEST_ID =
  'tui/tests/tools/featureGatedToolPolicy.test.ts::remote_schedule_workflow_tools_are_hidden_or_permission_gated'
export const TASK3_EVIDENCE_PATH =
  '.omo/evidence/cc-original-tool-layer-port/task-3-inventory.json'
export const TASK4_EVIDENCE_PATH =
  '.omo/evidence/cc-original-tool-layer-port/task-4-green.txt'
export const TASK5_EVIDENCE_PATH =
  '.omo/evidence/cc-original-tool-layer-port/task-5-green.txt'
export const TASK13_EVIDENCE_PATH =
  '.omo/evidence/cc-original-tool-layer-port/task-13-green.txt'
export const PARITY_ARTIFACT_ROOT =
  '.omo/evidence/cc-original-tool-layer-port/parity'

export const permissionModeBoundaries = [
  'default',
  'plan',
  'acceptEdits',
  'bypass-blocked',
]

export const bypassPermissionsPolicy = {
  cannot_override: ['AX', 'PIPA', 'identity'],
  enforcement:
    'bypassPermissions cannot override protected AX, PIPA, or identity walls.',
}

export const bypassRestriction =
  'bypassPermissions is bypass-blocked for protected AX, PIPA, and identity walls.'

export const exposurePolicyMatrix = [
  {
    policy_id: 'tier-0',
    trust_tier: 0,
    category: 'read-only local context',
    allowed_exposure_states: ['always-loaded', 'deferred-searchable', 'hidden', 'unsupported'],
    permission_mode_matrix: {
      default: 'Allowed only when bounded to workspace roots and transcript policy.',
      plan: 'Allowed for read-only planning with the same workspace boundary.',
      acceptEdits: 'No extra mutation authority; remains read-only.',
      'bypass-blocked': 'Not applicable unless the read path crosses protected data.',
    },
    bypass_permissions_overrides_protected_walls: false,
    bypass_permissions_restriction: bypassRestriction,
    protected_primitive_routing_allowed: false,
  },
  {
    policy_id: 'tier-1',
    trust_tier: 1,
    category: 'local mutation',
    allowed_exposure_states: ['permission-gated-callable', 'hidden', 'unsupported'],
    permission_mode_matrix: {
      default: 'Requires explicit one-shot approval before mutation.',
      plan: 'Plan-only; mutation is blocked.',
      acceptEdits: 'Allowed only through user edit approval or explicit one-shot approval.',
      'bypass-blocked': 'Raw document and protected data mutation bypasses are blocked.',
    },
    bypass_permissions_overrides_protected_walls: false,
    bypass_permissions_restriction: bypassRestriction,
    protected_primitive_routing_allowed: false,
  },
  {
    policy_id: 'tier-2',
    trust_tier: 2,
    category: 'shell/system execution',
    allowed_exposure_states: ['permission-gated-callable', 'hidden', 'unsupported'],
    permission_mode_matrix: {
      default: 'Requires command analysis and explicit one-shot approval.',
      plan: 'Plan-only; command execution is blocked.',
      acceptEdits: 'No automatic shell authority from edit approval.',
      'bypass-blocked': 'Destructive, credential, or protected-data commands are blocked.',
    },
    bypass_permissions_overrides_protected_walls: false,
    bypass_permissions_restriction: bypassRestriction,
    protected_primitive_routing_allowed: false,
  },
  {
    policy_id: 'tier-3',
    trust_tier: 3,
    category: 'external network/source acquisition',
    allowed_exposure_states: ['permission-gated-callable', 'hidden', 'unsupported'],
    permission_mode_matrix: {
      default: 'Requires explicit approval or approved source policy with URL evidence.',
      plan: 'Allowed only as cited source planning when policy pre-approves it.',
      acceptEdits: 'Cannot convert untrusted source text into approved document facts.',
      'bypass-blocked': 'Secret egress and protected data fetches are blocked.',
    },
    bypass_permissions_overrides_protected_walls: false,
    bypass_permissions_restriction: bypassRestriction,
    protected_primitive_routing_allowed: false,
  },
  {
    policy_id: 'tier-4',
    trust_tier: 4,
    category: 'agent/research orchestration',
    allowed_exposure_states: ['permission-gated-callable', 'hidden', 'unsupported'],
    permission_mode_matrix: {
      default: 'Requires bounded delegation within the parent permission scope.',
      plan: 'Can draft plans but cannot inherit broader tool authority.',
      acceptEdits: 'No lateral transfer of edit authority to child agents.',
      'bypass-blocked': 'Bypass cannot widen parent scope or protected walls.',
    },
    bypass_permissions_overrides_protected_walls: false,
    bypass_permissions_restriction: bypassRestriction,
    protected_primitive_routing_allowed: false,
  },
  {
    policy_id: 'tier-5',
    trust_tier: 5,
    category: 'protected national AX action',
    allowed_exposure_states: ['always-loaded', 'permission-gated-callable', 'hidden', 'unsupported'],
    permission_mode_matrix: {
      default: 'Requires identity, consent, delegation, and agency policy citation.',
      plan: 'Can plan protected actions but cannot execute them.',
      acceptEdits: 'Document edits do not grant protected AX action authority.',
      'bypass-blocked': 'Protected AX, PIPA, and identity walls are bypass-immune.',
    },
    bypass_permissions_overrides_protected_walls: false,
    bypass_permissions_restriction: bypassRestriction,
    protected_primitive_routing_allowed: true,
  },
]

export const internalDirectories = new Set(['__tests__', '_shared', 'shared', 'testing'])
export const antOnlyTools = new Set([
  'ConfigTool',
  'REPLTool',
  'SuggestBackgroundPRTool',
  'TungstenTool',
])
export const testOnlyTools = new Set(['TestingPermissionTool'])
export const unsupportedTools = new Set(['McpAuthTool', 'SyntheticOutputTool'])
export const featureGatedTools = new Set([
  'CtxInspectTool',
  'CronCreateTool',
  'CronDeleteTool',
  'CronListTool',
  'EnterWorktreeTool',
  'ExitWorktreeTool',
  'LSPTool',
  'ListPeersTool',
  'MonitorTool',
  'OverflowTestTool',
  'PowerShellTool',
  'PushNotificationTool',
  'RemoteTriggerTool',
  'ScheduleCronTool',
  'SendUserFileTool',
  'SleepTool',
  'SnipTool',
  'SubscribePRTool',
  'TeamCreateTool',
  'TeamDeleteTool',
  'TerminalCaptureTool',
  'VerifyPlanExecutionTool',
  'WebBrowserTool',
  'WorkflowTool',
])
