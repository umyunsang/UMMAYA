# CC Tool Layer Scope-Change Contract

Status: Active requirements contract for Task 1 of the CC original tool-layer
port lane.

input evidence: `docs/research/cc-original-tool-layer-port-2026-06-12.md`.

execution plan artifact: `.omo/plans/cc-original-tool-layer-port-lazycodex.md`.

## Purpose

UMMAYA remains the Claude Code original harness with two sanctioned swaps:
FriendliAI Serverless plus K-EXAONE as provider, and Korean national AX tool
surface as the user-intent domain. This contract reconciles the historical C6
helper-surface decision with the current direction to port the full Claude Code
original tool layer as support/runtime substrate.

The national AX primitive surface remains `find`, `locate`, `send`, and
`check`. Claude Code original tools such as read, search, edit, shell, web,
MCP, scheduling, workflow, and agent/task tools do not replace those primitives.
They may exist underneath the harness only according to the capability and
exposure rules below.

## Scope Terms

- `registered capability`: registered capability is not an exposure state. It
  means the runtime can construct or call a tool after feature flags, mode
  checks, registry policy, permission policy, and trust boundaries allow it.
- `always-loaded`: model-facing in the stable built-in prefix. This is allowed
  only for the national AX primitive surface and bounded Tier 0 support tools
  whose prompt/cache impact is accepted.
- `deferred-searchable`: discoverable through tool search or deferred loading.
  The schema is not part of the default prompt and must not flood the model
  context.
- `permission-gated-callable`: callable only after explicit permission approval
  or policy-backed preapproval. Local mutation, shell/system, network/source,
  MCP, and protected citizen-action tools default here unless stricter policy
  applies.
- `hidden`: registered internally but not model-facing for the current mode,
  server trust state, feature flag, user trust state, or kill-switch posture.
- `unsupported`: not callable in UMMAYA. The row must carry a blocker or
  accepted divergence reason before later tasks can revisit it.

Every future inventory row for the CC original tool-layer port must state both
whether the tool is a registered capability and which exposure state applies.
The two fields must never be collapsed into one boolean.

## Historical C6 Qualification

The earlier C6 helper-tool rule described the MVP citizen-facing helper surface.
It is no longer an active blanket prohibition on porting the Claude Code
original tool layer. Read, Write, Edit, Bash, Glob, Grep, and NotebookEdit may be
registered capabilities when source parity, policy, and trust-tier evidence
support them, but they are not automatically always-loaded.

The active distinction is:

- Read/search support can be always-loaded or deferred-searchable only when
  bounded to workspace policy, symlink resolution, transcript privacy, and
  evidence rules.
- Write, Edit, and NotebookEdit are permission-gated-callable by default and
  must not bypass `DocumentPrimitive` for document/binary mutation.
- Bash and other shell/system tools are permission-gated-callable by default and
  must keep command analysis, cwd/sandbox policy, cancellation, and destructive
  warnings observable.
- MCP, web/source acquisition, scheduling/remote, workflow, and agent/task tools
  require the trust boundary specified by their operation and may be hidden or
  unsupported until that policy exists.

## Non-Goals

This contract does not implement runtime tool behavior, create a second
registry, relax `check` or `send` consent boundaries, call live citizen
infrastructure from CI, or expose raw Claude Code developer tools as
always-loaded by default.
