"""
FastAPI v1 router aggregator.

All versioned sub-routers (auth, curriculum, progress, ai, admin) will be
included here and mounted under ``/api/v1`` in ``main.py``.
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.curriculum import router as curriculum_router
from app.api.v1.progress import router as progress_router
from app.api.v1.ai import router as ai_router
from app.api.v1.admin.cms import router as admin_cms_router
from app.api.v1.admin.analytics import router as admin_analytics_router

v1_router = APIRouter(prefix="/api/v1")

# ── Core sub-routers ─────────────────────────────────────────────────────
v1_router.include_router(auth_router)
v1_router.include_router(curriculum_router)
v1_router.include_router(progress_router)
v1_router.include_router(ai_router)

# ── Admin sub-routers ────────────────────────────────────────────────────
# All admin endpoints live under /api/v1/admin/...
_admin_router = APIRouter(prefix="/admin")
_admin_router.include_router(admin_cms_router, prefix="/cms")
_admin_router.include_router(admin_analytics_router, prefix="/analytics")

v1_router.include_router(_admin_router)
