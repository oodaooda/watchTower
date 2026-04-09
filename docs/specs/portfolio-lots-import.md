# Spec: Portfolio Lots and Bulk Import

## Purpose

Extend the portfolio feature from one-position-per-symbol into a lot-capable model that supports duplicate tickers, grouped summaries, and one-time bulk replacement import for onboarding an existing portfolio.

## Scope

- Multiple portfolio rows for the same ticker
- Stable portfolio CRUD by `position_id`
- Grouped-by-ticker portfolio summaries alongside raw lot rows
- Bulk import for stocks and ETFs
- Replace-existing import mode for onboarding
- Portfolio-aware QA aggregation across duplicate lots

## Non-Goals

- Trade-date storage in v1
- Realized gains, tax lots, or dividend accounting
- Broker-specific direct integrations
- Multi-user ownership

## Product Decisions

- Portfolio remains global for now
- Duplicate tickers are allowed
- Trade date is deferred until reliable export data is available
- Import should support a canonical internal format plus tolerant pasted table parsing
- The onboarding import flow should replace the current portfolio

## Core Contract

- Portfolio rows are lot-like holdings distinguished by `position_id`, not ticker.
- The same ticker may appear more than once with different quantities and cost bases.
- CRUD operations must target `position_id`.
- The API must return both raw position rows and grouped ticker summaries.
- QA should aggregate duplicate lots by ticker by default when answering portfolio questions.
- The UI should present grouped holdings as the default portfolio view.
- Lot-level rows should be secondary detail, revealed through a manage/view-lots action rather than shown alongside the grouped table by default.
- Import and manual add/edit flows should live in secondary panels, not as always-open primary cards.

## Import Contract

Supported canonical format:

`ticker,quantity,avg_cost_basis[,notes]`

Examples:

`AMD,26,219.18`
`VGT,509.913,619.22,long-term ETF`

Tolerant paste support should also accept delimited rows with recognizable headers such as:

- `Description`
- `Symbol` or `Ticker`
- `Shares` or `Quantity`
- `Cost Basis`
- `Trade Date` (ignored for now)

For onboarding, import should support `replace_existing=true` so the saved portfolio can be replaced in one pass.

## Data Model Direction

Recommended portfolio position fields:

- `id`
- `company_id`
- `quantity`
- `avg_cost_basis`
- `entry_source` (`manual` or `import`)
- `notes` (optional)
- `created_at`
- `updated_at`

Grouped ticker summary fields:

- `ticker`
- `asset_type`
- `name`
- `lot_count`
- `total_quantity`
- `weighted_avg_cost_basis`
- `total_cost_basis`
- `current_price`
- `market_value`
- `unrealized_gain_loss`
- `unrealized_gain_loss_pct`
- `portfolio_weight`
- `price_status`

## QA Contract

QA should support:

- "What is my gain on VGT?" across multiple lots
- "Tell me about my portfolio" with grouped holdings
- "Which holding is up the most?" using grouped ticker totals
- "Compare my ETF holdings to my stock holdings" using grouped portfolio context

QA should avoid:

- treating duplicate lots as separate companies in default portfolio answers
- implying lot-level dates when none are stored

## Risks

- Existing databases already have a unique-per-company portfolio constraint.
- Legacy UI/API calls still assume update and delete by ticker.
- Import parsing can become brittle if it tries to support too many brokerage variants at once.

## Mitigations

- Add an explicit schema upgrade path for the existing `portfolio_positions` table.
- Use `position_id` everywhere for mutable portfolio operations.
- Keep the first import parser focused on canonical CSV and recognizable pasted-table headers.
- Keep replace behavior explicit in the import endpoint.

## Acceptance Shape

V1 is successful when:

- duplicate `AMD` and `VGT` rows can coexist with different share counts and cost bases
- the API returns both lot rows and grouped ticker summaries
- the UI can replace the current portfolio from pasted rows without manual one-by-one entry
- QA aggregates duplicate holdings cleanly for portfolio answers
- the main portfolio screen defaults to one grouped holdings table instead of duplicating grouped and raw-lot tables
