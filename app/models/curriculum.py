"""
Curriculum models: Module → Topic → TopicContent / TopicAttachments.

Design note – **payload separation**:
  • ``Topic`` carries only lightweight metadata (title, slug, order, flags).
  • ``TopicContent`` holds the heavy HTML dashboard and media URLs in a
    separate table (1-to-1) so listing/navigation queries never load them.
  • ``TopicAttachment`` stores downloadable resource metadata (1-to-N).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Module(Base):
    """
    Top-level curriculum grouping (e.g. "Cost Accounting", "Taxation").

    ``order_index`` controls presentation order in the sidebar/nav tree.
    ``is_published`` controls visibility to students.
    """

    __tablename__ = "modules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # ── Relationships ────────────────────────────────────────────────────
    topics: Mapped[list["Topic"]] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
        order_by="Topic.order_index",
        lazy="selectin",
    )


class Topic(Base):
    """
    A single lesson within a module.

    ``is_free_preview`` determines whether the topic is accessible
    without an active subscription (freemium gate).
    """

    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("module_id", "slug", name="uq_topic_module_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("modules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    is_free_preview: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    estimated_read_time: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10
    )
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # ── Relationships ────────────────────────────────────────────────────
    module: Mapped["Module"] = relationship(back_populates="topics")

    content: Mapped["TopicContent | None"] = relationship(
        back_populates="topic",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="noload",  # Never loaded by default (payload separation)
    )
    attachments: Mapped[list["TopicAttachment"]] = relationship(
        back_populates="topic",
        cascade="all, delete-orphan",
        order_by="TopicAttachment.order_index",
        lazy="noload",  # Only loaded on the dedicated content endpoint
    )


class TopicContent(Base):
    """
    Heavy payload for a single topic: the pre-built HTML dashboard
    and NotebookLM URLs/raw notes.

    1-to-1 with ``Topic`` (enforced by ``unique=True`` on ``topic_id``).
    Intentionally in a separate table to enable payload separation.

    Note: video and audio are no longer supported.  Documents (PDF/PPTX)
    are referenced via Google Drive links stored on ``TopicAttachment``.
    """

    __tablename__ = "topic_contents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    html_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    notebooklm_url: Mapped[str | None] = mapped_column(
        String(1000), nullable=True
    )
    notebooklm_raw_notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=datetime.now,
    )

    # ── Relationships ────────────────────────────────────────────────────
    topic: Mapped["Topic"] = relationship(back_populates="content")


class TopicAttachment(Base):
    """
    Downloadable resource linked to a topic (PDF, PPTX, etc.).

    Files are not stored on the server.  Instead, the admin provides a
    Google Drive share link which is stored in ``drive_link``.
    ``file_type`` is still recorded for display/icon purposes.
    """

    __tablename__ = "topic_attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'pdf' | 'pptx'
    drive_link: Mapped[str] = mapped_column(String(2000), nullable=False)
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    # ── Relationships ────────────────────────────────────────────────────
    topic: Mapped["Topic"] = relationship(back_populates="attachments")
