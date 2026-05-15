# Spec: Portfolio Market Value Snapshots

## Purpose

Track forward-only daily portfolio market value using stored end-of-day closes, without backfilling or claiming true cash-flow-adjusted portfolio performance.

## Scope

- Daily portfolio market value snapshots from the day tracking starts forward
- One inferred initial baseline point from current portfolio cost basis
- Totals-only snapshot storage
- Optional historical snapshot rebuild from complete backfilled EOD dates using the current saved holdings definition
- Snapshot history API with daily/monthly/yearly change summaries
- Portfolio UI chart/cards for market value history
- Portfolio UI table view for daily snapshot rows, including market value, cost basis, day change, and day change percent
- Grouped holdings table sorting within each asset-type section
- Scheduler integration after EOD asset price refresh

## Non-Goals

- Historical backfill before snapshot tracking starts
- Transaction-aware performance
- Contributions, withdrawals, realized gains, dividends, or taxes
- Per-asset attribution snapshots
- Time-weighted or money-weighted returns
- Inferred daily closes between baseline and first real EOD snapshot
- Transaction-aware historical holdings reconstruction

## Product Decisions

- Snapshot timing should happen after EOD prices are refreshed.
- Snapshot values use stored EOD closes, not live intraday quotes.
- The chart may include one inferred initial cost-basis baseline point before the first real snapshot.
- Historical snapshot rebuild is allowed only as a current-holdings-based reconstruction after price-history backfill.
- Snapshots are trading-day based, using available EOD price dates.
- Snapshot totals are recomputable/idempotent for the latest trading day.
- UI labels should say `Portfolio Market Value` or `Market Value Change`, not `Performance`.
- Period summary cards should ignore the inferred baseline and use only real EOD snapshots.
- The snapshot table should follow the same visible range as the chart and use complete real snapshots only.
- Daily table change values should compare each snapshot's market value against the previous complete real snapshot.
- Holdings sorting should keep asset-type groups separate and sort rows only within their current group.

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
- Emit one inferred baseline row in the history response when a portfolio exists, using current `quantity * avg_cost_basis`.
- Mark the inferred baseline distinctly so the UI can label it as synthetic and not as a real close.

## API Contract

Recommended endpoints:

- `GET /portfolio/snapshots`
- `POST /portfolio/snapshots/run`
- `POST /portfolio/prices/backfill`

History response should include:

- snapshot rows
- `1d`, `1m`, `ytd`, and `1y` market value changes
- inferred baseline vs real snapshot metadata

## UI Contract

The portfolio market value history surface should provide:

- `Chart` and `Table` tabs using the same snapshot dataset and selected range.
- A daily table with sortable headers:
  - `Date`
  - `Market Value`
  - `Cost Basis`
  - `Day Change`
  - `Day Change %`
- Day change cells should be colored consistently with gain/loss conventions.
- Holdings table headers should be sortable while preserving asset-type grouping; subtotal rows remain pinned above each group.

## Acceptance Shape

V1 is successful when:

- the scheduler can create a daily portfolio market value snapshot after EOD prices refresh
- the system can backfill current portfolio holdings' price history from Alpha Vantage without aborting on a single symbol failure
- the system can rebuild reconstructed snapshot rows from complete backfilled EOD dates
- the endpoint returns snapshot history and period changes
- the portfolio page shows a market value chart, daily table view, and change cards
- the portfolio grouped holdings table can sort rows within Cash, Equity, ETF, and Option sections independently
- all wording avoids implying true portfolio performance
