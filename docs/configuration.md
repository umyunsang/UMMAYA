# KOSMOS Environment Variable Registry

Authoritative reference for every environment variable consumed by KOSMOS. Machine-parsed by
`scripts/audit-env-registry.py`. Adding a row here — not elsewhere — is the single source of truth.

---

## Overview

KOSMOS follows [12-Factor App Config](https://12factor.net/config): every runtime parameter that
varies between deploy environments (dev, ci, prod) is stored in the process environment, never
baked into source code.

**Prefix rule**: every variable MUST start with `KOSMOS_`. The sole permitted exception is the
`LANGFUSE_*` family, which uses the vendor SDK's default prefix convention and cannot be renamed
without forking the SDK. No other non-`KOSMOS_` prefix is allowed in `src/` code (FR-040,
FR-043).

**`.env` is read-only**: the file `.env` in the repository root is a symlink owned by your local
toolchain (e.g., a 1Password CLI shim, a macOS Keychain-backed mount). No KOSMOS code path may
write, rewrite, rename, or stat `.env`. The stdlib loader in `src/kosmos/_dotenv.py` reads through
the symlink without following it as a file.

**Shell wins over `.env`**: environment variables already set in the process environment take
priority over values in `.env`. This guarantees CI secret injection (Infisical, GitHub Actions
`env:` blocks) always wins over any local developer overrides.

---

## Quick Reference Table

Column definitions:

- **Required** — `Yes (dev/ci/prod)` means the startup guard fails immediately on absence in any
  environment. `Yes (prod only)` means the guard only enforces the variable when `KOSMOS_ENV=prod`.
  `No` means optional in all environments. `Deprecated` means the variable is still honoured for
  backward compatibility but MUST NOT be used for new tools. `Override pattern` marks a family row.
- **Default** — value used when the variable is absent and `Required` is `No`. `—` means no default
  (absence is a guard failure or the field stays empty).
- **Range** — accepted format or value set.
- **Consumed by** — fully qualified `module.Class.attribute` or `module.function` path.
- **Source doc** — where the credential is issued or the setting is documented.

| Variable | Required | Default | Range | Consumed by | Source doc |
|----------|----------|---------|-------|-------------|------------|
| `KOSMOS_ENV` | No | `dev` | `dev` \| `ci` \| `prod` | `kosmos.config.guard.current_env` | This doc |
| `KOSMOS_KAKAO_API_KEY` | Yes (dev/ci/prod) | — | REST API key string | `kosmos.settings.KosmosSettings.kakao_api_key` | [Kakao Developers Console](https://developers.kakao.com) |
| `KOSMOS_FRIENDLI_TOKEN` | Yes (dev/ci/prod) | — | Bearer token | `kosmos.llm.config.LLMClientConfig.token` | [FriendliAI Suite](https://suite.friendli.ai) |
| `KOSMOS_DATA_GO_KR_API_KEY` | Yes (dev/ci/prod) | — | API key string | `kosmos.settings.KosmosSettings.data_go_kr_api_key` | [공공데이터포털](https://www.data.go.kr) |
| `KOSMOS_JUSO_CONFM_KEY` | No (optional fallback) | — | Confirmation key string | `kosmos.settings.KosmosSettings.juso_confm_key` | [도로명주소 개발자센터](https://business.juso.go.kr) |
| `KOSMOS_SGIS_KEY` | No (optional fallback) | — | Consumer key string | `kosmos.settings.KosmosSettings.sgis_key` | [SGIS API](https://sgis.kostat.go.kr) |
| `KOSMOS_SGIS_SECRET` | No (optional fallback) | — | Consumer secret string | `kosmos.settings.KosmosSettings.sgis_secret` | [SGIS API](https://sgis.kostat.go.kr) |
| `KOSMOS_FRIENDLI_BASE_URL` | No | `https://api.friendli.ai/serverless/v1` | Valid HTTPS URL | `kosmos.llm.config.LLMClientConfig.base_url` | FriendliAI Suite |
| `KOSMOS_FRIENDLI_MODEL` | No | `LGAI-EXAONE/K-EXAONE-236B-A23B` | Model identifier string | `kosmos.llm.config.LLMClientConfig.model` | FriendliAI Suite |
| `KOSMOS_LLM_SESSION_BUDGET` | No | `100000` | Integer > 0 (tokens) | `kosmos.llm.config.LLMClientConfig.session_budget` | This doc |
| `KOSMOS_LLM_TIMEOUT_SECONDS` | No | `300` | Float > 0 (seconds) | `kosmos.llm.config.LLMClientConfig.timeout` | This doc |
| `KOSMOS_LLM_TIMEOUT` | **Deprecated** | `300` | Float > 0 (seconds) | Legacy alias for `kosmos.llm.config.LLMClientConfig.timeout`; use `KOSMOS_LLM_TIMEOUT_SECONDS` | This doc |
| `KOSMOS_AGENTIC_LOOP_MAX_TURNS` | No | `8` | Integer >= 1 (turns) | `kosmos.ipc.stdio` (Spec 1978 T029 — bounds the CC query-engine agentic loop) | Spec 1978 |
| `KOSMOS_REACT_MAX_TURNS` | No | `8` | Integer >= 1 (turns) | `kosmos.ipc.stdio` (legacy alias for `KOSMOS_AGENTIC_LOOP_MAX_TURNS`; preserved for backward compatibility) | Spec 1978 |
| `KOSMOS_TOOL_RESULT_TIMEOUT_SECONDS` | No | `120` | Float > 0 (seconds) | `kosmos.ipc.stdio` (Spec 1978 T030 — `asyncio.gather` timeout for primitive dispatch Futures, contracts/tool-bridge-protocol.md) | Spec 1978 |
| `KOSMOS_PROMPTS_DIR` | No | `<repo_root>/prompts` | Absolute or relative directory path | `kosmos.tools.verify_canonical_map._resolve_prompts_dir` (Epic ζ #2297 — overrides the path that `verify_canonical_map.py` parses to source the canonical 10-row `tool_id ↔ family_hint` mapping from `<verify_families>` in `system_v1.md`; defaults to walking up from the module's parent directories to find `prompts/`) | Epic #2297 |
| `KOSMOS_PERMISSION_TIMEOUT_SECONDS` | No | `60` | Float > 0 (seconds) | `kosmos.ipc.stdio` (Spec 1978 T045 — permission_request → permission_response wait; D2 invariant default-deny on timeout) | Spec 1978 |
| `KOSMOS_K_EXAONE_THINKING` | No | `true` | `true` \| `false` (case-insensitive; `1`/`yes` also accepted) | `kosmos.llm.client._build_payload` (Epic #2077 / Spec 2521 — opts in to K-EXAONE-236B-A23B's chain-of-thought channel via `chat_template_kwargs.enable_thinking`; default `true` per K-EXAONE model card and τ²-Bench measurement conditions; set `false` for sub-second first-token latency at the cost of losing the citizen-visible `∴ Thinking` glyph) | Epic #2077 / Spec 2521 |
| `KOSMOS_AVAILABLE_ADAPTERS_TOP_K` | No | `5` | Integer >= 1 | `kosmos.ipc.stdio._build_available_adapters_suffix` (Spec 2521 — bounds how many BM25 candidates are emitted into the dynamic `<available_adapters>` system-prompt suffix per citizen turn; lower for prompt-cache friendliness, higher for broader recall) | Spec 2521 |
| `KOSMOS_LLM_STREAM_CHUNK_MAX_CHARS` | No | `999` | Integer >= 1 (chars) | `kosmos.llm.client._pace_text_chunk` (Spec 2521 — when set <999, splits provider deltas into sub-chunks for headless / no-Ink callers that want server-side cadence; default `999` is effectively "no extra splitting" because Ink frontend typewriter handles the in-TUI cadence) | Spec 2521 |
| `KOSMOS_LLM_STREAM_PACE_MS` | No | `0` | Float >= 0 (milliseconds) | `kosmos.llm.client._pace_text_chunk` (Spec 2521 — sleep between sub-chunk emissions for headless callers; default `0` disables backend pacing because Ink's `FRAME_INTERVAL_MS=4` throttle relax handles the cadence inside the TUI) | Spec 2521 |
| `KOSMOS_LOOKUP_TOPK` | No | `5` | Integer [1, 20] | `kosmos.settings.KosmosSettings.lookup_topk` | This doc |
| `KOSMOS_NMC_FRESHNESS_MINUTES` | No | `30` | Integer [1, 1440] (minutes) | `kosmos.settings.KosmosSettings.nmc_freshness_minutes` | Epic #507 |
| `KOSMOS_RETRIEVAL_BACKEND` | No | `bm25` | `bm25` \| `dense` \| `hybrid` | `kosmos.tools.retrieval.backend.build_retriever_from_env` | Epic #585 |
| `KOSMOS_RETRIEVAL_COLD_START` | No | `lazy` | `eager` \| `lazy` | `kosmos.tools.retrieval.backend._parse_cold_start` | Epic #585 |
| `KOSMOS_RETRIEVAL_FUSION` | No | `rrf` | `rrf` | `kosmos.tools.retrieval.backend._parse_fusion_config` | Epic #585 |
| `KOSMOS_RETRIEVAL_FUSION_K` | No | `60` | Integer >= 1 | `kosmos.tools.retrieval.backend._parse_fusion_config` | Epic #585 |
| `KOSMOS_RETRIEVAL_MODEL_ID` | No | `intfloat/multilingual-e5-small` | Hugging Face model ID string | `kosmos.tools.retrieval.backend.build_retriever_from_env` | Epic #585 |
| `KOSMOS_MEMDIR_USER` | No | `~/.kosmos/memdir/user` | Filesystem path (expanduser) | `kosmos.session.store._get_session_dir`; TUI memdir/session helpers | Spec 027 |
| `KOSMOS_SESSION_DIR` | No | `~/.kosmos/sessions` | Filesystem path (expanduser) | `kosmos.session.store._get_session_dir` | Epic #287 |
| `KOSMOS_BACKEND_CMD` | No | `uv run python -m kosmos.ipc.mcp_server` | Shell command string spawned by the TUI as the backend process | TUI-side `tui/src/services/api` IPC bridge spawner; `kosmos.ipc.demo.mock_backend` is the canonical Mock-backend value used by Spec 2296 PTY + vhs smoke artefacts | Epic #2296 |
| `KOSMOS_BACKEND_LOG_FILE` | No | — | Filesystem path | `kosmos.ipc.stdio.run` diagnostic FileHandler | Spec multi-turn contamination |
| `KOSMOS_CHAT_REQUEST_DUMP` | No | `false` | `1` enables diagnostic dumps; unset disables | `kosmos.ipc.stdio._diag_chat_request_enabled` | Spec multi-turn contamination |
| `KOSMOS_CLI_HISTORY_SIZE` | No | `1000` | Integer >= 0 | `kosmos.cli.config.CLIConfig.history_size` | This doc |
| `KOSMOS_CLI_SHOW_USAGE` | No | `true` | `true` \| `false` | `kosmos.cli.config.CLIConfig.show_usage` | This doc |
| `KOSMOS_CLI_WELCOME_BANNER` | No | `true` | `true` \| `false` | `kosmos.cli.config.CLIConfig.welcome_banner` | This doc |
| `KOSMOS_THEME` | No | `default` | `default` \| `dark` \| `light` | `kosmos.cli.themes.load_theme` | This doc |
| `KOSMOS_CLI_THEME` | No | `default` | `default` \| `dark` \| `light` | `kosmos.cli.themes.load_theme` (alias for `KOSMOS_THEME`) | This doc |
| `KOSMOS_OTEL_ENDPOINT` | Yes (prod only) | — | Valid HTTPS URL | `kosmos.observability.otel (#501)` | Epic #501 |
| `KOSMOS_OTEL_COLLECTOR_PORT` | No | `4318` | Integer (TCP port) | `docker-compose.dev.yml` otelcol host port binding | Epic #501, spec 028 |
| `KOSMOS_LANGFUSE_OTLP_ENDPOINT` | No | `http://langfuse-web:3000/api/public/otel` | Valid HTTP(S) URL (base, no `/v1/traces` suffix) | `infra/otel-collector/config.yaml` otlphttp exporter | Epic #501, spec 028 |
| `KOSMOS_LANGFUSE_OTLP_AUTH_HEADER` | No | `` (empty = anonymous) | `Basic <base64(pk:sk)>` string | `infra/otel-collector/config.yaml` exporter Authorization header | Epic #501, spec 028 |
| `LANGFUSE_PUBLIC_KEY` | Yes (prod only) | — | `pk-lf-…` format string | `kosmos.observability.langfuse (#501)` | [Langfuse Cloud](https://cloud.langfuse.com) |
| `LANGFUSE_SECRET_KEY` | Yes (prod only) | — | `sk-lf-…` format string | `kosmos.observability.langfuse (#501)` | [Langfuse Cloud](https://cloud.langfuse.com) |
| `KOSMOS_PROMPT_REGISTRY_LANGFUSE` | No | `false` | `true` \| `false` | `kosmos.context.prompt_loader.PromptLoader` | Epic #467 |
| `KOSMOS_LANGFUSE_HOST` | No | — | Valid HTTPS URL | `kosmos.context.prompt_loader.PromptLoader` | Epic #467 |
| `KOSMOS_LANGFUSE_PUBLIC_KEY` | No | — | `pk-lf-…` format string | `kosmos.context.prompt_loader.PromptLoader` | [Langfuse Cloud](https://cloud.langfuse.com) |
| `KOSMOS_LANGFUSE_SECRET_KEY` | No | — | `sk-lf-…` format string | `kosmos.context.prompt_loader.PromptLoader` | [Langfuse Cloud](https://cloud.langfuse.com) |
| `KOSMOS_{TOOL_ID}_API_KEY` | Override pattern | — | API key string | `kosmos.permissions.credentials._tool_specific_var` | [Per-tool override pattern](#per-tool-override-pattern) |
| `KOSMOS_API_KEY` | **Deprecated** | — | API key string | `kosmos.permissions.credentials.resolve_credential` (global fallback) | [Deprecation notice](#kosmos_api_key-deprecated) |
| `KOSMOS_AGENT_MAILBOX_ROOT` | No | `~/.kosmos/mailbox` | Absolute directory path | `kosmos.settings.KosmosSettings.agent_mailbox_root` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `KOSMOS_AGENT_MAILBOX_MAX_MESSAGES` | No | `1000` | Integer [100, 10000] | `kosmos.settings.KosmosSettings.agent_mailbox_max_messages` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `KOSMOS_AGENT_MAX_WORKERS` | No | `4` | Integer [1, 16] | `kosmos.settings.KosmosSettings.agent_max_workers` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `KOSMOS_AGENT_WORKER_TIMEOUT_SECONDS` | No | `120` | Integer [10, 600] | `kosmos.settings.KosmosSettings.agent_worker_timeout_seconds` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `KOSMOS_AGENT_COORDINATOR_PHASE` | OTel span attr | n/a | String span attribute key | `kosmos.observability.semconv.KOSMOS_AGENT_COORDINATOR_PHASE` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `KOSMOS_AGENT_ROLE` | OTel span attr | n/a | String span attribute key | `kosmos.observability.semconv.KOSMOS_AGENT_ROLE` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `KOSMOS_AGENT_SESSION_ID` | OTel span attr | n/a | String span attribute key | `kosmos.observability.semconv.KOSMOS_AGENT_SESSION_ID` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `KOSMOS_AGENT_MAILBOX_MSG_TYPE` | OTel span attr | n/a | String span attribute key | `kosmos.observability.semconv.KOSMOS_AGENT_MAILBOX_MSG_TYPE` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `KOSMOS_AGENT_MAILBOX_CORRELATION_ID` | OTel span attr | n/a | String span attribute key | `kosmos.observability.semconv.KOSMOS_AGENT_MAILBOX_CORRELATION_ID` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `KOSMOS_AGENT_MAILBOX_SENDER` | OTel span attr | n/a | String span attribute key | `kosmos.observability.semconv.KOSMOS_AGENT_MAILBOX_SENDER` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `KOSMOS_AGENT_MAILBOX_RECIPIENT` | OTel span attr | n/a | String span attribute key | `kosmos.observability.semconv.KOSMOS_AGENT_MAILBOX_RECIPIENT` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `KOSMOS_TUI_THEME` | No | `default` | `default` \| `dark` \| `light` | `kosmos.config.env_registry.TUISettings.theme` | [Spec 287 TUI (Epic #287)](#tui-ink-react-bun-epic-287) |
| `KOSMOS_TUI_LOG_LEVEL` | No | `WARN` | `DEBUG` \| `INFO` \| `WARN` \| `ERROR` | `kosmos.config.env_registry.TUISettings.log_level` | [Spec 287 TUI (Epic #287)](#tui-ink-react-bun-epic-287) |
| `KOSMOS_TUI_IME_STRATEGY` | No | `fork` | `fork` \| `readline` | `kosmos.config.env_registry.TUISettings.ime_strategy` | [Spec 287 TUI (Epic #287)](#tui-ink-react-bun-epic-287) |
| `KOSMOS_TUI_SOAK_EVENTS_PER_SEC` | No | `100` | Integer >= 1 | `kosmos.config.env_registry.TUISettings.soak_events_per_sec` | [Spec 287 TUI (Epic #287)](#tui-ink-react-bun-epic-287) |
| `KOSMOS_IPC_RING_SIZE` | No | `256` | Integer >= 1 | `kosmos.ipc.ring_buffer._DEFAULT_RING_SIZE` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `KOSMOS_IPC_HWM` | No | `64` | Integer >= 1 | `kosmos.ipc.backpressure._DEFAULT_HWM` / `kosmos.ipc.ring_buffer._DEFAULT_HWM` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `KOSMOS_IPC_TX_CACHE_CAPACITY` | No | `512` | Integer >= 1 | `kosmos.ipc.tx_cache._DEFAULT_CAPACITY` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `KOSMOS_IPC_CORRELATION_ID` | OTel span attr | n/a | String span attribute key | `kosmos.ipc.otel_constants.KOSMOS_IPC_CORRELATION_ID` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `KOSMOS_IPC_TRANSACTION_ID` | OTel span attr | n/a | String span attribute key | `kosmos.ipc.otel_constants.KOSMOS_IPC_TRANSACTION_ID` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `KOSMOS_IPC_TX_CACHE_STATE` | OTel span attr | n/a | String span attribute key | `kosmos.ipc.otel_constants.KOSMOS_IPC_TX_CACHE_STATE` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `KOSMOS_IPC_BACKPRESSURE_KIND` | OTel span attr | n/a | String span attribute key | `kosmos.ipc.otel_constants.KOSMOS_IPC_BACKPRESSURE_KIND` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `KOSMOS_IPC_BACKPRESSURE_SEVERITY` | OTel span attr | n/a | String span attribute key | `kosmos.ipc.otel_constants.KOSMOS_IPC_BACKPRESSURE_SEVERITY` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `KOSMOS_IPC_BACKPRESSURE_SOURCE` | OTel span attr | n/a | String span attribute key | `kosmos.ipc.otel_constants.KOSMOS_IPC_BACKPRESSURE_SOURCE` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `KOSMOS_IPC_BACKPRESSURE_QUEUE_DEPTH` | OTel span attr | n/a | String span attribute key | `kosmos.ipc.otel_constants.KOSMOS_IPC_BACKPRESSURE_QUEUE_DEPTH` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `KOSMOS_IPC_SCHEMA_HASH` | OTel span attr | n/a | String span attribute key | `kosmos.ipc.otel_constants.KOSMOS_IPC_SCHEMA_HASH` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `KOSMOS_IPC_REPLAYED` | OTel span attr | n/a | String span attribute key | `kosmos.ipc.otel_constants.KOSMOS_IPC_REPLAYED` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `KOSMOS_PERMISSION_TIMEOUT_SEC` | No | `30` | Integer [1, 300] (seconds) | `kosmos.settings.KosmosSettings.permission_timeout_sec` | [Spec 033 Permission v2 (Epic #1297)](#permission-v2-epic-1297) |
| `KOSMOS_PERMISSION_TTL_SESSION_SEC` | No | `3600` | Integer [60, 86400] (seconds) | `kosmos.settings.KosmosSettings.permission_ttl_session_sec` | [Spec 033 Permission v2 (Epic #1297)](#permission-v2-epic-1297) |
| `KOSMOS_PERMISSION_KEY_PATH` | No | `~/.kosmos/keys/ledger.key` | Absolute filesystem path | `kosmos.settings.KosmosSettings.permission_key_path` | [Spec 033 Permission v2 (Epic #1297)](#permission-v2-epic-1297) |
| `KOSMOS_PERMISSION_KEY_REGISTRY_PATH` | No | `~/.kosmos/keys/registry.json` | Absolute filesystem path | `kosmos.settings.KosmosSettings.permission_key_registry_path` | [Spec 033 Permission v2 (Epic #1297)](#permission-v2-epic-1297) |
| `KOSMOS_PERMISSION_LEDGER_PATH` | No | `~/.kosmos/consent_ledger.jsonl` | Absolute filesystem path | `kosmos.settings.KosmosSettings.permission_ledger_path` | [Spec 033 Permission v2 (Epic #1297)](#permission-v2-epic-1297) |
| `KOSMOS_PERMISSION_RULE_STORE_PATH` | No | `~/.kosmos/permissions.json` | Absolute filesystem path | `kosmos.settings.KosmosSettings.permission_rule_store_path` | [Spec 033 Permission v2 (Epic #1297)](#permission-v2-epic-1297) |
| `KOSMOS_PERMISSION_MODE` | OTel span attr | n/a | String span attribute key | `kosmos.permissions.otel_integration.KOSMOS_PERMISSION_MODE` | [Spec 033 Permission v2 (Epic #1297)](#permission-v2-epic-1297) |
| `KOSMOS_PERMISSION_DECISION` | OTel span attr | n/a | String span attribute key | `kosmos.permissions.otel_integration.KOSMOS_PERMISSION_DECISION` | [Spec 033 Permission v2 (Epic #1297)](#permission-v2-epic-1297) |
| `KOSMOS_CONSENT_RECEIPT_ID` | OTel span attr | n/a | String span attribute key | `kosmos.permissions.otel_integration.KOSMOS_CONSENT_RECEIPT_ID` | [Spec 033 Permission v2 (Epic #1297)](#permission-v2-epic-1297) |
| `KOSMOS_IPC_HANDLER` | No | `llm` | `llm` \| `echo` | `kosmos.ipc.stdio.run` | [Epic #1633 dead-code + FriendliAI migration](#epic-1633-tui-boot-recovery) |
| `KOSMOS_USER_MEMDIR_ROOT` | No | `~/.kosmos/memdir/user` | Absolute filesystem path | `kosmos.settings.KosmosSettings.user_memdir_root` | [Spec 1636 P5 plugin DX (Epic #1636)](#epic-1636-plugin-dx-5-tier) |
| `KOSMOS_PLUGIN_INSTALL_ROOT` | No | `~/.kosmos/memdir/user/plugins` | Absolute filesystem path | `kosmos.settings.KosmosSettings.plugin_install_root` | [Spec 1636 P5 plugin DX (Epic #1636)](#epic-1636-plugin-dx-5-tier) |
| `KOSMOS_PLUGIN_BUNDLE_CACHE` | No | `~/.kosmos/cache/plugin-bundles` | Absolute filesystem path | `kosmos.settings.KosmosSettings.plugin_bundle_cache` | [Spec 1636 P5 plugin DX (Epic #1636)](#epic-1636-plugin-dx-5-tier) |
| `KOSMOS_PLUGIN_VENDOR_ROOT` | No | `~/.kosmos/vendor` | Absolute filesystem path | `kosmos.settings.KosmosSettings.plugin_vendor_root` | [Spec 1636 P5 plugin DX (Epic #1636)](#epic-1636-plugin-dx-5-tier) |
| `KOSMOS_PLUGIN_CATALOG_URL` | No | `https://raw.githubusercontent.com/kosmos-plugin-store/index/main/index.json` | https:// URL or `file://` path (tests only) | `kosmos.settings.KosmosSettings.plugin_catalog_url` | [Spec 1636 P5 plugin DX (Epic #1636)](#epic-1636-plugin-dx-5-tier) |
| `KOSMOS_PLUGIN_SLSA_SKIP` | No | `false` | `true` \| `false` | `kosmos.settings.KosmosSettings.plugin_slsa_skip` | [Spec 1636 P5 plugin DX (Epic #1636)](#epic-1636-plugin-dx-5-tier) |

> **Row count**: 52 rows (47 `KOSMOS_*` active + 2 `LANGFUSE_*` + 1 `KOSMOS_OTEL_ENDPOINT` +
> 1 override-family pattern + 1 deprecated). `KOSMOS_KOROAD_API_KEY` and
> `KOSMOS_KOROAD_ACCIDENT_SEARCH_API_KEY` are concrete expansions of the
> `KOSMOS_{TOOL_ID}_API_KEY` override-family pattern and are covered by that row.
> Spec 028 added `KOSMOS_OTEL_COLLECTOR_PORT`, `KOSMOS_LANGFUSE_OTLP_ENDPOINT`, and
> `KOSMOS_LANGFUSE_OTLP_AUTH_HEADER` (rows 29–31 of KOSMOS_* active set).
> Spec 287 (T010) added `KOSMOS_TUI_THEME`, `KOSMOS_TUI_LOG_LEVEL`,
> `KOSMOS_TUI_IME_STRATEGY`, and `KOSMOS_TUI_SOAK_EVENTS_PER_SEC`
> (rows 36–39 of KOSMOS_* active set).
> Spec 032 (T053–T061) added 3 env-var rows (`KOSMOS_IPC_RING_SIZE`,
> `KOSMOS_IPC_HWM`, `KOSMOS_IPC_TX_CACHE_CAPACITY`) and 9 OTel-span-attribute
> key constants (`KOSMOS_IPC_CORRELATION_ID`, `KOSMOS_IPC_TRANSACTION_ID`,
> `KOSMOS_IPC_TX_CACHE_STATE`, `KOSMOS_IPC_BACKPRESSURE_{KIND,SEVERITY,SOURCE,QUEUE_DEPTH}`,
> `KOSMOS_IPC_SCHEMA_HASH`, `KOSMOS_IPC_REPLAYED`) — rows 41–52 of KOSMOS_* active set.

---

## Variable Details

### `KOSMOS_ENV`

Controls which environment the process is running in. The startup guard uses this value to decide
which conditional-required variables to enforce.

Valid values: `dev` (default), `ci`, `prod`. Any unrecognised value falls through to `dev`
semantics.

When `KOSMOS_ENV ∈ {prod}`, the guard also enforces `KOSMOS_OTEL_ENDPOINT`,
`LANGFUSE_PUBLIC_KEY`, and `LANGFUSE_SECRET_KEY`.

---

### <a id="kosmos_kakao_api_key"></a>`KOSMOS_KAKAO_API_KEY`

Kakao REST API key. Required in all environments. Consumed by `KosmosSettings.kakao_api_key` and
the permission pipeline's credential resolver at `kosmos.permissions.credentials`.

Source: [Kakao Developers Console](https://developers.kakao.com) → My Application → App Keys →
REST API key.

---

### <a id="kosmos_friendli_token"></a>`KOSMOS_FRIENDLI_TOKEN`

FriendliAI Serverless API bearer token for K-EXAONE inference. Required in all environments.
The `LLMClientConfig.token` field validates that the value is non-empty after stripping whitespace.

Source: [FriendliAI Suite](https://suite.friendli.ai) → API Keys.

---

### <a id="kosmos_data_go_kr_api_key"></a>`KOSMOS_DATA_GO_KR_API_KEY`

Shared 공공데이터포털 (data.go.kr) API key. Required in all environments. Used as the shared
provider credential for KOROAD, KMA, HIRA, and NMC tool adapters. A per-tool override
(`KOSMOS_{TOOL_ID}_API_KEY`) takes precedence when present.

> **Defect note (FR-050)**: Prior to Epic #468, `.github/workflows/ci.yml` injected this variable
> under the typo name `KOSMOS_DATA_GO_KR_KEY`. That typo is fixed as part of this Epic's CI
> migration. If you see the old name in any file surface, it is stale and should be rewritten.

Source: [공공데이터포털](https://www.data.go.kr) → 마이페이지 → 인증키.

---

### <a id="kosmos_juso_confm_key"></a>`KOSMOS_JUSO_CONFM_KEY`

행정안전부 도로명주소 API 확인키. **Optional fallback** — when unset, the JUSO geocoding branch
in `resolve_location.py` logs-and-skips gracefully (the adapter falls through to SGIS / Kakao).
Consumed by `KosmosSettings.juso_confm_key`.

Source: [도로명주소 개발자센터](https://business.juso.go.kr) → 신청 및 현황 → 개발자 확인키.

---

### <a id="kosmos_sgis_key"></a>`KOSMOS_SGIS_KEY`

SGIS (통계지리정보서비스) consumer key, paired with `KOSMOS_SGIS_SECRET`. **Optional fallback** —
when either is unset, the SGIS branch in `resolve_location.py` logs-and-skips gracefully.

Source: [SGIS API](https://sgis.kostat.go.kr) → 활용신청 → 서비스ID/인증키.

---

### <a id="kosmos_sgis_secret"></a>`KOSMOS_SGIS_SECRET`

SGIS consumer secret paired with `KOSMOS_SGIS_KEY`. **Optional fallback** — see
`KOSMOS_SGIS_KEY` above for the skip-when-unset behaviour.

Source: [SGIS API](https://sgis.kostat.go.kr) → 활용신청 → 서비스ID/인증키.

---

### <a id="kosmos_otel_endpoint"></a>`KOSMOS_OTEL_ENDPOINT`

OTLP HTTP endpoint for OpenTelemetry trace export. Conditional-required: the startup guard enforces
this variable only when `KOSMOS_ENV=prod`. In `dev` and `ci`, the OTel SDK is initialised in
no-op mode and this variable is not consulted.

The consuming code lives in Epic #501 (`kosmos.observability.otel`), which is not yet merged.

---

### <a id="langfuse_public_key"></a>`LANGFUSE_PUBLIC_KEY`

Langfuse public key for trace ingestion. Conditional-required (`KOSMOS_ENV=prod`). The
`LANGFUSE_*` prefix is the only permitted non-`KOSMOS_` prefix in this registry; it is used
because the Langfuse Python SDK reads these variables by default and renaming them would require
forking the SDK (FR-040, FR-043).

Source: [Langfuse Cloud](https://cloud.langfuse.com) → Settings → API Keys.

---

### <a id="langfuse_secret_key"></a>`LANGFUSE_SECRET_KEY`

Langfuse secret key paired with `LANGFUSE_PUBLIC_KEY`. Conditional-required (`KOSMOS_ENV=prod`).

Source: [Langfuse Cloud](https://cloud.langfuse.com) → Settings → API Keys.

---

### <a id="per-tool-override-pattern"></a>Per-tool Override Pattern: `KOSMOS_{TOOL_ID}_API_KEY`

Any env var matching the expansion `KOSMOS_<TOOL_ID_UPPER>_API_KEY` (e.g.,
`KOSMOS_KOROAD_ACCIDENT_SEARCH_API_KEY`) is a per-tool credential override. When present, it takes
priority over the provider-level key (`KOSMOS_DATA_GO_KR_API_KEY` or `KOSMOS_KAKAO_API_KEY`) in
the lookup chain defined by `kosmos.permissions.credentials.resolve_credential`.

The audit script treats any env var name matching this pattern as covered by this family row,
suppressing "undocumented" false positives for concrete expansions.

Lookup order (from `kosmos.permissions.credentials.resolve_credential`):

1. `KOSMOS_{TOOL_ID_UPPER}_API_KEY` (this override)
2. Provider-level key (`KOSMOS_KAKAO_API_KEY` or `KOSMOS_DATA_GO_KR_API_KEY`)
3. `KOSMOS_API_KEY` (deprecated global fallback)

Do NOT add per-tool concrete expansions as individual registry rows. Use this family row.

---

### <a id="kosmos_api_key-deprecated"></a>`KOSMOS_API_KEY` — Deprecated

**Do not use for new tool adapters.** This is the legacy global credential fallback honoured by
`kosmos.permissions.credentials.resolve_credential` as the last resort in the lookup chain.

Replacement: use the appropriate provider-level key (`KOSMOS_KAKAO_API_KEY` or
`KOSMOS_DATA_GO_KR_API_KEY`) or a per-tool override (`KOSMOS_{TOOL_ID}_API_KEY`).

Removal target: post-#468 (tracking issue #744). Removal requires a cross-tool refactor to
eliminate all remaining callers; that work is deferred.

---

## How to Add a Variable

Adding a new `KOSMOS_*` variable is a **three-file change** (NFR-006). No schema migration, no
row reordering required.

### Step 1 — Add a row to this registry

Append a new row to the [Quick Reference Table](#quick-reference-table) above. Fill all six
columns:

```
| `KOSMOS_MY_NEW_VAR` | Yes (dev/ci/prod) | — | Description of format | `kosmos.my_module.MyClass.field` | Where credential is issued |
```

Also add a `###` detail section below the table with the anchor
`<a id="kosmos_my_new_var"></a>`.

Allowed `Required` column values: `Yes (dev/ci/prod)`, `Yes (prod only)`, `No`,
`Deprecated`, `Override pattern`.

### Step 2 — Add a line to `.env.example`

Open `.env.example` and append:

```bash
KOSMOS_MY_NEW_VAR=<redacted>  # kosmos.my_module — where to get this value
```

Use `<redacted>` exclusively. Never use a plausible-looking value (hex string, bearer format, UUID).

### Step 3 — Add the consumer in source

Add the field to the relevant `BaseSettings` subclass or read it with `os.environ.get()` in the
consuming module. Reference the exact `module.Class.attribute` path in the registry row's
`Consumed by` column.

**Optionally — add to the startup guard**

If the variable must be non-empty at process start in one or more environments, add a `RequiredVar`
entry to `_REQUIRED_VARS` in `src/kosmos/config/guard.py`:

```python
RequiredVar(
    name="KOSMOS_MY_NEW_VAR",
    consumer="kosmos.my_module.MyClass.field",
    required_in=frozenset({"dev", "ci", "prod"}),
    doc_anchor="#kosmos_my_new_var",
),
```

### Step 4 — Verify locally

```bash
uv run python scripts/audit-env-registry.py
```

Exit code `0` means code and registry agree. Non-zero prints a diff-style report.

---

## Infisical Operator Runbook

This section documents how to configure Infisical Cloud Free as the secrets provider for CI.
Perform these steps once per repository setup. No secret value appears here; all token fields are
`<redacted>`.

### Prerequisites

- Infisical Cloud Free account at [app.infisical.com](https://app.infisical.com)
- GitHub repository admin access to `umyunsang/KOSMOS`
- `gh` CLI authenticated

### Step 1 — Create the Infisical project

1. Log in to Infisical Cloud.
2. Create a new project named `kosmos`.
3. Note the project UUID shown in the project settings URL (e.g.,
   `app.infisical.com/project/<UUID>/settings`). This is your `project-id` for
   `Infisical/secrets-action@v1`.
4. Create two environments inside the project: `dev` and `test` (and `prod` when needed).

### Step 2 — Add secrets

In the Infisical dashboard, navigate to the `test` environment and add each required variable from
the [Quick Reference Table](#quick-reference-table) whose `Required` column is `Yes (dev/ci/prod)`.
Use the real credential values retrieved from the respective source portals. Never paste these
values into any file committed to the repository.

At minimum, the `test` environment must contain the guard-required variables:

- `KOSMOS_FRIENDLI_TOKEN`
- `KOSMOS_KAKAO_API_KEY`
- `KOSMOS_DATA_GO_KR_API_KEY`

Optional fallback variables (if unset, the corresponding geocoding branch logs-and-skips):

- `KOSMOS_JUSO_CONFM_KEY`
- `KOSMOS_SGIS_KEY`
- `KOSMOS_SGIS_SECRET`

### Step 3 — Register a Machine Identity with OIDC auth

1. In Infisical: **Access Control** → **Machine Identities** → **Create identity**.
   Name: `kosmos-github-actions`. Role: `member` scoped to the `kosmos` project.
2. Under the identity's **Auth methods**, select **OIDC Auth** and configure:

```
Issuer URL:    https://token.actions.githubusercontent.com
Audience:      https://github.com/umyunsang
```

3. Add a claim binding (trust rule):

| Claim | Operator | Value |
|-------|----------|-------|
| `repository` | `=` | `umyunsang/KOSMOS` |
| `workflow_ref` | contains | `umyunsang/KOSMOS/.github/workflows/ci.yml` |

4. Save the identity. Note the **Client ID** (a public UUID).

### Step 4 — Bind the machine identity to the repository

No GitHub secret is required when using pure OIDC federation. Store the Client ID as a GitHub
Actions **variable** (not a secret):

```
Settings → Secrets and variables → Actions → Variables → New repository variable
Name:  INFISICAL_CLIENT_ID
Value: <the Client ID UUID from Step 3>
```

This value is a public identifier and does not need secret protection.

### Step 5 — Environment slug mapping

| CI context | Infisical env slug |
|------------|--------------------|
| Unit tests (no live APIs) | `dev` |
| Live-suite tests | `dev` |
| Release builds | `prod` (when applicable) |

The `env-slug: dev` value in `.github/workflows/ci.yml` pulls from the Infisical `dev`
environment (the default environment created by Infisical Cloud for every new project).

### Step 6 — Verify the OIDC trust

Trigger a CI run on any branch. Inspect the "Fetch secrets from Infisical" step. A successful
output looks like:

```
✓ Authenticated with Infisical using OIDC
✓ Fetched 6 secrets from project kosmos / environment dev
```

If you see a `401 Unauthorized` error, the claim binding is misconfigured. Re-check the
`repository` and `workflow_ref` claim values in Step 3.

### Step 7 — Secret rotation

To rotate any credential (e.g., `KOSMOS_FRIENDLI_TOKEN`):

1. In Infisical dashboard: `kosmos` project → `test` environment → edit the secret value.
2. Re-run CI: `gh run rerun <run-id>` or push a trivial commit.
3. The next CI run picks up the new value. **Zero code changes required.**

### Known Failure Modes

<a id="infisical-rate-limit"></a>

**Infisical service unavailable or rate-limited (HTTP 503 / 429)**

The `Infisical/secrets-action@v1` step retries once with a 5-second backoff. On persistent
failure the job fails immediately with a log message naming Infisical as the blocker. The CI
workflow never falls back to stub values or empty variables on a secrets-fetch failure (FR-034).

If your CI run fails at the secrets-fetch step with a 503 or connection error:

1. Check [Infisical status](https://status.infisical.com) for active incidents.
2. Re-run the failed CI job (`gh run rerun <run-id> --failed`).
3. If the failure persists for more than 30 minutes, follow the [Rollback Procedure](#rollback-procedure)
   to restore GitHub Encrypted Secrets temporarily.

The CI workflow posts a GitHub annotation citing
`docs/configuration.md#infisical-rate-limit` when this failure mode is detected.

**OIDC token exchange rejected**

Infisical returns `401`. Cause: the GitHub Actions OIDC token claims do not match the trust
policy. Fix: update the claim binding in Infisical (Step 3 above). Do not add a fallback secret.

**Infisical Free tier capacity**

The Free tier supports up to 5 projects and an unlimited number of secrets per project. If the
project count or audit-log retention becomes a constraint, surface it as a blocker before
splitting secrets across two platforms.

---

## Rollback Procedure

**Target**: restore CI to a working state within 15 minutes when the Infisical migration is
broken (FR-036, SC-008).

### Step 1 — Identify the pre-migration `ci.yml` commit

```bash
git log --oneline .github/workflows/ci.yml
```

Note the commit SHA immediately before the Infisical migration commit.

### Step 2 — Revert the workflow file

```bash
git revert <ci.yml-infisical-migration-commit-sha>
git push origin feat/468-secrets-config
```

This restores `ci.yml` to its pre-Infisical state, which references GitHub Encrypted Secrets.

### Step 3 — Re-populate GitHub Encrypted Secrets

Export the current secret values from Infisical (dashboard → project → export) and re-enter them
as GitHub Encrypted Secrets at:

```
Settings → Secrets and variables → Actions → New repository secret
```

Minimum set required for CI to pass (guard-required; missing = startup EX_CONFIG):

| Secret name | Source |
|-------------|--------|
| `KOSMOS_FRIENDLI_TOKEN` | Infisical export |
| `KOSMOS_KAKAO_API_KEY` | Infisical export |
| `KOSMOS_DATA_GO_KR_API_KEY` | Infisical export |

Optional fallbacks (add only if the live geocoding suite needs them):

| Secret name | Source |
|-------------|--------|
| `KOSMOS_JUSO_CONFM_KEY` | Infisical export |
| `KOSMOS_SGIS_KEY` | Infisical export |
| `KOSMOS_SGIS_SECRET` | Infisical export |

### Step 4 — Verify

Trigger a CI run and confirm the test suite passes. Once stabilised, open a new PR to re-apply
the Infisical migration after the root cause is resolved.

> The 15-minute SLO assumes the operator has Infisical dashboard access and GitHub admin rights.
> Pre-stage these access tokens in a password manager before beginning the migration.

---

## Test-only Variables

The following variables appear exclusively in test fixtures and are never read by production code.
They do not need to be populated in production or developer `.env` files.

| Variable | Purpose | Required |
|----------|---------|----------|
| `KOSMOS_AUTH_TEST_TOOL_API_KEY` | Credential fixture for permission-pipeline unit tests | No (test only) |
| `KOSMOS_SKIP_PERF` | Skip performance-sensitive assertions in slow CI environments | No (test only) |

---

## Agent Swarm (Epic #13)

Four variables control the multi-agent coordinator/worker IPC layer introduced in spec 027.

### `KOSMOS_AGENT_MAILBOX_ROOT`

Root directory for the file-based at-least-once mailbox (mailbox-abi.md §1). FileMailbox
creates `<root>/<session_id>/<sender>/` subdirectories at mode `0o700`; message files are
written at mode `0o600`.

| Property | Value |
|----------|-------|
| **Default** | `~/.kosmos/mailbox` |
| **Required** | No |
| **Range** | Absolute path (relative paths are rejected at validation time, FR-032) |
| **Consumed by** | `kosmos.agents.mailbox.file_mailbox.FileMailbox.__init__` |

### `KOSMOS_AGENT_MAILBOX_MAX_MESSAGES`

Per-session message cap enforced by `FileMailbox.send()`. When the count of `.json` files
in the session directory reaches this value, `send()` raises `MailboxOverflowError` (FR-021).

| Property | Value |
|----------|-------|
| **Default** | `1000` |
| **Required** | No |
| **Range** | Integer [100, 10 000] |
| **Consumed by** | `kosmos.agents.mailbox.file_mailbox.FileMailbox.__init__` |

### `KOSMOS_AGENT_MAX_WORKERS`

Maximum number of specialist workers spawned concurrently by one coordinator session.
Workers beyond this limit are queued. Set lower in memory-constrained environments.

| Property | Value |
|----------|-------|
| **Default** | `4` |
| **Required** | No |
| **Range** | Integer [1, 16] |
| **Consumed by** | `kosmos.agents.coordinator.Coordinator._research_phase` |

### `KOSMOS_AGENT_WORKER_TIMEOUT_SECONDS`

Seconds a worker has to post a `result` or `error` message before the coordinator
cancels it (cooperative cancellation, FR-006). A cancelled worker is treated as an
error in the final plan.

| Property | Value |
|----------|-------|
| **Default** | `120` |
| **Required** | No |
| **Range** | Integer [10, 600] |
| **Consumed by** | `kosmos.agents.coordinator.Coordinator._research_phase` |

---

## TUI Layer (Epic #287)

Variables that control the Ink + React terminal UI introduced by Spec 287.
The TUI layer reads these at startup; none of them are hot-reloaded.

### `KOSMOS_TUI_THEME`

Controls the ANSI colour token set used by all `<Box>` / `<Text>` components
in the TUI.  The theme is read once at process startup by `ThemeProvider`
(`tui/src/theme/provider.tsx`) and propagated to every child component via
React context.  Components MUST use `useTheme()` — no inline hex literals
are permitted (FR-040).

#### Allowed values

| Value | Description |
|-------|-------------|
| `default` | ANSI 16-colour safe palette — maps to the same tokens as `dark` but uses the ANSI colour names instead of explicit RGB values. Falls back gracefully on terminals without 256-colour or true-colour support. **This is the recommended value for CI and headless environments.** |
| `dark` | Dark-background palette with explicit RGB values (default choice for modern terminal emulators on dark themes). |
| `light` | Light-background palette for terminals set to a white or cream background. |

#### Precedence

Shell environment variable > `.env` file > fallback to `default`.

If the variable is **unset**, `ThemeProvider` silently uses `default`.  
If the variable is set to an **unrecognised value**, `ThemeProvider` writes a
warning to `stderr` and falls back to `default`.  The process does NOT exit.

#### Preview each theme

```bash
# Preview dark theme
KOSMOS_TUI_THEME=dark bun run tui

# Preview light theme
KOSMOS_TUI_THEME=light bun run tui

# Preview default (ANSI-safe) theme
KOSMOS_TUI_THEME=default bun run tui
```

#### Follow-up reminder

`KOSMOS_TUI_THEME` MUST also be registered in `src/kosmos/config/env_registry.py`
following the `#468` pattern (see `TUISettings` class skeleton in
`specs/287-tui-ink-react-bun/spec.md § TUI Env Vars`).  Do NOT modify
`env_registry.py` in this wave — defer to the post-wave integration step
(tracked as part of Epic #287 T052).

| Property | Value |
|----------|-------|
| **Default** | `default` |
| **Required** | No |
| **Range** | `default` \| `dark` \| `light` |
| **Consumed by** | `tui/src/theme/provider.tsx → ThemeProvider` |
| **Spec** | Spec 287 FR-039, FR-040, FR-041 |

---

## IPC Stdio Hardening (Epic #1298)

<a id="ipc-stdio-hardening-epic-1298"></a>

Variables introduced by Spec 032 (`specs/032-ipc-stdio-hardening/spec.md`) to tune
the NDJSON stdio transport between the TUI (Bun) and the Python backend, and to
expose frame-level correlation state to OpenTelemetry.

The group splits into two kinds:

1. **Env-tunable defaults** — three integers read from `os.environ` at module
   import time (ring-buffer size, high-water mark, tx-cache LRU capacity).
2. **OTel span-attribute key constants** — nine Python string constants under
   `kosmos.ipc.otel_constants` whose values (`"kosmos.ipc.*"`) are used as
   span-attribute keys by the envelope emitter.  They appear in the registry
   for provenance tracking (Epic #468 audit contract), even though they are
   not read from the environment.  This mirrors the Agent Swarm convention
   for `KOSMOS_AGENT_*` OTel span attributes (Epic #13).

### `KOSMOS_IPC_RING_SIZE`

Maximum number of frames retained in `SessionRingBuffer` per session for resume
replay (FR-018..025).  Evicted FIFO once the buffer exceeds this depth.

| Property | Value |
|----------|-------|
| **Default** | `256` |
| **Required** | No |
| **Range** | Integer >= 1 |
| **Consumed by** | `kosmos.ipc.ring_buffer._DEFAULT_RING_SIZE` |
| **Spec** | Spec 032 FR-018, FR-023 |

### `KOSMOS_IPC_HWM`

High-water mark that drives the backpressure state machine (FR-013..017).
`SessionRingBuffer.is_above_hwm()` returns True when depth >= HWM; the
resume threshold is `HWM // 2`.

| Property | Value |
|----------|-------|
| **Default** | `64` |
| **Required** | No |
| **Range** | Integer >= 1 |
| **Consumed by** | `kosmos.ipc.backpressure._DEFAULT_HWM`, `kosmos.ipc.ring_buffer._DEFAULT_HWM` |
| **Spec** | Spec 032 FR-013, FR-014 |

### `KOSMOS_IPC_TX_CACHE_CAPACITY`

Per-session LRU capacity for the transaction-id dedup cache (FR-026..033).
Controls the maximum number of cached irreversible-tool responses before the
oldest entries are evicted.

| Property | Value |
|----------|-------|
| **Default** | `512` |
| **Required** | No |
| **Range** | Integer >= 1 |
| **Consumed by** | `kosmos.ipc.tx_cache._DEFAULT_CAPACITY` |
| **Spec** | Spec 032 FR-029, FR-031 |

### `KOSMOS_IPC_HANDLER`

Selects the `user_input` frame handler in the stdio IPC loop
(`kosmos.ipc.stdio.run`). The production handler routes UserInputFrames
through `LLMClient.stream()` to FriendliAI (K-EXAONE). The echo handler
is a test-only fixture that mirrors every user_input back as
`AssistantChunkFrame(delta="[echo] {text}", done=True)` — used by
integration tests in `tui/tests/ipc/bridge.test.ts` that must not depend
on `FRIENDLI_API_KEY` or network reachability.

| Property | Value |
|----------|-------|
| **Default** | `llm` |
| **Required** | No |
| **Range** | `llm` \| `echo` |
| **Consumed by** | `kosmos.ipc.stdio.run` |
| **Spec** | Epic #1633 FR-007 |

### OTel span-attribute keys

The following nine names are **not** environment variables — they are Python
string constants whose values are the OTel span-attribute keys written by
`kosmos.ipc.envelope.emit_ndjson`.  They carry the `KOSMOS_` prefix because
their values live under the `kosmos.ipc.*` namespace; they are listed in the
registry so the drift-audit script (`scripts/audit-env-registry.py`) recognises
the symbols rather than treating them as unregistered env vars (same pattern
as the Agent Swarm `KOSMOS_AGENT_*` OTel attributes).

| Constant | Value | Purpose |
|----------|-------|---------|
| `KOSMOS_IPC_CORRELATION_ID` | `kosmos.ipc.correlation_id` | UUIDv7 correlation chain across a full turn |
| `KOSMOS_IPC_TRANSACTION_ID` | `kosmos.ipc.transaction_id` | Per-action idempotency key (irreversible tools only) |
| `KOSMOS_IPC_TX_CACHE_STATE` | `kosmos.ipc.tx.cache_state` | `miss` \| `hit` \| `stored` |
| `KOSMOS_IPC_BACKPRESSURE_KIND` | `kosmos.ipc.backpressure.signal` | `pause` \| `resume` \| `throttle` |
| `KOSMOS_IPC_BACKPRESSURE_SEVERITY` | `kosmos.ipc.backpressure.severity` | `info` \| `warn` \| `critical` |
| `KOSMOS_IPC_BACKPRESSURE_SOURCE` | `kosmos.ipc.backpressure.source` | `tui_reader` \| `backend_writer` \| `upstream_429` |
| `KOSMOS_IPC_BACKPRESSURE_QUEUE_DEPTH` | `kosmos.ipc.backpressure.queue_depth` | Outbound queue depth at emission time |
| `KOSMOS_IPC_SCHEMA_HASH` | `kosmos.ipc.schema.hash` | SHA-256 of `frame.schema.json` (FR-037) |
| `KOSMOS_IPC_REPLAYED` | `kosmos.ipc.replayed` | Frame was retransmitted after resume handshake |

Defined in `src/kosmos/ipc/otel_constants.py`; emitted via `envelope.emit_ndjson`
and `backpressure.emit_backpressure_event`.

---

## Related Documents

- `AGENTS.md` § Hard rules — prefix rule and `.env` no-write constraint
- `docs/vision.md` — six-layer architecture; this registry maps to Layer 2 (Config)
- `src/kosmos/config/guard.py` — startup guard implementation; `_REQUIRED_VARS` must stay
  in sync with the `Yes (dev/ci/prod)` and `Yes (prod only)` rows in this table
- `specs/026-secrets-infisical-oidc/spec.md` — full FR/NFR specification for Epic #468
- `scripts/audit-env-registry.py` — CI enforcement script that parses this table
