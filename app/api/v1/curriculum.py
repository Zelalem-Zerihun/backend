"""
Curriculum endpoints – modules, topics, and topic content.

Payload separation is enforced here:
  • Listing / navigation endpoints return only lightweight metadata.
  • The ``GET /topics/{topic_id}/content`` endpoint is the **sole** path
    to the heavy HTML dashboard, media URLs, and attachments.
  • Premium content is gated by the ``require_topic_access`` dependency.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.api.deps import CurrentUser, require_topic_access
from app.schemas.curriculum import (
    ModuleRead,
    ModuleWithTopicsRead,
    TopicDetailRead,
    TopicRead,
)
from app.services.curriculum import (
    get_curriculum_tree,
    get_module_with_topics,
    get_topic,
    get_topic_content,
    list_modules,
)

router = APIRouter(tags=["Curriculum"])


# ── GET /modules ─────────────────────────────────────────────────────────
@router.get(
    "/modules",
    response_model=list[ModuleRead],
    summary="List all published modules",
)
async def list_all_modules(
    _current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[ModuleRead]:
    """
    Return every published module ordered by ``order_index``.

    Does **not** include nested topics (use ``GET /modules/{id}`` or
    ``GET /curriculum`` for the full tree).
    """
    return await list_modules(session)


# ── GET /curriculum ──────────────────────────────────────────────────────
@router.get(
    "/curriculum",
    response_model=list[ModuleWithTopicsRead],
    summary="Full curriculum navigation tree",
)
async def curriculum_tree(
    _current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[ModuleWithTopicsRead]:
    """
    Return all published modules with their published topics nested.

    Topics contain **only** lightweight metadata – never ``html_content``
    or media URLs (payload separation).
    """
    return await get_curriculum_tree(session)


# ── GET /modules/{module_id} ─────────────────────────────────────────────
@router.get(
    "/modules/{module_id}",
    response_model=ModuleWithTopicsRead,
    summary="Get a module with its topics",
)
async def read_module(
    module_id: uuid.UUID,
    _current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ModuleWithTopicsRead:
    """
    Return a single published module and its published topics.
    """
    return await get_module_with_topics(module_id, session)


# ── GET /topics/{topic_id} ──────────────────────────────────────────────
@router.get(
    "/topics/{topic_id}",
    response_model=TopicRead,
    summary="Get topic metadata",
)
async def read_topic(
    topic_id: uuid.UUID,
    _current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> TopicRead:
    """
    Return lightweight metadata for a single published topic.

    Does **not** include ``html_content`` or attachments – use
    ``GET /topics/{id}/content`` for the full payload.
    """
    topic = await get_topic(topic_id, session)
    return TopicRead.model_validate(topic)


# ── GET /topics/{topic_id}/content ───────────────────────────────────────
@router.get(
    "/topics/{topic_id}/content",
    response_model=TopicDetailRead,
    summary="Get full topic content (paywall-protected)",
    dependencies=[Depends(require_topic_access)],
)
async def read_topic_content(
    topic_id: uuid.UUID,
    _current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> TopicDetailRead:
    """
    Return the **full** topic payload: HTML dashboard, NotebookLM
    references, media URLs, and downloadable attachments.

    **Paywall-protected** – non-free-preview topics require an active
    subscription. Free-preview topics are accessible to all
    authenticated users.
    """
    return await get_topic_content(topic_id, session)
