"""
FastAPI v1 router aggregator.

All versioned sub-routers (auth, curriculum, progress, ai) will be
included here and mounted under ``/api/v1`` in ``main.py``.
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.curriculum import router as curriculum_router

v1_router = APIRouter(prefix="/api/v1")

# ── Sub-routers ──────────────────────────────────────────────────────────
v1_router.include_router(auth_router)
v1_router.include_router(curriculum_router)

# from app.api.v1.progress   import router as progress_router
# from app.api.v1.ai         import router as ai_router
#
# v1_router.include_router(progress_router)
# v1_router.include_router(ai_router)
