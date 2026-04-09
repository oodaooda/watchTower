# M004 EOD Price History Checklist

This checklist covers persistent asset-level end-of-day price history and EOD trend views.

## Phase 1 — Spec and Contract

- [x] Document asset-level EOD scope separate from true portfolio performance.
- [x] Define daily-close storage and range contract.
- [x] Define daily/monthly/yearly period change summaries.

**Phase 1 Tests**
- [x] Review: scope avoids claiming historical portfolio performance.

**Commit / Push Gate**
- [x] Commit after docs are updated.
- [x] Push after milestone/spec links are in place.

## Phase 2 — Backend Persistence and API

- [x] Add a dedicated daily price history table.
- [x] Add centralized fetch/store logic for daily close history.
- [x] Update `/prices/{identifier}/history` to use stored EOD data.
- [x] Add `1m`, `3m`, `ytd`, `1y`, and `max` EOD range support.
- [x] Add daily/monthly/yearly change summaries to the history response.
- [x] Wire a daily refresh path for tracked assets.

**Phase 2 Tests**
- [x] Unit: EOD range slicing works for the supported ranges.
- [x] Unit: daily/monthly/yearly change summaries are computed correctly.
- [x] Integration: history endpoint persists and returns EOD rows for a tracked asset.

**Commit / Push Gate**
- [x] Commit after backend tests pass.
- [x] Push after API verification succeeds.

## Phase 3 — UI EOD Trend Views

- [x] Update the shared price history component to use EOD ranges and change summaries.
- [x] Surface EOD trend and change cards in the grouped portfolio holding detail.
- [x] Keep the UI language focused on price history rather than portfolio performance.

**Phase 3 Tests**
- [x] Build: frontend compiles with the EOD history changes.
- [x] Review: grouped holding detail shows EOD trend plus day/month/year changes.

**Commit / Push Gate**
- [x] Commit after frontend verification passes.
- [x] Push after UI verification succeeds.
