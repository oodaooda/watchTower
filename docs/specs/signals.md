# Spec: WatchTower Signals

## Purpose

Add `/signals` as a real-time monitoring wall for portfolio-relevant financial and geopolitical signals, with explicit support for the user's VGT-heavy portfolio and path toward a `$1M` portfolio goal.

Signals should help answer:

- What changed?
- Which signals are stressed?
- What current context matters for VGT exposure?
- How is the portfolio progressing toward `$1M`?
- What can the assistant explain with citations?

Signals must not become an automated buy/sell or price-prediction system.

## Scope

- Native WatchTower module using the existing FastAPI, SQLAlchemy, Alembic, APScheduler, React Router, and Tailwind stack
- Authenticated `/signals` page with dense tile wall UI
- Signal storage, latest state, history, ingest runs, alert state, and layout persistence
- Server-Sent Events for live tile updates
- Read-only assistant context endpoints
- VGT and `$1M` portfolio goal modules using existing portfolio lots and market value snapshots
- Primary-source ingest modules for FRED, Alpha Vantage, SEC EDGAR, TSMC IR, Polymarket, and Federal Register
- Deterministic regime indicator

## Non-Goals

- Separate Node/Fastify service in v1
- TimescaleDB, pg-boss, Redis, TanStack Query, Zustand, or uPlot as required v1 infrastructure
- Client-side provider secrets
- News reader or infinite feed
- Automated trading recommendations
- Assistant write access to ingest jobs, alerts, thresholds, layouts, or portfolio records
- Duplicate Signals-owned holdings table

## Product Decisions

- Build Signals as a native WatchTower module first.
- Reuse existing `wt_` API keys and settings/admin token patterns.
- Use normal Postgres tables through Alembic before considering TimescaleDB.
- Use existing portfolio holdings/lots and portfolio snapshots for goal tracking.
- Use a fetch-stream SSE client instead of browser-native `EventSource` so auth stays in headers.
- Expose assistant-ready data through curated read-only context endpoints, not unrestricted SQL/table access.
- Keep language focused on monitoring, risk, velocity, drawdown, required return, and source context.

## Core Contract

- Each signal observation stores:
  - timestamp
  - module id
  - entity
  - metric
  - value
  - z-score
  - status
  - source
  - raw payload
- Signal inserts are idempotent by module, timestamp, metric, and entity.
- New observations create replayable signal events for SSE clients.
- Ingest failures are isolated to the module that failed.
- Every ingest run is logged.
- Missing or stale data must be visible as grey/stale state, not silently treated as zero.
- Assistant context must include source/citation fields and must exclude secrets.

## API Contract

Recommended endpoints:

- `GET /signals/catalog`
- `GET /signals/latest`
- `GET /signals/history?module_id=M1&range=30d`
- `GET /signals/stream`
- `GET /signals/layout`
- `PUT /signals/layout`
- `GET /signals/alerts`
- `POST /signals/alerts/{id}/ack`
- `POST /signals/ingest/{module_id}/run`
- `GET /signals/ingest-runs`
- `GET /signals/assistant/context`
- `GET /signals/assistant/brief`

Read-only endpoints accept active `wt_` keys. Admin/manual ingest endpoints require an admin-capable token until key scopes are added.

## UI Contract

The `/signals` page should provide:

- dark, dense monitoring wall
- top bar with current regime, goal progress, stream state, and assistant-read status
- grid of tiles showing:
  - title
  - status dot
  - primary value
  - unit
  - z-score
  - sparkline
  - source
  - age
  - expand affordance
- alert rail for recent alerts
- click-to-expand modal in later phases with full chart, thresholds, latest raw values, and citations

## Module Catalog

V1 target modules:

- `P1`: `$1M` Goal Tracker
- `P2`: VGT Exposure
- `P3`: Required Return
- `P4`: Drawdown From High
- `M1`: HY OAS
- `M2`: 10Y Real Yield
- `M3`: VIX
- `M4`: Dollar Broad Index
- `E1`: News Sentiment Top 5
- `E2`: NVDA EPS Estimate Delta
- `E3`: Insider Net Flow Top 5
- `E4`: Put/Call Skew VGT, skipped or replaced unless a reliable source is confirmed
- `S1`: TSMC Revenue YoY
- `S2`: Hyperscaler Capex Delta
- `G1`: Polymarket Taiwan
- `G2`: BIS Export Rules 90d
- `I1`: Ingest Health

## Assistant Contract

The assistant may answer:

- What signals are red or amber right now?
- Why is the regime stressed?
- What changed in the last 24 hours?
- Which modules are stale or failing?
- How is the `$1M` goal progressing?
- What current Signals matter most for VGT exposure?

The assistant must not:

- run ingest jobs
- acknowledge alerts
- change thresholds
- edit layouts
- edit portfolio data
- expose raw provider credentials
- present Signals as buy/sell recommendations

## Scope Gaps

- Current `wt_` keys do not have scopes.
- VGT constituent look-through needs a reliable holdings source.
- E4 options-chain source is unresolved.
- S2 capex normalization needs a company/tag study.
- Native `EventSource` cannot send auth headers.
- FRED key is not currently part of WatchTower settings.

## Recommendations

- Extract existing OpenClaw token validation into shared auth code.
- Start with active `wt_` keys for read-only access and `SETTINGS_ADMIN_TOKEN` for admin operations.
- Implement P1 from existing portfolio snapshots early.
- Implement P2 first from current VGT holding value and direct tech holdings; add constituent-level look-through later.
- Skip or replace E4 unless an options-chain source is confirmed.
- Implement S2 only after a capex tag study.
- Add `FRED_API_KEY` only when implementing M1.
- Keep the architecture doc at `docs/signals/ARCHITECTURE.md` as supporting implementation detail.

## Acceptance Shape

V1 is successful when:

- `/signals` renders as an authenticated monitoring wall.
- M1 ingests real FRED HY OAS data and updates the wall through SSE.
- Signal history and latest state are queryable through API endpoints.
- Assistant context returns latest signal state with citations.
- P1 goal progress is computed from existing portfolio snapshots.
- VGT exposure is visible from existing portfolio lots.
- Ingest failures are visible and do not break unrelated modules.
- Product copy avoids trading recommendations and unsupported prediction language.
