"""
User progress tracking endpoints.

All endpoints are scoped to the authenticated user – a student can only
read or modify their **own** progress records.

Endpoints
~~~~~~~~~
* ``GET  /progress``               – all progress records (most-recent first)
* ``GET  /progress/topics/{id}``   – single topic progress
* ``PUT  /progress``               – upsert: record visit / mark complete
* ``GET  /progress/summary``       – per-module completion summaries
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.database import get_async_session
from app.schemas.progress import (
    ModuleProgressSummary,
    ProgressRead,
    ProgressUpdate,
)
from app.services.progress import (
    get_module_progress_summaries,
    get_topic_progress,
    list_user_progress,
    upsert_progress,
)

router = APIRouter(prefix="/progress", tags=["Progress"])


# ── GET /progress ────────────────────────────────────────────────────────
@router.get(
    "",
    response_model=list[ProgressRead],
    summary="List all progress records for the current user",
)
async def list_progress(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[ProgressRead]:
    """
    Return every progress record for the authenticated user, ordered
    by ``last_visited_at`` descending (most recently visited first).
    """
    return await list_user_progress(current_user.id, session)


# ── GET /progress/summary ───────────────────────────────────────────────
@router.get(
    "/summary",
    response_model=list[ModuleProgressSummary],
    summary="Per-module progress summaries",
)
async def module_summaries(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[ModuleProgressSummary]:
    """
    Return aggregated completion stats for each published module.

    Each entry includes ``total_topics``, ``completed_topics``, and a
    ``completion_percent`` value that the frontend can use to render
    per-module progress bars.
    """
    return await get_module_progress_summaries(current_user.id, session)


# ── GET /progress/topics/{topic_id} ─────────────────────────────────────
@router.get(
    "/topics/{topic_id}",
    response_model=ProgressRead,
    summary="Get progress for a specific topic",
)
async def read_topic_progress(
    topic_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ProgressRead:
    """
    Return the progress record for a single topic.

    Returns ``404`` if the authenticated user has no progress record
    for the given topic.
    """
    return await get_topic_progress(current_user.id, topic_id, session)


# ── PUT /progress ────────────────────────────────────────────────────────
@router.put(
    "",
    response_model=ProgressRead,
    summary="Record a topic visit or mark as completed",
)
async def update_progress(
    payload: ProgressUpdate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ProgressRead:
    """
    Create or update a progress record (upsert semantics).

    **Behaviour:**

    * ``last_visited_at`` is **always** refreshed to ``now()``.
    * ``is_completed = true`` → marks the topic as completed and sets
      ``completed_at`` (only on first completion).
    * ``is_completed = false`` → un-completes the topic and clears
      ``completed_at``.
    * ``is_completed = null`` (omitted) → completion state is unchanged;
      only the visit timestamp is refreshed.
    """
    return await upsert_progress(current_user.id, payload, session)
