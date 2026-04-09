# M003 Portfolio Lots and Bulk Import Checklist

This checklist covers duplicate-ticker portfolio support, grouped summaries, and one-time replace import onboarding.

## Phase 1 — Spec and Contract

- [x] Document duplicate-ticker portfolio support as a lot-style model.
- [x] Document grouped ticker summaries in the portfolio API contract.
- [x] Document canonical import format and replace-existing onboarding behavior.
- [x] Link the new spec from roadmap/docs indexes.

**Phase 1 Tests**
- [x] Review: implementation plan aligns with global scope, no trade dates, and replace-on-import.

**Commit / Push Gate**
- [x] Commit after docs are updated.
- [x] Push after milestone/spec links are in place.

## Phase 2 — Backend Schema and Portfolio API

- [ ] Remove the unique-per-company restriction from portfolio positions.
- [ ] Update portfolio CRUD to use `position_id`.
- [ ] Add grouped ticker summaries to the portfolio response.
- [ ] Add explicit `entry_source` metadata.
- [ ] Add replace-capable bulk import endpoint.
- [ ] Add schema-upgrade path for existing databases.

**Phase 2 Tests**
- [ ] Unit: duplicate rows for the same ticker can coexist.
- [ ] Unit: grouped ticker summaries aggregate duplicate lots correctly.
- [ ] Integration: update/delete by `position_id` only affects one lot.
- [ ] Integration: replace import swaps the saved portfolio cleanly.

**Commit / Push Gate**
- [ ] Commit after backend tests pass.
- [ ] Push after API verification succeeds.

## Phase 3 — Portfolio UI Import and Editing

- [ ] Update the portfolio page to show both grouped summary and raw positions.
- [ ] Switch edit/remove flows to `position_id`.
- [ ] Add bulk paste import with preview and replace behavior.
- [ ] Surface canonical import format guidance in the UI.

**Phase 3 Tests**
- [ ] Integration: editing one duplicate lot leaves sibling lots unchanged.
- [ ] Integration: replace import updates the visible grouped totals correctly.
- [ ] Manual: pasted holdings populate the portfolio without one-by-one typing.

**Commit / Push Gate**
- [ ] Commit after frontend verification passes.
- [ ] Push after UI verification succeeds.

## Phase 4 — Portfolio QA Aggregation

- [ ] Aggregate duplicate lots by ticker in portfolio-aware QA answers.
- [ ] Keep explicit symbol questions focused on grouped ticker totals by default.
- [ ] Preserve ETF-vs-stock grouping behavior with duplicate lots present.

**Phase 4 Tests**
- [ ] Unit: gain answers aggregate duplicate lots for the same ticker.
- [ ] Integration: "tell me about my portfolio" returns grouped ticker summaries.
- [ ] Integration: "what is my gain on VGT?" aggregates all saved VGT lots.

**Commit / Push Gate**
- [ ] Commit after QA regression tests pass.
- [ ] Push after live QA verification succeeds.
