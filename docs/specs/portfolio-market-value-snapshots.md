# Spec: Portfolio Market Value Snapshots

## Purpose

Track forward-only daily portfolio market value using stored end-of-day closes, without backfilling or claiming true cash-flow-adjusted portfolio performance.

## Scope

- Daily portfolio market value snapshots from the day tracking starts forward
- Totals-only snapshot storage
- Snapshot history API with daily/monthly/yearly change summaries
- Portfolio UI chart/cards for market value history
- Scheduler integration after EOD asset price refresh

## Non-Goals

- Historical backfill before snapshot tracking starts
- Transaction-aware performance
- Contributions, withdrawals, realized gains, dividends, or taxes
- Per-asset attribution snapshots
- Time-weighted or money-weighted returns

## Product Decisions

- Snapshot timing should happen after EOD prices are refreshed.
- Snapshot values use stored EOD closes, not live intraday quotes.
- Snapshots are trading-day based, using available EOD price dates.
- Snapshot totals are recomputable/idempotent for the latest trading day.
- UI labels should say `Portfolio Market Value` or `Market Value Change`, not `Performance`.

## Core Contract

- Store one portfolio snapshot per `snapshot_date`.
- Store total cost basis at snapshot time.
- Store total market value only when every held position has an EOD close for the snapshot date.
- Store unrealized gain/loss and gain/loss percent only for complete snapshots.
- Store completeness metadata:
  - `is_complete`
  - `priced_positions`
  - `unpriced_positions`
- Missing prices should not be silently treated as zero or converted into partial overall portfolio totals.

## API Contract

Recommended endpoints:

- `GET /portfolio/snapshots`
- `POST /portfolio/snapshots/run`

History response should include:

- snapshot rows
- `1d`, `1m`, `ytd`, and `1y` market value changes

## Acceptance Shape

V1 is successful when:

- the scheduler can create a daily portfolio market value snapshot after EOD prices refresh
- the endpoint returns snapshot history and period changes
- the portfolio page shows a market value chart and change cards
- all wording avoids implying true portfolio performance
