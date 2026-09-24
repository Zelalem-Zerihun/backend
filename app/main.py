"""
AccOS E-Learning API – FastAPI application entry point.

Run locally with::

    uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.router import v1_router


# ── Lifespan (startup / shutdown) ────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    * **startup**: verify the database engine can connect (fail-fast).
    * **shutdown**: dispose of the connection pool cleanly.
    """
    from app.core.database import engine

    # Startup: lightweight connectivity check
    async with engine.begin() as conn:
        await conn.execute(
            __import__("sqlalchemy").text("SELECT 1")
        )

    yield

    # Shutdown: release all pooled connections
    await engine.dispose()


# ── Application Factory ──────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ── CORS Middleware ──────────────────────────────────────────────────────
# In production, replace the wildcard with your frontend origin(s).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Mount Versioned Router ───────────────────────────────────────────────
app.include_router(v1_router)


# ── Root Health Check ────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root() -> dict[str, str]:
    """Minimal health-check / liveness probe."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
