# WatchTower Signals Architecture

Last validated against codebase: 2026-05-17

## Goal

Add `/signals` as an authenticated, real-time OSINT monitoring wall inside the existing WatchTower application. Signals should feel like a Bloomberg-terminal/status-page hybrid: dense dark UI, monospace numerics, always-on tiles, sparse red/amber/green, and quick glanceability.

The practical investing goal is to monitor risks and opportunities around the user's VGT-heavy portfolio and the path toward a `$1M` portfolio target. Signals should help answer "what changed?", "what is stressed?", and "what affects VGT exposure?", not produce unsupported buy/sell predictions.

The implementation should reuse WatchTower's current architecture wherever it already works. The earlier proposal assumed a separate Node/Fastify service with pg-boss, TimescaleDB, TanStack Query, Zustand, and uPlot. After reviewing the current codebase, those are not the right v1 defaults.

## Architecture Decision

Build Signals as a native WatchTower module first.

Use existing:

- FastAPI router registration in `app/api/main.py`
- SQLAlchemy models in `app/core/models.py`
- Alembic migrations in `migrations/versions`
- `SessionLocal` / `get_db` from `app/core/db.py`
- APScheduler job lifecycle in `app/jobs/scheduler.py`
- existing `wt_` API key pattern from `api_keys`
- existing settings/env pattern from `app/core/config.py`
- existing React Router shell in `ui/src/main.tsx` and `ui/src/pages/AppShell.tsx`
- existing Tailwind styling and installed charting library (`recharts`) where charting is needed

Do not add a separate Node service, pg-boss, Redis, TimescaleDB, TanStack Query, Zustand, or uPlot in v1 unless the existing stack fails a concrete requirement.

## Non-Goals

- No news reader, article feed, or infinite scroll.
- No AI-generated trading instructions, buy/sell calls, or price prediction.
- No multi-tenant auth system.
- No new service boundary before the in-process FastAPI module is proven insufficient.
- No client-side provider keys or `VITE_*` secrets.
- No assistant write access to ingest runs, alert acknowledgements, thresholds, layouts, or portfolio records in v1.

## Final Route Tree

### Backend

```text
app/
  routers/
    signals.py
    signals_assistant.py
  services/
    signals/
      __init__.py
      catalog.py
      fetcher.py
      transforms.py
      zscore.py
      regime.py
      assistant_context.py
      goal_tracker.py
      sse.py
      jobs.py
      modules/
        m1_hy_oas.py
        m2_real_yield.py
        m3_vix.py
        m4_dollar_index.py
        e1_news_sentiment.py
        e2_nvda_eps_delta.py
        e3_insider_flow.py
        s1_tsmc_revenue.py
        s2_hyperscaler_capex.py
        g1_polymarket_taiwan.py
        g2_bis_export_rules.py
        i1_ingest_health.py
        p1_goal_tracker.py
        p2_vgt_exposure.py
        p3_required_return.py
        p4_drawdown.py
  jobs/
    scheduler.py
  core/
    models.py
    schemas.py
    config.py
migrations/
  versions/
```

### Frontend

```text
ui/src/
  pages/
    SignalsPage.tsx
  signals/
    SignalTile.tsx
    SignalWall.tsx
    SignalTileModal.tsx
    RegimeIndicator.tsx
    AlertRail.tsx
    sparkline.tsx
    types.ts
```

The current prototype uses a single `SignalsPage.tsx` while the design is still being evaluated. Split into `ui/src/signals/*` once behavior becomes real.

## Backend API Routes

Register `app.routers.signals` in both root and `/api/v1` route trees, matching existing router patterns.

```text
GET  /signals/catalog
GET  /signals/latest
GET  /signals/history?module_id=M1&range=30d
GET  /signals/stream
GET  /signals/layout
PUT  /signals/layout
GET  /signals/alerts
POST /signals/alerts/{id}/ack
POST /signals/ingest/{module_id}/run
GET  /signals/ingest-runs
GET  /signals/assistant/context
GET  /signals/assistant/brief
```

Manual ingest routes should require an admin-capable token. Read-only routes can use a scoped Signals viewer key if we add key scoping.

`/signals/assistant/*` routes are read-only, citation-aware endpoints intended for WatchTower's assistant layer. They should return compact, pre-shaped context instead of exposing raw tables directly.

## Data Model

Use normal Postgres tables through Alembic first. TimescaleDB can be revisited only if the table size or query patterns justify it.

Important correction from the earlier schema: `entity` cannot be nullable if it is part of a composite primary key. Use a surrogate id and a unique constraint, or make `entity` non-null with a default.

Recommended v1 tables:

```sql
CREATE TABLE signals (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL,
  module_id TEXT NOT NULL,
  entity TEXT NOT NULL DEFAULT '',
  metric TEXT NOT NULL,
  value DOUBLE PRECISION NOT NULL,
  z_score DOUBLE PRECISION,
  status TEXT NOT NULL CHECK (status IN ('green', 'amber', 'red', 'grey')),
  source TEXT NOT NULL,
  raw_payload JSONB,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(module_id, ts, metric, entity)
);

CREATE INDEX ix_signals_module_ts ON signals (module_id, ts DESC);
CREATE INDEX ix_signals_metric_entity_ts ON signals (metric, entity, ts DESC);

CREATE TABLE signal_events (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ DEFAULT now(),
  module_id TEXT NOT NULL,
  signal_id BIGINT REFERENCES signals(id) ON DELETE CASCADE,
  payload JSONB NOT NULL
);

CREATE INDEX ix_signal_events_ts ON signal_events (ts DESC);

CREATE TABLE signal_ingest_runs (
  id BIGSERIAL PRIMARY KEY,
  module_id TEXT NOT NULL,
  started_at TIMESTAMPTZ DEFAULT now(),
  finished_at TIMESTAMPTZ,
  status TEXT CHECK (status IN ('ok', 'fail', 'partial')),
  error TEXT,
  records_written INT DEFAULT 0
);

CREATE TABLE signal_module_state (
  module_id TEXT PRIMARY KEY,
  enabled BOOLEAN NOT NULL DEFAULT true,
  config JSONB NOT NULL DEFAULT '{}',
  last_success_at TIMESTAMPTZ,
  last_attempt_at TIMESTAMPTZ,
  last_status TEXT CHECK (last_status IN ('ok', 'fail', 'partial')),
  last_error TEXT,
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE signal_alerts (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ DEFAULT now(),
  module_id TEXT NOT NULL,
  severity TEXT CHECK (severity IN ('info', 'warn', 'crit')),
  message TEXT NOT NULL,
  acknowledged_at TIMESTAMPTZ,
  acknowledged_reason TEXT,
  state_snapshot JSONB
);

CREATE TABLE signal_layouts (
  key_hash TEXT PRIMARY KEY,
  config JSONB NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE signal_goal_snapshots (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  goal_name TEXT NOT NULL DEFAULT 'portfolio_1m',
  current_value NUMERIC(20, 4) NOT NULL,
  target_value NUMERIC(20, 4) NOT NULL,
  distance_to_goal NUMERIC(20, 4) NOT NULL,
  velocity_30d NUMERIC(20, 4),
  velocity_90d NUMERIC(20, 4),
  required_monthly_gain NUMERIC(20, 4),
  source TEXT NOT NULL,
  raw_payload JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ix_signal_goal_snapshots_goal_ts ON signal_goal_snapshots (goal_name, ts DESC);
```

Recommendation: do not create a separate `holdings` table for Signals in v1. WatchTower already has portfolio holdings/lots and portfolio market value snapshots. The goal tracker and equity modules should read from existing portfolio tables/snapshots or a small module config table, not duplicate holdings.

## Auth Model

Reuse the existing `wt_` API key mechanism.

Current codebase facts:

- `settings.py` creates keys with prefix `wt_`.
- `api_keys.key_hash` stores SHA-256 hashes.
- `openclaw.py` already validates bearer tokens against `api_keys` and optionally an env master token.
- Several admin routes use `SETTINGS_ADMIN_TOKEN`.

Recommended Phase 1 implementation:

1. Extract the OpenClaw token validation logic into a shared helper, e.g. `app/core/auth.py`.
2. Use that helper in `app/routers/openclaw.py` and new `app/routers/signals.py`.
3. Add optional key scopes only if needed:
   - `signals:read`
   - `signals:write`
   - `signals:admin`
4. Until scopes exist, use any active `wt_` key for read-only Signals and `SETTINGS_ADMIN_TOKEN` for manual ingest/admin routes.

Do not introduce JWT viewer sub-tokens in Phase 1. They are a future improvement if long-lived API keys become annoying for a wall display.

## Assistant Access Model

The WatchTower assistant should be able to use Signals after Phase 1/2, but only through read-only, source-aware context endpoints.

Allowed assistant questions:

- What signals are red or amber right now?
- Why is the regime `STRESSED` or `CRISIS`?
- What changed in the last 24 hours?
- Which modules are stale or failing?
- How is the `$1M` portfolio goal progressing?
- What current Signals matter most for VGT exposure?
- Show citations/source timestamps behind the answer.

Assistant boundaries:

- No direct provider API keys in assistant context.
- No raw secrets or auth headers in returned payloads.
- No admin actions by default.
- No running ingest jobs, acknowledging alerts, changing thresholds, editing layouts, or editing portfolio data without an explicit future admin approval flow.
- No "buy", "sell", or price-prediction language. Responses should be framed as monitoring, risk, and scenario context.

Recommended assistant endpoints:

```text
GET /signals/assistant/context?range=24h
GET /signals/assistant/brief
```

`/signals/assistant/context` should return:

- latest regime and contributing rules
- latest red/amber/green/grey modules
- top changes over the selected range
- stale/failing modules
- VGT/goal tracker summary
- source citations and observation timestamps

`/signals/assistant/brief` should return a compact daily-readable summary suitable for a chat answer, with links back to tile/module detail.

## SSE Protocol

FastAPI can serve SSE from the existing API process using `StreamingResponse`.

```text
GET /signals/stream
Authorization: Bearer wt_...
Accept: text/event-stream
Last-Event-ID: 12345
```

Event format:

```text
id: 12346
event: signal_update
data: {"moduleId":"M1","ts":"2026-05-18T01:23:45Z","value":312,"zScore":-0.4,"status":"green","source":"FRED"}
```

Implementation recommendation:

- Phase 1: use an in-process broadcaster plus DB replay from `signal_events`.
- On new observations, insert `signals`, insert `signal_events`, and publish to the broadcaster.
- On reconnect, read `Last-Event-ID` and replay from `signal_events`.
- If the cursor is too old, send `snapshot_required` and let the client refetch `/signals/latest`.

Scope gap: browser-native `EventSource` cannot send `Authorization` headers.

Recommendation: use a small fetch-stream client in React instead of native `EventSource`, so bearer auth stays in headers and never moves to query strings.

## Scheduler And Ingest Jobs

Reuse `app/jobs/scheduler.py` and APScheduler.

Add a Signals scheduler registration function:

```python
def register_signal_jobs(sched: BackgroundScheduler) -> None:
    ...
```

Call it inside `start_scheduler()` after existing jobs are registered.

Each module should follow a common function contract:

```python
def run_module(db: Session, *, now: datetime | None = None) -> SignalRunResult:
    ...
```

Handler contract:

1. Fetch from source through a shared `app.services.signals.fetcher`.
2. Apply timeout, retry, backoff, and source-specific rate limiting.
3. Validate response shape with Pydantic models or explicit canary checks.
4. Normalize to `SignalObservation`.
5. Compute trailing 1Y Z-score from the `signals` table.
6. Insert with idempotent `ON CONFLICT DO NOTHING`.
7. Insert `signal_events` and publish to SSE broadcaster for new rows.
8. Write `signal_ingest_runs` and update `signal_module_state`.

Use current app logging first. Sentry remains optional and should not block v1.

## Shared Fetcher

Add `app/services/signals/fetcher.py`.

It should provide:

- timeout
- retry with backoff
- source-specific rate limit guard
- JSON/text response handling
- canary hooks
- structured logs with no secrets
- SEC User-Agent support using existing `settings.sec_user_agent`

Use the standard library plus current project dependencies first. Add `httpx` only if requests/urllib proves insufficient for streaming/timeouts.

## Frontend Strategy

Use current React Router and Tailwind.

Phase 1 should avoid new frontend dependencies:

- Initial data: existing `fetch` pattern in `ui/src/lib/api.ts`
- Live data: fetch-stream SSE helper
- State: local React state or reducer
- Sparklines: inline SVG or existing Recharts

Reconsider TanStack Query/Zustand/uPlot after v1 if the page becomes hard to maintain or performance becomes measurable pain.

The current prototype route:

```text
/signals -> ui/src/pages/SignalsPage.tsx
```

The prototype is intentionally static and should be treated as visual scaffolding only.

## VGT And `$1M` Goal Tracking

The OSINT wall is practical for a VGT-heavy portfolio if it is treated as a risk/opportunity monitor rather than a prediction engine. VGT's value is heavily influenced by large-cap technology multiples, real yields, AI/semiconductor demand, hyperscaler capex, export controls, Taiwan risk, and earnings/sentiment from top holdings.

Add a portfolio-focused module group:

| ID | Tile | Source | Cadence | Purpose |
|---|---|---|---|---|
| P1 | `$1M` Goal Tracker | existing portfolio snapshots | Daily / on portfolio refresh | Current value, distance to target, 30d/90d velocity |
| P2 | VGT Exposure | existing portfolio lots + VGT constituents config | Daily | VGT shares/value, tech exposure, overlap with direct holdings |
| P3 | Required Return | goal config + portfolio snapshots | Daily | Required monthly gain/return to hit target by selected date |
| P4 | Drawdown From High | portfolio snapshots | Daily | Current drawdown from recent portfolio high |

Recommendation for v1: implement P1 using existing portfolio market value snapshots before adding new external sources. P2 can start as "VGT holding value + separate direct tech holdings" and become full constituent-aware only if a reliable VGT holdings source is added.

The top bar should include:

- current portfolio market value
- target value
- distance to `$1M`
- 30d and 90d velocity
- required monthly gain if the user sets a target date
- regime pill and contributing rules

The tile wall should include VGT-relevant context:

- macro stress: HY OAS, VIX, real yields, dollar broad index
- AI/semi cycle: TSMC revenue, hyperscaler capex, NVDA EPS estimate delta
- top holding context: MSFT, AAPL, NVDA, AVGO, GOOGL, META sentiment/earnings where available
- geopolitical/export controls: Polymarket Taiwan, BIS/Federal Register rule counts

## Module Catalog V1

| ID | Tile | Source | Auth | Cadence | V1 Decision |
|---|---|---|---|---|---|
| M1 | HY OAS | FRED `BAMLH0A0HYM2` | `FRED_API_KEY` | Daily | Phase 1 backbone |
| M2 | 10Y Real Yield | FRED `DFII10` | `FRED_API_KEY` | Daily | Phase 2 |
| M3 | VIX | FRED `VIXCLS` | `FRED_API_KEY` | Daily | Phase 3 or earlier |
| M4 | Dollar Broad Index | FRED `DTWEXBGS` | `FRED_API_KEY` | Daily | Rename from DXY |
| E1 | News Sentiment Top 5 | Alpha Vantage `NEWS_SENTIMENT` | existing Alpha key | 15m RTH | Use holdings/watchlist symbols |
| E2 | NVDA EPS Estimate Delta | Alpha Vantage `EARNINGS_CALENDAR` + baseline | existing Alpha key | Daily | Rename from Fwd EPS Revision |
| E3 | Insider Net Flow Top 5 | Alpha Vantage `INSIDER_TRANSACTIONS` | existing Alpha key | Daily | Aggregate watchlist/holdings |
| E4 | Put/Call Skew VGT | unresolved | TBD | TBD | Skip or replace in v1 |
| S1 | TSMC Revenue YoY | TSMC IR monthly revenue | None | Daily check | Scrape with canaries |
| S2 | Hyperscaler Capex Delta | existing SEC/XBRL utilities | SEC UA | Weekly | Requires tag study |
| G1 | Polymarket Taiwan | Polymarket Gamma | None | 5m | Pin market id/slug in config |
| G2 | BIS Export Rules 90d | Federal Register API | None | Daily | Count/citation only |
| I1 | Ingest Health | internal tables | None | 60s | Derive from module state |
| P1 | `$1M` Goal Tracker | existing portfolio snapshots | None | Daily / refresh | Add early for VGT goal |
| P2 | VGT Exposure | existing portfolio lots first | None | Daily | Add after P1 |

## Source Configuration

Add to `app/core/config.py` only when a module needs it:

```python
fred_api_key: str | None = Field(default=None, alias="FRED_API_KEY")
signals_enabled: bool = Field(default=True, alias="SIGNALS_ENABLED")
signals_poll_seconds: int = Field(default=60, alias="SIGNALS_POLL_SECONDS")
```

Alpha Vantage and SEC User-Agent already exist in settings.

Store dynamic module choices, such as pinned Polymarket market IDs or watchlist tickers, in `signal_module_state.config` or a later dedicated config table. Do not hard-code user-specific market IDs in code.

## Regime Indicator

Keep the deterministic rule set, but fix the threshold conflict from the earlier doc.

Evaluation order:

1. Hard overrides:
   - Taiwan probability > 15%
   - HY OAS > 450
   - VIX > 25
   - any signal moves > 3 sigma in one day
2. Count soft breaches:
   - HY OAS >= 350
   - VIX >= 16
   - any geopolitical market > 20%, except when already handled by hard override
3. Return highest severity:
   - `CRISIS`: any crisis hard override or 3+ soft breaches
   - `STRESSED`: HY OAS/VIX hard stress override or 2 soft breaches
   - `MIXED`: 1 soft breach
   - `BENIGN`: no breaches

Tooltip should list the contributing rules and source observations.

## Phased Delivery

### Phase 0A - Architecture Correction

- Replace separate-service assumptions with native WatchTower module plan.
- Keep the static `/signals` prototype as visual scaffolding.
- Decide E4: skip, replace, or confirm source.
- Decide whether key scopes are needed immediately.

### Phase 1 - Native Backbone

- Alembic migration for Signals tables.
- SQLAlchemy models and Pydantic schemas.
- `app/routers/signals.py`.
- Read-only assistant context endpoint shape, even if it only returns M1 and placeholder goal context initially.
- Shared auth helper based on existing `api_keys`.
- M1 FRED HY OAS ingest job.
- APScheduler registration and manual run endpoint.
- SSE endpoint with DB replay.
- Frontend `/signals` wired to real M1 latest/history/stream.

Definition of done: open `/signals`, see HY OAS from real FRED data, manually trigger M1 ingest, watch a `signal_update` arrive without reloading, and confirm `/signals/assistant/context` returns the latest M1 state with source/citation fields.

### Phase 2 - Three More Patterns

- M2 Real Yield.
- E1 News Sentiment.
- G1 Polymarket Taiwan.
- Unit tests for each transform.
- Module docs for implemented modules.

### Phase 3 - Expand Module Set

- Add M3, M4, E2, E3, S1, G2, I1.
- Defer or replace E4.
- Start S2 only after the capex tag study.

### Phase 4 - Regime And Goal Tracker

- Deterministic regime indicator.
- `$1M` goal tracker from existing portfolio totals, not duplicate holdings.
- Velocity calculation using existing portfolio snapshot history where possible.
- VGT exposure summary from current portfolio lots.

### Phase 5 - Alerts

- Declarative thresholds.
- Side rail backed by `signal_alerts`.
- Dismiss/acknowledge with reason.
- Telegram/webhook only after core alert state is stable.

## Scope Gaps And Recommendations

1. Earlier doc over-scoped infrastructure.
   - Recommendation: remove Node/Fastify, pg-boss, TimescaleDB, TanStack Query, Zustand, and uPlot from v1. Use them only if a measured limitation appears.

2. Auth should reuse existing `wt_` keys.
   - Recommendation: extract `openclaw._check_token` into shared auth code. Add scopes later if needed.

3. Existing API keys do not have scopes.
   - Recommendation: for v1, use any active `wt_` key for read-only Signals and `SETTINGS_ADMIN_TOKEN` for admin operations. Add scoped keys if you want a wall-only token.

4. SSE with auth needs a fetch-stream client.
   - Recommendation: do not use native `EventSource` unless you accept query-string tokens, which we should avoid.

5. `entity` in the original primary key is flawed.
   - Recommendation: use surrogate `id` plus unique constraint with `entity NOT NULL DEFAULT ''`.

6. Duplicate holdings table is unnecessary.
   - Recommendation: use existing portfolio holdings/lots and portfolio snapshots for goal tracking.

7. E4 has no confirmed source.
   - Recommendation: skip it in v1 or replace it with a supported Alpha/FRED signal.

8. S2 capex is not a simple API call.
   - Recommendation: run a company/tag study first and reuse existing SEC/XBRL utilities.

9. FRED key is missing from current `Settings`.
   - Recommendation: add `FRED_API_KEY` only when implementing M1.

10. Deployment should stay simple.
    - Recommendation: deploy with the existing API/frontend until SSE load or job runtime justifies splitting services.

11. Assistant needs curated context, not unrestricted database access.
    - Recommendation: add `signals_assistant.py` or assistant-specific service functions that return compact, citation-bearing summaries.

12. The original catalog is macro/geopolitical heavy for a VGT goal.
    - Recommendation: add the P1/P2 portfolio goal modules early and prioritize VGT-relevant holdings over broad generic signals.

13. VGT constituent-level exposure needs a data source.
    - Recommendation: start with existing portfolio lots and user-held VGT value; add full VGT constituent look-through only after selecting a reliable holdings source.

14. "Reach `$1M` as soon as possible" can create unsafe recommendation pressure.
    - Recommendation: keep the product language focused on velocity, drawdown, required return, concentration, and risk signals. Do not make automated trading recommendations.

## Approval Checklist

- [ ] Native WatchTower module approach accepted.
- [ ] No separate Node service in v1 accepted.
- [ ] No TimescaleDB in v1 accepted.
- [ ] Existing `wt_` auth reuse accepted.
- [ ] E4 skip/replace decision made.
- [ ] Static `/signals` prototype accepted as visual scaffolding.
- [ ] Phase 1 M1-only backbone accepted.
- [ ] Assistant read-only context model accepted.
- [ ] `$1M` goal tracker and VGT exposure modules accepted.
