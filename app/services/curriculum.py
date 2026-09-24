"""
Curriculum service – read-only business logic for modules, topics,
and topic content.

All queries filter on ``is_published = True`` by default so that
draft content is never leaked to students.  Admin endpoints (if added
later) should bypass this filter.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.curriculum import Module, Topic, TopicAttachment, TopicContent
from app.schemas.curriculum import (
    ModuleRead,
    ModuleWithTopicsRead,
    TopicDetailRead,
    TopicRead,
    TopicAttachmentRead,
    TopicContentRead,
)


# ── Modules ──────────────────────────────────────────────────────────────


async def list_modules(session: AsyncSession) -> list[ModuleRead]:
    """
    Return every published module, ordered by ``order_index``.

    Topics are **not** loaded (flat listing for top-level navigation).
    """
    stmt = (
        select(Module)
        .where(Module.is_published.is_(True))
        .order_by(Module.order_index)
    )
    result = await session.execute(stmt)
    modules = result.scalars().all()
    return [ModuleRead.model_validate(m) for m in modules]


async def get_module_with_topics(
    module_id: uuid.UUID,
    session: AsyncSession,
) -> ModuleWithTopicsRead:
    """
    Return a single published module with its published topics nested.

    Used for the sidebar navigation tree of a specific module.

    Raises
    ------
    HTTPException 404
        If the module does not exist or is unpublished.
    """
    stmt = (
        select(Module)
        .options(selectinload(Module.topics))
        .where(Module.id == module_id, Module.is_published.is_(True))
    )
    result = await session.execute(stmt)
    module = result.scalar_one_or_none()

    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Module not found.",
        )

    # Filter out unpublished topics at the application layer
    published_topics = sorted(
        [t for t in module.topics if t.is_published],
        key=lambda t: t.order_index,
    )

    return ModuleWithTopicsRead(
        id=module.id,
        title=module.title,
        slug=module.slug,
        description=module.description,
        order_index=module.order_index,
        is_published=module.is_published,
        created_at=module.created_at,
        topics=[TopicRead.model_validate(t) for t in published_topics],
    )


# ── Curriculum Tree ──────────────────────────────────────────────────────


async def get_curriculum_tree(
    session: AsyncSession,
) -> list[ModuleWithTopicsRead]:
    """
    Return the full curriculum navigation tree: all published modules,
    each with their published topics nested.

    Topics contain **only** lightweight metadata (payload separation).
    """
    stmt = (
        select(Module)
        .options(selectinload(Module.topics))
        .where(Module.is_published.is_(True))
        .order_by(Module.order_index)
    )
    result = await session.execute(stmt)
    modules = result.scalars().all()

    tree: list[ModuleWithTopicsRead] = []
    for module in modules:
        published_topics = sorted(
            [t for t in module.topics if t.is_published],
            key=lambda t: t.order_index,
        )
        tree.append(
            ModuleWithTopicsRead(
                id=module.id,
                title=module.title,
                slug=module.slug,
                description=module.description,
                order_index=module.order_index,
                is_published=module.is_published,
                created_at=module.created_at,
                topics=[TopicRead.model_validate(t) for t in published_topics],
            )
        )

    return tree


# ── Topics ───────────────────────────────────────────────────────────────


async def get_topic(
    topic_id: uuid.UUID,
    session: AsyncSession,
) -> Topic:
    """
    Load a single published topic by ID (ORM instance).

    This is used internally by both the metadata endpoint and the
    ``require_topic_access`` dependency.

    Raises
    ------
    HTTPException 404
        If the topic does not exist or is unpublished.
    """
    stmt = select(Topic).where(
        Topic.id == topic_id, Topic.is_published.is_(True)
    )
    result = await session.execute(stmt)
    topic = result.scalar_one_or_none()

    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found.",
        )

    return topic


async def get_topic_content(
    topic_id: uuid.UUID,
    session: AsyncSession,
) -> TopicDetailRead:
    """
    Load the heavy content payload for a topic (HTML dashboard, media
    URLs, and attachments).

    This is the **only** endpoint that returns ``html_content`` and
    related rich data (payload separation invariant).

    Raises
    ------
    HTTPException 404
        If the topic does not exist or is unpublished.
    """
    # Load topic with content and attachments eagerly
    stmt = (
        select(Topic)
        .options(
            selectinload(Topic.content),
            selectinload(Topic.attachments),
        )
        .where(Topic.id == topic_id, Topic.is_published.is_(True))
    )
    result = await session.execute(stmt)
    topic = result.scalar_one_or_none()

    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found.",
        )

    content_schema: TopicContentRead | None = None
    if topic.content is not None:
        content_schema = TopicContentRead.model_validate(topic.content)

    attachments_schema = [
        TopicAttachmentRead.model_validate(a)
        for a in sorted(topic.attachments, key=lambda a: a.order_index)
    ]

    return TopicDetailRead(
        topic=TopicRead.model_validate(topic),
        content=content_schema,
        attachments=attachments_schema,
    )
