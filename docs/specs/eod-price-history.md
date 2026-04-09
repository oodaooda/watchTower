# Spec: End-of-Day Asset Price History

## Purpose

Add persistent end-of-day price history for tracked assets so watchTower can show daily-close trends and period-over-period price changes without claiming full portfolio performance.

## Scope

- Persistent daily close history for supported assets
- API support for EOD history ranges and period change summaries
- UI support for asset-level daily/monthly/yearly trend viewing
- Daily refresh path for tracked assets

## Non-Goals

- True historical portfolio performance
- Contribution-adjusted returns
- Transaction-aware backfilled portfolio charts
- Benchmark-relative portfolio analytics

## Product Decisions

- Focus on asset-level EOD history first
- Use daily close data as the source of truth for trend charts
- Keep portfolio performance work separate until dated holdings or transactions exist
- Support stocks and ETFs in v1

## Core Contract

- Daily close history is stored in a dedicated table keyed by asset and trading date.
- The API serves EOD ranges from stored history and may refresh stale history from the market data provider.
- The UI should show asset-level period changes for day, month, and year using EOD closes.
- Any UI copy should say `price history` or `EOD trend`, not `portfolio performance`.

## Range Contract

Initial ranges:

- `1m`
- `3m`
- `ytd`
- `1y`
- `max`

Period change summaries:

- `1d`
- `1m`
- `1y`

Each summary should expose:

- absolute change
- percent change
- start date / end date used

## Data Model Direction

Recommended fields:

- `company_id`
- `price_date`
- `close_price`
- `source`
- `created_at`
- `updated_at`

## Risks

- Existing views may still rely on live Alpha Vantage calls and bypass persistence.
- Daily history refreshes can be rate-limit sensitive.
- Some assets may have sparse or partial history.

## Mitigations

- Centralize daily history fetch and persistence in one service.
- Reuse stored history whenever possible and refresh only when stale.
- Show partial history rather than failing when older points are unavailable.

## Acceptance Shape

V1 is successful when:

- tracked stocks and ETFs have persistent daily-close history
- `/prices/{identifier}/history` returns stored EOD points plus daily/monthly/yearly change summaries
- grouped portfolio holdings can show an EOD chart and change cards for the selected asset
- the UI never labels this as full portfolio performance
