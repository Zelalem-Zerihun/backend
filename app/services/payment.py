"""
Payment & subscription service layer.

Business logic for:
- Submitting a payment transaction
- Activating a subscription on admin approval (or auto-approve path)
- Querying a user's current subscription status
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import PaymentTransaction
from app.models.user import Subscription, User
from app.schemas.payment import (
    PLAN_CATALOGUE,
    PlanInfo,
    SubscribeRequest,
    SubscribeResponse,
    SubscriptionStatusResponse,
    PaymentTransactionRead,
)


# ── Plan catalogue ─────────────────────────────────────────────────────────


def get_plan_catalogue() -> list[PlanInfo]:
    """Return all available subscription plans."""
    return [
        PlanInfo(
            plan_type=key,
            label=info["label"],
            duration_months=info["duration_months"],
            price_etb=info["price_etb"],
            description=info["description"],
        )
        for key, info in PLAN_CATALOGUE.items()
    ]


# ── Submit payment ─────────────────────────────────────────────────────────


async def submit_payment(
    payload: SubscribeRequest,
    current_user: User,
    session: AsyncSession,
) -> SubscribeResponse:
    """
    Record a student's payment submission.

    Steps
    -----
    1. Validate the plan type (redundant – Pydantic already does this, but
       we also do it here for an informative error message).
    2. Reject duplicate ``transaction_reference`` values.
    3. Persist a ``PaymentTransaction`` with status ``pending_verification``.

    The transaction status advances to ``completed`` / ``rejected`` either
    through the admin verification endpoint or an automated webhook.

    Raises
    ------
    HTTPException 400
        If the plan type is unrecognised.
    HTTPException 409
        If the transaction reference has already been submitted.
    """
    # 1. Resolve plan
    plan = PLAN_CATALOGUE.get(payload.plan_type)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown plan type: '{payload.plan_type}'.",
        )

    # 2. Duplicate reference check
    stmt = select(PaymentTransaction).where(
        PaymentTransaction.transaction_reference == payload.transaction_reference
    )
    result = await session.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This transaction reference has already been submitted. "
                "Please check your reference number."
            ),
        )

    # 3. Persist transaction
    txn = PaymentTransaction(
        user_id=current_user.id,
        plan_type=payload.plan_type,
        payment_method=payload.payment_method,
        transaction_reference=payload.transaction_reference,
        amount=plan["price_etb"],
        receipt_url=payload.receipt_url,
        status="pending_verification",
    )
    session.add(txn)
    await session.flush()  # populate id / timestamps

    return SubscribeResponse(
        message=(
            "Payment submitted successfully. Your subscription will be activated "
            "once the transaction is verified by our team (usually within 24 hours)."
        ),
        transaction=PaymentTransactionRead.model_validate(txn),
    )


# ── Subscription status ────────────────────────────────────────────────────


async def get_subscription_status(
    current_user: User,
    session: AsyncSession,
) -> SubscriptionStatusResponse:
    """
    Return the user's current (most recent active) subscription.

    If the user has no active subscription, ``is_subscribed`` is ``False``
    and all other fields are ``None``.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        select(Subscription)
        .where(
            Subscription.user_id == current_user.id,
            Subscription.status == "active",
            Subscription.expires_at > now,
        )
        .order_by(Subscription.expires_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    sub = result.scalar_one_or_none()

    if sub is None:
        return SubscriptionStatusResponse(is_subscribed=False)

    days_remaining = (sub.expires_at.replace(tzinfo=timezone.utc) - now).days

    return SubscriptionStatusResponse(
        is_subscribed=True,
        plan_type=sub.plan_type,
        status=sub.status,
        expires_at=sub.expires_at,
        days_remaining=max(days_remaining, 0),
    )


# ── List user transactions ─────────────────────────────────────────────────


async def list_my_transactions(
    current_user: User,
    session: AsyncSession,
) -> list[PaymentTransactionRead]:
    """Return all payment transactions belonging to the authenticated user."""
    stmt = (
        select(PaymentTransaction)
        .where(PaymentTransaction.user_id == current_user.id)
        .order_by(PaymentTransaction.created_at.desc())
    )
    result = await session.execute(stmt)
    transactions = result.scalars().all()
    return [PaymentTransactionRead.model_validate(t) for t in transactions]


# ── Admin: verify transaction ──────────────────────────────────────────────


async def verify_transaction(
    transaction_id: str,
    approve: bool,
    rejection_reason: str | None,
    admin_user: User,
    session: AsyncSession,
) -> PaymentTransactionRead:
    """
    Approve or reject a pending payment transaction (admin-only).

    On approval:
    - Transaction status → ``completed``
    - A new ``Subscription`` is created (or extended) for the duration of
      the purchased plan.

    On rejection:
    - Transaction status → ``rejected``
    - ``rejection_reason`` is recorded.

    Raises
    ------
    HTTPException 404
        If the transaction does not exist.
    HTTPException 409
        If the transaction is not in ``pending_verification`` state.
    """
    import uuid as _uuid

    try:
        txn_uuid = _uuid.UUID(transaction_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid transaction ID format.",
        )

    txn = await session.get(PaymentTransaction, txn_uuid)
    if txn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found.",
        )

    if txn.status != "pending_verification":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Transaction is already '{txn.status}' and cannot be re-processed.",
        )

    now = datetime.now(timezone.utc)
    txn.verified_by = admin_user.email
    txn.verified_at = now

    if approve:
        txn.status = "completed"

        # Determine subscription window
        plan = PLAN_CATALOGUE[txn.plan_type]
        duration_months: int = plan["duration_months"]

        # If user already has an active sub, extend from its expiry
        stmt = (
            select(Subscription)
            .where(
                Subscription.user_id == txn.user_id,
                Subscription.status == "active",
                Subscription.expires_at > now,
            )
            .order_by(Subscription.expires_at.desc())
            .limit(1)
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()

        if existing:
            start = existing.expires_at.replace(tzinfo=timezone.utc)
        else:
            start = now

        # Approximate months as 30 days each
        end = start + timedelta(days=30 * duration_months)

        new_sub = Subscription(
            user_id=txn.user_id,
            plan_type=txn.plan_type,
            status="active",
            starts_at=start,
            expires_at=end,
        )
        session.add(new_sub)

    else:
        txn.status = "rejected"
        txn.rejection_reason = rejection_reason or "No reason provided."

    await session.flush()
    return PaymentTransactionRead.model_validate(txn)
