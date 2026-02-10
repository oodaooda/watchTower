# watchTower Operations Guide

This guide defines the canonical way to run, migrate, and troubleshoot watchTower.

## Canonical Development Setup (Docker + Vite)

### 1) Start the database
```
docker-compose -f docker/docker-compose.yml up -d db
```

### 2) Start the API (auto‑reload)
```
docker-compose -f docker/docker-compose.yml up -d api
```

### 3) Start the UI
```
cd ui
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## Environment Configuration

### API
- Docker DB (canonical): `DATABASE_URL=postgresql+pg8000://postgres:postgres@db:5432/watchtower`
- Alpha Vantage: `ALPHA_VANTAGE_API_KEY=...`
- OpenAI (Modeling): `MODELING_OPENAI_API_KEY=...`

### UI
- `VITE_API_BASE=http://10.0.0.2:8000` (or your API host)

## Migrations

### Run migrations (host)
```
conda activate watchTower
export DATABASE_URL=postgresql+pg8000://postgres:postgres@127.0.0.1:5432/watchtower
alembic upgrade head
```

### Run migrations (inside API container)
```
docker-compose -f docker/docker-compose.yml exec api alembic upgrade head
```

## Common Troubleshooting

### API starts but no data
Check DB connection:
```
docker exec -it docker_db_1 psql -U postgres -d watchtower -c "select count(*) from companies;"
```

### API crash: “host db not found”
The compose DB container isn’t running. Start it:
```
docker-compose -f docker/docker-compose.yml up -d db
```

### Vite not reachable on LAN
Ensure:
- `npm run dev -- --host 0.0.0.0 --port 5173`
- Firewall allows inbound 5173

## Canonical DB Choice

Use the compose DB (`docker_db_1`) as the canonical development database. Avoid mixing it with separate host‑run Postgres containers.

## Data Assistant (QA)

Test the QA endpoint:
```
curl -X POST http://localhost:8000/qa -H 'Content-Type: application/json' -d '{"question":"What is the P/E of AAPL?"}'
```

## OpenClaw Integration

Set env vars:
```
OPENCLAW_API_TOKEN=your_token
OPENCLAW_ALLOWED_IPS=1.2.3.4,5.6.7.8
OPENCLAW_RATE_LIMIT=60
```

Example request:
```
curl -X POST http://localhost:8000/openclaw/qa \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer your_token' \
  -d '{"question":"What is the P/E of AAPL?"}'
```

## Settings UI (OpenClaw Keys)

1) Set `SETTINGS_ADMIN_TOKEN` in `.env`
2) Restart API
3) Visit `/settings` and paste the admin token
4) Generate OpenClaw keys and set max active keys

## Testing

```
pytest
```

Core unit tests live in `tests/unit`.

## Git LFS (Large Files)

Large assets (e.g., `watchtower.sql`) are tracked via Git LFS. After cloning:

```
git lfs install
git lfs pull
```
