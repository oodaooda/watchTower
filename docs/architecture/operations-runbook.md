# watchTower Operations Runbook

This guide defines the canonical way to run, migrate, and troubleshoot watchTower.

Architecture philosophy and service-boundary decisions are in `system-overview.md`.

## Canonical Development Setup (Docker + Vite)

### 1) Start the database

```bash
docker compose -f docker/docker-compose.yml up -d db
```

### 2) Start the API (auto-reload)

```bash
docker compose -f docker/docker-compose.yml up -d api
```

### 3) Start the UI

```bash
cd ui
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## Environment Configuration

### API

- Docker DB (canonical): `DATABASE_URL=postgresql+pg8000://postgres:postgres@db:5432/watchtower`
- QA read-only DB (recommended): `QA_DATABASE_URL=postgresql+pg8000://watchtower_readonly:watchtower_readonly@db:5432/watchtower`
- SQL QA controls: `QA_SQL_ENABLED=true`, `QA_SQL_ROW_LIMIT=100`, `QA_SQL_TIMEOUT_MS=3000`
- Alpha Vantage: `ALPHA_VANTAGE_API_KEY=...`
- OpenAI modeling: `MODELING_OPENAI_API_KEY=...`

### UI

- `VITE_API_BASE=http://10.0.0.2:8000` or your API host

## Migrations

### Run migrations (host)

```bash
conda activate watchTower
export DATABASE_URL=postgresql+pg8000://postgres:postgres@127.0.0.1:5432/watchtower
alembic upgrade head
```

### Run migrations (inside API container)

```bash
docker compose -f docker/docker-compose.yml exec api alembic upgrade head
```

## Common Troubleshooting

### API starts but no data

Check DB connection:

```bash
docker exec -it docker_db_1 psql -U postgres -d watchtower -c "select count(*) from companies;"
```

### API crash: "host db not found"

The compose DB container is not running. Start it:

```bash
docker compose -f docker/docker-compose.yml up -d db
```

### Vite not reachable on LAN

Ensure:

- `npm run dev -- --host 0.0.0.0 --port 5173`
- Firewall allows inbound `5173`

## Canonical DB Choice

Use the compose DB (`db`) as the canonical development database. Avoid mixing it with separate host-run Postgres containers.

### QA Read-Only User (Postgres Hard Guardrail)

Create a dedicated read-only role for LLM-driven QA and NL-to-SQL:

```bash
docker compose -f docker/docker-compose.yml exec -T db psql -U postgres -d watchtower <<'SQL'
CREATE ROLE watchtower_readonly LOGIN PASSWORD 'watchtower_readonly';
GRANT CONNECT ON DATABASE watchtower TO watchtower_readonly;
GRANT USAGE ON SCHEMA public TO watchtower_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO watchtower_readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT SELECT ON TABLES TO watchtower_readonly;
SQL
```

Validation:

```bash
docker compose -f docker/docker-compose.yml exec -T db psql -U watchtower_readonly -d watchtower -c "SELECT count(*) FROM companies;"
docker compose -f docker/docker-compose.yml exec -T db psql -U watchtower_readonly -d watchtower -c "UPDATE companies SET name=name WHERE 1=0;"
```

## Data Assistant (QA)

Test the QA endpoint:

```bash
curl -X POST http://localhost:8000/qa -H 'Content-Type: application/json' -d '{"question":"What is the P/E of AAPL?"}'
```

## OpenClaw Integration

Set env vars:

```bash
OPENCLAW_API_TOKEN=your_token
OPENCLAW_ALLOWED_IPS=1.2.3.4,5.6.7.8
OPENCLAW_RATE_LIMIT=60
```

Example request:

```bash
curl -X POST http://localhost:8000/openclaw/qa \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer your_token' \
  -d '{"question":"What is the P/E of AAPL?"}'
```

## Settings UI (OpenClaw Keys)

1. Generate a strong token locally, for example: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
2. Set `SETTINGS_ADMIN_TOKEN` in `.env`
3. Restart the API
4. Visit `/settings` and paste the admin token
5. Generate OpenClaw keys and set max active keys

## Secret Handling

- Never paste live secrets into shared chat, tickets, screenshots, or screen recordings.
- Do not commit `.env`; keep `.env.example` placeholder-only.
- If you inspect `.env` or logs while debugging, summarize key names and redact values.
- If a secret appears in plaintext in terminal output, browser UI, agent output, or screenshots, rotate it.
- The Settings UI should display generated keys once only and should not redisplay the saved admin token after entry.
- For local debugging with coding agents, explicitly ask for redaction-first handling when secrets may appear.

Suggested prompt for agent-assisted debugging:

```text
Do not print, quote, or echo secrets from .env, logs, screenshots, request headers, or browser storage.
If you inspect sensitive config, summarize key names only and redact values.
For auth/settings work, default to masked inputs, write-only secret handling, show-once generated credentials, and no secret logging.
```

## Testing

```bash
pytest
```

Core unit tests live in `tests/unit`.

## Git LFS

Large assets such as `watchtower.sql` are tracked with Git LFS.

```bash
git lfs install
git lfs pull
```
