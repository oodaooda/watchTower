# watchTower Roadmap Checklist

This checklist is broken into phases. Each phase includes verification steps and when to commit.

## Phase 1 — Refactor & Engineering Alignment

- [x] Create `ENGINEERING_STANDARDS.md`
- [x] Create `OPERATIONS_GUIDE.md` (runbook equivalent)
- [x] Standardize canonical DB workflow in docs
- [x] Add API versioning (`/api/v1`)
- [x] Add request logging + request IDs
- [x] Add guardrails (modeling horizon clamp, LLM output validation)
- [x] Add unit test scaffolding (forecaster + DCF)
- [ ] Add API smoke tests (health, modeling run)
- [ ] Add CI guidance (GitHub Actions)

**Phase 1 Tests**
- [x] `pytest` (unit tests)
- [x] Manual: `GET /health` and `GET /api/v1/health`
- [x] Manual: `POST /modeling/{id}/run` returns scenarios

**Commit Point**
- [x] Commit after Phase 1 tests pass.

---

## Phase 2 — LLM Features for User Queries

- [x] Design `/qa` endpoint schema (question → answer + citations)
- [x] Implement safe query tool (whitelisted fields, read‑only)
- [x] Add LLM guardrails (schema validation, fallback response)
- [x] Add structured audit logging for LLM requests/responses
- [x] Add UI “Data Assistant” chat tab
- [x] Update docs (`ENGINEERING_STANDARDS.md`, `OPERATIONS_GUIDE.md`)

**Phase 2 Tests**
- [x] Unit: query tool validation
- [x] Integration: `/qa` returns answer for known company
- [x] Manual UI: Data Assistant chat returns valid response

**Commit Point**
- [x] Commit after Phase 2 tests pass.

---

## Phase 3 — OpenClaw API Integration

- [x] Add API token auth (Bearer)
- [x] Add optional IP allowlist
- [x] Add rate limiting
- [x] Expose `POST /openclaw/qa` (or reuse `/qa` with auth)
- [x] Add OpenClaw integration guide + example payloads

**Phase 3 Tests**
- [ ] Integration: authorized request succeeds, unauthorized fails
- [ ] Manual: OpenClaw example payload works

**Commit Point**
- [ ] Commit after Phase 3 tests pass.

---

## Notes

- Use `/api/v1` for new clients; legacy routes remain for compatibility.
- Keep DB use consistent (`docker_db_1` / `db` hostname).
