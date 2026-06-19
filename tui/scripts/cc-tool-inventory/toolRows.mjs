import {
  TASK13_EVIDENCE_PATH,
  TASK13_TEST_ID,
  TASK3_EVIDENCE_PATH,
  TASK3_TEST_ID,
  TASK4_EVIDENCE_PATH,
  TASK4_TEST_ID,
  TASK5_EVIDENCE_PATH,
  TASK5_TEST_ID,
  antOnlyTools,
  featureGatedTools,
  testOnlyTools,
  unsupportedTools,
} from './config.mjs'
import { isConcretePath } from './sourceSnapshots.mjs'

export function buildRow(seed, compareSources, writeDiffArtifact) {
  const ccPath = seed.cc_source_path ?? 'not-present-in-cc'
  const status = featureStatus(seed.tool_name, ccPath)
  const group = ccGroup(seed.tool_name)
  const tier = trustTier(seed.tool_name, group)
  const initialExposure = exposureState(seed.tool_name, status, group, tier)
  const seedWithDefaults = {
    cc_source_path: ccPath,
    ummaya_path: seed.ummaya_path ?? 'missing',
    ...seed,
  }
  const comparison = compareSources(
    seedWithDefaults.cc_source_path,
    seedWithDefaults.ummaya_path,
  )
  const parity = parityStatus(seedWithDefaults, status, initialExposure, comparison)
  const exposure = parity === 'missing' ? 'unsupported' : initialExposure
  const protectedRouting = isProtectedPrimitiveRouting(seed.tool_name, tier, exposure)
  const policyId = exposurePolicyId(tier)
  const hasUmmayaPath = seed.ummaya_path && seed.ummaya_path !== 'missing'
  const blocked = blockedReason(seedWithDefaults, status, parity, comparison)
  const diffArtifact =
    parity === 'modified'
      ? writeDiffArtifact(
          seed.tool_name,
          seedWithDefaults.cc_source_path,
          seedWithDefaults.ummaya_path,
          parity,
          comparison,
        )
      : 'not-applicable'

  return {
    tool_name: seed.tool_name,
    cc_group: group,
    source_path: sourcePath(seedWithDefaults),
    cc_source_path: seedWithDefaults.cc_source_path,
    ummaya_path: seedWithDefaults.ummaya_path,
    feature_status: status,
    parity_status: parity,
    status: parity,
    diff_status: comparison.diff_status,
    parity_diff_artifact: diffArtifact,
    blocked_reason: blocked,
    registered_capability: Boolean(hasUmmayaPath && status !== 'unsupported'),
    exposure_state: exposure,
    trust_tier: tier,
    exposure_policy_id: policyId,
    permission_mode_boundary: permissionModeBoundary(exposure, tier, protectedRouting),
    permission_policy: permissionPolicy(status, tier, exposure, protectedRouting),
    default_roots: group === 'file-search-edit' || group === 'shell-system' ? 'workspace' : 'not-applicable',
    mcp_server_class: group === 'mcp' ? 'trusted-configured' : 'not-mcp',
    protected_primitive_routing: protectedRouting,
    protected_primitive_reason: protectedPrimitiveReason(seed.tool_name),
    accepted_divergence: acceptedDivergence(
      seedWithDefaults,
      status,
      parity,
      comparison,
      blocked,
    ),
    tests: [TASK3_TEST_ID, TASK4_TEST_ID, TASK5_TEST_ID, TASK13_TEST_ID],
    evidence: [TASK3_EVIDENCE_PATH, TASK4_EVIDENCE_PATH, TASK5_EVIDENCE_PATH, TASK13_EVIDENCE_PATH],
    test_evidence: [TASK4_TEST_ID, TASK5_TEST_ID, TASK13_TEST_ID],
  }
}

function isUmmayaSpecific(name, ccPath) {
  return ccPath === 'not-present-in-cc' || name.endsWith('Primitive') || [
    'AdapterTool',
    'CalculatorTool',
    'DateParserTool',
    'DocumentPrimitive',
    'ExportPDFTool',
    'TranslateTool',
    'WorkspaceToolAdapter',
  ].includes(name)
}

function featureStatus(name, ccPath) {
  if (isUmmayaSpecific(name, ccPath)) return 'UMMAYA-specific'
  if (unsupportedTools.has(name)) return 'unsupported'
  if (testOnlyTools.has(name)) return 'test-only'
  if (antOnlyTools.has(name)) return 'ant-only'
  if (featureGatedTools.has(name)) return 'feature-gated'
  if (ccPath === 'missing') return 'unsupported'
  return 'default'
}

function ccGroup(name) {
  if (name.endsWith('Primitive') || ['AdapterTool', 'WorkspaceToolAdapter'].includes(name)) {
    return 'ummaya-primitive'
  }
  if (/^(File|Glob|Grep|Notebook)/u.test(name)) return 'file-search-edit'
  if (/(Bash|PowerShell|REPL|Config|Worktree|Terminal|CtxInspect)/u.test(name)) {
    return 'shell-system'
  }
  if (/(Web|Brief|SendUserFile)/u.test(name)) return 'web-source'
  if (/(Mcp|MCP)/u.test(name)) return 'mcp'
  if (/(Cron|Remote|Monitor|Sleep|PushNotification|SubscribePR|ListPeers)/u.test(name)) {
    return 'schedule-remote'
  }
  if (/(Skill|Workflow|ToolSearch)/u.test(name)) return 'skill-workflow'
  if (/(Testing|Overflow|LSP|Tungsten)/u.test(name)) return 'test-dev-only'
  return 'agent-task'
}

function trustTier(name, group) {
  if (group === 'ummaya-primitive') return ['LookupPrimitive', 'ResolveLocationPrimitive'].includes(name) ? 0 : 5
  if (group === 'file-search-edit') return /(Edit|Write|Notebook)/u.test(name) ? 1 : 0
  if (group === 'shell-system') return 2
  if (group === 'web-source' || group === 'mcp') return 3
  if (group === 'agent-task' || group === 'skill-workflow' || group === 'schedule-remote') return 4
  return 0
}

function exposurePolicyId(tier) {
  return `tier-${tier}`
}

function isAlwaysLoadedPrimitive(name) {
  return [
    'LookupPrimitive',
    'ResolveLocationPrimitive',
    'SubmitPrimitive',
    'VerifyPrimitive',
    'DocumentPrimitive',
  ].includes(name)
}

function protectedPrimitiveReason(name) {
  if (name === 'DocumentPrimitive') {
    return 'protected primitive routing: document and binary mutation must pass through DocumentPrimitive approval and cannot use raw file-write bypasses.'
  }
  if (name === 'SubmitPrimitive') {
    return 'protected primitive routing: protected AX submission remains visible as the intent boundary, but execution still requires identity, consent, and agency policy checks.'
  }
  if (name === 'VerifyPrimitive') {
    return 'protected primitive routing: protected AX identity and verification checks remain visible as the consent boundary, but PIPA and identity walls are bypass-immune.'
  }
  return ''
}

function isProtectedPrimitiveRouting(name, tier, exposure) {
  return tier >= 1 && exposure === 'always-loaded' && protectedPrimitiveReason(name).length > 0
}

function exposureState(name, status, group, tier) {
  if (status === 'unsupported' || status === 'test-only') return 'unsupported'
  if (isAlwaysLoadedPrimitive(name)) return 'always-loaded'
  if (status === 'ant-only' || status === 'feature-gated') return 'hidden'
  if (group === 'file-search-edit' && tier === 0) return 'deferred-searchable'
  if (tier >= 1) return 'permission-gated-callable'
  return 'deferred-searchable'
}

function permissionModeBoundary(exposure, tier, protectedRouting) {
  if (protectedRouting) return 'bypass-blocked'
  if (exposure !== 'permission-gated-callable') return 'not-applicable'
  if (tier === 1) return 'acceptEdits'
  if (tier === 4) return 'plan'
  if (tier >= 2) return 'bypass-blocked'
  return 'default'
}

function permissionPolicy(status, tier, exposure, protectedRouting) {
  const policyId = exposurePolicyId(tier)
  if (status === 'unsupported' || exposure === 'unsupported') {
    return `blocked: ${policyId}; docs/requirements/cc-tool-layer-scope-contract.md`
  }
  if (protectedRouting) {
    return `${policyId}: protected primitive routing; docs/vision.md Permission Pipeline and docs/requirements/cc-tool-layer-scope-contract.md`
  }
  if (exposure === 'permission-gated-callable') {
    return `${policyId}: explicit permission gauntlet; docs/vision.md Permission Pipeline and docs/requirements/cc-tool-layer-scope-contract.md`
  }
  return `${policyId}: bounded exposure; docs/requirements/cc-tool-layer-scope-contract.md`
}

function parityStatus(seed, status, exposure, comparison) {
  if (status === 'unsupported') return 'unsupported'
  if (comparison.diff_status === 'missing-ummaya-source' || seed.ummaya_path === 'missing') {
    return 'missing'
  }
  if (exposure === 'hidden') return 'registry-hidden'
  if (isUmmayaSpecific(seed.tool_name, seed.cc_source_path)) return 'modified'
  return comparison.diff_status === 'identical' ? 'source-parity' : 'modified'
}

function blockedReason(seed, status, parity, comparison) {
  if (parity === 'missing') return 'UMMAYA implementation path is missing.'
  if (status === 'unsupported') {
    if (seed.cc_source_path === 'missing' || comparison.diff_status === 'missing-cc-source') {
      return 'Restored Claude Code source path is missing; row remains unsupported.'
    }
    return 'Tool is blocked from callable UMMAYA exposure by the scope contract.'
  }
  return ''
}

function sourcePath(seed) {
  if (isConcretePath(seed.cc_source_path)) return seed.cc_source_path
  if (isConcretePath(seed.ummaya_path)) return seed.ummaya_path
  return 'blocked'
}

function acceptedDivergence(seed, status, parity, comparison, blocked) {
  if (parity === 'source-parity') return 'No accepted divergence; source digest matches restored Claude Code.'
  if (parity === 'registry-hidden') {
    return 'Capability exists but remains hidden until Task 5 exposure policy and later registry work allow it.'
  }
  if (blocked) return blocked
  if (status === 'unsupported') return 'Unsupported by current UMMAYA scope contract.'
  if (seed.cc_source_path === 'not-present-in-cc') {
    return 'UMMAYA tool-surface swap; not present in restored Claude Code.'
  }
  if (comparison.diff_status === 'different') {
    return 'Source differs from restored Claude Code; Task 4 records a bounded diff artifact.'
  }
  return 'UMMAYA-specific behavior is recorded without claiming source parity.'
}
