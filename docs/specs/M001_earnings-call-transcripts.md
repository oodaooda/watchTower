# M001 Spec: Earnings Call Transcripts

## Purpose

Add earnings-call transcript support to watchTower so users and the Data Assistant can access grounded management commentary by company and quarter.

## Scope

- Transcript ingestion from approved providers
- Persistent transcript storage and metadata in Postgres
- Transcript retrieval APIs for company views and QA flows
- UI support for browsing transcript history and viewing transcript content
- Retrieval path for Data Assistant context using transcript chunks and citations

## Goals

- Provide fast, reliable access to transcript text by ticker and quarter
- Preserve source metadata and attribution for each transcript
- Support assistant answers with transcript-grounded evidence and citations
- Balance freshness, provider limits, and operational cost with a cache-first model

## Non-Goals

- Real-time streaming transcription of live calls
- Provider-specific analytics dashboards in v1
- Full-text semantic search across the entire market universe on day one

## Proposed Approach

- Hybrid strategy:
  - Fetch on demand when transcript is requested and not cached
  - Persist transcript and metadata in Postgres for reuse
  - Refresh by schedule for tracked companies and recent quarters
- Normalize transcripts into chunked segments for retrieval and assistant context
- Use retrieval-first context assembly (top-N relevant chunks), not full transcript injection

## Provider and Storage Decision (Current)

- Primary provider: Alpha Vantage (`EARNINGS_CALL_TRANSCRIPT`)
- Fallback providers: deferred to follow-up milestone
- Storage mode default: `restricted`
  - Store excerpted transcript chunks for assistant grounding and citations
  - Do not enable full-transcript persistence (`standard`) until licensing clearance is confirmed

## Data Model (V1)

- `earnings_call_transcripts`
  - `id`
  - `company_id`
  - `ticker`
  - `fiscal_year`
  - `fiscal_quarter`
  - `call_date`
  - `source_provider`
  - `source_url`
  - `source_doc_id`
  - `content_hash`
  - `language`
  - `ingested_at`
  - `updated_at`
- `earnings_call_transcript_segments`
  - `id`
  - `transcript_id`
  - `segment_index`
  - `speaker`
  - `section`
  - `text`
  - `token_count`

## API Contracts (V1)

- `GET /companies/{company_id}/transcripts`
  - List available transcript metadata by quarter/date/source
- `GET /transcripts/{transcript_id}`
  - Return transcript metadata and segments
- `POST /transcripts/sync`
  - Trigger fetch for ticker + quarter (admin/internal use)

All transcript responses include source attribution fields and ingestion timestamps.

## Data Assistant Integration

- Add transcript retrieval tool/action for QA planning.
- For transcript-related prompts:
  - Resolve company and quarter intent
  - Retrieve relevant stored segments
  - Return answer with segment-level citations (`source_url`, quarter, segment index)
- Enforce grounding:
  - Claims from transcripts must cite retrieved transcript segments
  - Do not infer quoted text not present in retrieved segments

## Follow-Up Resolution Architecture (Root-Cause and Durable Fix)

### Root Cause

- QA endpoint is stateless per request and only receives the current question text.
- Follow-up prompts (for example: "their last earnings call") may contain no explicit ticker/company.
- Resolver fallback can misinterpret short tokens as tickers (for example `DO`), causing false clarification loops.

### Durable Design

- Add first-class conversation context to QA contract:
  - request includes `thread_id` and/or explicit `company_id`/`context_company`
  - backend stores/retrieves last resolved company per thread/session
- Resolver precedence must be deterministic:
  - explicit company in current question
  - thread context company
  - clarification request
- Restrict implicit ticker inference:
  - disable generic 2-letter ticker inference unless explicitly signaled (`(DO)`, `ticker DO`, etc.)
- Keep transcript grounding unchanged:
  - follow-up resolution changes only entity selection, not citation or synthesis guardrails

## Security and Compliance

- Validate provider terms before bulk storage or redistribution.
- Store source attribution and preserve traceability to original provider URL.
- Redact secrets from ingestion logs and provider request telemetry.
- Do not store provider API keys in code paths or responses.

## Reliability and Operations

- Retry with bounded backoff for provider failures.
- Guardrails: timeout, size limits, dedupe by `(ticker, year, quarter, source_doc_id/hash)`.
- Record ingestion status and errors for observability.
- Degrade gracefully: if provider unavailable, return cached data if present.

## Acceptance Criteria (V1)

- User can view transcript history for a company and open a transcript.
- Transcript API returns metadata plus segmented text with source attribution.
- Data Assistant can answer transcript questions with citation links and segment refs.
- Ingestion path supports idempotent re-runs without duplicate transcript rows.
- Unit/integration tests cover ingestion, dedupe, retrieval, and citation assembly.

## Automated Test Minimums (V1)

- Unit:
  - Provider payload-to-schema mapping
  - Normalization and deterministic chunk ordering
  - Dedupe key behavior and idempotent upsert logic
  - Citation payload generation from transcript segments
- Integration:
  - `POST /transcripts/sync` ingest path creates metadata + segments
  - Repeated sync for same quarter does not duplicate records
  - `GET /companies/{company_id}/transcripts` and `GET /transcripts/{id}` contract behavior
  - Data Assistant transcript-intent response includes transcript citations
- Security and guardrails:
  - Unauthorized sync attempts are rejected
  - Provider failures do not leak secrets in logs or responses
  - Response payloads exclude auth headers and API key material

## Risks

- Provider licensing or redistribution restrictions
- Missing transcripts for some companies/quarters
- Provider rate limits affecting freshness
- Increased storage/query cost for long transcript content

## Open Questions

- Licensing clearance for full-transcript storage and redistribution
- Final retention window for transcript segments in restricted mode
- Whether vector indexing is needed in v1 or deferred to v2
