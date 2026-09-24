"""
AI rate-limiting model for Gemini API cost protection.
"""

import uuid
from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, Integer, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AIRateLimit(Base):
    """
    Per-user daily counter for Gemini API requests.

    The unique constraint on ``(user_id, query_date)`` allows upsert
    logic: increment ``query_count`` if the row exists for today,
    otherwise insert a new row with ``query_count = 1``.

    The dependency checks ``query_count < settings.AI_DAILY_QUOTA``
    before forwarding a request to the Gemini API, returning HTTP 429
    when the cap is exceeded.
    """

    __tablename__ = "ai_rate_limits"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "query_date", name="uq_rate_limit_user_date"
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        server_default=text("CURRENT_DATE"),
    )
    query_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )
