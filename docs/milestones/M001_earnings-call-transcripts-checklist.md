# M001: Earnings Call Transcripts

This checklist tracks delivery of transcript ingestion, storage, retrieval, and assistant integration.

Primary spec: `../specs/M001_earnings-call-transcripts.md`

## Milestone A - Source and Compliance Foundation

- [ ] Confirm approved transcript providers and terms for storage/reuse
- [x] Document provider selection and fallback order
- [x] Add environment variable docs for transcript provider keys
- [ ] Define attribution requirements per source
- [ ] Define retention policy and legal constraints

## Milestone B - Data Model and Migrations

- [x] Create transcript metadata table migration
- [x] Create transcript segments table migration
- [x] Add indexes for `(company_id, fiscal_year, fiscal_quarter)` and transcript lookup
- [x] Add ORM models and schemas
- [ ] Add migration smoke checks

## Milestone C - Ingestion Pipeline

- [x] Implement provider client abstraction
- [x] Implement fetch for ticker + quarter
- [x] Implement normalization and chunking pipeline
- [x] Implement idempotent upsert/dedupe logic
- [x] Add error telemetry and ingestion status logging

## Milestone D - API and UI

- [x] Add `GET /companies/{company_id}/transcripts`
- [x] Add `GET /transcripts/{transcript_id}`
- [x] Add sync endpoint for targeted refresh
- [x] Add Company page transcript tab/list
- [x] Add transcript detail view with citations metadata

## Milestone E - Data Assistant Integration

- [x] Add transcript retrieval action/tool
- [x] Add planner routing for transcript-intent prompts
- [x] Add transcript-grounded synthesis with segment citations
- [x] Enforce grounding guardrails for transcript claims
- [x] Add fallback behavior when transcript is unavailable

### E1 - Follow-Up Context and Resolver Hardening

- [x] Add explicit conversation context fields to QA request contract (`thread_id` and/or `context_company`)
- [x] Persist and read last resolved company context by thread/session
- [x] Implement strict resolver precedence: explicit entity -> context entity -> clarification
- [x] Disable ambiguous implicit 2-letter ticker inference unless explicitly marked
- [x] Add resolver diagnostics fields for context-derived resolutions

## Milestone F - Testing and Readiness

- [x] Unit tests for normalization, dedupe, and segment retrieval
- [x] Integration tests for ingest + read APIs
- [x] Integration tests for assistant transcript Q&A with citations
- [ ] Manual QA on at least 3 companies and 2 quarters each
- [ ] Performance check for transcript retrieval latency
- [x] Security check: no secret values in logs/responses

### F1 - Automated Unit Tests

- [x] Provider adapter mapping test: upstream payload maps to internal transcript schema
- [x] Normalization test: speaker/section extraction and cleanup are deterministic
- [x] Chunking test: transcript split is stable and segment ordering is preserved
- [ ] Dedupe test: repeated ingest with same `(ticker, year, quarter, source_doc_id/hash)` does not create duplicates
- [x] Citation-builder test: segment references produce stable citation payloads
- [x] Retrieval ranking test: top-N relevant segments are returned for transcript-intent query terms
- [x] Follow-up context test: pronoun-only transcript question resolves using prior thread/company context
- [x] False-positive guard test: short token words (e.g. `do`, `it`) are not auto-promoted to ticker candidates

### F2 - Automated Integration Tests

- [x] Sync endpoint ingest test: `POST /transcripts/sync` creates transcript and segments for valid input
- [x] Idempotency test: repeating sync for same quarter does not duplicate rows
- [x] Transcript list API test: `GET /companies/{company_id}/transcripts` returns expected metadata ordering
- [x] Transcript detail API test: `GET /transcripts/{id}` returns segment sequence and source attribution
- [x] Assistant grounding test: transcript question returns answer with transcript segment citations
- [x] Fallback test: provider timeout/error returns cached transcript when available
- [ ] Conversation continuity test: multi-turn QA keeps company context and resolves transcript follow-ups

### F3 - Automated Security and Guardrail Tests

- [x] Auth test: unauthorized sync endpoint calls fail with `401/403`
- [x] Redaction test: ingestion/provider errors do not log API keys or bearer tokens
- [x] Response hygiene test: transcript APIs never return provider secrets or raw auth headers

## Exit Criteria

- [x] Transcript data is queryable from API and visible in UI
- [x] Assistant can answer transcript questions with citations
- [x] Ingestion is idempotent and resilient to provider failures
- [x] Documentation is complete and linked from roadmap/spec indexes
- [x] Follow-up transcript questions resolve without explicit ticker when prior company context exists
