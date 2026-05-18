# M006 WatchTower Signals Checklist

This checklist covers the native WatchTower Signals module: a real-time monitoring wall, assistant-readable context, and VGT/`$1M` goal tracking.

## Phase 0 - Spec, Architecture, and Prototype

- [x] Document Signals architecture with existing WatchTower stack reuse.
- [x] Document Signals product spec under `docs/specs`.
- [x] Add static `/signals` visual prototype.
- [x] Add Signals nav route.
- [x] Decide E4 source: skip in v1 unless options-chain data is confirmed later.
- [x] Decide whether scoped `wt_` keys are needed in v1: defer scopes and reuse active `wt_` keys for read-only access.
- [x] Accept P1/P2 portfolio goal modules as early scope.

**Phase 0 Tests**
- [x] Build: frontend compiles with static Signals prototype.
- [x] Review: architecture avoids unnecessary new service/dependency stack.
- [x] Review: spec avoids automated trading recommendation language.

**Commit / Push Gate**
- [x] Commit after spec, architecture, and prototype are accepted.
- [x] Push after review feedback is incorporated.

## Phase 1 - Native Backbone and M1

- [x] Add Alembic migration for Signals tables.
- [x] Add SQLAlchemy models and Pydantic schemas.
- [x] Add shared auth helper based on existing `wt_` API key validation.
- [x] Add `app/routers/signals.py`.
- [x] Add read-only assistant context endpoint.
- [x] Add shared Signals fetcher with timeout, retry, rate-limit guard, and source validation.
- [x] Add M1 HY OAS FRED ingest module.
- [x] Add APScheduler registration for Signals jobs.
- [x] Add manual M1 run endpoint.
- [x] Add SSE endpoint with replay from `signal_events`.
- [x] Wire `/signals` to real M1 latest/history/stream data.

**Phase 1 Tests**
- [x] Unit: M1 FRED transform handles valid observations and missing `"."` values.
- [x] Unit: Z-score calculation uses named input/output fixtures.
- [x] Unit: shared auth accepts active `wt_` key and rejects revoked/invalid keys.
- [x] Integration: migration runs cleanly on a fresh database.
- [x] Integration: manual M1 run writes idempotent signal rows and ingest run rows.
- [x] Integration: SSE replay honors `Last-Event-ID`.
- [x] Manual smoke: `/signals` shows real HY OAS and updates after manual ingest.
- [x] Manual smoke: `/signals/assistant/context` returns M1 state with source fields.

**Commit / Push Gate**
- [x] Backend tests pass.
- [x] Frontend build passes.
- [x] Commit after M1 end-to-end smoke succeeds.
- [x] Push after review.

## Phase 2 - Core Pattern Coverage

- [x] Add M2 10Y Real Yield from FRED.
- [x] Add E1 News Sentiment Top 5 from Alpha Vantage.
- [x] Add G1 Polymarket Taiwan with required pinned market config.
- [ ] Prompt owner to set and validate `POLYMARKET_TAIWAN_MARKET_ID` before treating G1 as live.
- [x] Add module docs for M1, M2, E1, and G1.
- [x] Expand assistant context to include red/amber summaries and top changes.
- [x] Add stale/grey status behavior for failed or delayed modules.

**Phase 2 Tests**
- [x] Unit: M2 transform.
- [x] Unit: E1 transform and top-five selection.
- [x] Unit: G1 transform and pinned market selection.
- [x] Unit: G1 fails closed when no pinned market id is configured.
- [x] Unit: stale module status calculation.
- [x] Integration: each module writes idempotent rows.
- [x] Manual smoke: M1, M2, and E1 live tiles render with documented cadence.
- [ ] Manual smoke: G1 live tile renders after `POLYMARKET_TAIWAN_MARKET_ID` is validated.

**Commit / Push Gate**
- [x] Tests pass.
- [x] Module docs are updated.
- [x] Commit after Phase 2 core modules work and G1 is safely config-gated.
- [x] Push after review.

## Phase 3 - Portfolio Goal and VGT Exposure

- [ ] Add P1 `$1M` Goal Tracker from existing portfolio snapshots.
- [ ] Add P2 VGT Exposure from existing portfolio lots.
- [ ] Add P3 Required Return from goal config and portfolio snapshots.
- [ ] Add P4 Drawdown From High from portfolio snapshots.
- [ ] Add goal snapshot persistence if needed for trend/history.
- [ ] Add assistant brief fields for goal progress and VGT exposure.

**Phase 3 Tests**
- [ ] Unit: goal distance calculation.
- [ ] Unit: 30d/90d velocity calculation.
- [ ] Unit: required monthly gain calculation.
- [ ] Unit: drawdown from high calculation.
- [ ] Integration: P1/P2 use existing portfolio data without duplicate holdings.
- [ ] Manual smoke: top bar shows goal progress and VGT exposure.

**Commit / Push Gate**
- [ ] Tests pass.
- [ ] Build passes.
- [ ] Commit after portfolio goal smoke succeeds.
- [ ] Push after review.

## Phase 4 - Expanded Module Set

- [ ] Add M3 VIX.
- [ ] Add M4 Dollar Broad Index.
- [ ] Add E2 NVDA EPS Estimate Delta.
- [ ] Add E3 Insider Net Flow Top 5.
- [ ] Add S1 TSMC Revenue YoY.
- [ ] Add G2 BIS Export Rules 90d.
- [ ] Add I1 Ingest Health.
- [ ] Decide and implement E4 replacement or keep disabled.
- [ ] Complete S2 capex tag study before implementation.
- [ ] Add S2 Hyperscaler Capex Delta if tag study is accepted.

**Phase 4 Tests**
- [ ] Unit tests for every implemented transform.
- [ ] Unit: Federal Register query normalization.
- [ ] Unit: TSMC table scrape canary.
- [ ] Unit: ingest health state.
- [ ] Integration: module failures do not crash unrelated modules.
- [ ] Manual smoke: full wall renders with expected statuses.

**Commit / Push Gate**
- [ ] Tests pass.
- [ ] Module docs are updated for every implemented module.
- [ ] Commit after full module smoke succeeds.
- [ ] Push after review.

## Phase 5 - Regime and Alerts

- [ ] Add deterministic regime classifier.
- [ ] Add regime contributor tooltip.
- [ ] Add alert threshold rules.
- [ ] Add alert side rail backed by `signal_alerts`.
- [ ] Add alert acknowledge/dismiss with reason.
- [ ] Add assistant explanation for regime and alerts.
- [ ] Add webhook or Telegram delivery only after core alert state is stable.

**Phase 5 Tests**
- [ ] Unit: regime classifier named fixtures.
- [ ] Unit: alert rule evaluation.
- [ ] Unit: acknowledge requires reason.
- [ ] Integration: alert state persists and appears in assistant context.
- [ ] Manual smoke: regime and alert rail update when thresholds are crossed.

**Commit / Push Gate**
- [ ] Tests pass.
- [ ] Build passes.
- [ ] Commit after alert/regime smoke succeeds.
- [ ] Push after review.

## Phase 6 - Polish and Operational Hardening

- [ ] Split prototype into reusable Signals components.
- [ ] Add tile expand modal with full chart, raw values, thresholds, and citations.
- [ ] Add layout persistence.
- [ ] Add mobile single-column layout.
- [ ] Add noindex behavior for `/signals`.
- [ ] Add runbook docs for Signals operations.
- [ ] Add retention/cleanup policy for signal events if needed.
- [ ] Re-evaluate whether TimescaleDB or a separate service is justified.

**Phase 6 Tests**
- [ ] Build: frontend compiles.
- [ ] Manual smoke: desktop and mobile layouts are usable.
- [ ] Manual smoke: modal citations match source data.
- [ ] Review: no provider secrets are exposed to client or assistant context.

**Commit / Push Gate**
- [ ] Tests pass.
- [ ] Docs are updated.
- [ ] Commit after polish review.
- [ ] Push final milestone state.
