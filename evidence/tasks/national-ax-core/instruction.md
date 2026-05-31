# UMMAYA National AX Core Evidence Task

Validate that UMMAYA's prompt-facing citizen-demand dataset remains natural,
versioned, domain-complete, and free of model-visible implementation hints.

The task is local-only. It must not call FriendliAI, KMA APIHub, data.go.kr,
identity providers, payment rails, utility operators, or other live
public-service channels.

Expected verifier behavior:

- Parse `evidence/scenarios/national_ax_citizen_requests_v1.yaml`.
- Resolve this task through `evidence/registry.yaml`.
- Reject adapter IDs, tool IDs, fixture references, and expected tool IDs when
  they appear in model-visible scenario or task metadata.
- Emit `evidence.v2` run evidence with task registry metadata and trace join keys.
