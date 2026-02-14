# watchTower Architecture

This document defines the architectural philosophy for watchTower and the decision boundaries for future changes.

## 1) Architecture Style

watchTower is a **modular monolith**:
- Single backend deployable (FastAPI)
- Single primary relational database (Postgres)
- Clear domain modules (`screen`, `financials`, `valuation`, `modeling`, `qa`, `openclaw`, `settings`)

This is intentional. For current team size and scope, a modular monolith is faster to change, easier to debug, and cheaper to operate than microservices.

## 2) Why Not Microservices (Yet)

Microservices add operational cost:
- More deployments and runtime surfaces
- More network contracts and failure modes
- More observability and on-call burden

watchTower should only split services when there is measurable pressure (team autonomy, scaling bottlenecks, hard isolation needs) that a monolith cannot handle cleanly.

## 3) Core Principles

- **Module boundaries first, process boundaries later**.
- **API-first integration** for external systems (OpenClaw talks to HTTP endpoints only).
- **Single source of truth in Postgres** for canonical financial/stateful data.
- **Deterministic core logic** for valuation/modeling; LLM output is advisory and validated.
- **Versioned public routes** via `/api/v1` for contract stability.

## 4) Backend Shape

Current layered structure:
- `app/api` and `app/routers`: transport + request/response handling
- `app/core`: config, db, models, schemas
- domain logic modules (`app/modeling`, `app/valuation`, ETL/jobs)
- `migrations`: schema change history

Rule of thumb:
- Routers should orchestrate, not own business math.
- Domain logic should be testable without HTTP.
- Schema changes must be via Alembic.

## 5) Integration Boundaries

- OpenClaw integration must remain read-only and API-gated.
- External data providers (Alpha Vantage, SEC, etc.) are wrapped behind internal modules.
- No external system should query watchTower DB directly.

## 6) Data and Ownership

- `companies` and normalized financial tables are canonical.
- Modeling assumptions/projections are owned by modeling modules and versioned through migrations.
- API keys/settings are owned by settings/openclaw modules with strict auth.

## 7) Operational Defaults

- Canonical local path: Docker Compose for API+DB, Vite for UI.
- Structured request logging with request IDs.
- Guardrails for LLM and user-provided modeling assumptions.

See:
- `docs/ENGINEERING_STANDARDS.md`
- `docs/OPERATIONS_GUIDE.md`

## 8) When to Split a Service

Consider extracting a service only if at least one is true:
- Independent scaling need is persistent and measurable.
- Different availability/security/compliance boundary is required.
- Team ownership demands independent release cadence.
- Domain complexity causes frequent high-risk coupling despite clean modules.

Before split:
- Prove module boundary inside monolith.
- Define API contract and data ownership.
- Add observability, SLOs, and failure handling for network calls.

## 9) Near-Term Target State

- Keep modular monolith.
- Improve test pyramid (unit + integration + smoke in CI).
- Add architecture fitness checks (layering/import boundaries).
- Keep public contracts stable under `/api/v1`.
