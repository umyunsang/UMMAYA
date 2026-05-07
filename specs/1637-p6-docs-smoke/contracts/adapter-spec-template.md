# Contract — AdapterSpec template

**Purpose**: defines the verbatim Markdown structure every adapter spec under `docs/api/` MUST follow. Authors of new adapter specs (during implement phase) copy this template, fill placeholders, and the result MUST satisfy spec FR-005.

**Validates**: SC-001 (active specs all complete), structural lint script.

---

```markdown
---
tool_id: <tool_id>
primitive: <lookup | submit | verify | resolve_location>
tier: <live | mock>
permission_tier: <1 | 2 | 3>
---

# <tool_id>

## Overview

<one-sentence purpose; describe what the adapter does for a citizen>

| Field | Value |
|---|---|
| Classification | <Live | Mock> · Permission tier <N> |
| Source | <ministry / agency / fixture origin> |
| Primitive | `<lookup | submit | verify | resolve_location>` |
| Module | `src/kosmos/tools/<path>.py` |

## Envelope

**Input model**: `<ModuleClass>` defined at `src/kosmos/tools/<path>.py:<line-range>`.

| Field | Type | Required | Description |
|---|---|---|---|
| <field-1> | <type> | <yes/no> | <description> |
| ... | | | |

**Output model**: `<ModuleClass>` defined at `src/kosmos/tools/<path>.py:<line-range>`.

| Field | Type | Required | Description |
|---|---|---|---|
| <field-1> | <type> | <yes/no> | <description> |
| ... | | | |

## Search hints

- 한국어: `<korean-hint-1>`, `<korean-hint-2>`, ...
- English: `<english-hint-1>`, `<english-hint-2>`, ...

## Endpoint

<for Live tier>
- **data.go.kr endpoint**: `<endpoint-id>`
- **Source URL**: <ministry portal URL>
- **Authentication**: API key via `KOSMOS_<NAME>_API_KEY` (per Constitution IV)

<for Mock tier>
- **Mode**: Fixture-replay only
- **Public spec source**: <URL or document citation per memory `feedback_mock_evidence_based`>
- **Fixture path**: `tests/fixtures/<source>/<tool>/...` (or recorded fixture origin)

## Permission tier rationale

<one paragraph explaining why this adapter sits at tier 1, 2, or 3, citing Spec 033>

## Worked example

### Input envelope

```json
{
  "mode": "fetch",
  "tool_id": "<tool_id>",
  "params": {
    "<field-1>": "<example-value>",
    ...
  }
}
```

### Output envelope (success)

```json
{
  "tool_id": "<tool_id>",
  "result": {
    "<field-1>": "<example-value>",
    ...
  }
}
```

### Conversation snippet

```text
Citizen: <example Korean question>
KOSMOS: <expected Korean answer summarizing the adapter response>
```

## Constraints

- **Rate limit**: <e.g., "data.go.kr daily quota: 1000 requests"> or "N/A (fixture)" for Mock.
- **Freshness window**: <e.g., "data refreshed every 60 minutes upstream"> or "N/A".
- **Fixture coverage gaps**: <which response shapes are NOT in fixtures, if any>.
- **Error envelope examples**:
  - Tier-1 fail: <example>
  - Tier-2 / Tier-3 (auth) fail: <example>
  - Network timeout: <example>
```

---

## Lint rules (codify in implement phase)

A structural linter (proposed `scripts/lint_adapter_specs.py`, deferred to "Auto-generated adapter spec stubs from Pydantic docstrings" follow-up Epic) MUST verify:

1. YAML front matter parses; `tool_id`, `primitive`, `tier`, `permission_tier` all present and within allowed values.
2. All seven `## ...` headings present in the listed order.
3. Search-hints section contains at least one entry under `한국어:` and at least one under `English:`.
4. Live-tier specs contain a `data.go.kr endpoint:` line OR an explicit "ministry direct API" justification.
5. Mock-tier specs contain "Fixture-replay only" verbatim AND a public-spec citation.
6. Every Markdown link to a `src/kosmos/tools/...` path resolves to an existing file.

For this Epic, manual review during PR review substitutes for the linter; the linter itself is deferred-to-future-work table row 4.

## Reference precedents

- `docs/tools/koroad.md` — original P3-era heading order (preserved with the additions of Permission tier rationale and YAML front matter).
- `specs/1636-plugin-dx-5tier/contracts/manifest.schema.json` — YAML front matter pattern.
- Spec 033 — permission tier classification source.
