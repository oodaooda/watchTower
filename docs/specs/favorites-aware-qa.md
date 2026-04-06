# Spec: Favorites-Aware QA

## Purpose

Allow watchTower QA to use the existing favorites list as a read-only portfolio context so OpenClaw can ask favorites-aware questions through the existing `/openclaw/qa` integration.

## Scope

- QA planner and resolver behavior
- Favorites-backed company set selection
- Read-only response behavior for portfolio-style questions
- Regression coverage for favorites-aware prompts

## Non-Goals

- New OpenClaw endpoints beyond `/openclaw/qa`
- Write access to favorites through QA
- Per-user favorites isolation

## Core Contract

- OpenClaw continues to talk only to watchTower QA over HTTP.
- QA may use the global favorites list as an implicit company set when no explicit ticker/company is resolved.
- Explicit company/ticker mentions always override favorites fallback.
- Favorites usage remains read-only.
- Broad favorites queries may be capped to a safe subset with the response stating that truncation occurred.

## Product Semantics

- "Favorites", "portfolio", "watchlist", and "tracked companies" refer to the existing global favorites list in watchTower.
- Favorites should be usable both explicitly and implicitly for portfolio-style prompts.
- Conceptual finance questions without portfolio intent should remain in general QA mode and must not silently pivot to favorites.

## Phase Plan

### Phase 1: Planner and Resolver Favorites Context

Add favorites-aware planning and fallback resolution inside QA.

Behavior:

- Detect explicit favorites prompts such as "my favorites", "my portfolio", and "my watchlist".
- Permit implicit favorites fallback for non-conceptual, unresolved portfolio-style questions.
- Load favorite companies as the resolved company set when the planner chooses favorites context.
- Preserve precedence: explicit tickers or resolved company names beat favorites.

Required tests:

- Planner marks favorites usage for explicit favorites prompts.
- Explicit ticker prompt does not fall back to favorites.
- Unresolved portfolio-style prompt can resolve to favorites.
- Empty favorites list returns a clear no-favorites answer instead of failing.

### Phase 2: Favorites-Aware Answer Behavior

Use the resolved favorites company set inside existing QA synthesis.

Behavior:

- List favorites through the normal QA answer path.
- Support compare/rank-style prompts across favorites.
- Support news-style favorites prompts with a capped favorites subset.
- Expose trace/plan metadata showing favorites fallback occurred and whether the favorites set was truncated.

Required tests:

- "What are my favorite companies?" returns the favorites list.
- "Compare my favorites" uses favorites as the company set.
- Favorites news prompts return structured news output.
- Large favorites sets are capped and produce a trace or answer note indicating truncation.

### Phase 3: Regression and Documentation

Lock behavior down and document it.

Behavior:

- QA and OpenClaw docs reflect that favorites are available only through QA.
- The OpenClaw integration remains read-only and `/openclaw/qa` remains the sole OpenClaw query surface for favorites-aware questions.

Required tests:

- Existing non-favorites QA tests still pass.
- Favorites-aware tests pass under targeted unit coverage.

## Risks

- Overly aggressive favorites fallback causing surprising answers for unresolved prompts
- Excessive fan-out for news queries on large favorites lists
- User confusion because favorites are global rather than user-scoped

## Mitigations

- Restrict favorites fallback to non-conceptual portfolio-style prompts
- Cap favorites query fan-out for expensive actions such as news
- Make favorites usage explicit in trace and response text when fallback occurs
