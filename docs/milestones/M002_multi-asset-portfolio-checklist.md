# M002 Multi-Asset Portfolio Tracking Checklist

This checklist covers ETF-capable watchlist tracking plus a new position-level portfolio model for stocks and ETFs.

## Phase 1 — Multi-Asset Universe and Watchlist

- [ ] Define asset-level contract for stocks and ETFs.
- [ ] Add or document `asset_type` support for tracked symbols.
- [ ] Ensure ETF-like symbols can exist in the tracked asset universe.
- [ ] Update watchlist/favorites flows to support ETFs as first-class tracked assets.
- [ ] Define fallback behavior for assets that do not have company-fundamental data.
- [ ] Update QA/watchlist docs to reflect mixed-asset support.

**Phase 1 Tests**
- [ ] Unit: asset classification distinguishes equities vs ETFs correctly for supported symbols.
- [ ] Unit: watchlist/favorites serialization handles ETF assets without requiring company fundamentals.
- [ ] Integration: add/list/remove ETF watchlist asset succeeds.
- [ ] Integration: QA can answer "what are my favorite assets?" when ETFs are present.
- [ ] Manual: mixed stock/ETF watchlist renders correctly in the UI.

**Commit / Push Gate**
- [ ] Commit after Phase 1 tests pass.
- [ ] Push after API and UI verification for mixed-asset watchlist behavior.

## Phase 2 — Portfolio Positions and Gain/Loss Math

- [ ] Add position-level portfolio storage for global holdings.
- [ ] Support quantity and average cost basis inputs.
- [ ] Implement current quote resolution for both stocks and ETFs.
- [ ] Calculate per-position market value, total cost basis, unrealized gain/loss, and unrealized gain/loss percent.
- [ ] Add portfolio-level summary totals and allocation percentages.
- [ ] Define behavior for positions with stale or missing quotes.

**Phase 2 Tests**
- [ ] Unit: portfolio math calculates market value and unrealized gain/loss correctly.
- [ ] Unit: missing-quote behavior is explicit and never treated as zero silently.
- [ ] Integration: create/update/delete portfolio position succeeds.
- [ ] Integration: mixed stock/ETF portfolio totals are returned correctly from the API.
- [ ] Manual: portfolio table shows current value and gains for a mixed sample portfolio.

**Commit / Push Gate**
- [ ] Commit after Phase 2 tests pass.
- [ ] Push after verifying API payloads and portfolio totals in the UI.

## Phase 3 — Portfolio UI and Editing Workflow

- [ ] Add portfolio UI surface distinct from the watchlist/favorites tab.
- [ ] Support add, edit, and remove for portfolio positions.
- [ ] Show per-position fields: symbol, asset type, quantity, cost basis, price, market value, gain/loss, gain/loss percent.
- [ ] Show portfolio-level totals and weights.
- [ ] Surface quote freshness or stale-price state where applicable.

**Phase 3 Tests**
- [ ] Integration: portfolio UI persists position edits correctly.
- [ ] Integration: UI totals match API totals for the same holdings set.
- [ ] Manual: add/update/remove flows behave correctly for both stocks and ETFs.
- [ ] Manual: stale quote state is visible and understandable.

**Commit / Push Gate**
- [ ] Commit after Phase 3 tests pass.
- [ ] Push after manual UI verification for add/edit/remove and totals rendering.

## Phase 4 — Portfolio-Aware QA

- [ ] Extend QA to use portfolio context in addition to watchlist context.
- [ ] Support mixed-asset portfolio prompts through the existing QA surface only.
- [ ] Add ETF-aware response behavior that avoids unsupported company-fundamental claims.
- [ ] Add ranking/summary answers such as biggest gainers/losers and allocation concentration.
- [ ] Keep OpenClaw integration on `/openclaw/qa` only.

**Phase 4 Tests**
- [ ] Unit: explicit ticker/symbol still overrides portfolio fallback.
- [ ] Unit: ETF-aware QA refuses unsupported company-fundamental answers cleanly.
- [ ] Integration: "tell me about my portfolio" returns mixed holdings summary.
- [ ] Integration: "what is my gain on VGT?" returns the correct unrealized gain/loss.
- [ ] Integration: "compare my ETF holdings to my stock holdings" returns grouped portfolio context.
- [ ] Manual: OpenClaw can ask portfolio questions without any new endpoint.

**Commit / Push Gate**
- [ ] Commit after Phase 4 tests pass.
- [ ] Push after regression verification across WatchTower assistant and OpenClaw QA flows.
