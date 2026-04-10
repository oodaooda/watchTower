# M005 Portfolio Market Value Snapshots Checklist

This checklist covers forward-only portfolio market value history based on stored EOD prices.

## Phase 1 — Spec and Contract

- [x] Document forward-only snapshot scope.
- [x] Document totals-only v1 and exclusions for true performance.
- [x] Define snapshot completeness behavior for missing prices.

**Phase 1 Tests**
- [x] Review: scope avoids backfill and performance-return claims.

**Commit / Push Gate**
- [x] Commit after docs are updated.
- [x] Push after milestone/spec links are in place.

## Phase 2 — Backend Snapshots and API

- [x] Add daily portfolio snapshot storage.
- [x] Add idempotent snapshot generation from stored EOD closes.
- [x] Add snapshot history endpoint and manual run endpoint.
- [x] Wire snapshot generation after daily EOD price refresh.
- [x] Incomplete snapshots avoid partial overall market value/gain totals.

**Phase 2 Tests**
- [x] Unit: snapshot generation calculates totals from EOD closes.
- [x] Unit: missing prices mark snapshots incomplete without zeroing values.
- [x] Integration: snapshot endpoint returns rows and period summaries.

**Commit / Push Gate**
- [x] Backend tests pass.
- [x] API schema applied and endpoint smoke checked.

## Phase 3 — Portfolio UI Market Value History

- [x] Add portfolio market value chart.
- [x] Add 1D/1M/YTD/1Y market value change cards.
- [x] Keep UI labels focused on market value, not performance.
- [x] Show incomplete snapshot warning and avoid charting incomplete portfolio totals.

**Phase 3 Tests**
- [x] Build: frontend compiles with snapshot history UI.
- [x] Review: wording avoids true-performance claims.

**Commit / Push Gate**
- [x] Commit after frontend verification passes.
- [x] Push after UI verification succeeds.
