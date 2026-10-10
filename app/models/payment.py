"""
Payment transaction model.

Records every payment attempt submitted by students.
The status lifecycle is:

    pending_verification → completed
                         → rejected

Verification can be performed automatically (via the ``/verify-reference``
internal endpoint) or manually by an admin via the admin payment panel.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PaymentTransaction(Base):
    """
    A single student payment submission.

    ``transaction_reference`` is unique and indexed so that duplicate
    submission of the same bank/Telebirr reference is rejected at the
    database level (unique constraint) as well as at the application layer.
    """

    __tablename__ = "payment_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'monthly' | 'semester' | 'annual'

    payment_method: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'telebirr' | 'cbe' | 'bank_transfer'

    transaction_reference: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    receipt_url: Mapped[str | None] = mapped_column(
        String(1000), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending_verification"
    )  # 'pending_verification' | 'completed' | 'rejected'

    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_by: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=datetime.now,
    )

    # ── Relationships ────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="payment_transactions")  # type: ignore[name-defined]
