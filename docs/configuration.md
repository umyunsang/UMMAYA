# UMMAYA Environment Variable Registry

Authoritative reference for every environment variable consumed by UMMAYA. Adding a row here — not elsewhere — is the single source of truth.

---

## Overview

UMMAYA follows [12-Factor App Config](https://12factor.net/config): every runtime parameter that
varies between deploy environments (dev, ci, prod) is stored in the process environment, never
baked into source code.

**Prefix rule**: every variable MUST start with `UMMAYA_`. The sole permitted exception is the
`LANGFUSE_*` family, which uses the vendor SDK's default prefix convention and cannot be renamed
without forking the SDK. No other non-`UMMAYA_` prefix is allowed in `src/` code (FR-040,
FR-043).

**`.env` is read-only**: the file `.env` in the repository root is a symlink owned by your local
toolchain (e.g., a 1Password CLI shim, a macOS Keychain-backed mount). No UMMAYA code path may
write, rewrite, rename, or stat `.env`. The stdlib loader in `src/ummaya/_dotenv.py` reads through
the symlink without following it as a file.

**Shell wins over `.env`**: environment variables already set in the process environment take
priority over values in `.env`. This guarantees CI secret injection (Infisical, GitHub Actions
`env:` blocks) always wins over any local developer overrides.

---

## Quick Reference Table

Column definitions:

- **Required** — `Yes (dev/ci/prod)` means the startup guard fails immediately on absence in any
  environment. `Yes (prod only)` means the guard only enforces the variable when `UMMAYA_ENV=prod`.
  `No` means optional in all environments. `Deprecated` means the variable is still honoured for
  backward compatibility but MUST NOT be used for new tools. `Override pattern` marks a family row.
- **Default** — value used when the variable is absent and `Required` is `No`. `—` means no default
  (absence is a guard failure or the field stays empty).
- **Range** — accepted format or value set.
- **Consumed by** — fully qualified `module.Class.attribute` or `module.function` path.
- **Source doc** — where the credential is issued or the setting is documented.

| Variable | Required | Default | Range | Consumed by | Source doc |
|----------|----------|---------|-------|-------------|------------|
| `UMMAYA_ENV` | No | `dev` | `dev` \| `ci` \| `prod` | `ummaya.config.guard.current_env` | This doc |
| `UMMAYA_KAKAO_API_KEY` | No (operator-managed) | — | REST API key string | `ummaya.settings.UmmayaSettings.kakao_api_key` | [Kakao Developers Console](https://developers.kakao.com) |
| `UMMAYA_FRIENDLI_TOKEN` | No (user session) | — | Bearer token | `ummaya.llm.config.LLMClientConfig.token` | [FriendliAI Suite](https://suite.friendli.ai) |
| `UMMAYA_DATA_GO_KR_API_KEY` | No (operator-managed) | — | API key string | `ummaya.settings.UmmayaSettings.data_go_kr_api_key` | [공공데이터포털](https://www.data.go.kr) |
| `UMMAYA_KMA_API_HUB_AUTH_KEY` | No (operator-managed) | — | API Hub auth key string | `ummaya.settings.UmmayaSettings.kma_api_hub_auth_key`; KMA VilageFcst adapters | [KMA API Hub](https://apihub.kma.go.kr/) |
| `UMMAYA_LIVE_ADAPTER_MODE` | No | `auto` | `auto` \| `proxy` \| `direct` | `ummaya.tools.live_proxy.should_use_live_adapter_proxy` | [Live adapter gateway](#ummaya_live_adapter_mode) |
| `UMMAYA_LIVE_ADAPTER_PROXY_URL` | No | `https://ummaya-live-gateway-ygjh3ipzqq-du.a.run.app/v1/adapters` | HTTPS URL | `ummaya.tools.live_proxy.invoke_live_adapter_proxy` | [Live adapter gateway](#ummaya_live_adapter_proxy_url) |
| `UMMAYA_LIVE_ADAPTER_PROXY_TIMEOUT_SECONDS` | No | `30.0` | Float > 0 | `ummaya.tools.live_proxy.invoke_live_adapter_proxy` | [Live adapter gateway](#ummaya_live_adapter_proxy_timeout_seconds) |
| `UMMAYA_LIVE_ADAPTER_PROXY_TOKEN` | No (operator-managed) | — | Bearer token | `ummaya.tools.live_proxy.invoke_live_adapter_proxy` | [Live adapter gateway](#ummaya_live_adapter_proxy_token) |
| `UMMAYA_LIVE_ADAPTER_GATEWAY_TOKEN` | No (operator-managed) | — | Bearer token | `ummaya.gateway.app._require_gateway_token` | [Live adapter gateway](#ummaya_live_adapter_gateway_token) |
| `UMMAYA_LIVE_ADAPTER_GATEWAY_RATE_LIMIT_PER_MINUTE` | No | `120` | Integer >= 1 | `ummaya.gateway.app._enforce_gateway_rate_limit` | [Live adapter gateway](#ummaya_live_adapter_gateway_rate_limit_per_minute) |
| `UMMAYA_LIVE_ADAPTER_GATEWAY_MAX_BODY_BYTES` | No | `65536` | Integer >= 1024 | `ummaya.gateway.app.request_size_guard` | [Live adapter gateway](#ummaya_live_adapter_gateway_max_body_bytes) |
| `UMMAYA_PACKAGE_ROOT` | No (internal wrapper) | — | Absolute package path | `bin/ummaya`, `ummaya.tools.live_proxy.should_use_live_adapter_proxy` | [Live adapter gateway](#ummaya_package_root) |
| `UMMAYA_ENABLE_ANTHROPIC_MARKETPLACE_AUTOINSTALL` | No | `false` | `true` \| `false` (case-insensitive; `1`/`yes` also accepted) | `tui/src/utils/plugins/officialMarketplaceStartupCheck.ts` | [Plugin marketplace auto-install](#ummaya_enable_anthropic_marketplace_autoinstall) |
| `UMMAYA_JUSO_CONFM_KEY` | No (optional fallback) | — | Confirmation key string | `ummaya.settings.UmmayaSettings.juso_confm_key` | [도로명주소 개발자센터](https://business.juso.go.kr) |
| `UMMAYA_SGIS_KEY` | No (operator-managed) | — | Consumer key string | `ummaya.settings.UmmayaSettings.sgis_key` | [SGIS API](https://sgis.mods.go.kr) |
| `UMMAYA_SGIS_SECRET` | No (operator-managed) | — | Consumer secret string | `ummaya.settings.UmmayaSettings.sgis_secret` | [SGIS API](https://sgis.mods.go.kr) |
| `UMMAYA_FRIENDLI_BASE_URL` | No | `https://api.friendli.ai/serverless/v1` | Valid HTTPS URL | `ummaya.llm.config.LLMClientConfig.base_url` | FriendliAI Suite |
| `UMMAYA_FRIENDLI_MODEL` | No | `LGAI-EXAONE/K-EXAONE-236B-A23B` | Model identifier string | `ummaya.llm.config.LLMClientConfig.model` | FriendliAI Suite |
| `UMMAYA_LLM_SESSION_BUDGET` | No | `100000` | Integer > 0 (tokens) | `ummaya.llm.config.LLMClientConfig.session_budget` | This doc |
| `UMMAYA_LLM_TIMEOUT_SECONDS` | No | `300` | Float > 0 (seconds) | `ummaya.llm.config.LLMClientConfig.timeout` | This doc |
| `UMMAYA_LLM_TIMEOUT` | **Deprecated** | `300` | Float > 0 (seconds) | Legacy alias for `ummaya.llm.config.LLMClientConfig.timeout`; use `UMMAYA_LLM_TIMEOUT_SECONDS` | This doc |
| `UMMAYA_AGENTIC_LOOP_MAX_TURNS` | No | `8` | Integer >= 1 (turns) | `ummaya.ipc.stdio` (Spec 1978 T029 — bounds the CC query-engine agentic loop) | Spec 1978 |
| `UMMAYA_REACT_MAX_TURNS` | No | `8` | Integer >= 1 (turns) | `ummaya.ipc.stdio` (legacy alias for `UMMAYA_AGENTIC_LOOP_MAX_TURNS`; preserved for backward compatibility) | Spec 1978 |
| `UMMAYA_TOOL_RESULT_TIMEOUT_SECONDS` | No | `120` | Float > 0 (seconds) | `ummaya.ipc.stdio` (Spec 1978 T030 — `asyncio.gather` timeout for primitive dispatch Futures, contracts/tool-bridge-protocol.md) | Spec 1978 |
| `UMMAYA_PERMISSION_TIMEOUT_SECONDS` | No | `60` | Float > 0 (seconds) | `ummaya.ipc.stdio` (Spec 1978 T045 — permission_request → permission_response wait; D2 invariant default-deny on timeout) | Spec 1978 |
| `UMMAYA_K_EXAONE_THINKING` | No | `false` | `true` \| `false` (case-insensitive; `1`/`yes` also accepted) | `ummaya.llm.client._build_payload` (Epic #2077 / Spec 2521 — default `false` keeps citizen-visible answers on K-EXAONE's `delta.content` channel; set `true` only for reasoning-channel diagnostics or benchmark runs that explicitly need `reasoning_content` / `∴ Thinking`) | Epic #2077 / Spec 2521 |
| `UMMAYA_CHAT_MAX_TOKENS` | No | `8192` | Integer [512, 32000] | `ummaya.ipc.stdio._effective_chat_max_tokens` | Spec 2521 |
| `UMMAYA_AVAILABLE_ADAPTERS_TOP_K` | No | `5` | Integer >= 1 | `ummaya.ipc.stdio._build_available_adapters_suffix` (Spec 2521 — bounds how many BM25 candidates are emitted into the dynamic `<available_adapters>` system-prompt suffix per citizen turn; lower for prompt-cache friendliness, higher for broader recall) | Spec 2521 |
| `UMMAYA_LLM_STREAM_CHUNK_MAX_CHARS` | No | `999` | Integer >= 1 (chars) | `ummaya.llm.client._pace_text_chunk` (Spec 2521 — when set <999, splits provider deltas into sub-chunks for headless / no-Ink callers that want server-side cadence; default `999` is effectively "no extra splitting" because Ink frontend typewriter handles the in-TUI cadence) | Spec 2521 |
| `UMMAYA_LLM_STREAM_PACE_MS` | No | `0` | Float >= 0 (milliseconds) | `ummaya.llm.client._pace_text_chunk` (Spec 2521 — sleep between sub-chunk emissions for headless callers; default `0` disables backend pacing because Ink's `FRAME_INTERVAL_MS=4` throttle relax handles the cadence inside the TUI) | Spec 2521 |
| `UMMAYA_LOOKUP_TOPK` | No | `5` | Integer [1, 20] | `ummaya.settings.UmmayaSettings.lookup_topk` | This doc |
| `UMMAYA_NMC_FRESHNESS_MINUTES` | No | `30` | Integer [1, 1440] (minutes) | `ummaya.settings.UmmayaSettings.nmc_freshness_minutes` | Epic #507 |
| `UMMAYA_RETRIEVAL_BACKEND` | No | `bm25` | `bm25` \| `dense` \| `hybrid` | `ummaya.tools.retrieval.backend.build_retriever_from_env` | Epic #585 |
| `UMMAYA_RETRIEVAL_COLD_START` | No | `lazy` | `eager` \| `lazy` | `ummaya.tools.retrieval.backend._parse_cold_start` | Epic #585 |
| `UMMAYA_RETRIEVAL_FUSION` | No | `rrf` | `rrf` | `ummaya.tools.retrieval.backend._parse_fusion_config` | Epic #585 |
| `UMMAYA_RETRIEVAL_FUSION_K` | No | `60` | Integer >= 1 | `ummaya.tools.retrieval.backend._parse_fusion_config` | Epic #585 |
| `UMMAYA_RETRIEVAL_MODEL_ID` | No | `intfloat/multilingual-e5-small` | Hugging Face model ID string | `ummaya.tools.retrieval.backend.build_retriever_from_env` | Epic #585 |
| `UMMAYA_MEMDIR_USER` | No | `~/.ummaya/memdir/user` | Filesystem path (expanduser) | `ummaya.session.store._get_session_dir`; TUI memdir/session helpers | Spec 027 |
| `UMMAYA_SESSION_DIR` | No | `~/.ummaya/sessions` | Filesystem path (expanduser) | `ummaya.session.store._get_session_dir` | Epic #287 |
| `UMMAYA_BACKEND_CMD_JSON` | No | Set by packaged launcher to `["uv","--directory",<packageRoot>,"run","--frozen","--no-dev","ummaya","--ipc","stdio"]`, or to `<packageRoot>/.venv/bin/python -m ummaya.cli --ipc stdio` when that venv exists | JSON string array spawned by the TUI as the backend process; preferred over `UMMAYA_BACKEND_CMD` because paths with spaces stay unambiguous | `bin/ummaya`; TUI-side `tui/src/ipc/bridge.ts` | Release packaging |
| `UMMAYA_BACKEND_CMD` | No | `uv run ummaya --ipc stdio` when no JSON command or package launcher is present | Shell command string spawned by the TUI as the backend process | TUI-side `tui/src/ipc/bridge.ts`; `ummaya.ipc.demo.mock_backend` is the canonical Mock-backend value used by Spec 2296 PTY + vhs smoke artefacts | Epic #2296 |
| `UMMAYA_ALLOW_BACKEND_CMD_OVERRIDE` | No | `0` | Set `1` only for release/debug harnesses that intentionally replace the packaged backend command | `bin/ummaya` | Release packaging |
| `UMMAYA_TUI_PRIMITIVE_TIMEOUT_MS` | No | `30000` in raw TUI; packaged launcher sets `90000` unless already set | Milliseconds before a model-facing primitive tool call reports a TUI-side delayed-backend timeout | `tui/src/tools/_shared/dispatchPrimitive.ts`; packaged override in `bin/ummaya` | Release packaging |
| `UMMAYA_BACKEND_LOG_FILE` | No | — | Filesystem path | `ummaya.ipc.stdio.run` diagnostic FileHandler | Spec multi-turn contamination |
| `UMMAYA_CHAT_REQUEST_DUMP` | No | `false` | `1` enables diagnostic dumps; unset disables | `ummaya.ipc.stdio._diag_chat_request_enabled` | Spec multi-turn contamination |
| `UMMAYA_CLI_HISTORY_SIZE` | No | `1000` | Integer >= 0 | `ummaya.cli.config.CLIConfig.history_size` | This doc |
| `UMMAYA_CLI_SHOW_USAGE` | No | `true` | `true` \| `false` | `ummaya.cli.config.CLIConfig.show_usage` | This doc |
| `UMMAYA_CLI_WELCOME_BANNER` | No | `true` | `true` \| `false` | `ummaya.cli.config.CLIConfig.welcome_banner` | This doc |
| `UMMAYA_THEME` | No | `default` | `default` \| `dark` \| `light` | `ummaya.cli.themes.load_theme` | This doc |
| `UMMAYA_CLI_THEME` | No | `default` | `default` \| `dark` \| `light` | `ummaya.cli.themes.load_theme` (alias for `UMMAYA_THEME`) | This doc |
| `UMMAYA_OTEL_ENDPOINT` | Yes (prod only) | — | Valid HTTPS URL | `ummaya.observability.otel (#501)` | Epic #501 |
| `UMMAYA_OTEL_COLLECTOR_PORT` | No | `4318` | Integer (TCP port) | `docker-compose.dev.yml` otelcol host port binding | Epic #501, spec 028 |
| `UMMAYA_LANGFUSE_OTLP_ENDPOINT` | No | `http://langfuse-web:3000/api/public/otel` | Valid HTTP(S) URL (base, no `/v1/traces` suffix) | `infra/otel-collector/config.yaml` otlphttp exporter | Epic #501, spec 028 |
| `UMMAYA_LANGFUSE_OTLP_AUTH_HEADER` | No | `` (empty = anonymous) | `Basic <base64(pk:sk)>` string | `infra/otel-collector/config.yaml` exporter Authorization header | Epic #501, spec 028 |
| `LANGFUSE_PUBLIC_KEY` | Yes (prod only) | — | `pk-lf-…` format string | `ummaya.observability.langfuse (#501)` | [Langfuse Cloud](https://cloud.langfuse.com) |
| `LANGFUSE_SECRET_KEY` | Yes (prod only) | — | `sk-lf-…` format string | `ummaya.observability.langfuse (#501)` | [Langfuse Cloud](https://cloud.langfuse.com) |
| `UMMAYA_PROMPT_REGISTRY_LANGFUSE` | No | `false` | `true` \| `false` | `ummaya.context.prompt_loader.PromptLoader` | Epic #467 |
| `UMMAYA_LANGFUSE_HOST` | No | — | Valid HTTPS URL | `ummaya.context.prompt_loader.PromptLoader` | Epic #467 |
| `UMMAYA_LANGFUSE_PUBLIC_KEY` | No | — | `pk-lf-…` format string | `ummaya.context.prompt_loader.PromptLoader` | [Langfuse Cloud](https://cloud.langfuse.com) |
| `UMMAYA_LANGFUSE_SECRET_KEY` | No | — | `sk-lf-…` format string | `ummaya.context.prompt_loader.PromptLoader` | [Langfuse Cloud](https://cloud.langfuse.com) |
| `UMMAYA_{TOOL_ID}_API_KEY` | Override pattern | — | API key string | `ummaya.permissions.credentials._tool_specific_var` | [Per-tool override pattern](#per-tool-override-pattern) |
| `UMMAYA_API_KEY` | **Deprecated** | — | API key string | `ummaya.permissions.credentials.resolve_credential` (global fallback) | [Deprecation notice](#ummaya_api_key-deprecated) |
| `UMMAYA_AGENT_MAILBOX_ROOT` | No | `~/.ummaya/mailbox` | Absolute directory path | `ummaya.settings.UmmayaSettings.agent_mailbox_root` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `UMMAYA_AGENT_MAILBOX_MAX_MESSAGES` | No | `1000` | Integer [100, 10000] | `ummaya.settings.UmmayaSettings.agent_mailbox_max_messages` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `UMMAYA_AGENT_MAX_WORKERS` | No | `4` | Integer [1, 16] | `ummaya.settings.UmmayaSettings.agent_max_workers` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `UMMAYA_AGENT_WORKER_TIMEOUT_SECONDS` | No | `120` | Integer [10, 600] | `ummaya.settings.UmmayaSettings.agent_worker_timeout_seconds` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `UMMAYA_AGENT_COORDINATOR_PHASE` | OTel span attr | n/a | String span attribute key | `ummaya.observability.semconv.UMMAYA_AGENT_COORDINATOR_PHASE` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `UMMAYA_AGENT_ROLE` | OTel span attr | n/a | String span attribute key | `ummaya.observability.semconv.UMMAYA_AGENT_ROLE` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `UMMAYA_AGENT_SESSION_ID` | OTel span attr | n/a | String span attribute key | `ummaya.observability.semconv.UMMAYA_AGENT_SESSION_ID` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `UMMAYA_AGENT_MAILBOX_MSG_TYPE` | OTel span attr | n/a | String span attribute key | `ummaya.observability.semconv.UMMAYA_AGENT_MAILBOX_MSG_TYPE` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `UMMAYA_AGENT_MAILBOX_CORRELATION_ID` | OTel span attr | n/a | String span attribute key | `ummaya.observability.semconv.UMMAYA_AGENT_MAILBOX_CORRELATION_ID` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `UMMAYA_AGENT_MAILBOX_SENDER` | OTel span attr | n/a | String span attribute key | `ummaya.observability.semconv.UMMAYA_AGENT_MAILBOX_SENDER` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `UMMAYA_AGENT_MAILBOX_RECIPIENT` | OTel span attr | n/a | String span attribute key | `ummaya.observability.semconv.UMMAYA_AGENT_MAILBOX_RECIPIENT` | [Agent Swarm (Epic #13)](#agent-swarm-epic-13) |
| `UMMAYA_TUI_THEME` | No | `default` | `default` \| `dark` \| `light` | `ummaya.config.env_registry.TUISettings.theme` | [Spec 287 TUI (Epic #287)](#tui-ink-react-bun-epic-287) |
| `UMMAYA_TUI_LOG_LEVEL` | No | `WARN` | `DEBUG` \| `INFO` \| `WARN` \| `ERROR` | `ummaya.config.env_registry.TUISettings.log_level` | [Spec 287 TUI (Epic #287)](#tui-ink-react-bun-epic-287) |
| `UMMAYA_TUI_SOAK_EVENTS_PER_SEC` | No | `100` | Integer >= 1 | `ummaya.config.env_registry.TUISettings.soak_events_per_sec` | [Spec 287 TUI (Epic #287)](#tui-ink-react-bun-epic-287) |
| `UMMAYA_IPC_RING_SIZE` | No | `256` | Integer >= 1 | `ummaya.ipc.ring_buffer._DEFAULT_RING_SIZE` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `UMMAYA_IPC_HWM` | No | `64` | Integer >= 1 | `ummaya.ipc.backpressure._DEFAULT_HWM` / `ummaya.ipc.ring_buffer._DEFAULT_HWM` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `UMMAYA_IPC_TX_CACHE_CAPACITY` | No | `512` | Integer >= 1 | `ummaya.ipc.tx_cache._DEFAULT_CAPACITY` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `UMMAYA_IPC_CORRELATION_ID` | OTel span attr | n/a | String span attribute key | `ummaya.ipc.otel_constants.UMMAYA_IPC_CORRELATION_ID` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `UMMAYA_IPC_TRANSACTION_ID` | OTel span attr | n/a | String span attribute key | `ummaya.ipc.otel_constants.UMMAYA_IPC_TRANSACTION_ID` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `UMMAYA_IPC_TX_CACHE_STATE` | OTel span attr | n/a | String span attribute key | `ummaya.ipc.otel_constants.UMMAYA_IPC_TX_CACHE_STATE` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `UMMAYA_IPC_BACKPRESSURE_KIND` | OTel span attr | n/a | String span attribute key | `ummaya.ipc.otel_constants.UMMAYA_IPC_BACKPRESSURE_KIND` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `UMMAYA_IPC_BACKPRESSURE_SEVERITY` | OTel span attr | n/a | String span attribute key | `ummaya.ipc.otel_constants.UMMAYA_IPC_BACKPRESSURE_SEVERITY` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `UMMAYA_IPC_BACKPRESSURE_SOURCE` | OTel span attr | n/a | String span attribute key | `ummaya.ipc.otel_constants.UMMAYA_IPC_BACKPRESSURE_SOURCE` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `UMMAYA_IPC_BACKPRESSURE_QUEUE_DEPTH` | OTel span attr | n/a | String span attribute key | `ummaya.ipc.otel_constants.UMMAYA_IPC_BACKPRESSURE_QUEUE_DEPTH` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `UMMAYA_IPC_SCHEMA_HASH` | OTel span attr | n/a | String span attribute key | `ummaya.ipc.otel_constants.UMMAYA_IPC_SCHEMA_HASH` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `UMMAYA_IPC_REPLAYED` | OTel span attr | n/a | String span attribute key | `ummaya.ipc.otel_constants.UMMAYA_IPC_REPLAYED` | [Spec 032 IPC (Epic #1298)](#ipc-stdio-hardening-epic-1298) |
| `UMMAYA_PERMISSION_TIMEOUT_SEC` | No | `30` | Integer [1, 300] (seconds) | `ummaya.settings.UmmayaSettings.permission_timeout_sec` | [Spec 033 Permission v2 (Epic #1297)](#permission-v2-epic-1297) |
| `UMMAYA_PERMISSION_TTL_SESSION_SEC` | No | `3600` | Integer [60, 86400] (seconds) | `ummaya.settings.UmmayaSettings.permission_ttl_session_sec` | [Spec 033 Permission v2 (Epic #1297)](#permission-v2-epic-1297) |
| `UMMAYA_PERMISSION_KEY_PATH` | No | `~/.ummaya/keys/ledger.key` | Absolute filesystem path | `ummaya.settings.UmmayaSettings.permission_key_path` | [Spec 033 Permission v2 (Epic #1297)](#permission-v2-epic-1297) |
| `UMMAYA_PERMISSION_KEY_REGISTRY_PATH` | No | `~/.ummaya/keys/registry.json` | Absolute filesystem path | `ummaya.settings.UmmayaSettings.permission_key_registry_path` | [Spec 033 Permission v2 (Epic #1297)](#permission-v2-epic-1297) |
| `UMMAYA_PERMISSION_LEDGER_PATH` | No | `~/.ummaya/consent_ledger.jsonl` | Absolute filesystem path | `ummaya.settings.UmmayaSettings.permission_ledger_path` | [Spec 033 Permission v2 (Epic #1297)](#permission-v2-epic-1297) |
| `UMMAYA_PERMISSION_RULE_STORE_PATH` | No | `~/.ummaya/permissions.json` | Absolute filesystem path | `ummaya.settings.UmmayaSettings.permission_rule_store_path` | [Spec 033 Permission v2 (Epic #1297)](#permission-v2-epic-1297) |
| `UMMAYA_PERMISSION_MODE` | OTel span attr | n/a | String span attribute key | `ummaya.permissions.otel_integration.UMMAYA_PERMISSION_MODE` | [Spec 033 Permission v2 (Epic #1297)](#permission-v2-epic-1297) |
| `UMMAYA_PERMISSION_DECISION` | OTel span attr | n/a | String span attribute key | `ummaya.permissions.otel_integration.UMMAYA_PERMISSION_DECISION` | [Spec 033 Permission v2 (Epic #1297)](#permission-v2-epic-1297) |
| `UMMAYA_CONSENT_RECEIPT_ID` | OTel span attr | n/a | String span attribute key | `ummaya.permissions.otel_integration.UMMAYA_CONSENT_RECEIPT_ID` | [Spec 033 Permission v2 (Epic #1297)](#permission-v2-epic-1297) |
| `UMMAYA_IPC_HANDLER` | No | `llm` | `llm` \| `echo` | `ummaya.ipc.stdio.run` | [Epic #1633 dead-code + FriendliAI migration](#epic-1633-tui-boot-recovery) |
| `UMMAYA_USER_MEMDIR_ROOT` | No | `~/.ummaya/memdir/user` | Absolute filesystem path | `ummaya.settings.UmmayaSettings.user_memdir_root` | [Spec 1636 P5 plugin DX (Epic #1636)](#epic-1636-plugin-dx-5-tier) |
| `UMMAYA_PLUGIN_INSTALL_ROOT` | No | `~/.ummaya/memdir/user/plugins` | Absolute filesystem path | `ummaya.settings.UmmayaSettings.plugin_install_root` | [Spec 1636 P5 plugin DX (Epic #1636)](#epic-1636-plugin-dx-5-tier) |
| `UMMAYA_PLUGIN_BUNDLE_CACHE` | No | `~/.ummaya/cache/plugin-bundles` | Absolute filesystem path | `ummaya.settings.UmmayaSettings.plugin_bundle_cache` | [Spec 1636 P5 plugin DX (Epic #1636)](#epic-1636-plugin-dx-5-tier) |
| `UMMAYA_PLUGIN_VENDOR_ROOT` | No | `~/.ummaya/vendor` | Absolute filesystem path | `ummaya.settings.UmmayaSettings.plugin_vendor_root` | [Spec 1636 P5 plugin DX (Epic #1636)](#epic-1636-plugin-dx-5-tier) |
| `UMMAYA_PLUGIN_CATALOG_URL` | No | `https://raw.githubusercontent.com/ummaya-plugin-store/index/main/index.json` | https:// URL or `file://` path (tests only) | `ummaya.settings.UmmayaSettings.plugin_catalog_url` | [Spec 1636 P5 plugin DX (Epic #1636)](#epic-1636-plugin-dx-5-tier) |
| `UMMAYA_PLUGIN_SLSA_SKIP` | No | `false` | `true` \| `false` | `ummaya.settings.UmmayaSettings.plugin_slsa_skip` | [Spec 1636 P5 plugin DX (Epic #1636)](#epic-1636-plugin-dx-5-tier) |

> **Row count**: 55 rows (50 `UMMAYA_*` active + 2 `LANGFUSE_*` + 1 `UMMAYA_OTEL_ENDPOINT` +
> 1 override-family pattern + 1 deprecated). `UMMAYA_KOROAD_API_KEY` and
> `UMMAYA_KOROAD_ACCIDENT_SEARCH_API_KEY` are concrete expansions of the
> `UMMAYA_{TOOL_ID}_API_KEY` override-family pattern and are covered by that row.
> Spec 028 added `UMMAYA_OTEL_COLLECTOR_PORT`, `UMMAYA_LANGFUSE_OTLP_ENDPOINT`, and
> `UMMAYA_LANGFUSE_OTLP_AUTH_HEADER` (rows 29–31 of UMMAYA_* active set).
> Spec 287 (T010) added `UMMAYA_TUI_THEME`, `UMMAYA_TUI_LOG_LEVEL`,
> and `UMMAYA_TUI_SOAK_EVENTS_PER_SEC`
> (rows 36–38 of UMMAYA_* active set).
> Spec 032 (T053–T061) added 3 env-var rows (`UMMAYA_IPC_RING_SIZE`,
> `UMMAYA_IPC_HWM`, `UMMAYA_IPC_TX_CACHE_CAPACITY`) and 9 OTel-span-attribute
> key constants (`UMMAYA_IPC_CORRELATION_ID`, `UMMAYA_IPC_TRANSACTION_ID`,
> `UMMAYA_IPC_TX_CACHE_STATE`, `UMMAYA_IPC_BACKPRESSURE_{KIND,SEVERITY,SOURCE,QUEUE_DEPTH}`,
> `UMMAYA_IPC_SCHEMA_HASH`, `UMMAYA_IPC_REPLAYED`) — rows 41–52 of UMMAYA_* active set.

---

## Variable Details

### `UMMAYA_ENV`

Controls which environment the process is running in. The startup guard uses this value to decide
which conditional-required variables to enforce.

Valid values: `dev` (default), `ci`, `prod`. Any unrecognised value falls through to `dev`
semantics.

When `UMMAYA_ENV ∈ {prod}`, the guard also enforces `UMMAYA_OTEL_ENDPOINT`,
`LANGFUSE_PUBLIC_KEY`, and `LANGFUSE_SECRET_KEY`.

---

### <a id="ummaya_kakao_api_key"></a>`UMMAYA_KAKAO_API_KEY`

Kakao REST API key. Operator-managed; required only for live adapter execution paths that call
Kakao-backed services. Consumed by `UmmayaSettings.kakao_api_key` and the permission pipeline's
credential resolver at `ummaya.permissions.credentials`.

Source: [Kakao Developers Console](https://developers.kakao.com) → My Application → App Keys →
REST API key.

---

### <a id="ummaya_friendli_token"></a>`UMMAYA_FRIENDLI_TOKEN`

FriendliAI Serverless API bearer token for K-EXAONE inference. Public CLI users provide this
through `/login`; it is a user session credential, not an
operator-managed Infisical secret. Backend-only developers may export it locally for live LLM
tests. The startup guard does not require it; `LLMClientConfig.token` validates it at LLM use time.

Source: [FriendliAI Suite](https://suite.friendli.ai) → API Keys.

---

### <a id="ummaya_data_go_kr_api_key"></a>`UMMAYA_DATA_GO_KR_API_KEY`

Shared 공공데이터포털 (data.go.kr) API key. Operator-managed; required only for live adapter
execution paths that call KOROAD, HIRA, NMC, or similar public-data services. A per-tool
override (`UMMAYA_{TOOL_ID}_API_KEY`) takes precedence when present.

> **Defect note (FR-050)**: Prior to Epic #468, `.github/workflows/ci.yml` injected this variable
> under the typo name `UMMAYA_DATA_GO_KR_KEY`. That typo is fixed as part of this Epic's CI
> migration. If you see the old name in any file surface, it is stale and should be rewritten.

Source: [공공데이터포털](https://www.data.go.kr) → 마이페이지 → 인증키.

---

### <a id="ummaya_kma_api_hub_auth_key"></a>`UMMAYA_KMA_API_HUB_AUTH_KEY`

KMA API Hub authentication key. Operator-managed; KMA-owned API Hub adapters use this
credential with the `authKey` query parameter on `https://apihub.kma.go.kr/api/...`.

The KMA VilageFcst adapters intentionally do not accept the data.go.kr `serviceKey`
credential. data.go.kr and KMA API Hub expose overlapping operation names, but the hosts,
credential names, and API utilization approvals are separate.

Source: [KMA API Hub](https://apihub.kma.go.kr/) → 마이페이지 → 인증키.

---

### <a id="ummaya_live_adapter_mode"></a>`UMMAYA_LIVE_ADAPTER_MODE`

Controls how live public-API adapters are invoked.

- `auto` (default): packaged CLI executions route eligible live adapters through the
  operator-managed gateway; source-tree executions use direct local adapters.
- `proxy`: force the operator-managed gateway route.
- `direct`: force the legacy local-env route for source/self-hosted development.

This keeps public release users from needing Kakao/data.go.kr/KMA API Hub credentials while avoiding
packaging those operator-managed credentials into npm/Homebrew artifacts.

---

### <a id="ummaya_live_adapter_proxy_url"></a>`UMMAYA_LIVE_ADAPTER_PROXY_URL`

Base URL for the operator-managed live adapter gateway. The CLI posts validated adapter
parameters to `{UMMAYA_LIVE_ADAPTER_PROXY_URL}/{tool_id}` and expects the same Lookup/Locate
envelope shape a local adapter would return.

This value is not a secret and may be packaged as a default. It must point to a service whose
server-side runtime holds `UMMAYA_KAKAO_API_KEY`, `UMMAYA_KMA_API_HUB_AUTH_KEY`,
`UMMAYA_DATA_GO_KR_API_KEY`, and any other operator-managed public API credentials in a
secret manager.

---

### <a id="ummaya_live_adapter_proxy_timeout_seconds"></a>`UMMAYA_LIVE_ADAPTER_PROXY_TIMEOUT_SECONDS`

Positive HTTP timeout, in seconds, for the operator-managed live adapter gateway.

---

### <a id="ummaya_live_adapter_proxy_token"></a>`UMMAYA_LIVE_ADAPTER_PROXY_TOKEN`

Optional bearer token for private or self-hosted live adapter gateways. Public release users
should not need to set this. If a gateway requires it, provision it through the operator's
deployment environment or secure credential store rather than checking it into the package.

---

### <a id="ummaya_live_adapter_gateway_token"></a>`UMMAYA_LIVE_ADAPTER_GATEWAY_TOKEN`

Optional server-side bearer token enforced by `ummaya-live-gateway`. When set, gateway
requests must include `Authorization: Bearer <token>`. Keep this value in the gateway
deployment secret store only. Do not package it into npm/Homebrew artifacts.

---

### <a id="ummaya_live_adapter_gateway_rate_limit_per_minute"></a>`UMMAYA_LIVE_ADAPTER_GATEWAY_RATE_LIMIT_PER_MINUTE`

Server-side per-client, per-tool rate limit for `ummaya-live-gateway`. This is an
instance-local abuse-control guard and should be paired with platform controls such as Cloud
Run maximum instances and Cloud Armor/API gateway limits for public deployments.

---

### <a id="ummaya_live_adapter_gateway_max_body_bytes"></a>`UMMAYA_LIVE_ADAPTER_GATEWAY_MAX_BODY_BYTES`

Maximum accepted request body size for `ummaya-live-gateway`. Oversized requests are rejected
before adapter dispatch.

---

### <a id="ummaya_package_root"></a>`UMMAYA_PACKAGE_ROOT`

Internal path set by the npm/Homebrew `bin/ummaya` wrapper. In `UMMAYA_LIVE_ADAPTER_MODE=auto`,
presence of this value marks a packaged CLI execution and selects the live adapter gateway for
eligible Kakao/data.go.kr/KMA API Hub-style adapters. The packaged launcher now force-sets this
to its own package root so arbitrary-cwd runs and stale shell environments cannot point the backend
at another checkout. Users should not set this manually.

---

### <a id="ummaya_enable_anthropic_marketplace_autoinstall"></a>`UMMAYA_ENABLE_ANTHROPIC_MARKETPLACE_AUTOINSTALL`

Opt-in switch for the upstream Anthropic plugin marketplace auto-install path inherited from
Claude Code. UMMAYA disables this by default so a fresh public-service CLI install does not clone
or register third-party Anthropic marketplace state during startup. Set this only for compatibility
testing of the inherited plugin marketplace code path.

---

### <a id="ummaya_juso_confm_key"></a>`UMMAYA_JUSO_CONFM_KEY`

행정안전부 도로명주소 API 확인키. Operator-managed live gateway deployments require this value
so every registered locate provider can run without fallback. Source-tree direct development may
omit it when not exercising the JUSO adapter.

Source: [도로명주소 개발자센터](https://business.juso.go.kr) → 신청 및 현황 → 개발자 확인키.

---

### <a id="ummaya_sgis_key"></a>`UMMAYA_SGIS_KEY`

SGIS (통계지리정보서비스) consumer key, paired with `UMMAYA_SGIS_SECRET`. Operator-managed live
gateway deployments require the complete key/secret pair. The Data API authentication endpoint
requires both `consumer_key` and `consumer_secret`.

Source: [SGIS API](https://sgis.mods.go.kr) → 활용신청 → 서비스ID/서비스 Secret.

---

### <a id="ummaya_sgis_secret"></a>`UMMAYA_SGIS_SECRET`

SGIS consumer secret paired with `UMMAYA_SGIS_KEY`. Operator-managed live gateway deployments
fail startup when this value is missing.

Source: [SGIS API](https://sgis.mods.go.kr) → 활용신청 → 서비스ID/서비스 Secret.

---

### <a id="ummaya_otel_endpoint"></a>`UMMAYA_OTEL_ENDPOINT`

OTLP HTTP endpoint for OpenTelemetry trace export. Conditional-required: the startup guard enforces
this variable only when `UMMAYA_ENV=prod`. In `dev` and `ci`, the OTel SDK is initialised in
no-op mode and this variable is not consulted.

The consuming code lives in Epic #501 (`ummaya.observability.otel`), which is not yet merged.

---

### <a id="langfuse_public_key"></a>`LANGFUSE_PUBLIC_KEY`

Langfuse public key for trace ingestion. Conditional-required (`UMMAYA_ENV=prod`). The
`LANGFUSE_*` prefix is the only permitted non-`UMMAYA_` prefix in this registry; it is used
because the Langfuse Python SDK reads these variables by default and renaming them would require
forking the SDK (FR-040, FR-043).

Source: [Langfuse Cloud](https://cloud.langfuse.com) → Settings → API Keys.

---

### <a id="langfuse_secret_key"></a>`LANGFUSE_SECRET_KEY`

Langfuse secret key paired with `LANGFUSE_PUBLIC_KEY`. Conditional-required (`UMMAYA_ENV=prod`).

Source: [Langfuse Cloud](https://cloud.langfuse.com) → Settings → API Keys.

---

### <a id="per-tool-override-pattern"></a>Per-tool Override Pattern: `UMMAYA_{TOOL_ID}_API_KEY`

Any env var matching the expansion `UMMAYA_<TOOL_ID_UPPER>_API_KEY` (e.g.,
`UMMAYA_KOROAD_ACCIDENT_SEARCH_API_KEY`) is a per-tool credential override. When present, it takes
priority over the provider-level key (`UMMAYA_KMA_API_HUB_AUTH_KEY`,
`UMMAYA_DATA_GO_KR_API_KEY`, or `UMMAYA_KAKAO_API_KEY`) in the lookup chain defined by
`ummaya.permissions.credentials.resolve_credential`.

This family pattern covers concrete per-tool expansions and keeps env-var reviews aligned
with the registry contract (no false-positive regressions on concrete
`UMMAYA_<TOOL_ID>_API_KEY` keys).

Lookup order (from `ummaya.permissions.credentials.resolve_credential`):

1. `UMMAYA_{TOOL_ID_UPPER}_API_KEY` (this override)
2. Provider-level key (`UMMAYA_KAKAO_API_KEY`, `UMMAYA_KMA_API_HUB_AUTH_KEY`, or `UMMAYA_DATA_GO_KR_API_KEY`)
3. `UMMAYA_API_KEY` (deprecated global fallback)

Do NOT add per-tool concrete expansions as individual registry rows. Use this family row.

---

### <a id="ummaya_api_key-deprecated"></a>`UMMAYA_API_KEY` — Deprecated

**Do not use for new tool adapters.** This is the legacy global credential fallback honoured by
`ummaya.permissions.credentials.resolve_credential` as the last resort in the lookup chain.

Replacement: use the appropriate provider-level key (`UMMAYA_KAKAO_API_KEY`,
`UMMAYA_KMA_API_HUB_AUTH_KEY`, or `UMMAYA_DATA_GO_KR_API_KEY`) or a per-tool override
(`UMMAYA_{TOOL_ID}_API_KEY`).

Removal target: post-#468 (tracking issue #744). Removal requires a cross-tool refactor to
eliminate all remaining callers; that work is deferred.

---

## How to Add a Variable

Adding a new `UMMAYA_*` variable is a **three-file change** (NFR-006). No schema migration, no
row reordering required.

### Step 1 — Add a row to this registry

Append a new row to the [Quick Reference Table](#quick-reference-table) above. Fill all six
columns:

```
| `UMMAYA_MY_NEW_VAR` | Yes (dev/ci/prod) | — | Description of format | `ummaya.my_module.MyClass.field` | Where credential is issued |
```

Also add a `###` detail section below the table with the anchor
`<a id="ummaya_my_new_var"></a>`.

Allowed `Required` column values: `Yes (dev/ci/prod)`, `Yes (prod only)`, `No`,
`Deprecated`, `Override pattern`.

### Step 2 — Add a line to `.env.example`

Open `.env.example` and append:

```bash
UMMAYA_MY_NEW_VAR=<redacted>  # ummaya.my_module — where to get this value
```

Use `<redacted>` exclusively. Never use a plausible-looking value (hex string, bearer format, UUID).

### Step 3 — Add the consumer in source

Add the field to the relevant `BaseSettings` subclass or read it with `os.environ.get()` in the
consuming module. Reference the exact `module.Class.attribute` path in the registry row's
`Consumed by` column.

**Optionally — add to the startup guard**

If the variable must be non-empty at process start in one or more environments, add a `RequiredVar`
entry to `_REQUIRED_VARS` in `src/ummaya/config/guard.py`:

```python
RequiredVar(
    name="UMMAYA_MY_NEW_VAR",
    consumer="ummaya.my_module.MyClass.field",
    required_in=frozenset({"dev", "ci", "prod"}),
    doc_anchor="#ummaya_my_new_var",
),
```

### Step 4 — Verify locally

변경 반영 전/후로 아래 항목을 점검하세요:

- 변수명 규칙(`UMMAYA_*` + 승인된 예외)을 준수하는지.
- 표의 `Consumed by`가 실제 모듈 경로와 일치하는지.
- `UMMAYA_FRIENDLI_TOKEN`은 사용자 세션 키로 분리되어 있는지.
- 운영자 키(`UMMAYA_KAKAO_API_KEY`, `UMMAYA_KMA_API_HUB_AUTH_KEY`,
  `UMMAYA_DATA_GO_KR_API_KEY`, per-tool 키)는 환경 변수 정책을 만족하는지.
- 필요한 경우 해당 기능/권한/세션 테스트로 회귀를 확인했는지.

---

## Infisical Operator Runbook

This section documents how to configure Infisical Cloud Free as the secrets provider for CI.
Perform these steps once per repository setup. No secret value appears here; all token fields are
`<redacted>`.

### Prerequisites

- Infisical Cloud Free account at [app.infisical.com](https://app.infisical.com)
- GitHub repository admin access to `umyunsang/UMMAYA`
- `gh` CLI authenticated

### Step 1 — Create the Infisical project

1. Log in to Infisical Cloud.
2. Create a new project named `ummaya`.
3. Note the project UUID shown in the project settings URL (e.g.,
   `app.infisical.com/project/<UUID>/settings`). This is your `project-id` for
   `Infisical/secrets-action@v1`.
4. Create environments inside the project: `dev`, `staging`, and `prod`.

### Step 2 — Add secrets

In the Infisical dashboard, navigate to the `dev` environment and add operator-managed provider
credentials needed by live adapters. Use the real credential values retrieved from the respective
source portals. Never paste these values into any file committed to the repository.

At minimum, live-adapter operator environments normally contain:

- `UMMAYA_KAKAO_API_KEY`
- `UMMAYA_DATA_GO_KR_API_KEY`
- `UMMAYA_KMA_API_HUB_AUTH_KEY`

Do not store `UMMAYA_FRIENDLI_TOKEN` in Infisical. Public CLI users enter their own FriendliAI key
through `/login`, and CI/unit tests use dummy local values where a code path explicitly needs the
variable.

Optional fallback variables (if unset, the corresponding geocoding branch logs-and-skips):

- `UMMAYA_JUSO_CONFM_KEY`
- `UMMAYA_SGIS_KEY`
- `UMMAYA_SGIS_SECRET`

### Step 3 — Register a Machine Identity with OIDC auth

1. In Infisical: **Access Control** → **Machine Identities** → **Create identity**.
   Name: `github-actions-ummaya`. Role: `member` scoped to the `ummaya` project.
2. Under the identity's **Auth methods**, select **OIDC Auth** and configure:

```
Issuer URL:    https://token.actions.githubusercontent.com
Audience:      https://github.com/umyunsang
```

3. Add a claim binding (trust rule):

| Claim | Operator | Value |
|-------|----------|-------|
| `repository` | `=` | `umyunsang/UMMAYA` |
| `workflow_ref` | contains | `umyunsang/UMMAYA/.github/workflows/ci.yml` |

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
| Staging release rehearsal | `staging` |
| Release builds | `prod` (when applicable) |

The `env-slug: dev` value in `.github/workflows/ci.yml` pulls from the Infisical `dev`
environment (the default environment created by Infisical Cloud for every new project).

Packaging release workflows should reuse the same Infisical OIDC pattern with a
separate `prod` environment and workflow-specific claim bindings. PyPI and npm
publishing should use registry-native Trusted Publishing when available; Infisical-held
registry tokens, if present, are break-glass fallback secrets rather than the default
release path. Homebrew tap credentials and other non-registry release secrets belong in
Infisical, not GitHub encrypted secrets.

### Step 6 — Verify the OIDC trust

Trigger a CI run on any branch. Inspect the "Fetch secrets from Infisical" step. A successful
output looks like:

```
✓ Authenticated with Infisical using OIDC
✓ Fetched 6 secrets from project ummaya / environment dev
```

If you see a `401 Unauthorized` error, the claim binding is misconfigured. Re-check the
`repository` and `workflow_ref` claim values in Step 3.

### Step 7 — Secret rotation

To rotate any operator-managed credential (e.g., `UMMAYA_DATA_GO_KR_API_KEY`):

1. In Infisical dashboard: `ummaya` project → `dev` environment → edit the secret value.
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

Minimum operator-managed set for live-adapter CI fallback:

| Secret name | Source |
|-------------|--------|
| `UMMAYA_KAKAO_API_KEY` | Infisical export |
| `UMMAYA_DATA_GO_KR_API_KEY` | Infisical export |
| `UMMAYA_KMA_API_HUB_AUTH_KEY` | Infisical export |

Optional fallbacks (add only if the live geocoding suite needs them):

| Secret name | Source |
|-------------|--------|
| `UMMAYA_JUSO_CONFM_KEY` | Infisical export |
| `UMMAYA_SGIS_KEY` | Infisical export |
| `UMMAYA_SGIS_SECRET` | Infisical export |

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
| `UMMAYA_AUTH_TEST_TOOL_API_KEY` | Credential fixture for permission-pipeline unit tests | No (test only) |
| `UMMAYA_SKIP_PERF` | Skip performance-sensitive assertions in slow CI environments | No (test only) |

---

## Agent Swarm (Epic #13)

Four variables control the multi-agent coordinator/worker IPC layer introduced in spec 027.

### `UMMAYA_AGENT_MAILBOX_ROOT`

Root directory for the file-based at-least-once mailbox (mailbox-abi.md §1). FileMailbox
creates `<root>/<session_id>/<sender>/` subdirectories at mode `0o700`; message files are
written at mode `0o600`.

| Property | Value |
|----------|-------|
| **Default** | `~/.ummaya/mailbox` |
| **Required** | No |
| **Range** | Absolute path (relative paths are rejected at validation time, FR-032) |
| **Consumed by** | `ummaya.agents.mailbox.file_mailbox.FileMailbox.__init__` |

### `UMMAYA_AGENT_MAILBOX_MAX_MESSAGES`

Per-session message cap enforced by `FileMailbox.send()`. When the count of `.json` files
in the session directory reaches this value, `send()` raises `MailboxOverflowError` (FR-021).

| Property | Value |
|----------|-------|
| **Default** | `1000` |
| **Required** | No |
| **Range** | Integer [100, 10 000] |
| **Consumed by** | `ummaya.agents.mailbox.file_mailbox.FileMailbox.__init__` |

### `UMMAYA_AGENT_MAX_WORKERS`

Maximum number of specialist workers spawned concurrently by one coordinator session.
Workers beyond this limit are queued. Set lower in memory-constrained environments.

| Property | Value |
|----------|-------|
| **Default** | `4` |
| **Required** | No |
| **Range** | Integer [1, 16] |
| **Consumed by** | `ummaya.agents.coordinator.Coordinator._research_phase` |

### `UMMAYA_AGENT_WORKER_TIMEOUT_SECONDS`

Seconds a worker has to post a `result` or `error` message before the coordinator
cancels it (cooperative cancellation, FR-006). A cancelled worker is treated as an
error in the final plan.

| Property | Value |
|----------|-------|
| **Default** | `120` |
| **Required** | No |
| **Range** | Integer [10, 600] |
| **Consumed by** | `ummaya.agents.coordinator.Coordinator._research_phase` |

---

## TUI Layer (Epic #287)

Variables that control the Ink + React terminal UI introduced by Spec 287.
The TUI layer reads these at startup; none of them are hot-reloaded.

### `UMMAYA_TUI_THEME`

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
UMMAYA_TUI_THEME=dark bun run tui

# Preview light theme
UMMAYA_TUI_THEME=light bun run tui

# Preview default (ANSI-safe) theme
UMMAYA_TUI_THEME=default bun run tui
```

#### Follow-up reminder

`UMMAYA_TUI_THEME` MUST also be registered in `src/ummaya/config/env_registry.py`
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
   `ummaya.ipc.otel_constants` whose values (`"ummaya.ipc.*"`) are used as
   span-attribute keys by the envelope emitter.  They appear in the registry
   for provenance tracking (Epic #468 audit contract), even though they are
   not read from the environment.  This mirrors the Agent Swarm convention
   for `UMMAYA_AGENT_*` OTel span attributes (Epic #13).

### `UMMAYA_IPC_RING_SIZE`

Maximum number of frames retained in `SessionRingBuffer` per session for resume
replay (FR-018..025).  Evicted FIFO once the buffer exceeds this depth.

| Property | Value |
|----------|-------|
| **Default** | `256` |
| **Required** | No |
| **Range** | Integer >= 1 |
| **Consumed by** | `ummaya.ipc.ring_buffer._DEFAULT_RING_SIZE` |
| **Spec** | Spec 032 FR-018, FR-023 |

### `UMMAYA_IPC_HWM`

High-water mark that drives the backpressure state machine (FR-013..017).
`SessionRingBuffer.is_above_hwm()` returns True when depth >= HWM; the
resume threshold is `HWM // 2`.

| Property | Value |
|----------|-------|
| **Default** | `64` |
| **Required** | No |
| **Range** | Integer >= 1 |
| **Consumed by** | `ummaya.ipc.backpressure._DEFAULT_HWM`, `ummaya.ipc.ring_buffer._DEFAULT_HWM` |
| **Spec** | Spec 032 FR-013, FR-014 |

### `UMMAYA_IPC_TX_CACHE_CAPACITY`

Per-session LRU capacity for the transaction-id dedup cache (FR-026..033).
Controls the maximum number of cached irreversible-tool responses before the
oldest entries are evicted.

| Property | Value |
|----------|-------|
| **Default** | `512` |
| **Required** | No |
| **Range** | Integer >= 1 |
| **Consumed by** | `ummaya.ipc.tx_cache._DEFAULT_CAPACITY` |
| **Spec** | Spec 032 FR-029, FR-031 |

### `UMMAYA_IPC_HANDLER`

Selects the `user_input` frame handler in the stdio IPC loop
(`ummaya.ipc.stdio.run`). The production handler routes UserInputFrames
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
| **Consumed by** | `ummaya.ipc.stdio.run` |
| **Spec** | Epic #1633 FR-007 |

### OTel span-attribute keys

The following nine names are **not** environment variables — they are Python
string constants whose values are the OTel span-attribute keys written by
`ummaya.ipc.envelope.emit_ndjson`.  They carry the `UMMAYA_` prefix because
their values live under the `ummaya.ipc.*` namespace; they are listed in the
registry so env-var review and migration checks recognise
the symbols rather than treating them as unregistered env vars (same pattern
as the Agent Swarm `UMMAYA_AGENT_*` OTel attributes).

| Constant | Value | Purpose |
|----------|-------|---------|
| `UMMAYA_IPC_CORRELATION_ID` | `ummaya.ipc.correlation_id` | UUIDv7 correlation chain across a full turn |
| `UMMAYA_IPC_TRANSACTION_ID` | `ummaya.ipc.transaction_id` | Per-action idempotency key (irreversible tools only) |
| `UMMAYA_IPC_TX_CACHE_STATE` | `ummaya.ipc.tx.cache_state` | `miss` \| `hit` \| `stored` |
| `UMMAYA_IPC_BACKPRESSURE_KIND` | `ummaya.ipc.backpressure.signal` | `pause` \| `resume` \| `throttle` |
| `UMMAYA_IPC_BACKPRESSURE_SEVERITY` | `ummaya.ipc.backpressure.severity` | `info` \| `warn` \| `critical` |
| `UMMAYA_IPC_BACKPRESSURE_SOURCE` | `ummaya.ipc.backpressure.source` | `tui_reader` \| `backend_writer` \| `upstream_429` |
| `UMMAYA_IPC_BACKPRESSURE_QUEUE_DEPTH` | `ummaya.ipc.backpressure.queue_depth` | Outbound queue depth at emission time |
| `UMMAYA_IPC_SCHEMA_HASH` | `ummaya.ipc.schema.hash` | SHA-256 of `frame.schema.json` (FR-037) |
| `UMMAYA_IPC_REPLAYED` | `ummaya.ipc.replayed` | Frame was retransmitted after resume handshake |

Defined in `src/ummaya/ipc/otel_constants.py`; emitted via `envelope.emit_ndjson`
and `backpressure.emit_backpressure_event`.

---

## Related Documents

- `AGENTS.md` § Hard rules — prefix rule and `.env` no-write constraint
- `docs/vision.md` — six-layer architecture; this registry maps to Layer 2 (Config)
- `src/ummaya/config/guard.py` — startup guard implementation; `_REQUIRED_VARS` must stay
  in sync with the `Yes (dev/ci/prod)` and `Yes (prod only)` rows in this table
- `specs/026-secrets-infisical-oidc/spec.md` — full FR/NFR specification for Epic #468
