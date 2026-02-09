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
- [ ] `pytest` (unit tests)
- [ ] Manual: `GET /health` and `GET /api/v1/health`
- [ ] Manual: `POST /modeling/{id}/run` returns scenarios

**Commit Point**
- [ ] Commit after Phase 1 tests pass.

---

## Phase 2 — LLM Features for User Queries

- [ ] Design `/qa` endpoint schema (question → answer + citations)
- [ ] Implement safe query tool (whitelisted fields, read‑only)
- [ ] Add LLM guardrails (schema validation, fallback response)
- [ ] Add structured audit logging for LLM requests/responses
- [ ] Add UI “Data Assistant” chat tab
- [ ] Update docs (`ENGINEERING_STANDARDS.md`, `OPERATIONS_GUIDE.md`)

**Phase 2 Tests**
- [ ] Unit: query tool validation
- [ ] Integration: `/qa` returns answer for known company
- [ ] Manual UI: Data Assistant chat returns valid response

**Commit Point**
- [ ] Commit after Phase 2 tests pass.

---

## Phase 3 — OpenClaw API Integration

- [ ] Add API token auth (Bearer)
- [ ] Add optional IP allowlist
- [ ] Add rate limiting
- [ ] Expose `POST /openclaw/qa` (or reuse `/qa` with auth)
- [ ] Add OpenClaw integration guide + example payloads

**Phase 3 Tests**
- [ ] Integration: authorized request succeeds, unauthorized fails
- [ ] Manual: OpenClaw example payload works

**Commit Point**
- [ ] Commit after Phase 3 tests pass.

---

## Notes

- Use `/api/v1` for new clients; legacy routes remain for compatibility.
- Keep DB use consistent (`docker_db_1` / `db` hostname).
