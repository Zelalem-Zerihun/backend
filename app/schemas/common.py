"""
Shared / cross-cutting response schemas.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ── Generic Responses ────────────────────────────────────────────────────


class MessageResponse(BaseModel):
    """Simple message envelope returned by mutation endpoints."""

    message: str


class DetailResponse(BaseModel):
    """Error detail envelope (mirrors FastAPI's ``HTTPException`` body)."""

    detail: str


# ── Paywall ──────────────────────────────────────────────────────────────


class PaywallResponse(BaseModel):
    """
    Standardized 403 body returned when a non-subscriber tries to
    access premium content.
    """

    detail: str = "Active subscription required to access this content."
    upgrade_url: str = "/pricing"
    is_free_preview: bool = False


# ── Rate Limit ───────────────────────────────────────────────────────────


class RateLimitResponse(BaseModel):
    """429 body returned when the daily AI quota is exceeded."""

    detail: str = "Daily AI query limit exceeded."
    daily_limit: int
    queries_used: int
