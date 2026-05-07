# Phase 1 — Data Model

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md) | **Date**: 2026-04-25

The 5 entities below are the load-bearing data shapes for the P5 Plugin DX. All Pydantic v2; all `frozen=True, extra="forbid"`. JSON Schema for the canonical contract entity is in [`contracts/manifest.schema.json`](./contracts/manifest.schema.json).

---

## 1 · `PluginManifest`

The top-level contract a plugin author writes (as `manifest.yaml`) and the registry consumes. Composes the existing Spec 022/031 `AdapterRegistration`; adds plugin-specific identity, tier, PIPA, provenance, OTEL, and discovery fields.

| Field | Type | Required | Default | Constraints | Source |
|---|---|---|---|---|---|
| `plugin_id` | `str` | ✓ | — | regex `^[a-z][a-z0-9_]*$`, max_length 64 | FR-019 |
| `version` | `str` | ✓ | — | SemVer regex `^\d+\.\d+\.\d+$` | FR-019 |
| `adapter` | `AdapterRegistration` | ✓ | — | full Spec 022/031 invariant chain (V1–V4 + V6) | R-6 |
| `tier` | `Literal["live", "mock"]` | ✓ | — | enum-set | FR-019 |
| `mock_source_spec` | `str \| None` | conditional | None | required + non-empty when `tier=="mock"`; URL or attribution string | FR-019 + R-1 Q7-MOCK-SOURCE |
| `processes_pii` | `bool` | ✓ | `True` | fail-closed default per Constitution §II | FR-023 |
| `pipa_trustee_acknowledgment` | `PIPATrusteeAcknowledgment \| None` | conditional | None | required when `processes_pii=True` | FR-014 + R-4 |
| `slsa_provenance_url` | `str` | ✓ | — | regex `^https://github\.com/` | FR-018 + R-3 |
| `otel_attributes` | `dict[str, str]` | ✓ | — | must contain key `"kosmos.plugin.id"` with value `== plugin_id` | FR-021 + Spec 021 |
| `search_hint_ko` | `str` | ✓ | — | min_length 1, recommended ≥ 3 Korean nouns (R-1 Q4-HINT-NOUNS) | FR-019 + R-1 Q4-HINT-KO |
| `search_hint_en` | `str` | ✓ | — | min_length 1 | R-1 Q4-HINT-EN |
| `permission_layer` | `Literal[1, 2, 3]` | ✓ | — | informational; Spec 033 is enforcement | R-1 Q5-LAYER-DECLARED |

### Cross-field validators

```python
@model_validator(mode="after")
def _v_mock_source(self) -> "PluginManifest":
    if self.tier == "mock" and not self.mock_source_spec:
        raise ValueError("mock_source_spec is required when tier='mock'")
    if self.tier == "live" and self.mock_source_spec is not None:
        raise ValueError("mock_source_spec must be None when tier='live'")
    return self

@model_validator(mode="after")
def _v_pipa_required(self) -> "PluginManifest":
    if self.processes_pii and self.pipa_trustee_acknowledgment is None:
        raise ValueError("pipa_trustee_acknowledgment required when processes_pii=True (PIPA §26)")
    if not self.processes_pii and self.pipa_trustee_acknowledgment is not None:
        raise ValueError("pipa_trustee_acknowledgment must be None when processes_pii=False")
    return self

@model_validator(mode="after")
def _v_pipa_hash(self) -> "PluginManifest":
    if self.pipa_trustee_acknowledgment is None:
        return self
    expected = canonical_acknowledgment.CANONICAL_ACKNOWLEDGMENT_SHA256
    actual = self.pipa_trustee_acknowledgment.acknowledgment_sha256
    if actual != expected:
        raise ValueError(
            f"acknowledgment_sha256 mismatch: expected {expected}, got {actual}. "
            "Re-read docs/plugins/security-review.md and update."
        )
    return self

@model_validator(mode="after")
def _v_otel_attribute(self) -> "PluginManifest":
    if self.otel_attributes.get("kosmos.plugin.id") != self.plugin_id:
        raise ValueError(
            f'otel_attributes["kosmos.plugin.id"] must equal plugin_id ({self.plugin_id})'
        )
    return self

@model_validator(mode="after")
def _v_namespace(self) -> "PluginManifest":
    expected_prefix = f"plugin.{self.plugin_id}."
    if not self.adapter.tool_id.startswith(expected_prefix):
        raise ValueError(
            f"adapter.tool_id must start with '{expected_prefix}' (got {self.adapter.tool_id!r})"
        )
    suffix = self.adapter.tool_id[len(expected_prefix):]
    if suffix not in {"lookup", "submit", "verify"}:
        raise ValueError(
            f"adapter.tool_id verb suffix must be one of the active plugin primitives (got {suffix!r})"
        )
    return self
```

### Lifecycle / state transitions

`PluginManifest` is **immutable per release** (`frozen=True`). State transitions happen at the *bundle* level, not the manifest level:

```
unpublished
   │ (slsa-github-generator on git tag push)
   ▼
published_unverified  ← bundle + .intoto.jsonl on GitHub Releases
   │ (catalog generator picks up release, adds to kosmos-plugin-store/index.json)
   ▼
catalogued
   │ (citizen runs `kosmos plugin install <name>`)
   ▼
verified  ← slsa-verifier exit 0 + manifest_schema.model_validate pass
   │ (installer.py writes to ~/.kosmos/memdir/user/plugins/<plugin_id>/)
   ▼
installed
   │ (registry.py auto-discovery rebuilds BM25 index entry)
   ▼
discoverable  ← appears in lookup(mode="search") results
   │ (citizen runs `kosmos plugin uninstall <name>`)
   ▼
uninstalled  ← directory removed; consent receipt for uninstall written
```

Failed verification (slsa-verifier exit ≠ 0 OR manifest validation fail) aborts the install; no state transition happens. The bundle stays in `~/.kosmos/cache/plugin-bundles/<plugin_id>-<sha>.tar.gz` for forensic inspection.

---

## 2 · `PIPATrusteeAcknowledgment`

Nested model required when `PluginManifest.processes_pii=True`. Encodes the PIPA §26 trustee chain so the validation workflow can mechanically reject missing or hash-tampered acknowledgments.

| Field | Type | Required | Constraints | Source |
|---|---|---|---|---|
| `trustee_org_name` | `str` | ✓ | min_length 1; org legal name | R-1 Q6-PIPA-ORG |
| `trustee_contact` | `str` | ✓ | min_length 1; email or phone | R-1 Q6-PIPA-ORG |
| `pii_fields_handled` | `list[str]` | ✓ | min_length 1; e.g. `["resident_registration_number", "phone_number"]` | R-1 Q6-PIPA-FIELDS-LIST |
| `legal_basis` | `str` | ✓ | min_length 1; PIPA article reference | R-4 |
| `acknowledgment_sha256` | `str` | ✓ | regex `^[a-f0-9]{64}$`; equals canonical hash | R-4 + R-1 Q6-PIPA-HASH |

`frozen=True, extra="forbid"`. No internal validators (validation is done by the parent `PluginManifest._v_pipa_hash`).

The canonical acknowledgment text is stored in `docs/plugins/security-review.md` between `<!-- CANONICAL-PIPA-ACK-START -->` and `<!-- CANONICAL-PIPA-ACK-END -->` markers. The hash is computed at module import time by `src/kosmos/plugins/canonical_acknowledgment.py:_compute_canonical_hash()` and exposed as the constant `CANONICAL_ACKNOWLEDGMENT_SHA256: str`. See [`contracts/pipa-acknowledgment.md`](./contracts/pipa-acknowledgment.md) for the canonical text content.

---

## 3 · `ReviewChecklistItem`

The 50-item review checklist source-of-truth row. Lives as YAML in `tests/fixtures/plugin_validation/checklist_manifest.yaml`; rendered as Markdown in `docs/plugins/review-checklist.md`. The `plugin-validation.yml` workflow iterates over the YAML to build its job matrix — no hand-written `if`/`else` branches in the workflow file.

| Field | Type | Required | Constraints | Source |
|---|---|---|---|---|
| `id` | `str` | ✓ | regex `^Q\d{1,2}-[A-Z][A-Z0-9-]*$` (e.g. `Q3-V1-NO-EXTRA`) | R-1 |
| `description_ko` | `str` | ✓ | min_length 1 | R-1 |
| `description_en` | `str` | ✓ | min_length 1 | R-1 |
| `source_rule` | `str` | ✓ | references Constitution principle, AGENTS.md section, or Spec NNN | Constitution §I + R-1 |
| `check_type` | `Literal["static", "unit", "workflow"]` | ✓ | `static` = AST/regex; `unit` = pytest assertion; `workflow` = workflow step | R-1 |
| `check_implementation` | `str` | ✓ | dotted path or workflow-step id (e.g. `kosmos.plugins.checks.q1_pyv2:check`) | R-1 |
| `failure_message_ko` | `str` | ✓ | min_length 1; user-facing Korean error shown by workflow on fail | FR-015 |
| `failure_message_en` | `str` | ✓ | min_length 1 | FR-015 |

The Pydantic model `ReviewChecklistManifest = TypeAdapter(list[ReviewChecklistItem])` is used to load + validate the YAML file at workflow startup. CI fails fast if any item is malformed or if the count is not exactly 50 (audit invariant).

---

## 4 · `CatalogEntry`

One row in `kosmos-plugin-store/index.json` describing a published plugin. Source-of-truth for `kosmos plugin install <name>` resolution.

| Field | Type | Required | Constraints | Source |
|---|---|---|---|---|
| `name` | `str` | ✓ | regex `^[a-z][a-z0-9-]*$`; matches the repo name (without `kosmos-plugin-` prefix) | FR-017 |
| `plugin_id` | `str` | ✓ | regex `^[a-z][a-z0-9_]*$`; matches `PluginManifest.plugin_id` | FR-017 |
| `latest_version` | `str` | ✓ | SemVer regex | FR-017 |
| `versions` | `list[CatalogVersion]` | ✓ | min_length 1; sorted descending by version | FR-017 |
| `tier` | `Literal["live", "mock"]` | ✓ | mirrors latest manifest's tier | FR-017 |
| `permission_layer` | `Literal[1, 2, 3]` | ✓ | mirrors latest manifest | FR-017 |
| `processes_pii` | `bool` | ✓ | mirrors latest manifest | FR-017 |
| `trustee_org_name` | `str \| None` | conditional | required when `processes_pii=True` | FR-014 |
| `last_published_iso` | `str` | ✓ | ISO-8601 timestamp UTC | FR-017 |

Where `CatalogVersion` is:

| Field | Type | Required | Constraints |
|---|---|---|---|
| `version` | `str` | ✓ | SemVer |
| `bundle_url` | `str` | ✓ | regex `^https://github\.com/.+\.tar\.gz$` |
| `provenance_url` | `str` | ✓ | regex `^https://github\.com/.+\.intoto\.jsonl$` |
| `bundle_sha256` | `str` | ✓ | regex `^[a-f0-9]{64}$` |
| `published_iso` | `str` | ✓ | ISO-8601 |

`index.json` schema export: [`contracts/catalog-index.schema.json`](./contracts/catalog-index.schema.json).

---

## 5 · `PluginConsentReceipt` (extension of Spec 035 ConsentRecord)

When the citizen runs `kosmos plugin install <name>`, an append-only consent receipt is written to the existing Spec 035 ledger at `~/.kosmos/memdir/user/consent/`. Mirrors the existing schema with one new `action_type` discriminator value: `"plugin_install"` (or `"plugin_uninstall"`).

| Field | Type | Required | Constraints | Source |
|---|---|---|---|---|
| `receipt_id` | `str` | ✓ | UUID v7 (Spec 027 pattern) | Spec 035 |
| `timestamp_iso` | `str` | ✓ | ISO-8601 UTC | Spec 035 |
| `action_type` | `Literal["plugin_install", "plugin_uninstall"]` | ✓ | new enum values | This spec |
| `plugin_id` | `str` | ✓ | matches installed plugin | This spec |
| `plugin_version` | `str` | ✓ | SemVer | This spec |
| `slsa_verification` | `Literal["passed", "failed", "skipped"]` | ✓ | `skipped` only allowed in dev mode w/ explicit `KOSMOS_PLUGIN_SLSA_SKIP=1` env | R-3 |
| `trustee_org_name` | `str \| None` | conditional | required if installed plugin's `processes_pii=True` | FR-014 |
| `consent_ledger_position` | `int` | ✓ | append-only sequence (Spec 035 invariant) | Spec 035 |

Persistence rules (inherited from Spec 035):
- One JSON file per receipt: `~/.kosmos/memdir/user/consent/<receipt_id>.json`
- `fsync()` on write; `.consumed` marker file pattern only applies to mailbox messages, not consent receipts
- Append-only — no in-place edits; revocation is a *new* receipt with `action_type="plugin_uninstall"` referencing the install receipt's id

---

## Entity relationships

```
PluginManifest (frozen)
  ├─ embeds: AdapterRegistration  ← Spec 031, free reuse
  └─ embeds: PIPATrusteeAcknowledgment (optional)

CatalogEntry
  ├─ resolves to: PluginManifest (via bundle_url + provenance_url)
  └─ list[CatalogVersion] (immutable history)

ReviewChecklistItem  ← independent registry, drives plugin-validation.yml
  └─ check_implementation → src/kosmos/plugins/checks/*.py

PluginConsentReceipt  ← writes to Spec 035 ledger
  └─ references: PluginManifest.plugin_id + version (no FK; the ledger is append-only)

ToolRegistry (existing, Spec 022)
  └─ register_plugin_adapter(manifest) → BM25Index.add_or_update(...)
                                       → emit OTEL span (kosmos.plugin.id=...)
```

---

## Storage layout summary

```
~/.kosmos/memdir/user/plugins/                  # NEW
├── index.json                                   # cached catalog snapshot for offline kosmos plugin list
└── <plugin_id>/                                 # one dir per installed plugin
    ├── manifest.yaml                            # PluginManifest.model_dump_json() + yaml-encoded
    ├── adapter.py                               # the contributed adapter code
    ├── schema.py                                # the contributed Pydantic schemas
    ├── tests/                                   # the contributed tests (replayed at install for sanity)
    │   ├── test_adapter.py
    │   └── fixtures/<tool_id>.json
    ├── README.ko.md
    └── .signature/                              # SLSA verification artifacts (kept for audit)
        ├── bundle.tar.gz
        ├── provenance.intoto.jsonl
        └── verify-result.json                   # slsa-verifier output

~/.kosmos/memdir/user/consent/                  # EXISTS (Spec 035) — extended with plugin_install / plugin_uninstall action types
└── <receipt_id>.json                            # PluginConsentReceipt records appended

~/.kosmos/cache/plugin-bundles/                 # NEW — forensic cache
└── <plugin_id>-<sha>.tar.gz                     # bundle retained on failed verification

~/.kosmos/vendor/slsa-verifier/                 # NEW (per R-3) — vendored binary
└── <platform>/slsa-verifier                     # one per darwin-amd64 / darwin-arm64 / linux-amd64 / linux-arm64
```

All paths are KOSMOS_-prefixed-env-var overridable (per AGENTS.md):
- `KOSMOS_PLUGIN_INSTALL_ROOT` (default `~/.kosmos/memdir/user/plugins`)
- `KOSMOS_PLUGIN_BUNDLE_CACHE` (default `~/.kosmos/cache/plugin-bundles`)
- `KOSMOS_PLUGIN_VENDOR_ROOT` (default `~/.kosmos/vendor`)
- `KOSMOS_PLUGIN_SLSA_SKIP` (default unset; opt-in to skip verification in dev only)
- `KOSMOS_PLUGIN_CATALOG_URL` (default `https://raw.githubusercontent.com/kosmos-plugin-store/index/main/index.json`)
