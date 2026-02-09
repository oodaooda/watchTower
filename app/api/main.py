from fastapi import FastAPI
from fastapi import APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
import time
import logging

from app.routers import companies, screen, financials, metrics, definitions, health, valuation, industries, prices, pharma, universe, favorites, modeling
from app.jobs.scheduler import start_scheduler, nightly_fundamentals_job, daily_prices_job, dev_router

from app.core.config import settings

app = FastAPI(
    title="watchTower API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

logging.basicConfig(level=getattr(logging, (settings.log_level or "INFO").upper(), logging.INFO))
log = logging.getLogger("watchtower.api")

# --- CORS (read from env; defaults to * for dev) ---
origins = [o.strip() for o in (getattr(settings, "cors_origins", "*") or "").split(",")]
if origins == ["*"] or origins == [""]:
    allow_origins = ["*"]
else:
    allow_origins = origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],  # dev-friendly
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logger(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid4()))
    start = time.time()
    try:
        response = await call_next(request)
    except Exception:
        duration = (time.time() - start) * 1000
        log.exception("request_failed", extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "duration_ms": round(duration, 2),
        })
        raise
    duration = (time.time() - start) * 1000
    response.headers["x-request-id"] = request_id
    log.info("request", extra={
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_ms": round(duration, 2),
    })
    return response

# --- Routers ---
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(companies.router)
app.include_router(screen.router)
#app.include_router(screen.router, prefix="/screen", tags="screen")
app.include_router(financials.router, prefix="/financials", tags=["financials"])
app.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
app.include_router(definitions.router, prefix="/definitions", tags=["definitions"])
app.include_router(valuation.router)
app.include_router(industries.router)
app.include_router(prices.router)
app.include_router(pharma.router)
app.include_router(universe.router)
app.include_router(favorites.router)
app.include_router(modeling.router)
app.include_router(dev_router)

# --- Versioned API (v1) ---
v1 = APIRouter(prefix="/api/v1")
v1.include_router(health.router, prefix="/health", tags=["health"])
v1.include_router(companies.router)
v1.include_router(screen.router)
v1.include_router(financials.router, prefix="/financials", tags=["financials"])
v1.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
v1.include_router(definitions.router, prefix="/definitions", tags=["definitions"])
v1.include_router(valuation.router)
v1.include_router(industries.router)
v1.include_router(prices.router)
v1.include_router(pharma.router)
v1.include_router(universe.router)
v1.include_router(favorites.router)
v1.include_router(modeling.router)
app.include_router(v1)


@app.get("/")
def root():
    return {
        "name": "watchTower",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


# --- Scheduler ---
_sched = None

@app.on_event("startup")
def _start_jobs():
    global _sched
    if _sched is None:
        c = start_scheduler("America/New_York")  # sets the global SCHED inside scheduler.py

@app.on_event("shutdown")
def _stop_jobs():
    global _sched
    if _sched:
        _sched.shutdown(wait=False)
        _sched = None

debug = APIRouter()

@debug.get("/_jobs")
def list_jobs():
    return [str(j) for j in (_sched.get_jobs() if _sched else [])]

app.include_router(debug)


@debug.post("/_run/nightly")
def run_nightly():
    return nightly_fundamentals_job()

@debug.post("/_run/prices")
def run_prices():
    return ()
