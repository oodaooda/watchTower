# watchTower Roadmap Checklist

This checklist is broken into phases. Each phase includes verification steps and when to commit.

## Phase 1 — Refactor & Engineering Alignment

- [x] Create `docs/ENGINEERING_STANDARDS.md`
- [x] Create `docs/OPERATIONS_GUIDE.md` (runbook equivalent)
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
- [x] Update docs (`docs/ENGINEERING_STANDARDS.md`, `docs/OPERATIONS_GUIDE.md`)

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
- [x] Add Settings page for OpenClaw API keys

**Phase 3 Tests**
- [x] Integration: authorized request succeeds, unauthorized fails
- [x] Manual: OpenClaw example payload works

**Commit Point**
- [x] Commit after Phase 3 tests pass.

---

## Phase 4 — Data Assistant Robustness (Planner + SQL Trace + Hybrid Responses)

Execution order for Phase 4: `4A -> 4D -> 4B -> 4C` (resolver foundations first).

### Phase 4A — Multi-Company + SQL Trace

- [x] Extend planner schema to support multi-company prompts (`companies`, `compare`, `response_mode`)
- [x] Add multi-company resolver (`NVDA vs TSMC` style prompts)
- [x] Add safe execution trace object (`sql_template`, `params`, `rows`, `duration_ms`)
- [x] Add API response fields for trace sections (`plan`, `queries`, `sources`)
- [x] Add UI trace viewer with readable sections and toggle

**Phase 4A Tests**
- [ ] Unit: planner handles multi-company prompts
- [ ] Unit: resolver returns partial success when one company is missing
- [ ] Unit: trace serializer redacts unsafe values and keeps allowlisted params only
- [ ] Integration: `/qa` returns both companies for compare prompt
- [ ] Manual UI: trace panel shows plan + query summaries correctly

**Phase 4A Commit/Push Point**
- [ ] Commit after Phase 4A tests pass
- [ ] Push after commit and manual UI verification

### Phase 4B — Hybrid Grounded + General Responses (execute after 4D)

- [x] Add response mode routing: `grounded` / `general` / `hybrid`
- [x] Add general-context synthesis path for conceptual finance questions
- [x] Enforce grounding rules for numeric claims from DB data only
- [x] Add explicit answer sections: `What data shows`, `General context`, `Gaps`
- [x] Add source tagging in response (`database`, `general_context`)

**Phase 4B Tests**
- [x] Unit: numeric claims validator rejects unsupported numbers
- [x] Unit: response mode classifier routes conceptual prompts to `general`/`hybrid`
- [x] Integration: broad question (`tell me about tesla`) returns grounded + context sections
- [x] Integration: conceptual question (`what is operating leverage`) answers without forcing ticker
- [x] Manual UI: response formatting is readable and labels context vs data

**Phase 4B Commit/Push Point**
- [x] Commit after Phase 4B tests pass
- [x] Push after regression check (`/qa`, `/openclaw/qa`, Data Assistant UI)

**Phase 4B Follow-up (Variable Retrieval Robustness)**
- [ ] Improve variable-specific answer targeting (e.g., "last close price") when multiple metrics are available in snapshot payloads.
- [ ] Add intent-to-field contract map in docs (`price` -> `close_price`, `valuation` -> `pe_ttm`, etc.).
- [ ] Add deterministic field-priority policy for synthesis (requested fields first, then optional context).
- [ ] Add unit tests for metric-intent prompts across common variants ("price", "last close", "latest close", "share price").
- [ ] Evaluate optional tool-routing upgrade: explicit metric tool calls from planner output vs static action bundles.

### Phase 4C — News Ingestion for Holistic Explanations (execute after 4D)

- [x] Add `news_context` action for “why up/down” prompts
- [x] Rank candidate headlines by relevance to prompt/company context
- [x] Fetch top-N article pages (allowlisted fetch + timeout + size caps)
- [x] Extract readable content snippets (title/body summary + source URL)
- [x] Add synthesis section combining DB metrics + news catalysts + confidence
- [x] Add citations with article links in response payload/UI

**Phase 4C Tests**
- [x] Unit: headline ranking prioritizes keyword/sentiment matches
- [x] Unit: fetch guardrails enforce domain/timeout/size limits
- [x] Integration: “why was TSLA down last week” returns news-backed explanation
- [x] Integration: graceful fallback when article fetch fails (headlines-only mode)
- [x] Manual UI: article citations are readable/clickable and trace includes ingestion steps

**Phase 4C Commit/Push Point**
- [x] Commit after Phase 4C tests pass
- [x] Push after regression check (`/qa`, `/openclaw/qa`, Data Assistant UI, Company profile news)

### Phase 4D — Root-Cause Entity Resolution (No More Token Guessing, execute before 4B/4C)

- [x] Define deterministic entity-resolution contract (ticker, company name, confidence, reason)
- [x] Replace heuristic token guessing with resolver pipeline:
- [x] normalize prompt entities
- [x] validate ticker-like tokens against `companies`
- [x] ranked company-name candidate matching (exact > prefix > fuzzy)
- [x] explicit low-confidence handling (return clarification needed)
- [x] Add candidate scoring and tie-break policy (documented)
- [x] Add optional compare-mode resolver (`A vs B`) with partial-success behavior
- [x] Return resolver diagnostics in trace (`resolved`, `unresolved`, `confidence`)

**Phase 4D Tests**
- [x] Unit: resolver ignores conversational tokens (`can`, `you`, `vs`, etc.) by design (not stopword patch)
- [x] Unit: ticker validation only resolves when ticker exists in `companies`
- [x] Unit: ambiguous name returns clarification-needed/low-confidence path
- [x] Unit: compare prompt resolves both entities when available
- [x] Integration: `/qa` compare prompt does not resolve unrelated tickers
- [x] Integration: unresolved entity path is graceful (no 500, no random match)
- [x] Manual UI: trace shows confidence/reason per resolved entity

**Phase 4D Commit/Push Point**
- [x] Commit after Phase 4D tests pass
- [x] Push after regression check (`/qa`, compare prompts, OpenClaw `/openclaw/qa`)

---

## Phase 5 — Read-Only NL-to-SQL Querying (Schema-Aware QA)

- [x] Add dedicated QA read-only DB connection (`QA_DATABASE_URL`)
- [x] Add SQL mode runtime controls (`QA_SQL_ENABLED`, row/time limits)
- [x] Build schema context loader (tables + columns + types) for SQL planning
- [x] Add SQL planning layer (LLM proposes SQL using schema context)
- [x] Add SQL validation guardrails (SELECT-only, allowlisted tables, single statement)
- [x] Add execution sandbox (statement timeout + row limit)
- [x] Add deterministic fallback to existing action pipeline when planning/validation fails
- [x] Add SQL traceability in QA response (`queries`, SQL statement, rows/duration)
- [x] Add OpenClaw-compatible news links contract (`news[]` and `data.news[]`)
- [x] Create Postgres read-only role for QA (`watchtower_readonly`) and grant SELECT-only access

**Phase 5 Tests**
- [x] Unit: SQL validator rejects DDL/DML and unknown-table queries
- [x] Unit: SQL helper functions (table extraction, LIMIT enforcement)
- [x] Integration: factual metric prompt can be answered through guarded SQL path
- [x] Integration: invalid SQL plan falls back to deterministic action path
- [x] Manual: verify read-only user cannot mutate schema/data (`INSERT/UPDATE/DROP` denied)

**Phase 5 Commit/Push Point**
- [ ] Commit after Phase 5 tests pass
- [ ] Push after regression check (`/qa`, `/api/v1/openclaw/qa`, Data Assistant UI)

---

## Notes

- Use `/api/v1` for new clients; legacy routes remain for compatibility.
- Keep DB use consistent (`docker_db_1` / `db` hostname).
