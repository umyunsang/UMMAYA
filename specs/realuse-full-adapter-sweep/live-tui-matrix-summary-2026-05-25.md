# Live TUI Matrix Summary - 2026-05-25

Scope: mock scenarios and `mock_` adapters excluded. These captures exercise live
TUI user queries through the FriendliAI/K-EXAONE tool loop, the backend stdio
tool surface, and concrete live adapters.

## Effective Result

- Pass: 10
- Remaining failure: 2
- Mock scenarios executed after the user exclusion request: 0

## Passed In `captures-live-only-final`

- `LOC-ER-HADAN-001`: Kakao locate -> NMC emergency search, returned `큐병원`.
- `LOC-WEATHER-DADAE-001`: Kakao locate -> KMA current/forecast path, used `nx=97`, `ny=74`.
- `LOC-WEATHER-CURRENT-001`: locate -> `kma_current_observation`.
- `SAFETY-WEATHER-ALERT-001`: KMA weather alert/pre-warning path.
- `HEALTH-HIRA-PEDIATRIC-001`: locate -> HIRA hospital search, exact decimal coordinates.
- `MOBILITY-ACCIDENT-HOTSPOT-001`: locate -> `koroad_accident_hazard_search` -> KMA weather.
- `WELFARE-ELIGIBILITY-001`: MOHW/SSIS welfare eligibility read-only lookup.
- `SESSION-CONTINUATION-001`: prior-session place context did not contaminate the new weather lookup.

## Passed In Rerun

- `SAFETY-NFA119-001`: NFA119 live API returned `천안동남소방서`, `202112`, and 구급활동 data.
- `DISCOVERY-TOOL-SEARCH-001`: live tool discovery selected `koroad_accident_hazard_search` before KMA weather.

Rerun capture root: `specs/realuse-full-adapter-sweep/captures-live-only-rerun-nfa-discovery/`.

## Remaining Failures

- `NEG-UNKNOWN-LOCATION-001`: the model did not issue a locate/tool call within the scenario deadline. No live adapter failure was observed; this is a clarification/error-recovery behavior gap.
- `NEG-AMBIGUOUS-PLACE-001`: the model resolved ambiguous `중앙로` through Kakao and called HIRA instead of asking for clarification. The live adapter call itself succeeded; this is an ambiguity-policy behavior gap.
