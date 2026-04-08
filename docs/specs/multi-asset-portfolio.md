# Spec: Multi-Asset Watchlist and Portfolio Tracking

## Purpose

Expand watchTower from company-only tracking into a mixed-asset workflow that supports stocks and ETFs in both the watchlist and a new position-level portfolio tracker.

## Scope

- Mixed-asset support for stocks and ETFs
- Watchlist/favorites support for non-company assets
- Position-level portfolio tracking with quantity and average cost basis
- Unrealized gain/loss calculations
- Portfolio-aware QA behavior through the existing QA surface

## Non-Goals

- Lot-level transaction history
- Realized gains, tax lots, or dividend accounting
- Historical portfolio performance reconstruction
- Multi-user or account-scoped ownership in v1
- Mutual funds, options, crypto, or bond support in v1

## Product Decisions

- Ownership scope: global for v1
- Position model: position-level only
- Required cost field: average cost basis per share/unit
- Supported asset classes in v1: stocks and ETFs
- OpenClaw/assistant access stays on the QA surface only

## Core Contract

- Favorites/watchlist can include stocks and ETFs.
- Portfolio positions can include stocks and ETFs.
- Portfolio positions store quantity and average cost basis.
- Unrealized gain/loss uses the current quote layer, not company fundamentals.
- Explicit ticker or symbol references override watchlist/portfolio fallback in QA.
- ETF-aware QA must not fabricate company-fundamental metrics for assets where they do not apply.

## Data Model Direction

Recommended logical model:

- Broaden the tracked security concept beyond operating companies.
- Add `asset_type` with at least:
  - `equity`
  - `etf`
- Keep a lightweight watchlist/favorites model for followed assets.
- Add a dedicated portfolio positions model for owned assets.

Recommended portfolio position fields:

- `symbol`
- `asset_type`
- `quantity`
- `avg_cost_basis`
- `notes` (optional)
- `created_at`
- `updated_at`

Derived portfolio fields:

- `current_price`
- `market_value`
- `total_cost_basis`
- `unrealized_gain_loss`
- `unrealized_gain_loss_pct`
- `portfolio_weight`

## Price and Analytics Contract

- Portfolio math must depend on a current quote layer that works for both equities and ETFs.
- When a live quote is unavailable, the system may use the latest cached price but must label it clearly.
- Missing price data must never be silently treated as zero.
- Company-fundamental analytics remain valid for operating companies only.
- ETF answers should emphasize price, allocation, and watchlist/portfolio context rather than DCF-style company analysis.

## QA Contract

QA should support:

- "What are my favorite assets?"
- "Tell me about my portfolio"
- "What are my gains?"
- "Which holding is up the most?"
- "What is my gain on VGT?"
- "Compare my ETF holdings to my stock holdings"

QA should avoid:

- unsupported company-fundamental claims for ETFs
- implied realized gains
- tax-aware recommendations

## Risks

- Current schema and naming are company-centric and may resist ETF support cleanly.
- Portfolio math may become inconsistent if quote sourcing is not unified first.
- Global scope may need migration work later for user/account ownership.
- Favorites semantics become misleading if the underlying model remains `favorite_companies` while supporting ETFs.

## Mitigations

- Introduce `asset_type` early.
- Centralize quote resolution before portfolio gain logic ships.
- Keep v1 limited to unrealized gain/loss only.
- Document the global-scope assumption explicitly.

## Acceptance Shape

V1 is successful when:

- ETFs can be tracked in the watchlist/favorites flow.
- Portfolio positions can be added, edited, and removed.
- Portfolio totals and per-position gains render correctly for mixed stock/ETF holdings.
- QA can answer mixed-asset portfolio questions without requiring new OpenClaw endpoints.
