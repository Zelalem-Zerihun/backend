"""
User progress service – track topic visits, completions, and compute
per-module progress summaries.

All operations are scoped to the authenticated user; a user can never
read or modify another user's progress.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import Module, Topic
from app.models.progress import UserProgress
from app.schemas.progress import (
    ModuleProgressSummary,
    ProgressRead,
    ProgressUpdate,
)


async def list_user_progress(
    user_id: uuid.UUID,
    session: AsyncSession,
) -> list[ProgressRead]:
    """
    Return every progress record for the given user, ordered by
    ``last_visited_at`` descending (most recently visited first).
    """
    stmt = (
        select(UserProgress)
        .where(UserProgress.user_id == user_id)
        .order_by(UserProgress.last_visited_at.desc())
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [ProgressRead.model_validate(r) for r in rows]


async def get_topic_progress(
    user_id: uuid.UUID,
    topic_id: uuid.UUID,
    session: AsyncSession,
) -> ProgressRead:
    """
    Return the progress record for a specific user + topic pair.

    Raises
    ------
    HTTPException 404
        If no progress record exists for this combination.
    """
    stmt = select(UserProgress).where(
        UserProgress.user_id == user_id,
        UserProgress.topic_id == topic_id,
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No progress record found for this topic.",
        )

    return ProgressRead.model_validate(row)


async def upsert_progress(
    user_id: uuid.UUID,
    payload: ProgressUpdate,
    session: AsyncSession,
) -> ProgressRead:
    """
    Create or update a progress record (upsert semantics).

    Behaviour
    ~~~~~~~~~
    * If no record exists for ``(user_id, topic_id)``, create one.
    * ``last_visited_at`` is **always** refreshed to ``now()``.
    * If ``is_completed`` is ``True`` and the topic was not previously
      completed, ``completed_at`` is set.
    * If ``is_completed`` is ``False``, ``completed_at`` is cleared
      (allows un-completing a topic).
    * If ``is_completed`` is ``None``, the completion state is unchanged.

    Raises
    ------
    HTTPException 404
        If the referenced ``topic_id`` does not exist.
    """
    # Verify the topic exists
    topic = await session.get(Topic, payload.topic_id)
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found.",
        )

    # Look for existing progress row
    stmt = select(UserProgress).where(
        UserProgress.user_id == user_id,
        UserProgress.topic_id == payload.topic_id,
    )
    result = await session.execute(stmt)
    progress = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if progress is None:
        # ── Create ───────────────────────────────────────────────────
        progress = UserProgress(
            user_id=user_id,
            topic_id=payload.topic_id,
            is_completed=payload.is_completed or False,
            completed_at=now if payload.is_completed else None,
            last_visited_at=now,
        )
        session.add(progress)
    else:
        # ── Update ───────────────────────────────────────────────────
        progress.last_visited_at = now

        if payload.is_completed is not None:
            if payload.is_completed and not progress.is_completed:
                # First-time completion
                progress.is_completed = True
                progress.completed_at = now
            elif not payload.is_completed:
                # Un-complete
                progress.is_completed = False
                progress.completed_at = None

    await session.flush()
    return ProgressRead.model_validate(progress)


async def get_module_progress_summaries(
    user_id: uuid.UUID,
    session: AsyncSession,
) -> list[ModuleProgressSummary]:
    """
    Compute per-module progress summaries for the authenticated user.

    Returns one ``ModuleProgressSummary`` per published module,
    ordered by ``Module.order_index``.  Each summary includes:

    * ``total_topics`` – count of **published** topics in the module.
    * ``completed_topics`` – count of those the user has completed.
    * ``completion_percent`` – ``completed / total * 100`` (0 if no topics).
    """
    # Subquery: count of completed topics per module for this user
    completed_sq = (
        select(
            Topic.module_id,
            func.count(UserProgress.id).label("completed"),
        )
        .join(
            UserProgress,
            (UserProgress.topic_id == Topic.id)
            & (UserProgress.user_id == user_id)
            & (UserProgress.is_completed.is_(True)),
        )
        .where(Topic.is_published.is_(True))
        .group_by(Topic.module_id)
        .subquery()
    )

    # Main query: all published modules with total topic count + completed
    stmt = (
        select(
            Module.id,
            Module.title,
            func.count(Topic.id).label("total_topics"),
            func.coalesce(completed_sq.c.completed, 0).label(
                "completed_topics"
            ),
        )
        .outerjoin(Topic, (Topic.module_id == Module.id) & Topic.is_published.is_(True))
        .outerjoin(completed_sq, completed_sq.c.module_id == Module.id)
        .where(Module.is_published.is_(True))
        .group_by(Module.id, Module.title, Module.order_index, completed_sq.c.completed)
        .order_by(Module.order_index)
    )

    result = await session.execute(stmt)
    rows = result.all()

    summaries: list[ModuleProgressSummary] = []
    for row in rows:
        total = row.total_topics
        completed = row.completed_topics
        pct = round((completed / total) * 100, 1) if total > 0 else 0.0

        summaries.append(
            ModuleProgressSummary(
                module_id=row.id,
                module_title=row.title,
                total_topics=total,
                completed_topics=completed,
                completion_percent=pct,
            )
        )

    return summaries
