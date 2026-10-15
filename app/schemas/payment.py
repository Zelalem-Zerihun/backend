"""
Payment & subscription Pydantic schemas.

Plan pricing (ETB):
    monthly  – 300 ETB  / 1 month
    quarterly – 900 ETB / 3 months
    biannual – 1 800 ETB / 6 months
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ── Plan catalogue ────────────────────────────────────────────────────────

PlanType = Literal["monthly", "quarterly", "biannual"]

PLAN_CATALOGUE: dict[str, dict] = {
    "monthly": {
        "label": "1 Month",
        "duration_months": 1,
        "price_etb": Decimal("300.00"),
        "description": "Full access for 1 month",
    },
    "quarterly": {
        "label": "3 Months",
        "duration_months": 3,
        "price_etb": Decimal("900.00"),
        "description": "Full access for 3 months (3 × 300 ETB)",
    },
    "biannual": {
        "label": "6 Months",
        "duration_months": 6,
        "price_etb": Decimal("1800.00"),
        "description": "Full access for 6 months (6 × 300 ETB)",
    },
}


# ── Requests ─────────────────────────────────────────────────────────────


class SubscribeRequest(BaseModel):
    """
    Payload submitted when a student initiates a subscription payment.

    The student transfers the exact plan amount via Telebirr / CBE /
    bank transfer and provides the bank reference to be verified.
    """

    plan_type: PlanType = Field(
        ...,
        description=(
            "Subscription plan: 'monthly' (300 ETB / 1 mo), "
            "'quarterly' (900 ETB / 3 mo), or 'biannual' (1 800 ETB / 6 mo)."
        ),
    )
    payment_method: Literal["telebirr", "cbe", "bank_transfer"] = Field(
        ...,
        description="Payment channel used to transfer the funds.",
    )
    transaction_reference: str = Field(
        ...,
        min_length=4,
        max_length=255,
        description=(
            "Unique reference number from your bank / Telebirr receipt. "
            "Duplicate references are rejected."
        ),
    )
    receipt_url: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional URL to an uploaded screenshot / PDF of the receipt.",
    )


# ── Responses ─────────────────────────────────────────────────────────────


class PlanInfo(BaseModel):
    """A single subscription plan in the public catalogue."""

    plan_type: str
    label: str
    duration_months: int
    price_etb: Decimal
    description: str


class PaymentTransactionRead(BaseModel):
    """Serialised ``PaymentTransaction`` returned after submission."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_type: str
    payment_method: str
    transaction_reference: str
    amount: Decimal
    receipt_url: str | None
    status: str
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime


class SubscribeResponse(BaseModel):
    """Response returned immediately after a payment is submitted."""

    message: str
    transaction: PaymentTransactionRead


class SubscriptionStatusResponse(BaseModel):
    """Current subscription state for the authenticated user."""

    is_subscribed: bool
    plan_type: str | None = None
    status: str | None = None
    expires_at: datetime | None = None
    days_remaining: int | None = None


# ── Admin ─────────────────────────────────────────────────────────────────


class VerifyPaymentRequest(BaseModel):
    """
    Admin payload to approve or reject a pending payment transaction.

    ``POST /payment/admin/transactions/{transaction_id}/verify``

    Fields
    ------
    approve
        ``True`` to mark the transaction as completed and activate the
        subscription.  ``False`` to reject it.
    rejection_reason
        Required (or at least helpful) when ``approve=False``.
        Recorded in ``payment_transactions.rejection_reason``.
    """

    approve: bool = True
    rejection_reason: str | None = Field(
        default=None,
        max_length=1000,
        description="Reason for rejection (required when approve=False).",
    )
