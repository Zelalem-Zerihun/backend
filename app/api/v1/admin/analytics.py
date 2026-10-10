"""
Admin Analytics router – ``/api/v1/admin/analytics``.

Thin HTTP layer over the analytics service.  Each endpoint:
  * Requires the ``require_admin`` dependency (JWT + session + role check).
  * Delegates all aggregation logic to ``app.services.admin_analytics``.
  * Returns a fully-typed Pydantic response model.

Endpoints
~~~~~~~~~
GET /overview           → OverviewAnalytics         (business KPIs)
GET /learning-engagement → LearningEngagementAnalytics (topic engagement)
GET /ai-utilization     → AIUtilizationAnalytics    (Gemini usage)
GET /finance-summary    → FinanceSummaryAnalytics   (payments)
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser, require_admin
from app.core.database import get_async_session
from app.schemas.admin_analytics import (
    AIUtilizationAnalytics,
    FinanceSummaryAnalytics,
    LearningEngagementAnalytics,
    OverviewAnalytics,
)
from app.services.admin_analytics import (
    get_ai_utilization,
    get_finance_summary,
    get_learning_engagement,
    get_overview,
)

router = APIRouter(
    tags=["Admin – Analytics"],
    dependencies=[Depends(require_admin)],
)

# ── Convenience type alias for the async DB session ──────────────────────
DBSession = Annotated[AsyncSession, Depends(get_async_session)]


# ── GET /overview ────────────────────────────────────────────────────────
@router.get(
    "/overview",
    response_model=OverviewAnalytics,
    summary="High-level business KPIs",
)
async def analytics_overview(
    _admin: AdminUser,
    session: DBSession,
) -> OverviewAnalytics:
    """
    Return aggregated business key-performance indicators:

    - **total_students** – registered students (role = 'student').
    - **active_subscriptions** – paid subscriptions currently valid.
    - **free_tier_students** – students without an active subscription.
    - **subscription_conversion_rate** – % of students who are paid subscribers.
    - **pending_verifications** – payment transactions awaiting review.
    - **total_verified_revenue** – sum of all completed transaction amounts.

    All values are computed by the database engine via scalar subqueries;
    no full-table scans occur in Python.
    """
    return await get_overview(session)


# ── GET /learning-engagement ─────────────────────────────────────────────
@router.get(
    "/learning-engagement",
    response_model=LearningEngagementAnalytics,
    summary="Topic engagement and completion funnel",
)
async def analytics_learning_engagement(
    _admin: AdminUser,
    session: DBSession,
    module_id: uuid.UUID | None = Query(
        default=None,
        description=(
            "UUID of the module to compute the completion funnel for. "
            "Defaults to the first published module by order_index."
        ),
    ),
) -> LearningEngagementAnalytics:
    """
    Return learning engagement metrics:

    - **most_completed_topics** – Top 5 topics by completion count.
    - **most_visited_topics** – Top 5 topics by total visit count.
    - **completion_funnel** – Per-topic completion percentages for the
      specified module (use ``?module_id=<uuid>`` to select a module;
      defaults to the first published module).

    The funnel is particularly useful for identifying topics where
    students disengage or get stuck.
    """
    module_id_str = str(module_id) if module_id else None
    return await get_learning_engagement(session, module_id_for_funnel=module_id_str)


# ── GET /ai-utilization ───────────────────────────────────────────────────
@router.get(
    "/ai-utilization",
    response_model=AIUtilizationAnalytics,
    summary="Gemini AI usage and cost monitoring",
)
async def analytics_ai_utilization(
    _admin: AdminUser,
    session: DBSession,
) -> AIUtilizationAnalytics:
    """
    Return AI usage metrics for **today** (server-local ``CURRENT_DATE``):

    - **total_queries_today** – Total Gemini API calls across all users.
    - **active_ai_users_today** – Distinct users who made at least one call.
    - **top_ai_users** – Top 10 users by query count (power-user / abuse detection).

    This endpoint is useful for budget forecasting and identifying users
    who are approaching or exceeding their daily quota.
    """
    return await get_ai_utilization(session)


# ── GET /finance-summary ──────────────────────────────────────────────────
@router.get(
    "/finance-summary",
    response_model=FinanceSummaryAnalytics,
    summary="Payment method breakdown and recent transaction log",
)
async def analytics_finance_summary(
    _admin: AdminUser,
    session: DBSession,
) -> FinanceSummaryAnalytics:
    """
    Return financial analytics:

    - **payment_method_breakdown** – Per-method transaction count and total
      verified revenue (e.g., CBE vs. Telebirr).
    - **recent_transactions** – The 20 most recent transactions across all
      statuses (pending, completed, rejected) with student identity,
      reference, and amount.
    """
    return await get_finance_summary(session)
