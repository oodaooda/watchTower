# M002 Multi-Asset Portfolio Tracking Checklist

This checklist covers ETF-capable watchlist tracking plus a new position-level portfolio model for stocks and ETFs.

## Phase 1 — Multi-Asset Universe and Watchlist

- [x] Define asset-level contract for stocks and ETFs.
- [x] Add or document `asset_type` support for tracked symbols.
- [x] Ensure ETF-like symbols can exist in the tracked asset universe.
- [x] Update watchlist/favorites flows to support ETFs as first-class tracked assets.
- [x] Define fallback behavior for assets that do not have company-fundamental data.
- [x] Update QA/watchlist docs to reflect mixed-asset support.

**Phase 1 Tests**
- [x] Unit: asset classification distinguishes equities vs ETFs correctly for supported symbols.
- [x] Unit: watchlist/favorites serialization handles ETF assets without requiring company fundamentals.
- [x] Integration: add/list/remove ETF watchlist asset succeeds.
- [x] Integration: QA can answer "what are my favorite assets?" when ETFs are present.
- [ ] Manual: mixed stock/ETF watchlist renders correctly in the UI.

Phase 1 verification note:
- Live API smoke test passed for `POST /favorites`, `GET /favorites`, and `DELETE /favorites/VGT`.
- Repo-wide frontend build is currently blocked by pre-existing TypeScript errors outside the favorites flow, so browser-level verification is deferred until the dedicated UI phase.

**Commit / Push Gate**
- [x] Commit after Phase 1 tests pass.
- [x] Push after API verification for mixed-asset watchlist behavior. Full browser verification remains deferred to Phase 3.

## Phase 2 — Portfolio Positions and Gain/Loss Math

- [x] Add position-level portfolio storage for global holdings.
- [x] Support quantity and average cost basis inputs.
- [x] Implement current quote resolution for both stocks and ETFs.
- [x] Calculate per-position market value, total cost basis, unrealized gain/loss, and unrealized gain/loss percent.
- [x] Add portfolio-level summary totals and allocation percentages.
- [x] Define behavior for positions with stale or missing quotes.

**Phase 2 Tests**
- [x] Unit: portfolio math calculates market value and unrealized gain/loss correctly.
- [x] Unit: missing-quote behavior is explicit and never treated as zero silently.
- [x] Integration: create/update/delete portfolio position succeeds.
- [x] Integration: mixed stock/ETF portfolio totals are returned correctly from the API.
- [ ] Manual: portfolio table shows current value and gains for a mixed sample portfolio.

Phase 2 verification note:
- Live API smoke test passed for `GET /portfolio`, `POST /portfolio`, `PUT /portfolio/VGT`, and cleanup via `DELETE`.
- Browser-level portfolio table verification is deferred to Phase 3 because that UI does not exist yet.

**Commit / Push Gate**
- [x] Commit after Phase 2 tests pass.
- [x] Push after verifying API payloads for mixed stock/ETF portfolio totals. UI rendering verification remains part of Phase 3.

## Phase 3 — Portfolio UI and Editing Workflow

- [x] Add portfolio UI surface distinct from the watchlist/favorites tab.
- [x] Support add, edit, and remove for portfolio positions.
- [x] Show per-position fields: symbol, asset type, quantity, cost basis, price, market value, gain/loss, gain/loss percent.
- [x] Show portfolio-level totals and weights.
- [x] Surface quote freshness or stale-price state where applicable.

**Phase 3 Tests**
- [ ] Integration: portfolio UI persists position edits correctly.
- [ ] Integration: UI totals match API totals for the same holdings set.
- [ ] Manual: add/update/remove flows behave correctly for both stocks and ETFs.
- [ ] Manual: stale quote state is visible and understandable.

Phase 3 verification note:
- File-scoped TypeScript check passed for `ui/src/lib/api.ts` and `ui/src/pages/PortfolioPage.tsx`.
- `esbuild` successfully bundled `ui/src/pages/PortfolioPage.tsx`.
- Full frontend build remains blocked by pre-existing TypeScript errors outside the portfolio files, so browser-level verification remains pending.

**Commit / Push Gate**
- [x] Commit after Phase 3 implementation and slice-level verification.
- [x] Push after portfolio route/page wiring and targeted UI verification. Full browser validation remains pending.

## Phase 4 — Portfolio-Aware QA

- [x] Extend QA to use portfolio context in addition to watchlist context.
- [x] Support mixed-asset portfolio prompts through the existing QA surface only.
- [x] Add ETF-aware response behavior that avoids unsupported company-fundamental claims.
- [x] Add ranking/summary answers such as biggest gainers/losers and allocation concentration.
- [x] Keep OpenClaw integration on `/openclaw/qa` only.

**Phase 4 Tests**
- [x] Unit: explicit ticker/symbol still overrides portfolio fallback.
- [x] Unit: ETF-aware QA refuses unsupported company-fundamental answers cleanly.
- [x] Integration: "tell me about my portfolio" returns mixed holdings summary.
- [x] Integration: "what is my gain on VGT?" returns the correct unrealized gain/loss.
- [x] Integration: "compare my ETF holdings to my stock holdings" returns grouped portfolio context.
- [x] Manual: OpenClaw can ask portfolio questions without any new endpoint.

Phase 4 verification note:
- QA regression tests cover mixed-holdings summary, explicit gain on `VGT`, and ETF-vs-stock grouping.
- Live `POST /qa` smoke tests passed for portfolio summary, gain, and grouping prompts.
- Live `POST /openclaw/qa` smoke test passed with a temporary API key, then the key was revoked.

**Commit / Push Gate**
- [x] Commit after Phase 4 tests pass.
- [x] Push after regression verification across WatchTower assistant and OpenClaw QA flows.
