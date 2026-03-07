# watchTower Engineering Standards

This document defines the operational and engineering standards for watchTower. The goal is long-term reliability, clear ownership, and safe change.

Architecture philosophy and boundaries are documented in `system-overview.md`.

## 1) Environments

### 1.1 Local (Recommended)

- Use a single, canonical development path.
- Preferred: Docker Compose for API and DB, Vite for UI.
- Avoid mixing a host DB and compose DB in the same workflow.

See `operations-runbook.md` for canonical commands.

### 1.2 Canonical DB

- The canonical DB for Docker is the compose service `db`.
- `DATABASE_URL` must be `postgresql+pg8000://postgres:postgres@db:5432/watchtower` when running the API in Docker.
- If using a host DB for any reason, it must be explicit and documented.

## 2) Configuration and Secrets

- All secrets live in `.env` and are never committed.
- `.env.example` must be kept up to date with required keys.
- All new environment variables must be documented in the README.
- Real secrets must not be pasted into issue trackers, chat transcripts, screenshots, or shared terminal logs.
- If a secret appears in plaintext in logs, UI, screenshots, or agent/tool output, treat it as compromised and rotate it.
- Settings and admin UIs must treat secrets as write-only where practical: masked inputs, no read-back of full values, and generated credentials shown once only.
- Server logs, debug output, and operational tooling must redact secret values rather than printing them.
- Browser persistence of admin tokens or API keys must be minimized; if local storage is used for development convenience, the UI must not redisplay the full token after save.

## 3) API Contracts

- Every endpoint must have a schema in `app/core/schemas.py`.
- Backward-incompatible changes require a versioned endpoint or opt-in flag.
- Inputs from LLMs must be validated and range-checked.

## 4) Data Integrity

- Schema changes always go through Alembic migrations.
- No manual schema edits in production.
- Migrations must be reversible and tagged.

## 5) LLM Usage Guardrails

- LLMs are advisory only; final model output is deterministic.
- LLM outputs must be structured JSON with validation.
- All LLM requests and responses are logged, with secrets redacted.
- A safe fallback is required if the LLM fails or returns invalid output.

## 6) Reliability and Observability

- Every major job logs start, end, and duration.
- API endpoints must return actionable errors and never fail silently.
- When external services fail, degrade gracefully.

## 7) Testing and Verification

- Critical calculations must have unit tests, especially modeling and valuation.
- Data model changes should include migration tests or a smoke query.

## 8) UX Consistency

- Tooltips and glossary definitions must use a finance-professional tone.
- New pages must fit the existing visual hierarchy.
- Chart labels must be explicit and unambiguous.

## 9) Change Management

- Every non-trivial change must include a short "what changed / why" note in the PR or commit.
- Use feature flags for major LLM-driven functionality changes.
- Bug fixes must target root cause rather than symptom masking; add regression tests whenever practical.

## 10) Security

- Any external integration must use an API key or token.
- Keys are read from environment variables only.
- Network access must be restricted to known peers for internal services.
- OpenClaw integration must enforce token auth, allowlist controls, and rate limits.
- Admin and settings tokens are high-sensitivity secrets and must never be returned from read endpoints.
- API key management flows must support identification without disclosure: prefix, short identifier, name, status, created time, and last-used time are acceptable; full secret values are not.

## 11) Agent and Debugging Hygiene

- When using coding agents or shared debugging sessions, instruct the agent not to print or repeat secret values from `.env`, logs, screenshots, or browser state.
- Prefer summaries over raw dumps when inspecting `.env`, Compose config, request headers, or browser storage.
- Before sharing logs externally, redact API keys, admin tokens, bearer headers, cookies, and connection strings.
- For auth, settings, or API-key work, default acceptance criteria should include masked inputs, write-only secret handling, show-once credential generation, and no secret logging.
