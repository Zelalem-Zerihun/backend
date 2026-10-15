"""
Admin CMS router – ``/api/v1/admin/cms``.

Provides CRUD endpoints for:
  1. **Modules**    – create, update metadata/order, delete (cascade).
  2. **Topics**     – create under a module, update metadata/flags, delete.
  3. **Content**    – upload HTML file + optional metadata URLs (multipart).
                      Preview current content payload.
  4. **Attachments**– add Drive link (PDF/PPTX); delete by attachment ID.

All endpoints require the ``require_admin`` dependency which verifies:
  * A valid, non-expired JWT with a matching ``session_id`` (single-session).
  * The authenticated user has ``role = 'admin'``.

Error contract
~~~~~~~~~~~~~~
* ``400 Bad Request`` – invalid input / validation failure.
* ``401 Unauthorized`` – missing or invalid token / invalidated session.
* ``403 Forbidden`` – authenticated but not an admin.
* ``404 Not Found`` – referenced resource does not exist.
* ``409 Conflict`` – unique constraint violation (duplicate slug, etc.)

Transaction safety
~~~~~~~~~~~~~~~~~~
Every mutating operation uses the session provided by ``get_async_session``,
which is committed automatically on success and rolled back on exception by
the ``get_async_session`` context manager (see ``app/core/database.py``).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser, require_admin
from app.core.database import get_async_session
from app.core.storage import read_html_upload
from app.models.curriculum import Module, Topic, TopicAttachment, TopicContent
from app.schemas.admin_cms import (
    AdminAttachmentRead,
    AdminModuleRead,
    AdminTopicContentRead,
    AdminTopicRead,
    AttachmentCreate,
    ModuleCreate,
    ModuleUpdate,
    TopicCreate,
    TopicUpdate,
)

router = APIRouter(
    tags=["Admin – CMS"],
    dependencies=[Depends(require_admin)],
)

# ── Convenience type alias for the async DB session ──────────────────────
DBSession = Annotated[AsyncSession, Depends(get_async_session)]


# ═══════════════════════════════════════════════════════════════════════════
# MODULES
# ═══════════════════════════════════════════════════════════════════════════


@router.post(
    "/modules",
    response_model=AdminModuleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new module",
)
async def create_module(
    _admin: AdminUser,
    payload: ModuleCreate,
    session: DBSession,
) -> AdminModuleRead:
    """
    Create a new curriculum module.

    ``slug`` must be unique across all modules.  If a duplicate slug is
    submitted the endpoint returns ``409 Conflict``.
    """
    module = Module(
        title=payload.title,
        slug=payload.slug,
        description=payload.description,
        order_index=payload.order_index,
        is_published=payload.is_published,
    )
    session.add(module)
    try:
        await session.flush()  # surface unique-constraint errors early
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A module with slug '{payload.slug}' already exists.",
        )
    await session.commit()
    await session.refresh(module)
    return AdminModuleRead.model_validate(module)


@router.patch(
    "/modules/{module_id}",
    response_model=AdminModuleRead,
    summary="Update module metadata or reorder",
)
async def update_module(
    module_id: uuid.UUID,
    _admin: AdminUser,
    payload: ModuleUpdate,
    session: DBSession,
) -> AdminModuleRead:
    """
    Partially update a module.

    Only fields explicitly provided in the request body are updated
    (standard PATCH semantics — ``None`` means "leave unchanged").
    """
    module = await session.get(Module, module_id)
    if module is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(module, field, value)

    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A module with slug '{payload.slug}' already exists.",
        )
    await session.commit()
    await session.refresh(module)
    return AdminModuleRead.model_validate(module)


@router.delete(
    "/modules/{module_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a module (cascade)",
)
async def delete_module(
    module_id: uuid.UUID,
    _admin: AdminUser,
    session: DBSession,
) -> None:
    """
    Permanently delete a module and **all** its child topics, contents,
    and attachments via ``CASCADE`` foreign-key rules.

    This operation is irreversible.  Since attachments are Google Drive
    links (no files stored server-side), only database records are removed.
    """
    module = await session.get(Module, module_id)
    if module is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found.")

    await session.delete(module)
    await session.commit()


# ═══════════════════════════════════════════════════════════════════════════
# TOPICS
# ═══════════════════════════════════════════════════════════════════════════


@router.post(
    "/modules/{module_id}/topics",
    response_model=AdminTopicRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a topic under a module",
)
async def create_topic(
    module_id: uuid.UUID,
    _admin: AdminUser,
    payload: TopicCreate,
    session: DBSession,
) -> AdminTopicRead:
    """
    Create a new topic inside the specified module.

    ``slug`` must be unique **within** the parent module (enforced by
    the ``uq_topic_module_slug`` unique constraint).
    """
    # Verify parent module exists
    module = await session.get(Module, module_id)
    if module is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found.")

    topic = Topic(
        module_id=module_id,
        title=payload.title,
        slug=payload.slug,
        order_index=payload.order_index,
        is_free_preview=payload.is_free_preview,
        estimated_read_time=payload.estimated_read_time,
        is_published=payload.is_published,
    )
    session.add(topic)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A topic with slug '{payload.slug}' already exists in this module.",
        )
    await session.commit()
    await session.refresh(topic)
    return AdminTopicRead.model_validate(topic)


@router.patch(
    "/topics/{topic_id}",
    response_model=AdminTopicRead,
    summary="Update topic metadata, flags, or published state",
)
async def update_topic(
    topic_id: uuid.UUID,
    _admin: AdminUser,
    payload: TopicUpdate,
    session: DBSession,
) -> AdminTopicRead:
    """
    Partially update a topic.

    Use this endpoint to:
    * Edit the title, slug, or reading-time estimate.
    * Toggle ``is_free_preview`` (freemium gate).
    * Toggle ``is_published`` (visibility to students).
    * Reorder within its module (``order_index``).
    """
    topic = await session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(topic, field, value)

    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A topic with slug '{payload.slug}' already exists in this module.",
        )
    await session.commit()
    await session.refresh(topic)
    return AdminTopicRead.model_validate(topic)


@router.delete(
    "/topics/{topic_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a topic and its contents",
)
async def delete_topic(
    topic_id: uuid.UUID,
    _admin: AdminUser,
    session: DBSession,
) -> None:
    """
    Permanently delete a topic along with its ``TopicContent`` record
    and all ``TopicAttachment`` records (via CASCADE).

    Since attachments are Google Drive links (no files stored server-side),
    only database records are removed.
    """
    topic = await session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")

    await session.delete(topic)
    await session.commit()


# ═══════════════════════════════════════════════════════════════════════════
# CONTENT (HTML INGESTION)
# ═══════════════════════════════════════════════════════════════════════════


@router.post(
    "/topics/{topic_id}/content",
    response_model=AdminTopicContentRead,
    summary="Upload HTML content and metadata for a topic",
)
async def upload_topic_content(
    topic_id: uuid.UUID,
    _admin: AdminUser,
    session: DBSession,
    html_file: UploadFile | None = None,
    notebooklm_url: Annotated[str | None, Form()] = None,
    notebooklm_raw_notes: Annotated[str | None, Form()] = None,
) -> AdminTopicContentRead:
    """
    Upload or replace the HTML dashboard and optional metadata for a topic.

    **Multipart form fields:**
    - ``html_file`` *(optional)* – ``.html`` / ``.htm`` file (≤ MAX_HTML_FILE_SIZE_MB).
      When provided, the raw UTF-8 string is persisted directly into
      ``topic_contents.html_content``.  The file is **not** stored on disk.
    - ``notebooklm_url`` *(optional)* – Public NotebookLM podcast/notebook URL.
    - ``notebooklm_raw_notes`` *(optional)* – Raw note text for AI context injection.

    If a ``TopicContent`` record already exists for this topic, it is
    updated in-place (upsert semantics).  Only explicitly supplied
    fields are overwritten; omitted fields retain their current values.

    Note: ``video_url`` and ``audio_url`` have been removed.  Documents
    (PDF/PPTX) are managed via the attachments endpoint using Drive links.
    """
    # Verify topic exists
    topic = await session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")

    # Read and validate HTML if provided
    html_content: str | None = None
    if html_file is not None:
        html_content = await read_html_upload(html_file)

    # Fetch existing content record (or create a new one)
    stmt = select(TopicContent).where(TopicContent.topic_id == topic_id)
    result = await session.execute(stmt)
    content = result.scalar_one_or_none()

    if content is None:
        content = TopicContent(topic_id=topic_id)
        session.add(content)

    # Apply updates for only the fields that were explicitly supplied
    if html_content is not None:
        content.html_content = html_content
    if notebooklm_url is not None:
        content.notebooklm_url = notebooklm_url
    if notebooklm_raw_notes is not None:
        content.notebooklm_raw_notes = notebooklm_raw_notes

    await session.commit()
    await session.refresh(content)
    return AdminTopicContentRead.model_validate(content)


@router.get(
    "/topics/{topic_id}/content",
    response_model=AdminTopicContentRead,
    summary="Preview current topic content payload",
)
async def get_topic_content_admin(
    topic_id: uuid.UUID,
    _admin: AdminUser,
    session: DBSession,
) -> AdminTopicContentRead:
    """
    Return the full content payload (HTML + metadata) for a topic.

    Useful for admins to verify uploaded HTML and metadata before
    publishing a topic to students.
    """
    # Verify topic exists first (clearer 404 message)
    topic = await session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")

    stmt = select(TopicContent).where(TopicContent.topic_id == topic_id)
    result = await session.execute(stmt)
    content = result.scalar_one_or_none()

    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No content has been uploaded for this topic yet.",
        )
    return AdminTopicContentRead.model_validate(content)


# ═══════════════════════════════════════════════════════════════════════════
# ATTACHMENTS
# ═══════════════════════════════════════════════════════════════════════════


@router.post(
    "/topics/{topic_id}/attachments",
    response_model=AdminAttachmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a Drive-link attachment (PDF or PPTX) to a topic",
)
async def add_attachment(
    topic_id: uuid.UUID,
    _admin: AdminUser,
    payload: AttachmentCreate,
    session: DBSession,
) -> AdminAttachmentRead:
    """
    Register a Google Drive document link as an attachment for a topic.

    **Request body (JSON):**
    - ``title`` – Human-readable label (e.g., *"Cost Accounting Slide Deck – Lesson 1"*).
    - ``file_type`` – ``"pdf"`` or ``"pptx"``.
    - ``drive_link`` – Google Drive share URL for the document.
    - ``order_index`` *(optional, default 0)* – Display position within the topic's
      attachment list.  Pass ``0`` to append at the front, or omit and reorder later.

    A ``TopicAttachment`` record is created with the Drive link.
    No file is stored on the server.
    """
    # Verify topic exists
    topic = await session.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")

    # Determine next order_index (max + 1) if not explicitly set
    from sqlalchemy import func

    max_stmt = select(func.max(TopicAttachment.order_index)).where(
        TopicAttachment.topic_id == topic_id
    )
    max_result = await session.execute(max_stmt)
    current_max: int | None = max_result.scalar_one_or_none()
    next_order = payload.order_index if payload.order_index else (current_max or 0) + 1

    attachment = TopicAttachment(
        topic_id=topic_id,
        title=payload.title,
        file_type=payload.file_type,
        drive_link=payload.drive_link,
        order_index=next_order,
    )
    session.add(attachment)
    await session.commit()
    await session.refresh(attachment)
    return AdminAttachmentRead.model_validate(attachment)


@router.delete(
    "/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an attachment record",
)
async def remove_attachment(
    attachment_id: uuid.UUID,
    _admin: AdminUser,
    session: DBSession,
) -> None:
    """
    Delete a ``TopicAttachment`` record from the database.

    Since attachments are Drive links (no file stored server-side),
    this only removes the database record.
    """
    attachment = await session.get(TopicAttachment, attachment_id)
    if attachment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found.",
        )

    await session.delete(attachment)
    await session.commit()
