# ADR-0001: Keep watchTower as a Modular Monolith

- Status: Accepted
- Date: 2026-02-28
- Owners: watchTower engineering

## Context

watchTower serves a single product surface with a FastAPI backend, a Postgres database, scheduled ETL jobs, and a Vite UI. The current team and deployment footprint do not justify service fragmentation.

The system already has clear internal domains:

- Screening
- Financials
- Valuation
- Modeling
- QA
- OpenClaw
- Settings

The architectural question is whether those domains should remain modules in one deployable or be split into services.

## Decision

watchTower will remain a modular monolith.

This means:

- One backend deployable
- One primary relational database
- Clear module boundaries inside the codebase
- HTTP APIs as the only integration boundary for external systems

## Consequences

- Development and debugging stay simpler and faster.
- Operational overhead stays low.
- Internal module boundaries must be enforced with discipline because process isolation does not exist.
- If scaling or compliance constraints emerge later, service extraction must happen from already-clean module seams.

## Alternatives Considered

- Microservices from the start: rejected due to deployment overhead, more failure modes, and a mismatch with current scale.
- Separate service only for QA or LLM features: rejected for now because the code is still evolving quickly and benefits from in-process access to shared schemas and deterministic logic.
