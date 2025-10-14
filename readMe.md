# boot system:
watchtower:
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload

watchtower/ui:
npm run dev

database:
docker start wt-pg
docker ps -a

# SSH Binding:
 ssh -L 5173:localhost:5173 -L 8000:localhost:8000 ares@10.0.0.9 -p 1634


# Start up and intial setup

create database
create tables: python -m ops.create_tables

# Add see file instructions here (Contains list of all stocks tickers/cik)

# For testing
python -m ops.run_backfill --limit 50docker exec -it wt-pg psql -U postgres -d watchtower -c \
"UPDATE companies SET is_tracked = TRUE WHERE ticker IN ('AAPL','MSFT','NVDA','GOOGL','AMZN');"


# Backfill fundimentals 
PYTHONPATH=. python -m ops.run_backfill 

# Recompute Metrics
python -m ops.recompute_metrics 

# Back fill prices
python -m ops.backfill_prices_alpha_vantage --sleep 1

# Populate industry_name
PYTHONPATH=. python -m ops.backfill_industries --force --only-tracked --sleep .5

# Start Website / Server (Code Here)

# Modify database example: 
docker exec -it wt-pg psql -U postgres -d watchtower -c "
SELECT ticker, sic, industry_name
FROM companies
ORDER BY ticker
LIMIT 20;"

# watchTower

Fundamental analytics backend that ingests **SEC EDGAR** (Inline XBRL) annual fundamentals (up to \~20 years), rolls **prices** to fiscal years, computes value-oriented metrics (P/E, Cash/Debt, Growth Consistency, Piotroski F, Altman Z, CAGR, margins, FCF, leverage), and serves them via a **FastAPI** for a screening UI.

---

## Table of contents

* [What it does](#what-it-does)
* [Scope / Universe](#scope--universe)
* [Architecture](#architecture)
* [Directory Layout](#directory-layout)
* [Dependencies (`requirements.txt`)](#dependencies-requirementstxt)
* [Environment (`.env.example`)](#environment-envexample)
* [Setup](#setup)
* [Data Model (tables)](#data-model-tables)
* [ETL Overview](#etl-overview)
* [Company Selection Rules](#company-selection-rules)
* [API Endpoints](#api-endpoints)
* [Glossary Seeds](#glossary-seeds)
* [Toggles & Roadmap](#toggles--roadmap)
* [Notes](#notes)
* [License](#license)

---

## What it does

* **Sources**

  * **EDGAR `companyfacts`** (US-GAAP, USD) → annual fundamentals
  * **Daily prices** (e.g., Alpha Vantage) → rolled to **fiscal-year** close/average
* **Stores**

  * `companies`, `financials_annual`, `prices_annual`, `metrics_annual`, `definitions`, `fact_provenance`
* **Computes**

  * P/E (TTM/FY), YoY, 5y/10y CAGR, margins, FCF, Debt/EBITDA, Interest coverage
  * Cash/Debt, Piotroski F, Altman Z, Growth Consistency
* **APIs**

  * `/screen`, `/companies`, `/financials/{company_id}`, `/metrics/{company_id}`, `/definitions`

---

## Scope / Universe

* **Include:** EDGAR filers with Inline XBRL (**US-GAAP**, **USD**), common stock (REITs/banks optional).
* **Exclude (v1):** Non-EDGAR OTC, IFRS filers, funds/ETFs/SPAC shells (unless you toggle them on).

---

## Architecture

```
+-------------+        +--------------------+        +------------------+
|  Schedulers |  --->  |  ETL (SEC, Prices) |  --->  | PostgreSQL        |
|  (APScheduler)       |  - companyfacts     |        |  companies        |
|                     |  - price rollups     |        |  financials_annual|
+-------------+        +--------------------+        |  prices_annual   |
                                                     |  metrics_annual  |
                                                     |  definitions     |
                                                     |  fact_provenance |
                                                     +---------+--------+
                                                               |
                                                 +-------------v------------+
                                                 |       FastAPI            |
                                                 | /screen /companies ...   |
                                                 +-------------+------------+
                                                               |
                                                      Frontend / Clients
```

---

## Directory Layout

```
watchTower/
├─ README.md
├─ requirements.txt
├─ .env.example
├─ docker/
│  ├─ api.Dockerfile
│  └─ docker-compose.yml
├─ app/
│  ├─ api/
│  │  ├─ main.py
│  │  └─ routers/
│  │     ├─ health.py
│  │     ├─ companies.py
│  │     ├─ screen.py
│  │     ├─ financials.py
│  │     ├─ metrics.py
│  │     └─ definitions.py
│  ├─ core/
│  │  ├─ config.py
│  │  ├─ db.py
│  │  ├─ models.py
│  │  ├─ schemas.py
│  │  └─ tagmap_xbrl.py
│  ├─ etl/
│  │  ├─ sec_fetch_companyfacts.py
│  │  ├─ alpha_fetch_prices.py
│  │  └─ transform_compute_metrics.py
│  └─ jobs/
│     └─ scheduler.py
└─ ops/
   ├─ create_tables.py
   ├─ seed_companies.py
   ├─ seed_definitions.py
   ├─ run_backfill.py
   ├─ recompute_metrics.py
   └─ rebuild_materialized_views.py
```

app/
  api/
    main.py                      # FastAPI entry (mounted routers)
  core/
    db.py, models.py, schemas.py # SQLAlchemy + Pydantic
    valuation_engine.py          # DCF helpers (optional)
  etl/
    sec_fetch_companyfacts.py    # Pulls SEC facts
    transform_compute_metrics.py # Build metrics rows
  routers/
    companies.py, financials.py, metrics.py
    screen.py                    # /screen endpoint
    valuation.py                 # /valuation/dcf, /valuation/summary
  valuation/
    dcf.py                       # two-stage DCF (pure function)
docker/
  api.Dockerfile, docker-compose.yml
ops/
  create_tables.py
  run_backfill.py                # SEC backfill -> financials_annual
  backfill_prices_alpha_vantage.py
  recompute_metrics.py           # compute metrics -> metrics_annual
ui/
  src/
    components/{FilterBar,ResultsTable,ThemeToggle,ValuationModal}.tsx
    lib/{api.ts,types.ts}

---

## Dependencies (`requirements.txt`)

```txt
fastapi==0.115.0
uvicorn[standard]==0.30.6
pydantic==2.9.2
pydantic-settings==2.4.0
SQLAlchemy==2.0.35
psycopg2-binary==2.9.9
httpx==0.27.2
requests==2.32.3
python-dateutil==2.9.0.post0
pandas==2.2.2
apscheduler==3.10.4
```

---

## Environment (`.env.example`)

```env
# Database
DATABASE_URL=postgresql+psycopg2://postgres:postgres@db:5432/watchtower

# External services
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key_here
SEC_USER_AGENT=watchTower/0.1 (your-email@example.com)

# Scheduler / TZ
TIMEZONE=America/New_York

# Universe toggles
INCLUDE_BANKS=false
INCLUDE_REITS=false
INCLUDE_OTC_SEC_REPORTERS=true
ALLOW_IFRS=false
```

---

## Setup

### Local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env  # edit values
python -m ops.create_tables
python -m ops.seed_companies
python -m ops.seed_definitions

uvicorn app.api.main:app --reload --port 8000
# Open http://localhost:8000/docs
```

### Docker

```bash
cp .env.example .env  # edit values
cd docker
docker compose up --build
# API -> http://localhost:8000/docs
```

---

## Data Model (tables)

### `companies`

* `id (PK)`, `ticker`, `name`, `cik`, `sic`, `industry_name`
* `exchange`, `status`, `delisted_on`, `currency`, `fiscal_year_end_month`
* `is_tracked` (bool), `track_reason` (`rules|watchlist|on_demand`), `tracked_since`

### `financials_annual`

* `company_id (FK)`, `fiscal_year`, `fiscal_period=FY`, `report_date`
* `revenue`, `net_income`, `cash_and_sti`, `total_debt`, `shares_diluted`
* `source` (`sec|fmp|otc_alt`), `xbrl_confidence`
* **Unique:** `(company_id, fiscal_year, source)`

### `prices_annual`

* `company_id (FK)`, `fiscal_year`
* `close_price`, `avg_price`, `market_cap`, `pe_ttm`

### `metrics_annual`

* `company_id (FK)`, `fiscal_year`
* `fcf`, `gross_margin`, `op_margin`, `roe`, `roic`, `debt_ebitda`, `interest_coverage`
* `rev_yoy`, `ni_yoy`, `rev_cagr_5y`, `ni_cagr_5y`, `growth_consistency`, `cash_debt_ratio`
* `piotroski_f`, `altman_z`, `ttm_eps`, `data_quality_score`, `has_ttm`

### `definitions`

* `key` (e.g., `piotroski_f`), `title`, `body_md` (Markdown)

### `fact_provenance`

* `financial_id (FK)`, `xbrl_tag`, `unit`, `accession` (audit trail)

---

## ETL Overview

1. **Seed companies (one-time)**
   Load SEC `company_tickers.json` → `companies`.
2. **Select universe (deterministic)**
   EDGAR + US-GAAP + USD + common stock; optional watchlist/on-demand add.
3. **Fundamentals (nightly)**
   `companyfacts` → extract **annual USD** for: Revenue, Net Income, Cash+STI, Debt (ST+LT), Shares (diluted).
   Normalize units, align to FY, choose best tag per concept, write to `financials_annual` + `fact_provenance`.
4. **Prices (daily)**
   Daily adjusted close → roll to FY close/avg → `prices_annual`.
5. **Metrics**
   Compute YoY, 5y/10y CAGR, margins, FCF, Cash/Debt, Debt/EBITDA, coverage, P/E (TTM/FY), Piotroski F, Altman Z → `metrics_annual`.

---

## Company Selection Rules

A company is **tracked** iff:

1. EDGAR filer with `companyfacts` in **US-GAAP** and **USD**
2. **Operating company** (not fund/ETF/SPAC)
3. **Common stock** security type
4. Optional: include/exclude **banks/insurers** and **REITs** via toggles
   Plus:

* **Watchlist** → always tracked
* **On-demand** → tracked when first requested

---

## API Endpoints

### `GET /health`

* Returns `{ ok: true, db: true|false }`

### `GET /companies`

Query:

```
/companies?q=AMD&industry=Semiconductors&limit=50&offset=0
```

Response (array):

```json
[
  {"id":1,"ticker":"AMD","name":"Advanced Micro Devices","cik":2488,"industry_name":"Semiconductors"}
]
```

### `GET /screen`

Query params (all optional):

* `pe_max`, `cash_debt_min`, `growth_consistency_min`
* `rev_cagr_min`, `ni_cagr_min`
* `industry`, `year`, `limit`, `offset`

Example:

```
/screen?pe_max=12&cash_debt_min=1.0&growth_consistency_min=7&industry=Semiconductors
```

Response (array):

```json
[
  {
    "company_id": 123,
    "ticker": "TXN",
    "name": "Texas Instruments",
    "pe_ttm": 11.8,
    "cash_debt_ratio": 1.25,
    "growth_consistency": 8,
    "rev_cagr_5y": 0.05,
    "ni_cagr_5y": 0.06
  }
]
```

### `GET /financials/{company_id}`

Annual raw items:

```json
[
  {"fiscal_year": 2018, "revenue": 10000000000.0, "net_income": 1200000000.0,
   "cash_and_sti": 2500000000.0, "total_debt": 1000000000.0, "shares_diluted": 980000000.0}
]
```

### `GET /metrics/{company_id}`

Derived metrics (joined with P/E from `prices_annual`):

```json
[
  {"fiscal_year": 2018, "pe_ttm": 11.2, "cash_debt_ratio": 2.5, "growth_consistency": 8,
   "rev_cagr_5y": 0.07, "ni_cagr_5y": 0.08, "piotroski_f": 7, "altman_z": 3.1}
]
```

### `GET /definitions` and `/definitions/{key}`

Returns Markdown bodies you can render on the frontend.

---

## Glossary Seeds

* **Piotroski F-Score** — 9 binary tests over profitability, leverage/liquidity, efficiency (0–9).
* **Altman Z-Score** — distress score; public manufacturing formula `Z = 1.2X1 + 1.4X2 + 3.3X3 + 0.6X4 + 1.0X5`.
* **ROIC** — after-tax operating profit / invested capital.
* **FCF** — CFO − CapEx.
* **CAGR** — `((End/Start)^(1/n)) − 1`.
* **Debt/EBITDA** — leverage proxy.
* **Interest Coverage** — EBIT / Interest Expense.
* **TTM EPS** — trailing twelve months earnings / diluted shares.

*(Store these as Markdown in `definitions`.)*

---

## Toggles & Roadmap

* **Toggles:** `INCLUDE_BANKS`, `INCLUDE_REITS`, `INCLUDE_OTC_SEC_REPORTERS`, `ALLOW_IFRS`
* **Nice-to-haves:**

  * TTM rollups from quarterly facts
  * Dividend & buyback yield
  * Industry-relative percentiles
  * Anomaly flags (unit flips, big restatements)
  * Materialized view for faster screens
  * On-demand ingest endpoint (`POST /ingest?ticker=...`)

---

## Notes

* Ingestion is **deterministic** (no AI in ETL).
* Optional natural-language **/nl-screen** helper can translate phrases to `/screen` params but is not required.
* **Provenance** is recorded for each fact (tag, unit, accession).
* Treat **banks/insurers** and **REITs** with specialized metrics if enabled.

---

"""Refresh materialized views (placeholder).

If you choose to create Postgres materialized views (e.g., for faster screens
or latest-year snapshots), put their refresh logic here.

Example views you might add later:
- `mv_latest_metrics` — latest fiscal-year metrics per company
- `mv_screen_grid`   — denormalized join for the screener results grid

Usage
-----
$ python -m ops.rebuild_materialized_views
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal


VIEWS = [
    # ("mv_latest_metrics", "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_latest_metrics"),
    # ("mv_screen_grid", "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_screen_grid"),
]


def main() -> None:
    db: Session = SessionLocal()
    try:
        for name, sql in VIEWS:
            print(f"[watchTower] Refreshing {name}...")
            db.execute(text(sql))
        db.commit()
        print("[watchTower] Materialized views refreshed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

## Troubleshooting

### Host↔Docker routing issue (iptables/UFW)
If you can connect **inside** the Postgres container (e.g., `docker exec -it wt-pg psql -h 127.0.0.1 ...`) but connections from the host to `127.0.0.1:5432` or `172.x.x.x:5432` fail or reset, it may be a host↔Docker bridge routing/forwarding issue.

**What we ran to diagnose and temporarily allow traffic**
```bash
# Inspect current rules
sudo iptables -L DOCKER-USER -n -v --line-numbers
sudo iptables -L FORWARD -n -v --line-numbers

# Allow traffic in/out of docker0 (insert at top)
sudo iptables -I DOCKER-USER 1 -i docker0 -j ACCEPT
sudo iptables -I DOCKER-USER 1 -o docker0 -j ACCEPT

# Also ensure FORWARD isn’t dropping docker0 traffic
sudo iptables -I FORWARD 1 -i docker0 -j ACCEPT
sudo iptables -I FORWARD 1 -o docker0 -j ACCEPT

# Verify rules are there now
sudo iptables -S DOCKER-USER
sudo iptables -S FORWARD
```

**Related checks**
```bash
# docker bridge IP and route
ip addr show docker0
ip route | grep 172.17.0.0

# Restart Docker if docker0 lacks an IP/route
sudo systemctl restart docker
```
> Note: iptables edits like the above are not persistent across reboots unless saved/applied via your firewall tool (e.g., UFW) or a system script.



## License

MIT (or your preferred license).


Todo List: 

Suggested Implementation Order

x Company Header (super quick, just fetch from /companies).

x Negative Values in Red (CSS tweak).

x Net Income Formatting (CSS tweak).

Quarterly/Yearly Toggle (small backend + frontend changes).

Expanded Income Statement Items (extend PREFERRED_TAGS, DB schema, ETL).

Subtotals & Derived Values (compute at transform layer, return in API).


Company Header (Simple)

Show:

x Company Name

x Ticker Symbol

x Company Description (from SEC company_tickers.json or an added field in your DB).

x Negative Values in Red (Simple)

x Apply a conditional CSS class for <td> values < 0.

Example: className={value < 0 ? "text-red-500" : ""}

Net Income Formatting (Subtotal style)

Bold and maybe a top/bottom border (like financial statements).

Example: font-bold border-t-2 border-zinc-400.

Expanded Income Statement Line Items

Add more from EDGAR (via PREFERRED_TAGS):

Cost of Revenue (COGS)

R&D Expense

SG&A Expense

Interest Expense

Income Tax Expense

Quarterly / Yearly Toggle

Add a UI toggle: “Annual” | “Quarterly”.

Annual: show up to 20 years.

Quarterly: show 8 quarters (2 years).

Backend: update /company/{id}/financials?period=annual|quarterly.

Frontend: switch table rendering based on period.

Subtotals and Derived Values

Expenses (Revenue – Net Income).

Margins (Operating Margin %, Net Margin %).

Derived Free Cash Flow (already done).

Suggested Implementation Order

Company Header (super quick, just fetch from /companies).

Negative Values in Red (CSS tweak).

Net Income Formatting (CSS tweak).

Quarterly/Yearly Toggle (small backend + frontend changes).

Expanded Income Statement Items (extend PREFERRED_TAGS, DB schema, ETL).

Subtotals & Derived Values (compute at transform layer, return in API).
