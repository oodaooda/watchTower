# watchTower Engineering Standards

This document defines the operational and engineering standards for watchTower. The goal is long‑term reliability, clear ownership, and safe change.
Architecture philosophy and boundaries are documented in `ARCHITECTURE.md`.

## 1) Environments

### 1.1 Local (Recommended)
- Use a single, canonical dev path.
- Preferred: Docker Compose for API + DB, Vite for UI.
- Avoid mixing host DB and compose DB in the same workflow.
See `OPERATIONS_GUIDE.md` for the canonical commands.

### 1.2 Canonical DB
- The canonical DB for Docker is the compose service `db`.
- `DATABASE_URL` must be `postgresql+pg8000://postgres:postgres@db:5432/watchtower` when running the API in Docker.
- If using host DB for any reason, it must be explicit and documented.

## 2) Configuration & Secrets
- All secrets live in `.env` (never committed).
- `.env.example` must be kept up‑to‑date with required keys.
- All new env vars must be documented in README.

## 3) API Contracts
- Every endpoint must have a schema in `app/core/schemas.py`.
- Backward‑incompatible changes require a versioned endpoint or opt‑in flag.
- Inputs from LLMs must be validated and range‑checked.

## 4) Data Integrity
- Schema changes always via Alembic migrations.
- No manual schema edits in production.
- Migrations must be reversible and tagged.

## 5) LLM Usage (Guardrails)
- LLMs are advisory only; final model output is deterministic.
- LLM outputs must be structured JSON with validation.
- All LLM requests and responses are logged (redact secrets).
- A safe fallback is required if the LLM fails or returns invalid output.

## 6) Reliability & Observability
- Every major job logs start/end + duration.
- API endpoints must return actionable errors (no silent failures).
- When external services fail, degrade gracefully.

## 7) Testing & Verification
- Critical calculations must have unit tests (modeling, valuation).
- When changing data models, include migration tests or a smoke query.

## 8) UX Consistency
- Tooltips and glossary definitions must use finance‑pro tone.
- New pages must fit the existing visual hierarchy.
- Chart labels must be explicit and unambiguous.

## 9) Change Management
- Every non‑trivial change must include a short “what changed / why” note in PR or commit.
- Feature flags for major changes (LLM‑driven functionality).
- Bug fixes must target root cause, not symptom masking; add regression tests for the failure mode whenever practical.

## 10) Security
- Any external integration must use an API key or token.
- Keys are read from environment variables only.
- Network access must be restricted to known peers for internal services.
 - OpenClaw integration must enforce token auth + allowlist + rate limits.
