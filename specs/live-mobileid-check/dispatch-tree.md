# Dispatch Tree: Live MobileID Check Adapter

## Registry Path

```text
register_all_tools()
  ├─ register_mvp_surface()
  ├─ import mock adapters
  ├─ register live_verify_mobile_id
  │    ├─ registry.register(GovAPITool(... primitive="check" ...))
  │    ├─ executor.register_adapter("live_verify_mobile_id", adapter)
  │    └─ register_verify_adapter("mobile_id", invoke, tool_id="live_verify_mobile_id")
  └─ bridge_per_primitive_registries()
       └─ skip existing live_verify_mobile_id registration
```

## Engine Path

```text
User prompt
  └─ query engine selects root primitive "check"
       └─ _dispatch_root_primitive()
            └─ tool_executor.invoke_raw("live_verify_mobile_id", params)
                 └─ live adapter validates input
                      ├─ optional /mip/vp call when vp metadata is provided
                      ├─ /mip/trxsts call
                      └─ MobileIdContext output
```

## Stdio Primitive Path

```text
check tool call with tool_id="live_verify_mobile_id"
  └─ _dispatch_primitive()
       ├─ resolve_family("live_verify_mobile_id") -> "mobile_id"
       ├─ _build_verify_session_context() adds _verify_tool_id
       └─ verify(family_hint="mobile_id", session_context)
            └─ selected adapter key "live_verify_mobile_id"
```

## Safety Branches

```text
Missing trxcode
  └─ validation error before HTTP call

Malformed MIP envelope
  └─ sanitized MobileIdEnvelopeError

Upstream non-2xx or timeout
  └─ sanitized MobileIdUpstreamError

Expired or non-complete status
  └─ sanitized MobileIdVerificationError

Unknown selected tool id
  └─ no fallback to mock adapter
```

## Non-Goals

- No `find`, `locate`, or `send` registration.
- No Government24 live submit.
- No downstream MobileID delegation-token minting.
- No raw VP or decrypted identity field persistence.
