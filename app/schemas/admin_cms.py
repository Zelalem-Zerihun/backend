"""
Admin CMS request / response schemas.

These schemas support the admin content-management endpoints under
``/api/v1/admin/cms``.  They cover CRUD operations for modules, topics,
topic content (HTML ingestion), and file attachments.

Note: multipart upload endpoints (content ingestion, attachment upload)
use ``Form()`` + ``UploadFile`` parameters directly in the router
signature rather than a Pydantic body model.  The schemas here cover
the **JSON** request bodies and **all** response models.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ═══════════════════════════════════════════════════════════════════════════
# MODULE SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════


class ModuleCreate(BaseModel):
    """Payload for ``POST /admin/cms/modules``."""

    title: str = Field(min_length=1, max_length=255)
    slug: str = Field(
        min_length=1,
        max_length=255,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="URL-safe slug (lowercase, hyphens only).",
    )
    description: str | None = Field(default=None, max_length=5000)
    order_index: int = Field(default=0, ge=0)
    is_published: bool = False


class ModuleUpdate(BaseModel):
    """
    Payload for ``PATCH /admin/cms/modules/{module_id}``.

    All fields are optional — only supplied fields are updated.
    """

    title: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    description: str | None = None
    order_index: int | None = Field(default=None, ge=0)
    is_published: bool | None = None


class AdminModuleRead(BaseModel):
    """
    Admin-facing module response.

    Identical to the student ``ModuleRead`` but kept separate so the
    admin view can be extended independently (e.g. with topic counts,
    draft indicators) without affecting the student API contract.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    description: str | None = None
    order_index: int
    is_published: bool
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# TOPIC SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════


class TopicCreate(BaseModel):
    """Payload for ``POST /admin/cms/modules/{module_id}/topics``."""

    title: str = Field(min_length=1, max_length=255)
    slug: str = Field(
        min_length=1,
        max_length=255,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="URL-safe slug, unique within the parent module.",
    )
    order_index: int = Field(default=0, ge=0)
    is_free_preview: bool = False
    estimated_read_time: int = Field(
        default=10,
        ge=1,
        description="Estimated read time in minutes.",
    )
    is_published: bool = False


class TopicUpdate(BaseModel):
    """
    Payload for ``PATCH /admin/cms/topics/{topic_id}``.

    All fields are optional — only supplied fields are updated.
    """

    title: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    order_index: int | None = Field(default=None, ge=0)
    is_free_preview: bool | None = None
    estimated_read_time: int | None = Field(default=None, ge=1)
    is_published: bool | None = None


class AdminTopicRead(BaseModel):
    """
    Admin-facing topic metadata response.

    Includes ``module_id`` for cross-referencing and all flags
    that admins need to manage (published state, free preview toggle).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    module_id: uuid.UUID
    title: str
    slug: str
    order_index: int
    is_free_preview: bool
    estimated_read_time: int
    is_published: bool


# ═══════════════════════════════════════════════════════════════════════════
# TOPIC CONTENT (HTML INGESTION) SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════


class AdminTopicContentRead(BaseModel):
    """
    Admin preview of a topic's full content payload.

    Returned by ``GET /admin/cms/topics/{topic_id}/content`` so admins
    can verify uploaded HTML and metadata before publishing.

    Note: video and audio are no longer supported.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topic_id: uuid.UUID
    html_content: str | None = None
    notebooklm_url: str | None = None
    notebooklm_raw_notes: str | None = None
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# ATTACHMENT SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════


class AttachmentCreate(BaseModel):
    """
    Payload for ``POST /admin/cms/topics/{topic_id}/attachments``.

    Instead of uploading a file, the admin provides a Google Drive
    share link alongside the document title and type.
    """

    title: str = Field(min_length=1, max_length=255)
    file_type: str = Field(
        description="Document type: 'pdf' or 'pptx'.",
        pattern=r"^(pdf|pptx)$",
    )
    drive_link: str = Field(
        min_length=1,
        max_length=2000,
        description="Google Drive share link for the document.",
    )
    order_index: int = Field(default=0, ge=0)


class AdminAttachmentRead(BaseModel):
    """
    Admin-facing attachment metadata, returned after creation and in
    listing responses.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topic_id: uuid.UUID
    title: str
    file_type: str
    drive_link: str
    order_index: int
