"""
Curriculum schemas: Modules, Topics, TopicContent, TopicAttachments.

Design note – **payload separation** is enforced at the schema level:
  • ``TopicRead`` carries only lightweight metadata (title, slug, flags).
  • ``TopicContentRead`` is the heavy response containing the HTML dashboard,
    media URLs, and attachments — only served by the dedicated content endpoint.
  • ``ModuleWithTopicsRead`` nests ``TopicRead`` (never content) for nav trees.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── Topic Attachments ────────────────────────────────────────────────────


class TopicAttachmentRead(BaseModel):
    """Metadata for a single downloadable resource."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    file_type: str
    file_url: str
    file_size_bytes: int | None = None
    order_index: int


# ── Topics ───────────────────────────────────────────────────────────────


class TopicRead(BaseModel):
    """
    Lightweight topic metadata for listing / navigation.

    **Never** includes ``html_content``, raw notes, or media URLs.
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


class TopicContentRead(BaseModel):
    """
    Full topic payload — served **only** by
    ``GET /api/v1/topics/{id}/content``.

    Contains the pre-built HTML dashboard, NotebookLM references,
    media URLs, and the list of downloadable attachments.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topic_id: uuid.UUID
    html_content: str | None = None
    notebooklm_url: str | None = None
    notebooklm_raw_notes: str | None = None
    video_url: str | None = None
    audio_url: str | None = None
    updated_at: datetime


class TopicDetailRead(BaseModel):
    """
    Combined response for the dedicated content endpoint.

    Nests lightweight topic metadata alongside the heavy content
    and attachments so the frontend gets everything in one call.
    """

    topic: TopicRead
    content: TopicContentRead | None = None
    attachments: list[TopicAttachmentRead] = []


# ── Modules ──────────────────────────────────────────────────────────────


class ModuleRead(BaseModel):
    """Module metadata without nested topics (flat listing)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    description: str | None = None
    order_index: int
    is_published: bool
    created_at: datetime


class ModuleWithTopicsRead(BaseModel):
    """
    Module with nested lightweight topics — used for the full
    curriculum / navigation tree.

    Topics contain **only** metadata, never heavy content.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    description: str | None = None
    order_index: int
    is_published: bool
    created_at: datetime
    topics: list[TopicRead] = []
