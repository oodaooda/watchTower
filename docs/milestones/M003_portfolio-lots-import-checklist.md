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

- [x] Remove the unique-per-company restriction from portfolio positions.
- [x] Update portfolio CRUD to use `position_id`.
- [x] Add grouped ticker summaries to the portfolio response.
- [x] Add explicit `entry_source` metadata.
- [x] Add replace-capable bulk import endpoint.
- [x] Add schema-upgrade path for existing databases.

**Phase 2 Tests**
- [x] Unit: duplicate rows for the same ticker can coexist.
- [x] Unit: grouped ticker summaries aggregate duplicate lots correctly.
- [x] Integration: update/delete by `position_id` only affects one lot.
- [x] Integration: replace import swaps the saved portfolio cleanly.

**Commit / Push Gate**
- [x] Commit after backend tests pass.
- [x] Push after API verification succeeds.

## Phase 3 — Portfolio UI Import and Editing

- [x] Update the portfolio page to show both grouped summary and raw positions.
- [x] Switch edit/remove flows to `position_id`.
- [x] Add bulk paste import with preview and replace behavior.
- [x] Surface canonical import format guidance in the UI.

**Phase 3 Tests**
- [x] Build: frontend compiles with grouped portfolio response and import UI changes.
- [x] Smoke: live `/portfolio` response shape matches the grouped UI contract.
- [x] Review: import preview accepts canonical format and recognizable headed table layouts.

**Commit / Push Gate**
- [x] Commit after frontend verification passes.
- [x] Push after UI verification succeeds.

## Phase 4 — Portfolio QA Aggregation

- [x] Aggregate duplicate lots by ticker in portfolio-aware QA answers.
- [x] Keep explicit symbol questions focused on grouped ticker totals by default.
- [x] Preserve ETF-vs-stock grouping behavior with duplicate lots present.

**Phase 4 Tests**
- [x] Unit: gain answers aggregate duplicate lots for the same ticker.
- [x] Integration: "tell me about my portfolio" returns grouped ticker summaries.
- [x] Integration: "what is my gain on VGT?" aggregates all saved VGT lots.

**Commit / Push Gate**
- [x] Commit after QA regression tests pass.
- [x] Push after live QA verification succeeds.

## Phase 5 — Portfolio UI Cleanup

- [x] Make grouped holdings the default primary portfolio table.
- [x] Move lot-level rows behind a per-ticker manage/view action.
- [x] Move import and manual add/edit flows into secondary panels instead of always-open cards.
- [x] Keep position editing and removal available from the lot detail view.

**Phase 5 Tests**
- [x] Build: frontend compiles with grouped-first portfolio UI.
- [x] Review: duplicate lots are no longer shown as redundant top-level tables.
- [x] Review: manual add/edit and replace import remain accessible through secondary panels.

**Commit / Push Gate**
- [x] Commit after grouped-first UI verification passes.
- [x] Push after the cleaned portfolio page is verified.
