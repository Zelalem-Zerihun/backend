"""
Gemini AI Study Assistant router.

Endpoints
~~~~~~~~~
* ``POST /ai/ask``     – submit a question to the AI study assistant
* ``GET  /ai/quota``   – check remaining daily quota

Both endpoints require authentication.  The ``/ask`` endpoint
additionally enforces the daily rate limit defined in
``settings.AI_DAILY_QUOTA`` (default: 50 requests/day per user).
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.database import get_async_session
from app.models.ai import AIRateLimit
from app.schemas.ai import AIQueryRequest, AIQueryResponse, AIQuotaResponse
from app.services.ai import ask_study_assistant

router = APIRouter(prefix="/ai", tags=["AI Study Assistant"])


# ── POST /ai/ask ─────────────────────────────────────────────────────────
@router.post(
    "/ask",
    response_model=AIQueryResponse,
    summary="Ask the AI study assistant a question",
    responses={
        429: {
            "description": "Daily AI query limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": (
                            "Daily AI query limit reached "
                            "(50 queries/day).  Please try again tomorrow."
                        )
                    }
                }
            },
        },
    },
)
async def ask_ai(
    payload: AIQueryRequest,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> AIQueryResponse:
    """
    Submit a question to the Gemini-powered study assistant.

    The AI's answer is **grounded** in the topic's course material
    (``notebooklm_raw_notes``), keeping responses on-curriculum.

    **Rate limiting**: each user is allowed ``AI_DAILY_QUOTA`` queries
    per calendar day.  The response includes ``queries_used_today`` and
    ``daily_limit`` so the frontend can display remaining quota.
    """
    return await ask_study_assistant(current_user.id, payload, session)


# ── GET /ai/quota ────────────────────────────────────────────────────────
@router.get(
    "/quota",
    response_model=AIQuotaResponse,
    summary="Check remaining AI query quota for today",
)
async def check_quota(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> AIQuotaResponse:
    """
    Return how many AI queries the authenticated user has used today
    and how many remain.
    """
    today = date.today()

    stmt = select(AIRateLimit).where(
        AIRateLimit.user_id == current_user.id,
        AIRateLimit.query_date == today,
    )
    result = await session.execute(stmt)
    rate_row = result.scalar_one_or_none()

    used = rate_row.query_count if rate_row else 0

    return AIQuotaResponse(
        queries_used_today=used,
        daily_limit=settings.AI_DAILY_QUOTA,
        remaining=max(settings.AI_DAILY_QUOTA - used, 0),
    )
