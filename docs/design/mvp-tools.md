# UMMAYA MVP — Main Tools Precision Design

> **Status**: Shipped design (Spec 022 merged). This document is the historical record for the MVP 2-tool facade as shipped.
> **Scope (as shipped)**: MVP ships **1 main tool** (`find`) and **1 primitive** (`locate`) on top of the existing 6-layer architecture in `docs/vision.md`.
> **Expansion**: The main-tool axis was reset to an active primitive harness design. Current active primitives are `find`, `locate`, `send`, and `check`; `subscribe` is deferred until UMMAYA has an app/push-notification runtime. All ministry- and domain-specific knowledge (eligibility, payment, certificate issuance, application submission, slot reservation, notification handoff) collapses into adapters under `src/ummaya/tools/<ministry>/<adapter>.py`; the main surface stays domain-agnostic. The previous 8-verb proposal and its Discussion have been retired.
> **Last updated**: 2026-05-07 (8-verb expansion retired; active primitive harness corrected after subscribe deferral. Body preserved at 2026-04-16 shipped-MVP state).

## 1. Scope and non-goals

### In scope (MVP)
- Two LLM-visible "main" tools that together cover the common citizen-query pattern: *resolve a place → query a government dataset*.
- A thin **Facade + Tool Search hybrid** surface where hot-path tools are always resident and cold-path API adapters load lazily.
- A seed set of **4 per-API adapters** (KOROAD · KMA · HIRA · NMC) that exercise every canonical return shape (`collection`, `timeseries`) and every spatial-parameter convention (sido/gugun codes, KMA LCC grid, WGS84 coord+radius, distance-sorted WGS84) so `find` is validated end-to-end against real provider heterogeneity.

### Explicit non-goals
- Domain-specific action verbs (eligibility check, payment, certificate issuance, application submission, slot reservation, alert subscription) — **deferred at shipped-MVP time (2026-04-16)** and **no longer tracked as main-tool verbs**. Active primitives treat these as adapter concerns beneath `find`, `locate`, `send`, and `check`. Legal/auth barriers for live promotion remain (student project, PASS TEE-bound, 공동인증서 NDA-closed); see `docs/vision.md § access matrix`.
- Writing/mutating endpoints. MVP is **read-only**.
- Full coverage of `data.go.kr`. MVP needs only enough adapters to prove the retrieval pattern works.
- Multi-turn planning, permission pipeline depth beyond fail-closed defaults.

## 2. Key research findings that shape the design

Citations abbreviated; full URLs in § 11.

| Finding | Source | Implication for UMMAYA |
|---|---|---|
| **Single "universal" API-call facade hallucinates 30–45% of params** | ToolBench (arXiv:2307.16789), API-Bank (arXiv:2304.08244) | Do NOT expose `lookup(api_id, params)` as a flat tool. |
| **Hierarchical retrieval router beats flat facades** on 16k-tool benchmarks | AnyTool (arXiv:2402.04253) | `find` must be a *retrieval surface*, not a monolithic dispatcher. |
| **Tree dispatcher anti-pattern**: nested tool calls amplify failure up to 17× | NESTful (EMNLP'25, arXiv:2409.03797); multi-agent-trap survey | Dispatcher tool calling sub-tools is banned. Use 2-step flat chain: retrieve → call. |
| **Anthropic Tool Search Tool (BM25)** ships as first-party primitive (2025-11) | Anthropic docs; Arcade, Spring, Stacklok replications | Pattern is validated. UMMAYA reimplements client-side (FriendliAI/K-EXAONE has no server-side equivalent). |
| **Cursor Dynamic Context Discovery: 46.9% token reduction** (production A/B) | Cursor blog (2026-01) | Realistic ceiling; design for 30–50% savings, not 90%. |
| **Structured envelope `{items, next_cursor, meta}` + opaque cursor** | LangChain / MCP reference servers; data.go.kr convention | Canonical shape for `find` return. Offset/page pagination causes loops. |
| **`shape` discriminator beats inference** (record / timeseries / collection) | Anthropic computer-use; Cursor `@docs` | Return `shape` field explicitly. |
| **Claude Code tool convention: 2–4 required params, mode enums over booleans, discriminated-union returns, fail-closed defaults via `buildTool()` factory** | `.references/claude-reviews-claude/docs/chapters/02-tool-system.md` | Direct blueprint — UMMAYA adopts the same shape. |
| **Korean geocoding: 카카오 Local + 도로명주소 + SGIS** covers all MVP needs with zero-cost student access | API survey (this doc's Agent C) | `locate` backend is a 3-provider deterministic chain. |
| **Korean-public-API specifics**: ~`response.header.resultCode` envelope, XML default with `?type=json`, 429 signalled in-band not via HTTP status | data.go.kr convention; KOROAD docs | Adapter layer must normalize envelope; client HTTP status is insufficient. |

## 3. Architecture overview

### 3.1 Two-tier surface (Facade + Tool Search hybrid)

```
┌─────────────────────────────────────────────────────────────┐
│ LLM hot path  —  always resident in the tool list           │
│                                                             │
│   ┌────────────────────┐     ┌────────────────────┐        │
│   │  resolve_location  │     │       lookup       │        │
│   │   (thin facade)    │     │ (retrieval surface)│        │
│   └─────────┬──────────┘     └──────────┬─────────┘        │
│             │                           │                   │
└─────────────┼───────────────────────────┼──────────────────┘
              │                           │
              ▼                           ▼
   ┌──────────────────────┐    ┌─────────────────────────────┐
   │  3 geocoding back-   │    │  Tool Search index (BM25)   │
   │  ends, deterministic │    │  over per-API adapters      │
   │  dispatch chain      │    │  — deferred, lazy loaded    │
   │                      │    │                             │
   │  • kakao.local       │    │  • koroad_accident_hazard_  │
   │  • juso.go.kr        │    │      search                 │
   │  • sgis.kostat.go.kr │    │  • kma_forecast_fetch       │
   └──────────────────────┘    │  • hira_hospital_search     │
                               │  • nmc_emergency_search     │
                               │  • …                        │
                               └─────────────────────────────┘
                                            │
                                    (on lookup.fetch)
                                            ▼
                               Typed Pydantic v2 adapter
                               call + envelope normalization
```

- **Hot path (always loaded)**: 2 tools, total schema budget ~1–2K tokens.
- **Cold path**: N per-API adapters, registered via `GovAPITool` (`docs/tool-adapters.md`). Schemas NOT loaded until `find` surfaces them.
- **Dispatch flatness**: every path is at most **2 LLM tool calls** — never a dispatcher-calls-subtool chain. This avoids the 17× compound failure amplification (NESTful).

### 3.2 Why not one universal `lookup(api_id, params)` facade?

Published benchmarks (ToolBench, API-Bank, AnyTool) show flat universal facades fail on **param hallucination**: the model guesses `startDate` vs `start_date`, `region` vs `sido`, omits required auth params, etc. Rate: 30–45% of failures. A hierarchical retrieve-then-call pattern shifts failures to tool-selection (~20%), which is recoverable via retrieval re-ranking.

UMMAYA `find` therefore exposes **two operations** — `search` (retrieve candidates) and `fetch` (invoke the selected adapter with typed args). The LLM sees one tool with a `mode` discriminator, which is how Claude Code's `Grep` handles `output_mode: "content"|"files_with_matches"|"count"`.

## 4. Tool #1 — `locate`

### 4.1 Problem scope

Turn natural-language place references ("강남역", "서울 종로구 세종대로 175", "37.5,127.0", "상암월드컵경기장") into structured location data consumable by `find` adapters: WGS84 coordinates, road-name address, jibun address, 10-digit 행정동 code.

Small, bounded domain → **true thin facade with deterministic dispatch** is the right pattern here (distinct from `find`'s retrieval pattern).

### 4.2 Public schema

```python
# Pydantic v2, strict. Follows Claude Code's thin-params convention.

class ResolveWant(str, Enum):
    coords            = "coords"              # WGS84 (lat, lon)
    adm_cd            = "adm_cd"              # 10-digit 행정동 code
    coords_and_admcd  = "coords_and_admcd"    # bundle: coords + adm_cd (MVP default)
    road_address      = "road_address"        # 도로명주소
    jibun_address     = "jibun_address"
    poi               = "poi"                 # POI id + canonical name + coords
    all               = "all"                 # union of all variants — opt-in, costly
    # NOTE: kma_grid (nx, ny) and sido_gugun codes are derived inside their
    # respective adapters from coords/adm_cd. resolve_location does not
    # expose them as first-class 'want' variants — that would leak provider
    # specifics (LCC projection, 2023 code shifts) into a generic tool.

class ResolveLocationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(
        description="Natural-language place reference in Korean or English. "
                    "Examples: '강남역', '서울시 종로구 세종대로 175', '37.5,127.0'.",
    )
    want: ResolveWant = Field(
        default=ResolveWant.coords_and_admcd,
        description="What shape of location data to return. Default 'coords_and_admcd' "
                    "covers the common case: WGS84 + 10-digit 행정동 code. Adapters derive "
                    "provider-specific variants (KOROAD siDo/guGun, KMA nx/ny) from these.",
    )
    near: Optional[tuple[float, float]] = Field(
        default=None,
        description="Optional (lat, lon) anchor to disambiguate ambiguous names "
                    "(e.g., multiple '중앙역' cases). WGS84.",
    )
```

**Why these params** (2 required + 1 optional mode flag, 1 optional anchor):
- Mirrors Claude Code's `Grep(pattern, path?, -A/-B/-C/mode)` shape.
- `want` is a discriminated enum, not a boolean explosion (Claude Code convention, `02-tool-system.md:521`).
- `near` handles the single most common disambiguation case; everything else is deferred to `query` rewrite by the LLM.

### 4.3 Return shape (discriminated union)

```python
class CoordResult(BaseModel):
    kind: Literal["coords"] = "coords"
    lat: float
    lon: float
    confidence: Literal["high", "medium", "low"]
    source: Literal["kakao", "juso", "sgis"]

class AdmCodeResult(BaseModel):
    kind: Literal["adm_cd"] = "adm_cd"
    code: str = Field(pattern=r"^\d{10}$")
    name: str          # e.g. "서울특별시 강남구 역삼1동"
    level: Literal["sido", "sigungu", "emd"]
    source: Literal["juso", "sgis", "kakao"]

class AddressResult(BaseModel):
    kind: Literal["address"] = "address"
    road_address: Optional[str]
    jibun_address: Optional[str]
    zipcode: Optional[str]
    bd_mgt_sn: Optional[str]   # 건물관리번호 (juso.go.kr)
    rn_mgt_sn: Optional[str]   # 도로명코드
    source: Literal["juso", "kakao"]

class POIResult(BaseModel):
    kind: Literal["poi"] = "poi"
    poi_id: str
    name: str
    category: Optional[str]
    coords: tuple[float, float]
    source: Literal["kakao"]   # kakao is the only MVP POI source

class ResolveError(BaseModel):
    kind: Literal["error"] = "error"
    reason: Literal["not_found", "ambiguous", "rate_limited", "upstream_down"]
    candidates: list[str] = Field(default_factory=list)  # populated when ambiguous
    suggested_rewrite: Optional[str] = None              # LLM-consumable hint

ResolveLocationOutput = Annotated[
    Union[CoordResult, AdmCodeResult, AddressResult, POIResult, ResolveError],
    Field(discriminator="kind"),
]

# For want ∈ {coords_and_admcd, all}, return a bundle:
class ResolveBundle(BaseModel):
    kind: Literal["bundle"] = "bundle"
    coords: Optional[CoordResult]
    adm_cd: Optional[AdmCodeResult]
    address: Optional[AddressResult]   # only populated when want='all'
    poi: Optional[POIResult]           # only populated when want='all'
    confidence: Literal["high", "medium", "low"]
```

**Why discriminated union**:
- Matches Claude Code's `FileReadTool` output (`type: 'text'|'image'|'notebook'|'pdf'`, `02-tool-system.md:541-549`).
- Model pattern-matches on `kind` — no string sniffing.
- `ResolveError` is a variant, not an exception. Fail-closed per `AGENTS.md § Hard rules`.

### 4.4 Internal dispatch chain (deterministic, LLM-invisible)

```
                    ┌──────────────────────────┐
   query   ─────▶   │ classify(query)          │
                    │   → coord | addr | place │
                    └────────┬─────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
     [coord path]       [addr path]       [place path]
          │                  │                  │
          │                  ▼                  ▼
          │          juso.go.kr           kakao keyword
          │          addrLinkApi          search
          │                  │                  │
          │                  ▼                  ▼
          │          (road_address,       (poi, coords)
          │           bd_mgt_sn,                │
          │           admCd)                    │
          │                  │                  │
          └──────────────────┼──────────────────┘
                             ▼
                   ┌───────────────────────┐
                   │ SGIS coord2region     │  (only if want ∈
                   │  → adm_cd (10-digit)  │   {adm_cd, all} and
                   └───────────┬───────────┘   still missing)
                               │
                               ▼
                       Assemble ResolveBundle
                       or specific ResolveWant variant
```

**Dispatch rules**:
1. **Input classifier** — regex only, no LLM:
   - `^-?\d+\.\d+\s*,\s*-?\d+\.\d+$` → coord path
   - contains road-name suffix (`로`, `길`, `번길`) and digits → address path
   - else → place path
2. **Provider preference ladder** (reverse-order fallback on 4xx/5xx/empty result):
   - Place: kakao → juso (address mode) → v-world (deferred, post-MVP)
   - Address: juso → kakao → v-world
   - Adm_cd: sgis (canonical) → juso (returns `admCd` directly) → kakao (`coord2regioncode`)
3. **Never re-enter the LLM loop** inside `locate`. All fallback is handled by this chain.

**Why deterministic dispatch (not Tool Search)**:
- Only 3 backends, bounded for 2+ years.
- Each provider has a *known best-use case*; routing is a lookup, not a search.
- Eliminates LLM cost + latency per geocoding call.

**Provider-specific spatial variants are adapter-owned, not resolver-owned**:
- `locate` returns generic primitives only (WGS84 coords, 10-digit adm_cd, road/jibun address, POI).
- KMA adapter runs the Lambert-Conformal-Conic projection (`docs/vision.md` refs: docx P264-P271, xlsx fallback `research/data/kma/격자_위경도.xlsx`) **inside the adapter**, taking `lat`/`lon` as input.
- KOROAD adapter owns the sido/gugun codebook including year-dependent quirks (2023 강원 42→51, 전북 45→52; 부천시 split history 197/199/195 → 190 → 192/194/196), converting from `adm_cd` at call time.
- Rationale: provider pathology stays localized. `locate` remains a stable, generic surface.

### 4.5 Backend provider selection (evidence-backed)

| Provider | Role | Why | Access |
|---|---|---|---|
| **Kakao Local** | Primary for place/POI, coord2region secondary | 300K/day free, instant auth, highest Korean POI density | Kakao account only |
| **juso.go.kr** (도로명주소) | Canonical for address normalization + admCd | 행정안전부 ground truth; returns `admCd` directly in response | confmKey, instant |
| **SGIS** | Canonical for admCd (10-digit), coord system conversion | Only provider with both legal+admin 10-digit codes + EPSG:4326↔5179 | API key + Secret, 1–2 day approval |
| ~~V-World~~ | Deferred post-MVP | Strong for 공간정보/지적 but overkill for MVP | — |
| ~~Naver Maps~~ | Excluded | NCP billing card required, student barrier | — |
| ~~Google Geocoding~~ | Excluded | Billing required, 카카오 대비 POI 열세 | — |
| ~~Nominatim~~ | Excluded | 한국 coverage 50–70%, self-host cost | — |

### 4.6 Fail-closed defaults (following `docs/tool-adapters.md § Adapter shape`)

```python
# resolve_location's facade tool metadata
requires_auth = False            # no citizen PII
is_concurrency_safe = True       # pure read, idempotent
is_personal_data = False         # place name is not PII
cache_ttl_seconds = 86400        # 24h; place↔admCd mapping is stable
rate_limit_per_minute = 60       # well under kakao's 300K/day
```

## 5. Tool #2 — `find`

### 5.1 Problem scope

Resolve a citizen question to **one or more registered Korean public-API adapters** and invoke them with typed args. Adapter surface is open-ended (100+ over project lifetime) but the LLM sees a single 2-operation tool.

### 5.2 Public schema

```python
class LookupMode(str, Enum):
    search = "search"   # retrieve candidate adapters; does not invoke any API
    fetch  = "fetch"    # invoke a specific adapter with typed args

class LookupInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: LookupMode = Field(
        description="'search' returns candidate adapters and their input schemas. "
                    "'fetch' invokes the chosen adapter with its required args.",
    )
    # search mode
    query: Optional[str] = Field(
        default=None,
        description="Natural-language question, used when mode='search'. "
                    "Can mix Korean and English.",
    )
    domain: Optional[Literal[
        "traffic", "weather", "health", "welfare", "disaster", "civil_service"
    ]] = Field(default=None, description="Optional domain filter for search.")
    # fetch mode
    adapter_id: Optional[str] = Field(
        default=None,
        description="Tool ID from a previous search result (e.g. 'koroad_accident_search'). "
                    "Required when mode='fetch'.",
    )
    args: Optional[dict[str, object]] = Field(
        default=None,
        description="Typed arguments matching the adapter's input schema, "
                    "as surfaced in the prior search result. Required when mode='fetch'.",
    )
    page: Optional[str] = Field(
        default=None,
        description="Opaque pagination cursor from a prior fetch response.",
    )

    @model_validator(mode="after")
    def _validate_mode_args(self) -> "LookupInput":
        if self.mode == LookupMode.search and not self.query:
            raise ValueError("search mode requires 'query'")
        if self.mode == LookupMode.fetch and not (self.adapter_id and self.args is not None):
            raise ValueError("fetch mode requires 'adapter_id' and 'args'")
        return self
```

**Why `mode` discriminator not two tools**:
- Claude Code's `Grep` uses `output_mode` the same way (`02-tool-system.md:521-525`). One tool, multiple modes. Reduces LLM tool-selection burden.
- BUT each mode has different required params → enforced via `model_validator`. Fail-closed at the schema boundary.

### 5.3 Return shape — `search` mode

```python
class AdapterCandidate(BaseModel):
    adapter_id: str
    name_ko: str
    name_en: str
    provider: str                # e.g. "KOROAD"
    description: str             # 1-2 sentences
    search_hint: str             # bilingual terms for this adapter
    input_schema: dict           # JSON Schema of the adapter's Pydantic input
    # — no endpoint / URL exposed to the LLM
    bm25_score: float

class LookupSearchOutput(BaseModel):
    kind: Literal["search"] = "search"
    candidates: list[AdapterCandidate]   # top-k, default k=5
    query_echo: str
    total_indexed: int
```

### 5.4 Return shape — `fetch` mode

All adapters normalize to a **single canonical envelope**:

```python
class LookupRecord(BaseModel):
    kind: Literal["record"] = "record"
    adapter_id: str
    data: dict            # adapter's Pydantic output, dumped
    next_cursor: None = None

class LookupCollection(BaseModel):
    kind: Literal["collection"] = "collection"
    adapter_id: str
    items: list[dict]
    next_cursor: Optional[str]
    total_count: Optional[int]

class LookupTimeseries(BaseModel):
    kind: Literal["timeseries"] = "timeseries"
    adapter_id: str
    points: list[dict]    # each has a canonical 'ts' field added by adapter;
                          # remaining keys use semantic names + units (e.g. 'temperature_c',
                          # 'precipitation_mm', 'humidity_pct', 'wind_ms', 'pop_pct')
                          # rather than provider codes (TMP/PCP/REH/WSD/POP).
                          # Category pivoting (e.g. KMA's 4-tuple rows → one point per ts)
                          # is the adapter's responsibility, not the LLM's.
    interval: Literal["minute", "hour", "day", "month", "year"]
    next_cursor: Optional[str]

class LookupError(BaseModel):
    kind: Literal["error"] = "error"
    adapter_id: str
    reason: Literal[
        "rate_limited",        # HTTP 429 OR in-envelope resultCode=22
        "auth_failed",         # API key rejected by upstream (resultCode=30/31)
        "auth_required",       # Layer 3 harness gate refused (PII adapter, MVP interface-only)
        "not_found",           # valid call, empty result
        "invalid_args",        # upstream rejected params
        "upstream_down",       # 5xx
        "schema_mismatch",     # normalization failed
        "stale_data",          # e.g., NMC hvidate older than freshness SLO
    ]
    upstream_code: Optional[str]   # e.g. data.go.kr resultCode
    upstream_message: Optional[str]
    retryable: bool

LookupFetchOutput = Annotated[
    Union[LookupRecord, LookupCollection, LookupTimeseries, LookupError],
    Field(discriminator="kind"),
]
```

**Why a `shape` discriminator + canonical envelope**:
- data.go.kr envelopes vary wildly (`response.body.items.item` vs `response.body.item` vs flat arrays). Normalization happens inside the adapter — the LLM only ever sees `kind` + `items`/`points`/`data`.
- Opaque `next_cursor` string, not `offset`/`page` — proven in LangChain/MCP to reduce off-by-one loop failures.
- `retryable` lets the LLM decide whether to re-attempt without needing to parse HTTP codes.

### 5.5 Retrieval index (the `search` backend)

- **Algorithm**: BM25 (`rank_bm25`) over a corpus of `{name_ko + name_en + search_hint + input_schema.field_names}` per adapter. Matches Anthropic's Tool Search Tool v1 (BM25 variant), whose Arcade-replicated accuracy is 64% on 4k-tool pools.
- **Tokenizer**: **`kiwipiepy>=0.17`** (pure Python, MIT). Chosen over `mecab-ko` because it has no system-install dependency (CI-friendly under `uv`), matches mecab-ko on F1 in 2024-2025 benchmarks, and is actively maintained. Morpheme tokens are used both at indexing time and at query time.
- **Index source**: the in-process `ToolRegistry` (existing `src/ummaya/tools/registry.py`). Build on startup; rebuild on adapter add/remove.
- **Not a vector store**: BM25 is sufficient at MVP scale (<100 adapters), zero infra cost, matches Anthropic/Arcade results. Defer embeddings to post-MVP if retrieval precision becomes a bottleneck (gate defined in §5.5.1).
- **Top-k default**: `min(5, len(registry))`. Env override: `UMMAYA_LOOKUP_TOPK` (clamped to `[1, 20]`). Adaptive floor prevents empty candidate lists during MVP's 4-adapter phase; hard ceiling prevents LLM context explosion as the registry grows. Matches Anthropic Tool Search Tool defaults (5) and Arcade's finding that increasing k beyond 5 yields marginal recall gains.
- **Domain filter**: when `domain` is set, restrict corpus to adapters with matching `category` tag before BM25. Reduces false positives on broad queries.

#### 5.5.1 Retrieval quality gate (recall evaluation)

To prevent the BM25 retriever from silently degrading as adapters are added, retrieval behavior is now checked through Evidence Fabric v2 and focused deterministic retrieval tests. The old standalone labeled-query eval files were retired with the pre-v2 verification pipeline.

- **Dataset**: citizen-facing scenarios live at `evidence/scenarios/national_ax_citizen_requests_v1.yaml` and must not expose adapter IDs, fixture IDs, or expected tool IDs to the model-visible prompt.
- **Metrics** (both reported):
  - `recall@5` — correct adapter present in top-5 candidates (primary gate).
  - `recall@1` — correct adapter is the first candidate (upper-bound on LLM tool-selection burden).
- **Thresholds**:

  | Band | `recall@5` | Action |
  |---|---|---|
  | Pass | ≥ 80% AND `recall@1` ≥ 50% | ship |
  | Warn | 60% ≤ `recall@5` < 80% | reinforce `search_hint` bilingual terms, re-test |
  | Fail | < 60% | escalate to embedding-based retrieval (fallback tracked in §8.2) |

- **Test hook**: `tests/tools/test_bm25_retrieval.py` covers deterministic BM25 behavior. Evidence Fabric rejects model-visible implementation leakage and records scenario coverage in `.evidence/run.json`.
- **Evidence basis**: 80% target = Kruczek/MCP-Bench midpoint for BM25 at <100-tool scale. 60% fail threshold = Anthropic's 64% at 4K scale; anything worse at our smaller scale indicates a structural retrieval problem, not a scale problem.

### 5.6 Invocation (the `fetch` backend)

1. Resolve `adapter_id` → `GovAPITool` instance from the registry. Unknown id → `LookupError(reason="not_found")`.
2. Validate `args` against the adapter's Pydantic input schema. Failure → `LookupError(reason="invalid_args")` with the Pydantic error message as `upstream_message`.
3. Call the adapter (`httpx` async, existing `executor.py` pipeline: rate limiter → auth inject → call → envelope parse).
4. Normalize the adapter's output into one of `{LookupRecord, LookupCollection, LookupTimeseries}` based on the adapter's declared `output_shape` metadata.
5. Upstream errors (HTTP 4xx/5xx, `resultCode != "00"`, rate-limit envelope codes) → `LookupError(reason=..., retryable=...)`.

### 5.7 Tool Search / lazy loading posture

- All registered `GovAPITool` instances are **not** sent to the LLM as individual tools. They live only in the BM25 index.
- The LLM only ever sees `find` + `locate`. Context tokens for adapters: **zero until requested**.
- This is the UMMAYA equivalent of Anthropic's `defer_loading: true`, implemented client-side because FriendliAI/K-EXAONE has no server-side Tool Search primitive.
- When `lookup(mode="search")` returns candidates, their `input_schema` field provides the just-in-time schema the LLM needs to construct a correct `fetch` call. Mirrors Cursor's `describe_tools` and Claude Code's `shouldDefer` + ToolSearch hint pattern (`02-tool-system.md:250-263, 371-398`).

### 5.8 Seed adapter set (MVP closure)

To validate the pattern end-to-end, MVP ships with **4 adapters** covering every canonical shape and every spatial-parameter convention UMMAYA will ever encounter:

| adapter_id | provider | endpoint | spatial input | shape | PII | rationale |
|---|---|---|---|---|---|---|
| `koroad_accident_hazard_search` | KOROAD | `frequentzoneLg/getRestFrequentzoneLg` (사고다발지역) | `siDo` + `guGun` codes (+`searchYearCd`) — adapter derives from `adm_cd` | collection | `is_personal_data=False` | Exercises sido/gugun code-table join + year-dependent code quirks (2023 강원/전북 shift, 부천시 code history) |
| `kma_forecast_fetch` | KMA | `VilageFcstInfoService_2.0/getVilageFcst` (단기예보) | `nx` + `ny` LCC grid — adapter derives from `coords` via LCC projection | timeseries | `is_personal_data=False` | Validates `timeseries` shape + Lambert-Conformal-Conic projection (docx formula or xlsx fallback) + category-pivoted envelope (14 category codes → one point per hour) |
| `hira_hospital_search` | HIRA | `HospInfoServicev2/getHospBasisList` (병원 목록) | `xPos` + `yPos` + `radius` (meters, WGS84) | collection | `is_personal_data=False` | Only seed adapter with **native coord+radius** — exercises `ykiho` as the downstream join key for follow-up detail calls |
| `nmc_emergency_search` | NMC | `ErmctInfoInqireService/getEgytLcinfoInqire` (응급실 검색, 거리순) | `WGS84_LON` + `WGS84_LAT` only (distance-sorted, no radius) | collection | `is_personal_data=True` ⚑ | Tests "coords-in, no-radius" pattern + real-time bed fields (`hv1`~`hv61`, `hvidate` freshness). **Deliberately flagged PII** so Layer 3 harness has a live end-to-end path in MVP (stub gate returns `auth_required`) |

**Coverage claim**: these 4 adapters together span (a) both canonical shapes (`collection` + `timeseries` — `record` is covered post-MVP by composite adapters), (b) all four spatial-input flavors UMMAYA will encounter in practice (code-pair, LCC grid, coord+radius, coord-only), (c) both ways a data.go.kr provider signals rate-limiting (`resultCode=22` in envelope), and (d) **one live Layer 3 harness path** via `nmc_emergency_search` so the auth-gate is demonstrable rather than theoretical.

**Implementation sequencing**: KOROAD first (Lead solo) to land the executor/envelope/fixture pipeline, then KMA + HIRA + NMC in parallel via Agent Teams once the pipeline is stable. Rationale: avoid 4-way schema divergence before executor conventions are fixed.

**NMC freshness threshold**: `hvidate` older than **30 minutes** emits `LookupError(reason="stale_data", retryable=False)`. Override via `UMMAYA_NMC_FRESHNESS_MINUTES`.

Additional adapters follow the standard `docs/tool-adapters.md` spec cycle and require no changes to `find` itself — pure registration.

### 5.9 Fail-closed defaults

```python
# lookup's facade tool metadata
requires_auth = False            # the tool itself doesn't expose PII;
                                 # individual adapters set their own flags
is_concurrency_safe = False      # fetch mutates rate-limiter state
is_personal_data = False         # adapter-level flag, not tool-level
cache_ttl_seconds = 0            # caching is per-adapter, not per-tool
rate_limit_per_minute = 120      # cap on the tool itself; adapters add their own
```

## 6. LLM-facing surface summary

This is the **entire** tool list the model sees, in order:

```
[
  {
    "name": "locate",
    "description":
      "Convert Korean place references to structured coordinates, addresses, "
      "or 행정동(administrative-dong) codes. Prefer this BEFORE calling `find` "
      "when a government API requires location parameters.",
    "input_schema": <ResolveLocationInput schema>
  },
  {
    "name": "find",
    "description":
      "Search the Korean public-API registry and invoke a specific adapter. "
      "Two-step usage: first call with mode='search' to retrieve candidates, "
      "then call with mode='fetch' using the selected adapter_id and its typed args.",
    "input_schema": <LookupInput schema>
  }
]
```

### System-prompt coupling (instruction preamble)

Following Claude Code's static/dynamic split (`10-context-assembly.md:25-54`), the UMMAYA system prompt adds these rules — *not* the tool description:

```
# Tool usage rules

- If a user question requires Korean government data AND mentions a place,
  call `locate` FIRST to obtain coordinates or 행정동 code, THEN
  call `find` using those values as adapter args.
- `find` is always two steps: `search` returns candidates, then `fetch`
  invokes a specific adapter. Do not attempt to fetch without searching
  first unless you already know a valid adapter_id from an earlier turn.
- Never guess `adapter_id` — it must come from a `search` result.
- On `LookupError(retryable=true)` you may retry once; otherwise report
  the error to the user plainly.
```

This preamble is the UMMAYA analog of Claude Code's "Use FileRead instead of cat" rule — behavior couples to tool design via the system prompt, not via nested tool calls.

## 7. Chain patterns (happy-path walkthroughs)

### Pattern A — "강남구 사고다발지역 알려줘" (KOROAD, code-pair spatial)

```
LLM → resolve_location(query="서울 강남구", want="adm_cd")
        → AdmCodeResult(code="1168000000", name="서울특별시 강남구", level="sigungu",
                        source="sgis")
LLM → lookup(mode="search", query="사고다발지역", domain="traffic")
        → candidates=[{adapter_id: "koroad_accident_hazard_search", input_schema: {...}}, ...]
LLM → lookup(mode="fetch", adapter_id="koroad_accident_hazard_search",
             args={"adm_cd": "1168000000", "year": 2025})
        → LookupCollection(items=[{spot_nm, tot_dth_cnt, lo_crd, la_crd, geom_json}, ...],
                           next_cursor=None, total_count=14)
LLM → [synthesize Korean answer for user]
```

**Adapter internals hidden**: LLM passes `adm_cd`+`year`; the KOROAD adapter internally maps to `siDo`+`guGun`+`searchYearCd`, applying year-dependent code quirks (2023 강원 42→51, 전북 45→52; 부천시 split history). resolver stays generic.

### Pattern B — "서울 종로구 오늘 날씨 어때?" (KMA, LCC grid derived in adapter)

```
LLM → resolve_location(query="서울 종로구", want="coords")
        → CoordResult(lat=37.5735, lon=126.9788, confidence="high", source="kakao")
LLM → lookup(mode="search", query="단기예보 날씨", domain="weather")
        → candidates=[{adapter_id: "kma_forecast_fetch", ...}, ...]
LLM → lookup(mode="fetch", adapter_id="kma_forecast_fetch",
             args={"lat": 37.5735, "lon": 126.9788, "base_date": "20260416", "base_time": "1400"})
        → LookupTimeseries(
              points=[{ts: "2026-04-16T15:00",
                       temperature_c: 12.1, precipitation_mm: 0.0,
                       sky_condition: "mostly_cloudy", humidity_pct: 55,
                       wind_ms: 3.2, pop_pct: 20, ...}, ...],
              interval="hour")
```

**Semantic field names with units** — LLM reads `temperature_c=12.1` instead of provider code `TMP=12.1`. Category pivoting (4-tuple → point-per-ts) + LCC projection both happen inside the adapter.

### Pattern C — error with recovery

```
LLM → lookup(mode="fetch", adapter_id="kma_forecast_fetch",
             args={"lat": 37.5735, "lon": 126.9788, "base_date": "20260416", "base_time": "1530"})
        → LookupError(reason="invalid_args",
                      upstream_code="10",
                      upstream_message="base_time must be one of 0200,0500,...,2300",
                      retryable=False)
LLM → [asks user to clarify OR re-runs with the nearest valid base_time]
```

The LLM pattern-matches on `kind="error"` and `retryable`. No string parsing.

### Pattern D — "강남역에서 사고나면 가장 가까운 응급실은?" (chained coord reuse, Layer 3 gate)

```
LLM → resolve_location(query="강남역", want="coords")
        → CoordResult(lat=37.498, lon=127.028, confidence="high", source="kakao")

LLM → lookup(mode="search", query="응급실 실시간 병상", domain="health")
        → candidates=[{adapter_id: "nmc_emergency_search", ...},
                      {adapter_id: "hira_hospital_search", ...}]

LLM → lookup(mode="fetch", adapter_id="nmc_emergency_search",
             args={"lat": 37.498, "lon": 127.028, "limit": 5})
        → LookupError(kind="error", reason="auth_required", retryable=False,
                      upstream_message="nmc_emergency_search requires citizen auth "
                                       "(Layer 3 harness stub — no provider implemented in MVP)")
          # ⚑ PII flag → Layer 3 gate refuses; demonstrates end-to-end auth path

LLM → lookup(mode="fetch", adapter_id="hira_hospital_search",
             args={"xPos": 127.028, "yPos": 37.498, "radius": 2000})
        → LookupCollection(items=[{ykiho, yadmNm, distance, ...}, ...])
          # ykiho is the join key to HIRA MadmDtlInfoService2.7 (11 sub-ops) — deferred post-MVP

LLM → [explains to user: real-time bed data requires consent (post-MVP);
       falls back to nearest canonical hospitals via HIRA]
```

**Pattern D is the UMMAYA sweet spot**: one `locate` output feeds multiple adapters with different spatial conventions + the Layer 3 harness gate fires on the PII-flagged adapter, letting the LLM gracefully degrade to a non-PII alternative.

## 8. Non-MVP / deferred (tracked but not built)

### 8.1 Layer 3 harness posture (interface-only in MVP)

UMMAYA is a **harness/framework**, not a turnkey citizen app. Layer 3 (auth, permission, consent) ships as **interface slots only** in MVP:

- `requires_auth`, `is_personal_data`, `auth_required` `LookupError` variant, and the fail-closed default matrix are **wired through the schema and executor** — the LLM and adapters interact with them as if Layer 3 were live.
- No identity Provider is implemented. No OAuth, no 본인인증, no 간편인증, no PASS/카카오/NAVER/Toss/신한 broker integration. Attempts to invoke an adapter with `is_personal_data=True` return `LookupError(reason="auth_required", retryable=False)` from a stub guard, not from a real provider.
- Post-MVP, a concrete Provider can drop in behind the existing slot without touching tool schemas or the LLM-facing surface.
- **One seed adapter (`nmc_emergency_search`) is deliberately flagged `is_personal_data=True`** so the Layer 3 stub guard fires on at least one end-to-end call path in MVP. Without this, the harness slot would be untested dead code.

This preserves the architectural shape for KSC 2026 evaluation while keeping scope realistic for a student portfolio.

### 8.2 Other deferrals

- V-World backend for `locate` (지적/공간정보).
- Vector-retrieval upgrade for `lookup.search` (only if BM25 precision <60% on eval set).
- Per-turn result caching (beyond `cache_ttl_seconds`).
- Write-oriented tools (`submit_application`, `pay`, etc.) — legal/auth barriers.
- Multi-adapter composition within `lookup.fetch` — the LLM chains primitive adapters (e.g., `koroad_accident_search` + `kma_*`) end-to-end through `find`. Composite adapters were prototyped early and then removed in Epic #1634 per migration tree § L1-B B6 in favour of primitive chaining.
- HIRA `MadmDtlInfoService2.7` (11 sub-operations joined on `ykiho`) — adapter surface too large for MVP; add post-MVP once the `ykiho` join idiom is validated by `hira_hospital_search`.
- NMC real-time bed fields (`hv1`~`hv61`, acceptance mkiosk fields `mkioskty1`~`28`) are surfaced in `nmc_emergency_nearby` responses but not individually queryable — post-MVP may add a dedicated `nmc_bed_availability` adapter.
- Cost/budget tracking across chains (planned for Phase 2).

## 9. Decisions log (Q1–Q5 all resolved as of 2026-04-16)

1. ~~**Korean tokenizer choice**~~ **Resolved (2026-04-16)**: `kiwipiepy>=0.17` (MIT, pure Python). mecab-ko rejected due to CI system-install friction under `uv`. 2024-2025 benchmarks show F1 parity on morpheme segmentation.
2. ~~**Default `top_k` for `lookup.search`**~~ **Resolved (2026-04-16)**: `min(5, len(registry))` with env override `UMMAYA_LOOKUP_TOPK` clamped to `[1, 20]`. Adaptive floor handles MVP's 4-adapter phase; ceiling prevents context explosion at scale.
3. ~~**Seed adapter count**: 3 vs 5~~ **Resolved (2026-04-16)**: 4 adapters selected — KOROAD + KMA + HIRA + NMC. Justification in §5.8: covers both canonical shapes (`collection`+`timeseries`) and all four spatial-input flavors (code-pair, LCC grid, coord+radius, coord-only).
4. ~~**Tool-Search recall gate**~~ **Replaced (2026-05-26)**: standalone labeled-query eval files were removed. Evidence Fabric v2 now owns scenario-level verification while focused BM25 unit tests keep deterministic retrieval invariants.
5. ~~**`resolve_location.want=all` token cost**~~ **Resolved (2026-04-16)**: default is `coords_and_admcd` (bundle with 2 slots). `all` is opt-in only. Adapter-specific variants (KMA LCC grid, KOROAD sido/gugun) are derived inside their adapters from `coords`/`adm_cd` — not exposed as first-class `want` values.

## 10. Compliance against project rules

| Rule (`AGENTS.md § Hard rules`) | Status |
|---|---|
| All source text in English | ✓ (Korean only in domain data — place names, `name_ko`) |
| `UMMAYA_` env prefix | ✓ (`UMMAYA_KAKAO_API_KEY`, `UMMAYA_JUSO_CONFM_KEY`, `UMMAYA_SGIS_KEY`, `UMMAYA_SGIS_SECRET`, `UMMAYA_LOOKUP_TOPK`, `UMMAYA_NMC_FRESHNESS_MINUTES`) |
| Stdlib logging only | ✓ |
| Pydantic v2, never `Any` | ✓ (all schemas typed; `args: dict[str, object]` in `LookupInput` is the only loose field, validated against adapter schema at fetch time) |
| No live API from CI | ✓ (recorded fixtures per `docs/tool-adapters.md § Recording fixtures`) |
| No new deps outside spec-driven PR | ⚠ New deps: `rank_bm25` (Apache-2.0), `kiwipiepy>=0.17` (MIT). Land via the upcoming spec PR only. |
| Apache-2.0 compatibility | ✓ (both deps MIT/Apache-2.0) |

## 11. References

### Claude Code / Gemini CLI internal patterns
- `.references/claude-reviews-claude/docs/chapters/02-tool-system.md` — tool factory, deferred tools, discriminated-union outputs, 13-step pipeline
- `.references/claude-reviews-claude/docs/chapters/08-agent-swarms.md` — Zod discriminated-union control messages
- `.references/claude-reviews-claude/docs/chapters/10-context-assembly.md` — static/dynamic system prompt split, CLAUDE.md priority
- `.references/claude-code-sourcemap/`, `.references/claw-code/`, `.references/gemini-cli/`

### Anthropic Tool Search Tool
- Anthropic docs: https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool
- Arcade replication (64% BM25 accuracy, 4k tools): https://blog.arcade.dev/anthropic-tool-search-claude-mcp-runtime
- Spring AI 34–64% token savings: https://spring.io/blog/2025/12/11/spring-ai-tool-search-tools-tzolov/
- Stacklok head-to-head: https://stacklok.com/blog/stackloks-mcp-optimizer-vs-anthropics-tool-search-tool-a-head-to-head-comparison/

### Progressive disclosure / lazy loading
- Cursor Dynamic Context Discovery (46.9% production A/B): https://cursor.com/blog/dynamic-context-discovery
- Speakeasy Dynamic Toolsets v2: https://www.speakeasy.com/blog/how-we-reduced-token-usage-by-100x-dynamic-toolsets-v2
- MCP SEP #1888 (progressive disclosure): https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1888
- Kruczek benchmark: https://matthewkruczek.ai/blog/progressive-disclosure-mcp-servers.html

### Foundational research papers
- RestGPT (arXiv:2306.06624) — Planner → API Selector → Executor: https://arxiv.org/abs/2306.06624
- Gorilla (arXiv:2305.15334): https://arxiv.org/abs/2305.15334
- ToolLLM / ToolBench (arXiv:2307.16789): https://arxiv.org/abs/2307.16789
- AnyTool — hierarchical router (arXiv:2402.04253): https://arxiv.org/abs/2402.04253
- API-Bank (arXiv:2304.08244): https://arxiv.org/abs/2304.08244
- MetaTool (arXiv:2310.03128): https://arxiv.org/html/2310.03128v4
- NESTful — nested-call anti-pattern (arXiv:2409.03797): https://arxiv.org/html/2409.03797v1
- MCP-Bench (arXiv:2508.20453): https://arxiv.org/pdf/2508.20453
- ToolScan (arXiv:2411.13547): https://arxiv.org/html/2411.13547v2
- Multi-Agent Trap survey (17× failure amplification): https://towardsdatascience.com/the-multi-agent-trap/

### Korean geocoding API documentation
- V-World v4: https://www.vworld.kr/dev/v4api.do
- 도로명주소 API: https://business.juso.go.kr/addrlink/openApi/apiExprn.do
- SGIS (통계청): https://sgis.kostat.go.kr/developer/html/newOpenApi/api/dataApi/addr.html
- Kakao Local: https://developers.kakao.com/docs/latest/ko/local/dev-guide

### UMMAYA internal
- `docs/vision.md` — 6-layer canonical architecture
- `docs/tool-adapters.md` — `GovAPITool` shape, PR checklist
- `docs/conventions.md` — commit / PR rules
- `.specify/memory/constitution.md` — fail-closed rules
