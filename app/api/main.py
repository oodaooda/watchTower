from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import companies, screen, financials, metrics, definitions, health
from app.routers import screen

from app.core.config import settings
from app.jobs.scheduler import start_scheduler
from app.routers import valuation

app = FastAPI(
    title="watchTower API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

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

# --- Routers ---
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(companies.router, prefix="/companies", tags=["companies"])
app.include_router(screen.router)
#app.include_router(screen.router, prefix="/screen", tags="screen")
app.include_router(financials.router, prefix="/financials", tags=["financials"])
app.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
app.include_router(definitions.router, prefix="/definitions", tags=["definitions"])
app.include_router(valuation.router)


@app.get("/")
def root():
    return {
        "name": "watchTower",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


# --- Scheduler ---
_scheduler = None

@app.on_event("startup")
def _on_startup():
    global _scheduler
    try:
        _scheduler = start_scheduler(settings.timezone)
    except Exception as e:
        # In dev, don't crash the app if scheduler fails to start
        print(f"[watchTower] Scheduler start failed: {e}")


@app.on_event("shutdown")
def _on_shutdown():
    global _scheduler
    try:
        if _scheduler:
            _scheduler.shutdown(wait=False)
    except Exception:
        pass
