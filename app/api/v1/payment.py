"""
Payment & subscription endpoints.

Public plan catalogue  →  GET  /payment/plans
Submit payment         →  POST /payment/subscribe
My subscription status →  GET  /payment/my-subscription
My transactions        →  GET  /payment/my-transactions
Admin: list pending    →  GET  /payment/admin/transactions
Admin: verify          →  POST /payment/admin/transactions/{id}/verify
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser, CurrentUser
from app.core.database import get_async_session
from app.models.payment import PaymentTransaction
from app.schemas.payment import (
    PaymentTransactionRead,
    PlanInfo,
    SubscribeRequest,
    SubscribeResponse,
    SubscriptionStatusResponse,
)
from app.services.payment import (
    get_plan_catalogue,
    get_subscription_status,
    list_my_transactions,
    submit_payment,
    verify_transaction,
)

router = APIRouter(prefix="/payment", tags=["Payment & Subscriptions"])


# ── GET /plans ────────────────────────────────────────────────────────────


@router.get(
    "/plans",
    response_model=list[PlanInfo],
    summary="List available subscription plans",
    description=(
        "Returns the three subscription tiers:\n\n"
        "| Plan | Duration | Price |\n"
        "|------|----------|-------|\n"
        "| `monthly` | 1 month | **300 ETB** |\n"
        "| `quarterly` | 3 months | **900 ETB** |\n"
        "| `biannual` | 6 months | **1 800 ETB** |"
    ),
)
async def list_plans() -> list[PlanInfo]:
    """No authentication required – publicly visible pricing."""
    return get_plan_catalogue()


# ── POST /subscribe ───────────────────────────────────────────────────────


@router.post(
    "/subscribe",
    response_model=SubscribeResponse,
    status_code=201,
    summary="Submit a subscription payment",
    description=(
        "Record a bank / Telebirr / CBE payment for one of the subscription plans.\n\n"
        "1. Transfer the exact amount to the platform's payment account.\n"
        "2. Submit your **transaction reference** here.\n"
        "3. Your subscription will be activated once an admin verifies the payment "
        "(typically within 24 hours).\n\n"
        "Duplicate references are rejected with **409 Conflict**."
    ),
)
async def subscribe(
    payload: SubscribeRequest,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> SubscribeResponse:
    return await submit_payment(payload, current_user, session)


# ── GET /my-subscription ──────────────────────────────────────────────────


@router.get(
    "/my-subscription",
    response_model=SubscriptionStatusResponse,
    summary="Get current subscription status",
    description=(
        "Returns the authenticated user's active subscription details, "
        "or `is_subscribed: false` if no active subscription exists."
    ),
)
async def my_subscription(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> SubscriptionStatusResponse:
    return await get_subscription_status(current_user, session)


# ── GET /my-transactions ──────────────────────────────────────────────────


@router.get(
    "/my-transactions",
    response_model=list[PaymentTransactionRead],
    summary="List my payment history",
    description="Returns all payment submissions by the authenticated user, newest first.",
)
async def my_transactions(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[PaymentTransactionRead]:
    return await list_my_transactions(current_user, session)


# ── Admin: GET /admin/transactions ────────────────────────────────────────


@router.get(
    "/admin/transactions",
    response_model=list[PaymentTransactionRead],
    summary="[Admin] List payment transactions",
    description=(
        "Returns all payment transactions. Filter by status using the "
        "`status` query parameter (default: `pending_verification`)."
    ),
)
async def admin_list_transactions(
    admin: AdminUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    filter_status: str = Query(
        default="pending_verification",
        alias="status",
        description="Filter by status: pending_verification | completed | rejected",
    ),
) -> list[PaymentTransactionRead]:
    stmt = (
        select(PaymentTransaction)
        .where(PaymentTransaction.status == filter_status)
        .order_by(PaymentTransaction.created_at.asc())
    )
    result = await session.execute(stmt)
    transactions = result.scalars().all()
    return [PaymentTransactionRead.model_validate(t) for t in transactions]


# ── Admin: POST /admin/transactions/{id}/verify ───────────────────────────




from pydantic import BaseModel


class VerifyPaymentRequest(BaseModel):
    """Admin payload to approve or reject a pending payment."""

    approve: bool = True
    rejection_reason: str | None = None


@router.post(
    "/admin/transactions/{transaction_id}/verify",
    response_model=PaymentTransactionRead,
    summary="[Admin] Approve or reject a payment",
    description=(
        "Set `approve: true` to activate the subscription, or `approve: false` "
        "to reject the payment and record the reason.\n\n"
        "Only transactions in `pending_verification` state can be acted on."
    ),
)
async def admin_verify_transaction(
    transaction_id: str,
    payload: VerifyPaymentRequest,
    admin: AdminUser,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> PaymentTransactionRead:
    return await verify_transaction(
        transaction_id=transaction_id,
        approve=payload.approve,
        rejection_reason=payload.rejection_reason,
        admin_user=admin,
        session=session,
    )
