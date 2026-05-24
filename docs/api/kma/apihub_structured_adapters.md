# KMA APIHub Structured Adapters

Spec 2800 registers KMA APIHub structured `typ02/openApi` operations as
read-only `find` adapters.

## Scope

- Source host: `https://apihub.kma.go.kr`
- API family: `/api/typ02/openApi/<service>/<operation>`
- Wrapped operations: 85
- Credential env var: `UMMAYA_KMA_API_HUB_AUTH_KEY`
- Auth query parameter: `authKey`
- Legacy `UMMAYA_DATA_GO_KR_API_KEY` / `serviceKey`: not accepted for this
  adapter family

## Catalog Evidence

The 2026-05-24 APIHub catalog pass found 235 sample URLs across category pages.
The evidence file is
[`specs/2800-kma-apihub-openapi-adapters/evidence/apihub-catalog-2026-05-24.md`](../../../specs/2800-kma-apihub-openapi-adapters/evidence/apihub-catalog-2026-05-24.md).
Only 85 structured `typ02/openApi` operations are wrapped here. The remaining
`typ01`, `typ03`, `typ05`, `typ06`, and `typ09` URL families have different
response contracts and are tracked separately.

Approved-app browser evidence showed these APIHub operations active for the
current account:

- `VilageFcstInfoService_2.0/getFcstVersion`
- `VilageFcstInfoService_2.0/getVilageFcst`
- `VilageFcstInfoService_2.0/getUltraSrtFcst`

Other cataloged operations are still registered because users may have separate
APIHub approvals. If KMA returns HTTP 401 or 403 for one of those operations,
the adapter reports an approval-aware failure instead of falling back to
data.go.kr or fabricating weather data.

## Runtime Shape

Each generated adapter:

- exposes KMA request parameters as snake_case Pydantic fields
- omits `authKey` from model-visible input
- injects `authKey` from `UMMAYA_KMA_API_HUB_AUTH_KEY`
- parses KMA XML or JSON `response.header/body/items.item`
- returns a `LookupRecord` envelope through the existing `ToolExecutor`

Specialized citizen-weather tools remain the preferred user-facing route for
forecast/current-weather questions:

- `kma_forecast_fetch`
- `kma_current_observation`
- `kma_short_term_forecast`
- `kma_ultra_short_term_forecast`

The generic APIHub wrappers are broad coverage adapters, not replacements for
the specialized weather chain.
